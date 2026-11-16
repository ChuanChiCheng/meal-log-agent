"""Controllers the harness can run.

A controller answers one user message through `env` (see mealenv.py) and returns the final
reply text. The harness creates a fresh Env per run, so a controller keeps no state between runs.
The returned reply ends the conversation: a question to the user only counts if it goes
through the ask_user tool, so say that in your system prompt.

    class MyAgent(Controller):
        name = "react"
        def run(self, question, env):
            ...                      # env.chat(...), env.call_tool(...)
            return reply_text

Run your own with  python eval.py --controllers my_module:MyAgent,other_module:Baseline

The built-ins below are for checking the harness, not for the report:
  oracle     reads the expected answer from the task; should pass every task
  noop       does nothing; passes only tasks where doing nothing is right
  flaky      the oracle with injected mistakes in ~25% of runs; exercises pass@k and flips
  tool_loop  a plain tool-calling loop on the real model; an untuned example of env.chat
"""
from __future__ import annotations

import json
import random
from copy import deepcopy


class Controller:
    name = "controller"
    uses_llm = True

    def run(self, question, env):
        raise NotImplementedError


class Oracle(Controller):
    name = "oracle"
    uses_llm = False

    def run(self, question, env):
        return self._execute(env, env.task)

    def _execute(self, env, t, skip_approval=False):
        if "expected_call" in t:
            call = dict(t["expected_call"])
            env.call_tool(call.pop("name"), call)
        else:
            env.call_tool("get_events", {"date_from": env.today, "date_to": env.today})
        if t["must_clarify"]:
            env.call_tool("ask_user", {"question": "Which record do you mean?"})
        if t["expected_changes"]:
            cs = env.call_tool("propose_changes", {"changes": t["expected_changes"]})
            if "change_set_id" in cs:
                if not skip_approval:
                    env.call_tool("request_approval", {"change_set_id": cs["change_set_id"]})
                env.call_tool("commit", {"change_set_id": cs["change_set_id"]})
        if t.get("expected"):
            return t["expected"][0]
        if t.get("rubric"):
            return " ".join(f"{r[0].upper()}{r[1:]}." for r in t["rubric"])
        return "Done."


class Noop(Controller):
    name = "noop"
    uses_llm = False

    def run(self, question, env):
        return "Sorry, I can't help with that."


class Flaky(Oracle):
    name = "flaky"
    p_fail = 0.25

    def run(self, question, env):
        rng = random.Random(f"{env.task['id']}/{env.repeat}")
        if rng.random() >= self.p_fail:
            return self._execute(env, env.task)
        t = deepcopy(env.task)
        mode = rng.choice(["skip_clarify", "wrong_servings", "skip_approval", "wrong_answer"])
        env.note(f"flaky: injected {mode}")
        if mode == "skip_clarify":
            t["must_clarify"] = False
        elif mode == "wrong_servings":
            for c in t["expected_changes"]:
                target = c.get("set") or c.get("row") or {}
                if "servings" in target:
                    target["servings"] = target["servings"] / 2
                    break
        elif mode == "wrong_answer":
            t["expected"] = ["I'm not sure."] if t.get("expected") else None
            t["rubric"] = None
        return self._execute(env, t, skip_approval=(mode == "skip_approval"))


SYSTEM = """You manage the user's meal-prep log: batches of prepared boxes and the servings eaten from them.
Your text reply ends the conversation. To ask the user anything, including confirming a guess, call ask_user.
Rules:
- Look up the relevant batches and events before changing anything.
- If the target batch or event is uncertain, ask_user before proposing changes.
- To change records: propose_changes, then request_approval, then commit. Never commit without approval.
- If the log is already correct, say so and do not ask for approval.
- If the log cannot answer a question, say so. Do not guess numbers. Do not give medical advice."""


class ToolLoop(Controller):
    """Untuned example of a controller on the real model. Replace it with your own."""
    name = "tool_loop"

    def run(self, question, env):
        messages = [{"role": "system", "content": SYSTEM + "\n\n" + env.context()},
                    {"role": "user", "content": question}]
        while True:
            msg = env.chat(messages=messages, tools=env.tool_schemas).choices[0].message
            if not msg.tool_calls:
                return msg.content or ""
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                result = env.call_tool(tc.function.name, tc.function.arguments)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})


BUILTIN = {c.name: c for c in (Oracle, Noop, Flaky, ToolLoop)}
