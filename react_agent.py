"""ReAct agent (Yao et al., ICLR 2023) on OpenAI tool calling.

Each step the model writes a short Thought about the latest observation, then picks the next
tool call; the tool result is the next observation. The loop ends when the model replies without
a tool call. The harness's ceilings (model calls, tool calls, tokens, clarifications) bound it.
"""
from __future__ import annotations

import json

from controllers import Controller
from prompts import RULES

SYSTEM = RULES + """

Tools: look things up with find_batches, get_events and get_totals; ask with ask_user. To change
records call propose_changes, then request_approval, then commit; never commit without approval.
Put every change for the request into one propose_changes call: once one change set is committed,
any other open preview is stale and cannot be committed.
If propose_changes reports problems, fix them or explain them to the user.
Your text reply ends the conversation, so any question for the user must go through ask_user.
Work step by step: before each tool call, write one line starting with "Thought:" saying what you
know and what you will do next. Your final reply has no Thought line and says what changed or why
nothing changed."""


def strip_thoughts(text):
    kept = [line for line in text.splitlines() if not line.strip().lower().startswith("thought:")]
    return "\n".join(kept).strip() or text.strip()


class ReAct(Controller):
    name = "react"

    def run(self, question, env):
        messages = [{"role": "system", "content": SYSTEM + "\n\n" + env.context()},
                    {"role": "user", "content": question}]
        while True:
            msg = env.chat(messages=messages, tools=env.tool_schemas).choices[0].message
            if not msg.tool_calls:
                return strip_thoughts(msg.content or "")
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                result = env.call_tool(tc.function.name, tc.function.arguments)
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(result, separators=(",", ":"))})
