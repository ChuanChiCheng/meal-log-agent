#!/usr/bin/env python3
"""Eval harness for the meal-log agent (EE P 500D, Week 6 take-home).

Runs every controller on every task in tasks.jsonl, each run on a fresh database, grades
the final database state, the order of actions and the reply, and writes a side-by-side report.

  # check the harness itself (no API key needed)
  python eval.py --controllers oracle,noop,flaky --repeats 3 --judge-model none

  # the take-home run: baseline and agent, 3 runs each for pass@3 / pass^3
  python eval.py --controllers my_baseline:FixedWorkflow,my_agent:ReAct --repeats 3

  # print one run's trace for the failure write-up
  python eval.py --show-trace results/<run>/traces/react/h13_r2.json

A run passes when all of these hold:
  state    final DB equals fixture + expected_changes (semantic fields only; ids and audit ignored;
           a new event with no meal in expected_changes may have any meal)
  process  no blocked write (unapproved, stale or repeated commit); if must_clarify, ask_user comes
           before the first request_approval or commit; if expected_changes is empty, no approval request
  answer   exact: reply contains one of `expected` | tool: first tool call matches `expected_call` |
           rubric / unanswerable / state with `rubric`: the LLM judge passes every criterion
  no crash a controller exception fails the run; hitting a budget ceiling stops the run and the
           state is graded as it is
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime
from math import comb
from pathlib import Path

import controllers as builtin
from mealenv import DEFAULT_LIMITS, BudgetExceeded, Env, remaining

HERE = Path(__file__).resolve().parent

STANDARD_RUBRIC = [
    "Correct: every fact in the reply matches the meal log",
    "Grounded: every number in the reply can be traced to the log data",
    "Complete: the reply answers every part of the user's message",
    "In policy: no invented facts, no medical advice, no changes the user did not approve",
]
NO_INVENTION = "In policy: the reply states no numbers or facts that are not in the meal log"

JUDGE_SYSTEM = """You grade one reply from a meal-log assistant against a list of criteria.
Use only the data given: the log before the conversation, the user's clarifying answers, and the
changes that were actually saved. The log listing is the ground truth: check each claim in the
reply against it line by line before deciding. Numbers are equal when their values are equal
(1.0 = 1 = one).
The assistant's clarifying questions were also shown to the user, so a criterion about telling the
user something passes if a question or the final reply says it, in any wording. It must actually
be said: doing the right thing without saying it fails, and "I did not change anything" is not
the same as "no change is needed". A vague or hedged reply fails any criterion that needs a
specific fact. Judge each criterion on its own.
Return JSON only: {"criteria": [{"n": 1, "pass": true, "reason": "..."}, ...]} with one entry per criterion, in order."""


# ------------------------------------------------------------------ loading
def load_tasks(path, splits=None, ids=None):
    tasks = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if splits:
        tasks = [t for t in tasks if t["split"] in splits]
    if ids:
        tasks = [t for t in tasks if t["id"] in ids]
    if not tasks:
        raise SystemExit("no tasks selected")
    return tasks


def load_controller(spec):
    if spec in builtin.BUILTIN:
        return builtin.BUILTIN[spec]()
    if ":" not in spec:
        raise SystemExit(f"unknown controller {spec!r}: use one of {sorted(builtin.BUILTIN)} or module:Class")
    module, cls = spec.split(":", 1)
    return getattr(importlib.import_module(module), cls)()


def make_client(key_file):
    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("The openai package is missing: pip install openai")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        for p in (key_file, HERE / "openai_llm_class_key.txt", HERE.parent / "openai_llm_class_key.txt"):
            if p and Path(p).is_file():
                key = Path(p).read_text().strip()
                break
    if not key:
        raise SystemExit("No API key: set OPENAI_API_KEY or pass --key-file "
                         "(or use --judge-model none with the built-in controllers)")
    return OpenAI(api_key=key)


# ------------------------------------------------------------------ grading
def apply_changes(fixture, changes):
    st = deepcopy({"batches": fixture["batches"], "events": fixture["events"]})
    for c in changes:
        if c["op"] in ("update", "delete"):
            tbl = next(t for t in ("batches", "events") if any(r["id"] == c["id"] for r in st[t]))
            row = next(r for r in st[tbl] if r["id"] == c["id"])
            if c["op"] == "update":
                row.update(c["set"])
            else:
                st[tbl].remove(row)
        else:
            row = {**c["row"], "id": None}
            if c["table"] == "events":
                row.setdefault("meal", None)
            st[c["table"]].append(row)
    return st


def _batch_key(b):
    ps = b["per_serving"]
    return (b["prepared_on"], float(b["servings_total"]), float(ps["kcal"]), float(ps["protein_g"]))


def _names_match(expected, actual):
    e, a = expected.strip().lower(), actual.strip().lower()
    return e in a or a in e


def compare_state(fixture, expected, actual):
    problems = []
    names = {b["id"]: b["name"] for b in fixture["batches"] + actual["batches"] if b.get("id")}
    fx_ids = {b["id"] for b in fixture["batches"]}
    exp_b = {b["id"]: b for b in expected["batches"] if b.get("id")}
    act_b = {b["id"]: b for b in actual["batches"]}
    for bid in sorted(fx_ids):
        e, a = exp_b.get(bid), act_b.get(bid)
        if e and not a:
            problems.append(f"batch {bid} ({names[bid]}) was deleted")
        elif a and not e:
            problems.append(f"batch {bid} ({names[bid]}) should have been deleted")
        elif e and a and (_batch_key(e) != _batch_key(a) or e["name"] != a["name"]):
            problems.append(f"batch {bid} ({names[bid]}) was changed")
    new_act = [b for bid, b in act_b.items() if bid not in fx_ids]
    for e in (b for b in expected["batches"] if not b.get("id")):
        m = next((a for a in new_act if _batch_key(a) == _batch_key(e) and _names_match(e["name"], a["name"])), None)
        if m:
            new_act.remove(m)
        else:
            problems.append(f"missing new batch: {e['name']}, prepared {e['prepared_on']}, "
                            f"{e['servings_total']} servings, {e['per_serving']}")
    for a in new_act:
        problems.append(f"unexpected new batch: {a['name']}, prepared {a['prepared_on']}, "
                        f"{a['servings_total']} servings, {a['per_serving']}")

    def show(e):
        return f"{names.get(e['batch_id'], e['batch_id'])} {e['date']} {e.get('meal') or 'any meal'} {e['servings']:g}"

    def match(e, a):
        return (e["batch_id"] == a["batch_id"] and e["date"] == a["date"]
                and abs(float(e["servings"]) - float(a["servings"])) < 1e-6
                and (e.get("meal") is None or e["meal"] == a.get("meal")))

    left = list(actual["events"])
    for e in sorted(expected["events"], key=lambda e: e.get("meal") is None):
        m = next((a for a in left if match(e, a)), None)
        if m:
            left.remove(m)
        else:
            problems.append(f"missing event: {show(e)}")
    for a in left:
        problems.append(f"unexpected event: {show(a)}")
    return not problems, problems


def check_process(task, env):
    problems = [f"blocked write: {v.replace('_', ' ')}" for v in env.violations]
    kinds = [k for k, _ in env.gate_log]
    if task["must_clarify"]:
        if "ask_user" not in kinds:
            problems.append("required clarification never asked")
        else:
            first_ask = kinds.index("ask_user")
            acted = [i for i, k in enumerate(kinds) if k in ("request_approval", "commit", "commit_blocked")]
            if acted and acted[0] < first_ask:
                problems.append("asked for approval or committed before clarifying")
    if not task["expected_changes"] and "request_approval" in kinds:
        problems.append("asked for approval although no change was needed")
    return not problems, problems


def _n(x):
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def render_log(state):
    """The log as plain lines, so the judge reads facts instead of joining JSON tables."""
    rem = remaining(state)
    names = {b["id"]: b for b in state["batches"]}
    lines = ["Batches:"]
    for b in state["batches"]:
        ps = b["per_serving"]
        lines.append(f"- {b['name']} ({b['id']}): prepared {b['prepared_on']}, {_n(b['servings_total'])} servings, "
                     f"{_n(ps['kcal'])} kcal and {_n(ps['protein_g'])} g protein per serving, "
                     f"{_n(rem[b['id']])} servings left")
    lines.append("Servings eaten:")
    days = {}
    order = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3}
    for e in sorted(state["events"], key=lambda e: (e["date"], order.get(e.get("meal"), 9))):
        b = names[e["batch_id"]]
        kcal, prot = e["servings"] * b["per_serving"]["kcal"], e["servings"] * b["per_serving"]["protein_g"]
        wd = datetime.fromisoformat(e["date"]).strftime("%A")
        lines.append(f"- {e['date']} {wd}, {e.get('meal') or 'meal not given'}: {_n(e['servings'])} serving of "
                     f"{b['name']} = {_n(round(kcal, 2))} kcal, {_n(round(prot, 2))} g protein")
        d = days.setdefault(f"{e['date']} {wd}", [0.0, 0.0])
        d[0] += kcal
        d[1] += prot
    lines.append("Daily totals:")
    lines += [f"- {day}: {_n(round(k, 2))} kcal, {_n(round(p, 2))} g protein" for day, (k, p) in sorted(days.items())]
    return "\n".join(lines)


def conversation_facts(env):
    qa = [{"assistant_asked": s["args"].get("question"), "user_replied": s["result"].get("user_reply")}
          for s in env.trace if s["kind"] == "tool" and s["name"] == "ask_user" and "user_reply" in s["result"]]
    saved = [{"op": kind, "table": tbl, "id": rid, "data": data}
             for c in env.commits for kind, tbl, rid, data in c["ops"]]
    return qa, saved


def facts_from_trace(trace):
    qa = [{"assistant_asked": s["args"].get("question"), "user_replied": s["result"].get("user_reply")}
          for s in trace if s["kind"] == "tool" and s["name"] == "ask_user" and "user_reply" in s.get("result", {})]
    proposed = {s["result"]["change_set_id"]: s["args"].get("changes", "undo")
                for s in trace if s["kind"] == "tool" and s["name"] in ("propose_changes", "undo_last")
                and "change_set_id" in s.get("result", {})}
    saved = [proposed.get(s["result"]["change_set_id"]) for s in trace
             if s["kind"] == "tool" and s["name"] == "commit" and s.get("result", {}).get("committed")]
    return qa, saved


def criteria_for(task):
    if task["type"] == "rubric":
        return STANDARD_RUBRIC + task["rubric"]
    if task["type"] == "unanswerable":
        return task["rubric"] + [NO_INVENTION]
    if task["type"] == "state" and task.get("rubric"):
        return task["rubric"]
    return None


def judge(client, model, task, answer, criteria, qa, saved, final_state):
    listing = "\n".join(f"{i}. {c}" for i, c in enumerate(criteria, 1))
    prompt = (f"Current time: {task['now']} ({task['tz']})\n"
              f"User message: {task['question']}\n\n"
              f"Meal log before the conversation:\n{render_log(task['fixture'])}\n\n"
              f"Clarifying questions and the user's answers: {json.dumps(qa) if qa else 'none'}\n"
              f"Changes saved during the conversation: {json.dumps(saved) if saved else 'none'}\n"
              + (f"\nMeal log after the conversation:\n{render_log(final_state)}\n" if saved else "")
              + f"\nAssistant's final reply:\n<<<\n{answer}\n>>>\n\nCriteria:\n{listing}")
    try:
        resp = client.chat.completions.create(
            model=model, temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": prompt}])
        usage = resp.usage
        tokens = (usage.prompt_tokens + usage.completion_tokens) if usage else 0
        verdicts = json.loads(resp.choices[0].message.content).get("criteria", [])
    except Exception as e:  # API or JSON failure: leave the run ungraded rather than failed
        return None, [{"criterion": c, "pass": None, "reason": f"judge error: {e}"} for c in criteria], 0
    if len(verdicts) != len(criteria):
        return None, [{"criterion": c, "pass": None, "reason": "judge returned the wrong number of verdicts"}
                      for c in criteria], tokens
    out = [{"criterion": c, "pass": v.get("pass") is True, "reason": v.get("reason", "")}
           for c, v in zip(criteria, verdicts)]
    return all(v["pass"] for v in out), out, tokens


def check_answer(task, env, answer, client, judge_model):
    """Returns (ok or None if not judged, problems, judge_details, judge_tokens)."""
    typ = task["type"]
    if typ == "exact":
        ok = any(e.lower() in answer.lower() for e in task["expected"])
        return ok, [] if ok else [f"reply lacks any of {task['expected']}"], None, 0
    if typ == "tool":
        exp = dict(task["expected_call"])
        name = exp.pop("name")
        got = env.first_tool_call
        if got is None:
            return False, ["no tool call"], None, 0
        bad = [k for k, v in exp.items() if str(got["args"].get(k)) != str(v)]
        ok = got["name"] == name and not bad
        return ok, [] if ok else [f"first call {got['name']}({got['args']}), expected {task['expected_call']}"], None, 0
    criteria = criteria_for(task)
    if criteria is None:
        return True, [], None, 0
    if client is None:
        return None, ["answer not judged (--judge-model none)"], None, 0
    qa, saved = conversation_facts(env)
    return run_judge(client, judge_model, task, answer, criteria, qa, saved, env.state())


def run_judge(client, judge_model, task, answer, criteria, qa, saved, final_state):
    ok, details, tokens = judge(client, judge_model, task, answer, criteria, qa, saved, final_state)
    problems = [f"judge: fails '{d['criterion']}': {d['reason']}" for d in details if d["pass"] is False]
    if ok is None:
        problems = [details[0]["reason"]]
    return ok, problems, details, tokens


def combine(crashed, state_ok, proc_ok, ans_ok):
    if crashed or not state_ok or not proc_ok or ans_ok is False:
        return False
    return None if ans_ok is None else True


def grade(task, env, answer, crashed, client, judge_model):
    expected = apply_changes(task["fixture"], task["expected_changes"])
    state_ok, state_p = compare_state(task["fixture"], expected, env.state())
    proc_ok, proc_p = check_process(task, env)
    ans_ok, ans_p, details, jt = check_answer(task, env, answer, client, judge_model)
    problems = (["controller crashed"] if crashed else []) + state_p + proc_p + ans_p
    return {"pass": combine(crashed, state_ok, proc_ok, ans_ok), "state_ok": state_ok, "process_ok": proc_ok,
            "answer_ok": ans_ok, "problems": problems, "judge": details, "judge_tokens": jt}


def rejudge(run_dir, args):
    """Grade a finished run's replies again with the current judge, without rerunning controllers."""
    run_dir = Path(run_dir)
    rows = [json.loads(line) for line in (run_dir / "rows.jsonl").read_text().splitlines() if line.strip()]
    old = json.loads((run_dir / "summary.json").read_text())["config"]
    tasks = {t["id"]: t for t in load_tasks(args.tasks)}
    client = make_client(args.key_file)

    def one(row):
        task = tasks[row["task_id"]]
        criteria = criteria_for(task)
        row = {**row, "trace_file": str(run_dir / row["trace_file"])}
        if criteria is None:
            return row
        d = json.loads(Path(row["trace_file"]).read_text())
        qa, saved = facts_from_trace(d["trace"])
        ok, ans_p, details, jt = run_judge(client, args.judge_model, task, d["answer"], criteria, qa, saved,
                                           d["final_state"])
        kept = [p for p in row["problems"] if not p.startswith(("judge", "answer not judged"))]
        return {**row, "answer_ok": ok, "judge": details, "judge_tokens": jt, "problems": kept + ans_p,
                "pass": combine(row["error"] is not None, row["state_ok"], row["process_ok"], ok)}

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        rows = list(ex.map(one, rows))
    names = old["controllers"]
    config = {**old, "judge_model": args.judge_model, "rejudged_from": str(run_dir),
              "judge_tokens": sum(r["judge_tokens"] for r in rows)}
    out_dir = run_dir.parent / f"{run_dir.name}-rejudge-{args.judge_model}"
    out_dir.mkdir(exist_ok=True)
    tasks_run = [tasks[i] for i in old["task_ids"]]
    md = report(rows, summarize(rows, names, old["repeats"]), names, tasks_run, old["repeats"], config)
    (out_dir / "rows.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in rows))
    (out_dir / "summary.md").write_text(md)
    (out_dir / "summary.json").write_text(json.dumps({"config": config,
                                                      "metrics": summarize(rows, names, old["repeats"])},
                                                     indent=2, default=str))
    print(md.split("## Failed runs")[0])
    print(f"Full report: {out_dir / 'summary.md'}")


# ------------------------------------------------------------------ running
def run_one(ctrl, task, repeat, args, client, judge_client, out_dir):
    env = Env(task, llm=client if ctrl.uses_llm else None, model=args.model,
              temperature=args.temperature, repeat=repeat)
    answer, error, exhausted = "", None, None
    start = time.perf_counter()
    try:
        answer = ctrl.run(task["question"], env) or ""
    except BudgetExceeded as e:
        exhausted = str(e)
    except Exception:
        error = traceback.format_exc(limit=6)
    seconds = time.perf_counter() - start
    g = grade(task, env, answer, error is not None, judge_client, args.judge_model)
    asked = env.counters["clarify_rounds"] > 0
    row = {"controller": ctrl.name, "task_id": task["id"], "repeat": repeat + 1, "split": task["split"],
           "category": task["category"], "type": task["type"], **g,
           "turns": env.counters["model_calls"], "tool_calls": env.counters["tool_calls"],
           "tool_errors": env.counters["tool_errors"], "clarify_rounds": env.counters["clarify_rounds"],
           "unnecessary_clarify": asked and not task["must_clarify"],
           "tokens": env.counters["tokens"], "prompt_tokens": env.counters["prompt_tokens"],
           "completion_tokens": env.counters["completion_tokens"], "seconds": round(seconds, 3),
           "violations": list(env.violations), "exhausted": exhausted, "error": error, "answer": answer}
    path = out_dir / "traces" / ctrl.name / f"{task['id']}_r{repeat + 1}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**row, "question": task["question"], "note": task.get("note"),
                                "trace": env.trace, "final_state": env.state()}, indent=1, default=str))
    row["trace_file"] = str(path.relative_to(out_dir))
    return row


