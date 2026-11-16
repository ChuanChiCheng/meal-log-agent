"""Non-agentic baseline: a fixed workflow.

The control flow is fixed in code; the model only fills in one structured decision at a time.
  1. Retrieve: all batches, plus events and daily totals for the last 14 days (always the same calls).
  2. Decide: one model call returns JSON with action = answer | clarify | change.
  3. Branch:  clarify -> ask_user, then decide again
              change  -> propose_changes; if validation fails, decide again with the problems;
                         otherwise request_approval -> commit
              answer  -> reply
The model never picks tools, so this tests whether adaptive tool use (ReAct) adds anything.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from controllers import Controller
from prompts import RULES

WINDOW_DAYS = 14
MAX_DECISIONS = 6

DECIDE = RULES + """

You cannot run tools. The log data for the last 14 days is given to you. Choose exactly one action
and return JSON only:
{"action": "answer" | "clarify" | "change", "reply": "...", "question": "...", "changes": [...]}
- answer: reply is your whole message to the user. Nothing is changed.
- clarify: question is one question for the user. You will see their reply and decide again.
- change: changes is the complete list of changes, and reply is the message to show once they are
  saved. The user sees a preview and approves or rejects it.
The user's replies to your questions override your own guesses; follow them.
If changes you proposed earlier were rejected by validation, the problems are listed; fix them."""


class FixedWorkflow(Controller):
    name = "baseline"

    def run(self, question, env):
        start = (date.fromisoformat(env.today) - timedelta(days=WINDOW_DAYS)).isoformat()
        data = {
            "batches": env.call_tool("find_batches", {}).get("batches", []),
            "events": env.call_tool("get_events", {"date_from": start, "date_to": env.today}).get("events", []),
            "daily_totals": env.call_tool("get_totals", {"date_from": start, "date_to": env.today}).get("days", []),
        }
        history = []
        for _ in range(MAX_DECISIONS):
            d = self._decide(env, question, data, history)
            action = d.get("action")
            if action == "clarify" and d.get("question"):
                r = env.call_tool("ask_user", {"question": d["question"]})
                history.append({"you_asked": d["question"], "user_replied": r.get("user_reply")})
                continue
            if action == "change" and d.get("changes"):
                p = env.call_tool("propose_changes", {"changes": d["changes"]})
                if "error" in p:
                    history.append({"your_changes": d["changes"],
                                    "rejected_by_validation": p.get("problems") or p["error"]})
                    continue
                a = env.call_tool("request_approval", {"change_set_id": p["change_set_id"]})
                if not a.get("approved"):
                    return "OK, I left your log unchanged."
                c = env.call_tool("commit", {"change_set_id": p["change_set_id"]})
                if "error" in c:
                    return f"I could not save the change: {c['error']}"
                return (d.get("reply") or "Saved.") + "\n" + "\n".join(f"- {line}" for line in p["preview"])
            return d.get("reply") or ""
        return "Sorry, I could not work this out, so I did not change anything."

    def _decide(self, env, question, data, history):
        user = (f"{env.context()}\n\nLog data (JSON):\n{json.dumps(data, separators=(',', ':'))}\n\n"
                f"User message: {question}\n\n"
                f"Conversation since that message, oldest first: {json.dumps(history) if history else 'nothing yet'}")
        resp = env.chat(messages=[{"role": "system", "content": DECIDE}, {"role": "user", "content": user}],
                        response_format={"type": "json_object"})
        text = resp.choices[0].message.content or ""
        try:
            d = json.loads(text)
        except json.JSONDecodeError:
            return {"action": "answer", "reply": text}
        return d if isinstance(d, dict) else {"action": "answer", "reply": text}
