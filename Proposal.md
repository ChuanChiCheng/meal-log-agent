# Reliable Cross Day Meal Log Corrections

Yu-Heng Huang and Karry Cheng \| EE P 500 D \| Autumn 2026 \| October 27 2026

# Area and problem

We propose a text based Nutrition Agent for meal prep tracking, with cross day corrections as the main research task. I currently use ChatGPT to help calculate and revise meal records, while maintaining the relevant context myself. A correction such as “I ate only half of yesterday’s box and finished it today” requires identifying the correct batch and dates, checking existing consumption events, and updating persistent records without logging the same meal twice. A fixed workflow may already be sufficient; this project will test whether adaptive tool selection or explicit planning improves correctness. It will not assume that an agent is necessary or that either agent strategy will win.

# Challenges and scope

The main challenges are ambiguous references, distinguishing an existing event from a separate meal, and coordinating changes across dates. Equal quantities alone do not establish that two records describe the same event. When identity is uncertain, the system must ask before modifying records. The prototype will support meal prep creation, partial consumption, queries, and corrections, but evaluation will focus on cross day repair. Images, voice, raw ingredient inventory, recommendations, medical advice, and a full mobile app are outside scope. Nutrition arithmetic will be deterministic and separate from language understanding.

# Outcomes and demonstration

By Week 10, We will deliver a runnable command line prototype, a frozen task set with an automatic state checker, execution traces, and a comparison report. The demonstration starts with one box incorrectly logged as 1 serving yesterday and 0.5 serving today. The user explicitly identifies the batch and confirms that today’s half is already recorded. After a change preview and approval, only yesterday’s record becomes 0.5; today’s record and unrelated meals remain unchanged. Consumption totals 1 serving and remaining quantity is zero. A second demonstration introduces two plausible batches and requires clarification before any write. These are planned outcomes, not completed results.

# Tools and execution boundary

We plan to use Python, SQLite, typed JSON tool schemas, and the course notebook’s gpt-4o-mini model through its existing API integration, subject to access verification. One exact model version and decoding configuration will be frozen before evaluation. A small controller will implement each strategy without requiring a large agent framework. Tools will query batches and logs, request clarification, prepare and validate a change set, display a preview, commit an approved transaction, and undo the latest valid change. Code will calculate nutrients and remaining portions, enforce quantity constraints, check state versions, and record an audit trail. Only the application can grant approval; text returned by a tool cannot authorize a commit. Nutrient fixtures will be fixed and documented, with synthetic values clearly labeled. Live food search will not affect evaluation.

# Experiments and baseline

We will compare three controllers. The fixed workflow baseline uses a predetermined retrieval stage covering candidate batches, relevant dates, and existing events; it then produces a structured change set and follows predefined clarification and validation branches. ReAct selects the next query or action from each observation \[1\]. Plan and execute creates an explicit task plan, executes it, and may revise it after new evidence; this is a project defined controller, not a claim to reproduce a published algorithm. All three receive the same tools, initial state, model, validation feedback, scripted user answers, and approval rules. The baseline can clarify and retry validation rather than being forced into a single attempt. All share ceilings of 12 model calls, 24 tool executions, 16,000 total input plus output tokens, and 3 clarification rounds per task. A round is one request and reply; parallel and failed tool executions count individually. These initial ceilings will be finalized on development tasks before freezing evaluation. Planning and recovery count; exhaustion stops further actions and is scored against the expected outcome.

# Measurement and test protocol

Six separate development tasks will be used for prompt and controller tuning. The held out set will contain 24 tasks: three variants each of today absent, today already recorded, correction already complete, a partial record of the same event, ambiguous batch, ambiguous event identity, missing yesterday record, and similar unrelated records. Each specifies a fixed clock and time zone, database fixture, user command, scripted clarification answers, expected state, and allowed changes. The missing record case must clarify and then follow its predefined answer, or make no change if unresolved. Each controller will run each task three times from a fresh database, for 216 main runs. Prompts and tasks will be frozen first; controller order will be interleaved.

Primary success is binary: the final semantic database state must match the expected result, unrelated business data must be preserved, required clarification must precede action, and no write may occur before approval. A safe refusal on a solvable task, blocked wrong write, or unsupported “done” response is not success. Unresolved cases pass only with the required clarification and no unauthorized change. Already correct cases succeed by reporting no change, without a write or approval request; ordinary reads and a no change preview are allowed. Necessary audit fields are excluded from state equality. We will report success counts and rates by category, paired differences from the baseline, and variation across repeats; repeated runs are not independent new tasks. Diagnostics will include duplicate events, wrong targets, tool argument errors, necessary and unnecessary clarification, model calls, tokens, latency, and cost for all attempts and per successful task. The hypothesis is that adaptive controllers help on ambiguous and corrective tasks; a null result remains useful.

# Safety and feasibility

A separate six case suite will test rejection before approval, stale previews, repeated commit requests, interrupted transactions, valid undo, and instructions injected into retrieved food notes. Checks will inspect both attempted actions and saved state, so shared database protection is not credited as agent reasoning. Deliberately inconsistent repair fixtures will be imported only by the test harness; normal writes must produce a valid final state atomically. Weeks 4–5 will implement the shared data and execution layer plus baseline; Weeks 6–7 will add the two controllers and freeze the checker; Weeks 8–9 will run evaluation and analyze failures; Week 10 will finalize the demo and report. The scope is designed for a two person team. If time becomes tight, We will simplify the interface and meal prep input while retaining all three controllers and the correction benchmark.

# Reference

\[1\] Yao et al. ReAct Synergizing Reasoning and Acting in Language Models. ICLR 2023\. https\://arxiv.org/abs/2210.03629

