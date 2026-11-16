"""Shared data and execution layer for the meal-log agent and its eval harness.

Every controller (baseline, ReAct, plan-and-execute) gets one fresh Env per run. The Env
owns the SQLite database, the tools, the approval gate, the budget ceilings and the trace,
so all controllers see exactly the same tools, rules and accounting.

A controller may only use:
    env.context()                -> clock line to put in the system prompt
    env.today                    -> "YYYY-MM-DD" in the task's time zone
    env.tool_schemas             -> OpenAI tool definitions (list of dicts)
    env.call_tool(name, args)    -> dict; failures come back as {"error": ...}
    env.chat(messages, tools)    -> OpenAI ChatCompletion; counts tokens, enforces ceilings
    env.note(text)               -> add a line (e.g. your plan) to the trace
`env.task` holds the expected answers. It is there for the harness and the oracle only.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from copy import deepcopy
from datetime import date, datetime

MEALS = ("breakfast", "lunch", "dinner", "snack")
DEFAULT_LIMITS = {"model_calls": 12, "tool_calls": 24, "tokens": 16000, "clarify_rounds": 3}
# Reply to a question the task has no scripted answer for. It must not read as a refusal, or an
# unneeded question would turn into a failed task instead of a counted diagnostic.
FALLBACK_REPLY = "I've told you what I know. Please go ahead based on my message."
EVENT_FIELDS = {"batch_id", "date", "meal", "servings"}
BATCH_UPDATABLE = {"name", "prepared_on", "servings_total"}
NAME_STOPWORDS = {"box", "boxes", "the", "and", "bowl", "jar", "meal", "prep", "batch", "container"}

SCHEMA = """
CREATE TABLE batches (id TEXT PRIMARY KEY, name TEXT NOT NULL, prepared_on TEXT NOT NULL,
                      servings_total REAL NOT NULL, kcal REAL NOT NULL, protein_g REAL NOT NULL);
CREATE TABLE events  (id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id),
                      date TEXT NOT NULL, meal TEXT, servings REAL NOT NULL);
CREATE TABLE audit   (seq INTEGER PRIMARY KEY AUTOINCREMENT, change_set TEXT NOT NULL,
                      op TEXT NOT NULL, tbl TEXT NOT NULL, row_id TEXT NOT NULL,
                      before TEXT, after TEXT);