# ------------------------------------------------------------------ report
def pct(xs, q):
    s = sorted(xs)
    if not s:
        return None
    k = (len(s) - 1) * q
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def summarize(rows, names, repeats):
    per = {}
    for name in names:
        rs = [r for r in rows if r["controller"] == name]
        graded = [r for r in rs if r["pass"] is not None]
        m = {"runs": len(rs), "graded": len(graded), "passed": sum(1 for r in graded if r["pass"]),
             "accuracy": mean(1.0 if r["pass"] else 0.0 for r in graded),
             "avg_turns": mean(r["turns"] for r in rs), "avg_tool_calls": mean(r["tool_calls"] for r in rs),
             "avg_latency_s": mean(r["seconds"] for r in rs), "p95_latency_s": pct([r["seconds"] for r in rs], 0.95),
             "avg_tokens": mean(r["tokens"] for r in rs),
             "blocked_writes": sum(len(r["violations"]) for r in rs),
             "unnecessary_clarify": sum(r["unnecessary_clarify"] for r in rs),
             "tool_errors": sum(r["tool_errors"] for r in rs),
             "budget_exhausted": sum(1 for r in rs if r["exhausted"]), "crashes": sum(1 for r in rs if r["error"])}
        if repeats > 1:
            by_task = {}
            for r in sorted(rs, key=lambda r: r["repeat"]):
                by_task.setdefault(r["task_id"], []).append(r["pass"])
            full = {t: ps for t, ps in by_task.items() if None not in ps}
            n = k = repeats
            m["pass_at_k"] = mean(1 - comb(n - sum(ps), k) / comb(n, k) for ps in full.values())
            m["pass_hat_k"] = mean(comb(sum(ps), k) / comb(n, k) for ps in full.values())
            m["k_tasks"] = len(full)
            m["flips"] = {t: "".join("✓" if p else "✗" for p in ps)
                          for t, ps in full.items() if 0 < sum(ps) < len(ps)}
        per[name] = m
    return per


def fmt_pct(x):
    return "n/a" if x is None else f"{x:.1%}"


def fmt_num(x, digits=1):
    return "n/a" if x is None else f"{x:,.{digits}f}"


def report(rows, per, names, tasks, repeats, config):
    L = [f"# Eval results · {config['started']}", "",
         f"{len(tasks)} tasks × {repeats} run(s) · model `{config['model']}` (temperature {config['temperature']}) · "
         f"judge `{config['judge_model']}` · tasks.jsonl sha256 `{config['tasks_sha256']}`", ""]
    head = "| Metric | " + " | ".join(names) + " |"
    sep = "|---|" + "---|" * len(names)
    lines = [
        ("Task accuracy (all runs)", lambda m: f"{fmt_pct(m['accuracy'])} ({m['passed']}/{m['graded']})"),
        ("Avg turns (model calls)", lambda m: fmt_num(m["avg_turns"])),
        ("Avg tool calls", lambda m: fmt_num(m["avg_tool_calls"])),
        ("Avg latency (s)", lambda m: fmt_num(m["avg_latency_s"], 2)),
        ("p95 latency (s)", lambda m: fmt_num(m["p95_latency_s"], 2)),
        ("Avg tokens per task", lambda m: fmt_num(m["avg_tokens"], 0)),
    ]
    if repeats > 1:
        lines += [(f"pass@{repeats}", lambda m: fmt_pct(m["pass_at_k"])),
                  (f"pass^{repeats}", lambda m: fmt_pct(m["pass_hat_k"])),
                  ("Tasks that flip", lambda m: str(len(m["flips"])))]
    lines += [("Blocked writes", lambda m: str(m["blocked_writes"])),
              ("Unnecessary clarifications", lambda m: str(m["unnecessary_clarify"])),
              ("Tool errors", lambda m: str(m["tool_errors"])),
              ("Budget exhausted / crashes", lambda m: f"{m['budget_exhausted']} / {m['crashes']}")]
    L += ["## Side by side", "", head, sep]
    L += [f"| {label} | " + " | ".join(f(per[n]) for n in names) + " |" for label, f in lines]
    ungraded = {n: per[n]["runs"] - per[n]["graded"] for n in names if per[n]["runs"] != per[n]["graded"]}
    if ungraded:
        L += ["", "Ungraded runs (answer not judged) are left out of accuracy: "
              + ", ".join(f"{n} {c}" for n, c in ungraded.items())]

    L += ["", "## Accuracy by category", "", "| Split | Category | " + " | ".join(names) + " |",
          "|---|---|" + "---|" * len(names)]
    cats = sorted({(t["split"], t["category"]) for t in tasks}, key=lambda c: (["dev", "heldout", "general"].index(c[0])
                                                                              if c[0] in ("dev", "heldout", "general") else 9, c[1]))
    for split, cat in cats:
        cells = []
        for n in names:
            rs = [r for r in rows if r["controller"] == n and r["split"] == split and r["category"] == cat
                  and r["pass"] is not None]
            cells.append(f"{sum(r['pass'] for r in rs)}/{len(rs)}" if rs else "–")
        L.append(f"| {split} | {cat} | " + " | ".join(cells) + " |")

    if repeats > 1:
        L += ["", f"## Tasks that flip across {repeats} runs", ""]
        for n in names:
            flips = per[n]["flips"]
            L.append(f"- **{n}**: " + (", ".join(f"{t} {p}" for t, p in sorted(flips.items())) if flips else "none"))

    fails = [r for r in rows if r["pass"] is False]
    L += ["", f"## Failed runs ({len(fails)})", "", "| Controller | Task | Run | Category | First problem | Trace |",
          "|---|---|---|---|---|---|"]
    for r in sorted(fails, key=lambda r: (r["controller"], r["task_id"], r["repeat"])):
        first = (r["problems"] or ["?"])[0].replace("|", "/")
        L.append(f"| {r['controller']} | {r['task_id']} | {r['repeat']} | {r['category']} | {first} | `{r['trace_file']}` |")
    L += ["", "Turns = model calls per task. Latency is wall time per task and excludes the judge. "
          f"Ceilings per task: {config['limits']}. Judge tokens (not in the table): {config['judge_tokens']:,}."]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ trace viewer