"""


class BudgetExceeded(Exception):
    """A ceiling was hit. The harness stops the run and grades the state as it is."""


# ----------------------------------------------------------------- tool schemas
def _fn(name, description, properties, required=()):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": list(required)}}}


_DATE = {"type": "string", "description": "Date as YYYY-MM-DD"}
_CHANGE = {
    "type": "object",
    "properties": {
        "op": {"type": "string", "enum": ["update", "insert", "delete"]},
        "id": {"type": "string", "description": "Row id for update or delete, e.g. E2 or B1"},
        "table": {"type": "string", "enum": ["events", "batches"], "description": "Table for insert"},
        "set": {"type": "object", "description": "For update. Event fields: batch_id, date, meal, servings. "
                                                 "Batch fields: name, prepared_on, servings_total"},
        "row": {"type": "object", "description": "For insert. Event: batch_id, date, servings, optional meal "
                                                 "(breakfast|lunch|dinner|snack). Batch: name, prepared_on, "
                                                 "servings_total, per_serving {kcal, protein_g}"},
    },
    "required": ["op"],
}

TOOL_SCHEMAS = [
    _fn("find_batches", "List meal-prep batches with servings left. All filters are optional.",
        {"name_query": {"type": "string", "description": "Words to match in the batch name, e.g. 'chili'"},
         "prepared_from": _DATE, "prepared_to": _DATE}),
    _fn("get_events", "List logged consumption events between two dates (inclusive) with batch name, "
                      "servings, kcal and protein.",
        {"date_from": _DATE, "date_to": _DATE, "batch_id": {"type": "string"}}, ["date_from", "date_to"]),
    _fn("get_totals", "Daily kcal and protein totals between two dates (inclusive), computed from the log. "
                      "Days with nothing logged are left out.",
        {"date_from": _DATE, "date_to": _DATE}, ["date_from", "date_to"]),
    _fn("ask_user", "Ask the user one clarifying question and get their reply.",
        {"question": {"type": "string"}}, ["question"]),
    _fn("propose_changes", "Validate a list of changes and get a preview and a change_set_id. Saves nothing.",
        {"changes": {"type": "array", "items": _CHANGE}}, ["changes"]),
    _fn("request_approval", "Show a change set's preview to the user and get their approve or reject.",
        {"change_set_id": {"type": "string"}}, ["change_set_id"]),
    _fn("commit", "Save an approved change set atomically.",
        {"change_set_id": {"type": "string"}}, ["change_set_id"]),
    _fn("undo_last", "Prepare a change set that reverts the most recent commit. "
                     "It still needs request_approval and commit.", {}),
]


# ----------------------------------------------------------------- helpers
def remaining(state):
    out = {b["id"]: b["servings_total"] for b in state["batches"]}
    for e in state["events"]:
        if e["batch_id"] in out:
            out[e["batch_id"]] -= e["servings"]
    return {k: round(v, 6) for k, v in out.items()}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _iso(v):
    if not isinstance(v, str) or len(v) != 10:
        return False
    try:
        date.fromisoformat(v)
        return True
    except ValueError:
        return False


def _fmt(x):
    if not _num(x):
        return repr(x)
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _find(state, rid):
    for tbl in ("batches", "events"):
        for row in state[tbl]:
            if row["id"] == rid:
                return tbl, row
    return None, None


# ----------------------------------------------------------------- Env
class Env:
    def __init__(self, task, llm=None, model="gpt-4o-mini", temperature=0.0, limits=None, repeat=0):
        self.task = task
        self.repeat = repeat
        self.now = datetime.fromisoformat(task["now"])
        self.today = self.now.date().isoformat()
        self.tz = task["tz"]
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        self.llm, self.model, self.temperature = llm, model, temperature
        self.tool_schemas = deepcopy(TOOL_SCHEMAS)
        self.counters = dict(model_calls=0, tool_calls=0, prompt_tokens=0, completion_tokens=0,
                             tokens=0, clarify_rounds=0, tool_errors=0)
        self.trace = []          # every model call, tool call, note
        self.gate_log = []       # ordered (event, step): ask_user / request_approval / commit / commit_blocked
        self.violations = []     # blocked write attempts
        self.commits = []        # committed change sets, oldest first
        self.first_tool_call = None
        self._t0 = time.perf_counter()
        self._sets, self._next_set, self._version, self._clarify_i = {}, 1, 0, 0
        self._db = sqlite3.connect(":memory:")
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._load(task["fixture"])
        self._tools = {
            "find_batches": self._find_batches, "get_events": self._get_events,
            "get_totals": self._get_totals, "ask_user": self._ask_user,
            "propose_changes": self._propose_changes, "request_approval": self._request_approval,
            "commit": self._commit, "undo_last": self._undo_last,
        }

    # ---- public API -----------------------------------------------------
    def context(self):
        return (f"Current time: {self.now:%A, %B %d, %Y %H:%M} ({self.tz}). "
                f"Today's date is {self.today}.")

    def note(self, text):
        self._log("note", "controller", text=str(text))

    def state(self):
        batches = [{"id": r["id"], "name": r["name"], "prepared_on": r["prepared_on"],
                    "servings_total": r["servings_total"],
                    "per_serving": {"kcal": r["kcal"], "protein_g": r["protein_g"]}}
                   for r in self._db.execute("SELECT * FROM batches ORDER BY id")]
        events = [dict(r) for r in self._db.execute("SELECT * FROM events ORDER BY id")]
        return {"batches": batches, "events": events}

    def call_tool(self, name, arguments=None):
        parse_error = None
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as e:
                parse_error, arguments = f"arguments are not valid JSON: {e}", {}
        arguments = {} if arguments is None else arguments
        if self.counters["tool_calls"] >= self.limits["tool_calls"]:
            self._log("budget", "tool_calls", limit=self.limits["tool_calls"])
            raise BudgetExceeded("tool_calls")
        self.counters["tool_calls"] += 1
        if self.first_tool_call is None:
            self.first_tool_call = {"name": name, "args": arguments}
        start = time.perf_counter()
        fn = self._tools.get(name)
        try:
            if parse_error:
                result = {"error": parse_error}
            elif fn is None:
                result = {"error": f"unknown tool {name!r}"}
            elif not isinstance(arguments, dict):
                result = {"error": "arguments must be a JSON object"}
            else:
                result = fn(**arguments)
        except BudgetExceeded as e:
            self._log("tool", name, args=arguments, result={"error": f"budget exceeded: {e}"},
                      ms=self._ms(start))
            raise
        except TypeError as e:
            result = {"error": f"bad arguments for {name}: {e}"}
        except ValueError as e:
            result = {"error": str(e)}
        if "error" in result:
            self.counters["tool_errors"] += 1
        self._log("tool", name, args=arguments, result=result, ms=self._ms(start))
        return result

    def chat(self, messages, tools=None, **kwargs):
        """Call the frozen model. Every controller must use this, never the client directly."""
        if self.llm is None:
            raise RuntimeError("No LLM client. Set OPENAI_API_KEY or pass --key-file to eval.py.")
        if self.counters["model_calls"] >= self.limits["model_calls"]:
            self._log("budget", "model_calls", limit=self.limits["model_calls"])
            raise BudgetExceeded("model_calls")
        if self.counters["tokens"] >= self.limits["tokens"]:
            self._log("budget", "tokens", limit=self.limits["tokens"])
            raise BudgetExceeded("tokens")
        self.counters["model_calls"] += 1
        params = {"model": self.model, "temperature": self.temperature, "messages": messages, **kwargs}
        if tools:
            params["tools"] = tools
        start = time.perf_counter()
        resp = self.llm.chat.completions.create(**params)
        usage = getattr(resp, "usage", None)
        p = getattr(usage, "prompt_tokens", 0) or 0
        c = getattr(usage, "completion_tokens", 0) or 0
        self.counters["prompt_tokens"] += p
        self.counters["completion_tokens"] += c
        self.counters["tokens"] += p + c
        msg = resp.choices[0].message
        calls = [{"name": tc.function.name, "arguments": tc.function.arguments}
                 for tc in (getattr(msg, "tool_calls", None) or [])]
        self._log("llm", params["model"], result={"content": msg.content, "tool_calls": calls},
                  tokens={"prompt": p, "completion": c}, ms=self._ms(start))
        if self.counters["tokens"] > self.limits["tokens"]:
            self._log("budget", "tokens", limit=self.limits["tokens"])
            raise BudgetExceeded("tokens")
        return resp

    # ---- internals ------------------------------------------------------
    def _ms(self, start):
        return round((time.perf_counter() - start) * 1000, 1)

    def _log(self, kind, name, **fields):
        step = len(self.trace) + 1
        self.trace.append({"step": step, "t": round(time.perf_counter() - self._t0, 3),
                           "kind": kind, "name": name, **fields})
        return step

    def _load(self, fixture):
        for b in fixture["batches"]:
            self._db.execute("INSERT INTO batches VALUES (?,?,?,?,?,?)",
                             (b["id"], b["name"], b["prepared_on"], b["servings_total"],
                              b["per_serving"]["kcal"], b["per_serving"]["protein_g"]))
        for e in fixture["events"]:
            self._db.execute("INSERT INTO events VALUES (?,?,?,?,?)",
                             (e["id"], e["batch_id"], e["date"], e.get("meal"), e["servings"]))
        self._db.commit()

    def _row(self, tbl, rid):
        r = self._db.execute(f"SELECT * FROM {tbl} WHERE id = ?", (rid,)).fetchone()
        return dict(r) if r else None

    def _new_id(self, tbl):
        prefix = "E" if tbl == "events" else "B"
        ids = [r[0] for r in self._db.execute(f"SELECT id FROM {tbl}")]
        ids += [r[0] for r in self._db.execute("SELECT row_id FROM audit WHERE tbl = ?", (tbl,))]
        nums = [int(i[1:]) for i in ids if i[:1] == prefix and i[1:].isdigit()]
        return f"{prefix}{max(nums, default=0) + 1}"

    def _describe(self, state, tbl, row):
        if tbl == "events":
            b = next((b for b in state["batches"] if b["id"] == row.get("batch_id")), None)
            name = b["name"] if b else row.get("batch_id")
            meal = f" {row['meal']}" if row.get("meal") else ""
            return f"{row.get('id') or 'new event'} ({name}, {row.get('date')}{meal}, {_fmt(row['servings'])} serving)"
        return (f"{row.get('id') or 'new batch'} ({row.get('name')}, prepared {row.get('prepared_on')}, "
                f"{_fmt(row['servings_total'])} servings)")

    # ---- read tools -----------------------------------------------------
    def _check_range(self, date_from, date_to):
        for label, v in (("date_from", date_from), ("date_to", date_to)):
            if not _iso(v):
                raise ValueError(f"{label} must be YYYY-MM-DD, got {v!r}")
        if date_from > date_to:
            raise ValueError("date_from is after date_to")

    def _find_batches(self, name_query=None, prepared_from=None, prepared_to=None):
        for label, v in (("prepared_from", prepared_from), ("prepared_to", prepared_to)):
            if v is not None and not _iso(v):
                raise ValueError(f"{label} must be YYYY-MM-DD, got {v!r}")
        st = self.state()
        rem = remaining(st)
        words = [w for w in re.findall(r"[a-z]+", (name_query or "").lower())
                 if len(w) >= 3 and w not in NAME_STOPWORDS]
        out = []
        for b in st["batches"]:
            if words and not any(w in b["name"].lower() for w in words):
                continue
            if prepared_from and b["prepared_on"] < prepared_from:
                continue
            if prepared_to and b["prepared_on"] > prepared_to:
                continue
            out.append({**b, "servings_left": rem[b["id"]]})
        return {"batches": out}

    def _get_events(self, date_from, date_to, batch_id=None):
        self._check_range(date_from, date_to)
        st = self.state()
        bmap = {b["id"]: b for b in st["batches"]}
        rows = []
        for e in st["events"]:
            if not (date_from <= e["date"] <= date_to) or (batch_id and e["batch_id"] != batch_id):
                continue
            ps = bmap[e["batch_id"]]["per_serving"]
            rows.append({**e, "weekday": date.fromisoformat(e["date"]).strftime("%A"),
                         "batch_name": bmap[e["batch_id"]]["name"],
                         "kcal": round(e["servings"] * ps["kcal"], 2),
                         "protein_g": round(e["servings"] * ps["protein_g"], 2)})
        order = {m: i for i, m in enumerate(MEALS)}
        rows.sort(key=lambda r: (r["date"], order.get(r["meal"], 9), r["id"]))
        return {"events": rows}

    def _get_totals(self, date_from, date_to):
        days = {}
        for e in self._get_events(date_from, date_to)["events"]:
            d = days.setdefault(e["date"], {"date": e["date"], "kcal": 0.0, "protein_g": 0.0})
            d["kcal"] = round(d["kcal"] + e["kcal"], 2)
            d["protein_g"] = round(d["protein_g"] + e["protein_g"], 2)
        out = sorted(days.values(), key=lambda d: d["date"])
        return {"days": out, "total": {"kcal": round(sum(d["kcal"] for d in out), 2),
                                       "protein_g": round(sum(d["protein_g"] for d in out), 2)}}

    # ---- user simulation ------------------------------------------------
    def _ask_user(self, question):
        if self.counters["clarify_rounds"] >= self.limits["clarify_rounds"]:
            raise BudgetExceeded("clarify_rounds")
        self.counters["clarify_rounds"] += 1
        self.gate_log.append(("ask_user", len(self.trace) + 1))
        answers = self.task.get("clarify_answers") or []
        reply = answers[self._clarify_i] if self._clarify_i < len(answers) else FALLBACK_REPLY
        self._clarify_i += 1
        return {"user_reply": reply}

    # ---- write path -----------------------------------------------------
    def _plan(self, changes):
        """Resolve and validate a change list. Returns (problems, ops, preview)."""
        before = self.state()
        st = deepcopy(before)
        problems, preview, ops, touched = [], [], [], set()
        if not isinstance(changes, list):
            return ["changes must be a list"], [], []
        for n, c in enumerate(changes, 1):
            if not isinstance(c, dict):
                problems.append(f"change {n}: must be an object")
                continue
            op = c.get("op")
            if op in ("update", "delete"):
                tbl, row = _find(st, c.get("id"))
                if row is None:
                    problems.append(f"change {n}: no row with id {c.get('id')!r}")
                    continue
                if op == "delete":
                    if tbl == "batches" and any(e["batch_id"] == row["id"] for e in st["events"]):
                        problems.append(f"change {n}: batch {row['id']} still has events")
                        continue
                    preview.append(f"delete {self._describe(st, tbl, row)}")
                    st[tbl].remove(row)
                    touched.add(row["batch_id"] if tbl == "events" else row["id"])
                    ops.append(("delete", tbl, row["id"], None))
                    continue
                fields = c.get("set")
                allowed = EVENT_FIELDS if tbl == "events" else BATCH_UPDATABLE
                if not isinstance(fields, dict) or not fields:
                    problems.append(f"change {n}: update needs a non-empty 'set'")
                    continue
                if set(fields) - allowed:
                    problems.append(f"change {n}: cannot update {sorted(set(fields) - allowed)}; "
                                    f"allowed: {sorted(allowed)}")
                    continue
                old = {k: row.get(k) for k in fields}
                desc = self._describe(st, tbl, row)
                if tbl == "events":
                    touched.add(row["batch_id"])
                row.update(fields)
                touched.add(row["batch_id"] if tbl == "events" else row["id"])
                ops.append(("update", tbl, row["id"], dict(fields)))
                preview.append(f"update {desc}: " + ", ".join(f"{k} {old[k]} -> {fields[k]}" for k in fields))
            elif op == "insert":
                tbl, r = c.get("table", "events"), c.get("row")
                if not isinstance(r, dict):
                    problems.append(f"change {n}: insert needs a 'row' object")
                    continue
                r = dict(r)
                if tbl == "events":
                    missing, extra = {"batch_id", "date", "servings"} - set(r), set(r) - EVENT_FIELDS
                    if missing or extra:
                        problems.append(f"change {n}: event row missing {sorted(missing)} / unknown {sorted(extra)}")
                        continue
                    r.setdefault("meal", None)
                    r["id"] = None
                    st["events"].append(r)
                    touched.add(r["batch_id"])
                    ops.append(("insert", "events", None, {k: r[k] for k in EVENT_FIELDS}))
                elif tbl == "batches":
                    ps = r.get("per_serving") or {}
                    flat = {"name": r.get("name"), "prepared_on": r.get("prepared_on"),
                            "servings_total": r.get("servings_total"),
                            "kcal": ps.get("kcal", r.get("kcal")), "protein_g": ps.get("protein_g", r.get("protein_g"))}
                    if not isinstance(flat["name"], str) or not flat["name"].strip():
                        problems.append(f"change {n}: batch needs a name")
                        continue
                    if not (_num(flat["kcal"]) and _num(flat["protein_g"])) or flat["kcal"] < 0 or flat["protein_g"] < 0:
                        problems.append(f"change {n}: batch needs per_serving kcal and protein_g >= 0")
                        continue
                    nb = {"id": f"new{n}", "name": flat["name"], "prepared_on": flat["prepared_on"],
                          "servings_total": flat["servings_total"],
                          "per_serving": {"kcal": flat["kcal"], "protein_g": flat["protein_g"]}}
                    st["batches"].append(nb)
                    touched.add(nb["id"])
                    ops.append(("insert", "batches", None, flat))
                    r = nb
                else:
                    problems.append(f"change {n}: table must be events or batches")
                    continue
                preview.append(f"insert {self._describe(st, tbl, r)}")
            else:
                problems.append(f"change {n}: op must be update, insert or delete")
        bmap = {b["id"]: b for b in st["batches"]}
        for b in st["batches"]:
            if b["id"] not in touched:
                continue
            if not _iso(b["prepared_on"]) or b["prepared_on"] > self.today:
                problems.append(f"batch {b['name']}: prepared_on must be a date on or before {self.today}")
            if not _num(b["servings_total"]) or b["servings_total"] <= 0:
                problems.append(f"batch {b['name']}: servings_total must be a number > 0")
        for e in st["events"]:
            label = e["id"] or "new event"
            b = bmap.get(e["batch_id"])
            if b is None:
                problems.append(f"{label}: batch {e['batch_id']!r} does not exist")
                continue
            if not _num(e["servings"]) or e["servings"] <= 0:
                problems.append(f"{label}: servings must be a number > 0")
            if not _iso(e["date"]):
                problems.append(f"{label}: date must be YYYY-MM-DD")
            elif e["date"] > self.today:
                problems.append(f"{label}: date {e['date']} is in the future")
            elif _iso(b["prepared_on"]) and e["date"] < b["prepared_on"]:
                problems.append(f"{label}: {e['date']} is before {b['name']} was prepared ({b['prepared_on']})")
            if e["meal"] not in MEALS and e["meal"] is not None:
                problems.append(f"{label}: meal must be one of {list(MEALS)} or null")
        if not problems:
            rem_before, rem_after = remaining(before), remaining(st)
            for bid in sorted(touched):
                if bid in bmap and rem_after[bid] < 0:
                    problems.append(f"{bmap[bid]['name']} would have {_fmt(rem_after[bid])} servings left")
                elif bid in bmap:
                    was = _fmt(rem_before[bid]) if bid in rem_before else "new"
                    preview.append(f"servings left: {bmap[bid]['name']} {was} -> {_fmt(rem_after[bid])}")
        return problems, ops, preview

    def _store_set(self, ops, preview, kind="changes"):
        cs_id = f"CS{self._next_set}"
        self._next_set += 1
        self._sets[cs_id] = {"ops": ops, "preview": preview, "version": self._version,
                             "approved": None, "committed": False, "kind": kind}
        return cs_id

    def _propose_changes(self, changes):
        problems, ops, preview = self._plan(changes)
        if problems:
            return {"error": "change set rejected", "problems": problems}
        cs_id = self._store_set(ops, preview or ["No changes."])
        return {"change_set_id": cs_id, "preview": preview or ["No changes."],
                "next": "Nothing is saved yet. Call request_approval, then commit."}

    def _request_approval(self, change_set_id):
        cs = self._sets.get(change_set_id)
        if cs is None:
            return {"error": f"unknown change_set_id {change_set_id!r}"}
        self.gate_log.append(("request_approval", len(self.trace) + 1))
        ok = bool(self.task.get("approve", True))
        cs["approved"] = ok
        return {"approved": ok, "user_reply": "Yes, go ahead." if ok else "No, don't make this change."}

    def _commit(self, change_set_id):
        cs = self._sets.get(change_set_id)
        if cs is None:
            return {"error": f"unknown change_set_id {change_set_id!r}"}
        if cs["committed"]:
            problem = "repeated_commit"
        elif cs["approved"] is not True:
            problem = "commit_without_approval"
        elif cs["version"] != self._version:
            problem = "stale_preview"
        else:
            problem = None
        if problem:
            self.violations.append(problem)
            self.gate_log.append(("commit_blocked", len(self.trace) + 1))
            return {"error": f"commit blocked: {problem.replace('_', ' ')}"}
        undo = []
        with self._db:
            for kind, tbl, rid, data in cs["ops"]:
                if kind == "insert":
                    rid = data.get("id") or self._new_id(tbl)
                    row = {**data, "id": rid}
                    cols = ",".join(row)
                    self._db.execute(f"INSERT INTO {tbl} ({cols}) VALUES ({','.join('?' * len(row))})",
                                     list(row.values()))
                    undo.append(("delete", tbl, rid, None))
                    before, after = None, row
                elif kind == "update":
                    before = self._row(tbl, rid)
                    sets = ",".join(f"{k} = ?" for k in data)
                    self._db.execute(f"UPDATE {tbl} SET {sets} WHERE id = ?", [*data.values(), rid])
                    undo.append(("update", tbl, rid, {k: before[k] for k in data}))
                    after = self._row(tbl, rid)
                else:
                    before = self._row(tbl, rid)
                    self._db.execute(f"DELETE FROM {tbl} WHERE id = ?", (rid,))
                    undo.append(("insert", tbl, None, before))
                    after = None
                self._db.execute("INSERT INTO audit (change_set, op, tbl, row_id, before, after) VALUES (?,?,?,?,?,?)",
                                 (change_set_id, kind, tbl, rid, json.dumps(before), json.dumps(after)))
        undo.reverse()
        cs["committed"] = True
        if cs["kind"] == "undo":
            cs["undo_of"]["undone"] = True
        self._version += 1
        self.commits.append({"change_set_id": change_set_id, "kind": cs["kind"], "ops": cs["ops"],
                             "undo": undo, "undone": False})
        self.gate_log.append(("commit", len(self.trace) + 1))
        return {"committed": True, "change_set_id": change_set_id, "changes_applied": len(cs["ops"])}

    def _undo_last(self):
        target = next((c for c in reversed(self.commits) if c["kind"] == "changes" and not c["undone"]), None)
        if target is None:
            return {"error": "nothing to undo"}
        preview = [f"revert {target['change_set_id']}: {kind} {tbl} {rid or (data or {}).get('id', '')}".strip()
                   for kind, tbl, rid, data in target["undo"]]
        cs_id = self._store_set(target["undo"], preview, kind="undo")
        self._sets[cs_id]["undo_of"] = target
        return {"change_set_id": cs_id, "preview": preview,
                "next": "Nothing is reverted yet. Call request_approval, then commit."}