def _short(x, n=160):
    s = x if isinstance(x, str) else json.dumps(x, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"


def show_trace(path):
    d = json.loads(Path(path).read_text())
    print(f"{d['controller']} · task {d['task_id']} · run {d['repeat']} · pass={d['pass']}")
    print(f"question: {d['question']}")
    if d.get("note"):
        print(f"task note: {d['note']}")
    for s in d["trace"]:
        head = f"#{s['step']:>2} {s['t']:7.2f}s {s['kind']:<6}"
        if s["kind"] == "tool":
            print(f"{head} {s['name']}({_short(s.get('args'), 120)})")
            print(f"{'':19}-> {_short(s.get('result'), 220)}")
        elif s["kind"] == "llm":
            r = s["result"]
            tok = s.get("tokens", {})
            print(f"{head} {s['name']} [{tok.get('prompt', 0)}+{tok.get('completion', 0)} tok]")
            if r.get("content"):
                print(f"{'':19}says: {_short(r['content'], 220)}")
            for c in r.get("tool_calls") or []:
                print(f"{'':19}calls: {c['name']}({_short(c['arguments'], 160)})")
        else:
            print(f"{head} {s['name']} {_short({k: v for k, v in s.items() if k not in ('step', 't', 'kind', 'name')})}")
    print(f"final reply: {d['answer']!r}")
    if d.get("exhausted"):
        print(f"budget exhausted: {d['exhausted']}")
    if d.get("error"):
        print(d["error"])
    for p in d["problems"]:
        print(f"PROBLEM: {p}")


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--controllers", default="oracle,noop",
                    help=f"comma list of built-ins {sorted(builtin.BUILTIN)} or module:Class")
    ap.add_argument("--tasks", default=str(HERE / "tasks.jsonl"))
    ap.add_argument("--split", help="comma list: dev, heldout, general (default: all)")
    ap.add_argument("--ids", help="comma list of task ids")
    ap.add_argument("--repeats", type=int, default=1, help="runs per task per controller (3 for pass@3)")
    ap.add_argument("--model", default="gpt-4o-mini", help="model for controllers (freeze an exact version)")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--judge-model", default="gpt-4o-mini", help="'none' skips the LLM judge")
    ap.add_argument("--key-file", help="file holding the OpenAI key (default: OPENAI_API_KEY)")
    ap.add_argument("--workers", type=int, default=1, help="parallel tasks (latency rises under rate limits)")
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--show-trace", metavar="TRACE_JSON", help="print one trace and exit")
    ap.add_argument("--rejudge", metavar="RUN_DIR", help="grade a finished run again with --judge-model")
    args = ap.parse_args(argv)

    if args.show_trace:
        show_trace(args.show_trace)
        return
    if args.rejudge:
        rejudge(args.rejudge, args)
        return

    tasks = load_tasks(args.tasks, args.split and args.split.split(","), args.ids and args.ids.split(","))
    ctrls = [load_controller(s.strip()) for s in args.controllers.split(",") if s.strip()]
    names = [c.name for c in ctrls]
    if len(set(names)) != len(names):
        raise SystemExit(f"controller names must be unique, got {names}")
    use_judge = args.judge_model.lower() != "none"
    client = make_client(args.key_file) if (use_judge or any(c.uses_llm for c in ctrls)) else None
    judge_client = client if use_judge else None

    started = datetime.now()
    out_dir = Path(args.out) / started.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    config = {"started": started.strftime("%Y-%m-%d %H:%M"), "controllers": names, "model": args.model,
              "temperature": args.temperature, "judge_model": args.judge_model, "repeats": args.repeats,
              "limits": DEFAULT_LIMITS, "tasks_file": args.tasks, "task_ids": [t["id"] for t in tasks],
              "tasks_sha256": hashlib.sha256(Path(args.tasks).read_bytes()).hexdigest()[:12]}

    # each job is one task in one repeat; controller order rotates so no controller always runs first
    jobs = [(r, i, t) for r in range(args.repeats) for i, t in enumerate(tasks)]
    total = len(jobs) * len(ctrls)
    rows, lock, done = [], threading.Lock(), [0]

    def job(r, i, t):
        shift = (i + r) % len(ctrls)
        out = []
        for c in ctrls[shift:] + ctrls[:shift]:
            row = run_one(c, t, r, args, client, judge_client, out_dir)
            out.append(row)
            with lock:
                done[0] += 1
                mark = {True: "PASS", False: "FAIL", None: "----"}[row["pass"]]
                why = f"  {row['problems'][0]}" if row["pass"] is False and row["problems"] else ""
                print(f"[{done[0]:>4}/{total}] {c.name:<12} {t['id']} r{r + 1} {mark} "
                      f"{row['seconds']:6.2f}s {row['turns']:>2} calls{why}", flush=True)
        return out

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        for fut in as_completed([ex.submit(job, *j) for j in jobs]):
            rows.extend(fut.result())

    rows.sort(key=lambda r: (names.index(r["controller"]), r["task_id"], r["repeat"]))
    config["judge_tokens"] = sum(r["judge_tokens"] for r in rows)
    per = summarize(rows, names, args.repeats)
    md = report(rows, per, names, tasks, args.repeats, config)
    (out_dir / "rows.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in rows))
    (out_dir / "summary.json").write_text(json.dumps({"config": config, "metrics": per}, indent=2, default=str))
    (out_dir / "summary.md").write_text(md)
    print("\n" + md.split("## Failed runs")[0])
    print(f"Full report: {out_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
