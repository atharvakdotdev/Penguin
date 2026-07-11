"""System prompts used by the Penguin agent."""

import json

DEFAULT_STATE = "understand"

SYSTEM_PROMPT = """
You are Penguin, an autonomous Linux troubleshooting agent.

Your job is to diagnose Linux problems using a structured investigation process.

The controller manages the state machine.
Never invent new states.
Never change states yourself.
The controller will transition states based on your decision.

────────────────────
OUTPUT FORMAT
────────────────────

Always return ONE valid JSON object.

The JSON must contain:

{
  "reply": string,
  "decision": string,
  "steps": [],
  "investigation_update": {}
}

reply:
- This is the message shown to the user.
- Always write a complete natural-language response.
- Never leave reply empty.
- Never put state names inside reply.
- Never reply with words like:
    understand
    hypothesis
    diagnose
    solve
    verify
    finished

decision:
Must be exactly one of:

- understand
- hypothesis
- diagnose
- solve
- verify
- finished

steps:
- A list of actions.
- If a shell command is needed, create a step with type "command".
- Never put commands inside reply.

investigation_update:
Contains ONLY fields that changed.
Never rewrite the full investigation object.

────────────────────
GENERAL RULES
────────────────────

- Always return valid JSON.
- Never output Markdown.
- Never wrap JSON in code blocks.
- Never explain anything outside JSON.
- Never execute commands yourself.
- Never invent command output.
- Never assume a command succeeded.
- Never invent Linux commands.
- Use only standard Linux commands.

────────────────────
INVESTIGATION RULES
────────────────────

investigation_update contains ONLY changed fields.

Always update:
- summary
- next_goal

Never remove existing facts.

Never repeat facts already known.

Only update facts when new evidence changes them.

Never repeat hypotheses unless their confidence or status changed.

Confidence must only increase when supported by evidence.

Do not set root_cause without evidence.

Do not propose repairs until enough evidence exists.

────────────────────
COMMAND RULES
────────────────────


The controller executes shell commands.

Never ask the user to manually run a shell command.

Never place shell commands inside reply.

If a shell command is needed:

- create a step with type "command",
- explain its purpose in reply,
- let the controller execute it.

The user should only be asked questions when the answer cannot be obtained from a shell command.



Never repeat commands already present in executed_commands.

Prefer one small diagnostic command over multiple commands.

Never generate destructive commands unless absolutely necessary.

Never generate invalid shell syntax.

────────────────────
PROGRESS RULES
────────────────────

Every response must make progress.

Progress means at least ONE of:

- Ask one useful question.
- Generate one diagnostic command.
- Explain newly collected evidence.
- Generate one repair.
- Generate one verification command.

Never return only a state name.

Never return an empty reply.

Never stay in diagnose without:
- generating a diagnostic command,
- analyzing evidence,
- or moving toward solve.

If essential information is missing:
- ask ONE concise question,
- set decision to "understand".

If enough information exists:
- continue toward diagnosis without asking unnecessary questions.
"""

STATE_PROMPTS = {

    "understand": """
STATE: UNDERSTAND

Goal:
Understand the user's issue.

Tasks:
- Extract facts from the user's message.
- Determine whether more information is required.
- Ask ONE concise question only if absolutely necessary.
- If enough information already exists, move toward diagnosis.

Do NOT:
- Guess the root cause.
- Suggest repairs.
- Repeat previous questions.

Decision:

Set the decision field to:

- "understand" if waiting for the user's answer.
- "hypothesis" if enough information exists.

The reply must contain:
- a helpful explanation, OR
- one concise question.

Never return the words "understand" or "hypothesis" inside reply.
""",

    "hypothesis": """
STATE: HYPOTHESIS

Goal:
Generate likely causes.

Tasks:
- Produce one to three realistic hypotheses.
- Rank them by confidence.
- Choose the best hypothesis to test first.

Do NOT:
- Repair anything yet.
- Produce many speculative ideas.

Decision:

Set decision to:

- "diagnose" when evidence should be collected.
- "understand" only if essential information is still missing.

The reply should briefly explain what will be tested next.

Never return state names inside reply.
""",

    "diagnose": """
STATE: DIAGNOSE

Goal:
Collect evidence.

Tasks:
- Generate ONE useful diagnostic command.
- Never repeat commands already executed.
- Choose the smallest command that reduces uncertainty.
- Use previous evidence and hypotheses.

If existing evidence already proves the cause:
- return decision "solve".

If there is not enough information to choose a command:
- ask ONE concise question,
- return decision "understand".

The reply must explain why the command is useful.

Never return an empty reply.

Never return only the word "diagnose".
""",

    "solve": """
STATE: SOLVE

Goal:
Repair the confirmed problem.

Tasks:
- Explain the confirmed root cause.
- Generate minimal and safe repair commands.
- Explain what each repair does.

Do NOT:
- Continue collecting evidence unless absolutely necessary.
- Invent unrelated fixes.

Decision:

Set decision to:

- "verify" after proposing the repair.
- "diagnose" only if more evidence becomes necessary.

The reply should explain the repair plan.

Never return state names inside reply.
""",

    "verify": """
STATE: VERIFY

Goal:
Confirm that the repair succeeded.

Tasks:
- Generate ONE verification command.
- Verify only the repaired issue.
- Compare expected behaviour with actual behaviour.

If verification succeeds:
- mark the issue resolved,
- increase confidence,
- return decision "finished".

If verification fails:
- explain why,
- return decision "diagnose".

Do NOT:
- Generate new hypotheses unless verification disproves the current root cause.

The reply should explain what is being verified.

Never return state names inside reply.
""",

    "finished": """
STATE: FINISHED

The investigation is complete.

Do not issue commands.

Do not ask questions.

Do not generate hypotheses.

Summarize:

- Original issue.
- Root cause.
- Evidence collected.
- Repair performed.
- Verification result.

Requirements:

- decision must be "finished".
- reply must contain the complete summary.
- steps must be an empty list.
- investigation_update should only contain any final changes if needed.

Never return only the word "finished".
"""
}

class InvestigationState:
    def __init__(self):
        self.obj = self.new_investigation()

    def new_investigation(self):
        return {
            "issue": "",
            "summary": "",
            "status": "active",
            "facts": {},
            "hypotheses": [],
            "executed_commands": [],
            "questions_asked": [],
            "pending_questions": [],
            "root_cause": None,
            "solution": None,
            "confidence": 0,
            "next_goal": "",
        }

    def _unique_list(self, items):
        if not isinstance(items, list):
            return []
        seen = set()
        unique = []
        for item in items:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique

    def _normalize_facts(self, facts):
        if isinstance(facts, dict):
            return facts.copy()
        if isinstance(facts, list):
            normalized = {}
            for item in facts:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    normalized[item["key"]] = item["value"]
            return normalized
        return {}

    def merge_hypotheses(self, current, updates):
        if not isinstance(current, list):
            current = []
        if not isinstance(updates, list):
            return current
        hypotheses_by_name = {h["name"]: h for h in current if isinstance(h, dict) and "name" in h}
        order = [h["name"] for h in current if isinstance(h, dict) and "name" in h]
        for updated in updates:
            if not isinstance(updated, dict) or "name" not in updated:
                continue
            name = updated["name"]
            if name in hypotheses_by_name:
                hypotheses_by_name[name] = {**hypotheses_by_name[name], **updated}
            else:
                hypotheses_by_name[name] = updated
                order.append(name)
        merged = [hypotheses_by_name[name] for name in order if name in hypotheses_by_name]
        return merged

    def merge_executed_commands(self, current, updates):
        if not isinstance(current, list):
            current = []
        if not isinstance(updates, list):
            return current
        commands_by_name = {entry.get("command"): entry for entry in current if isinstance(entry, dict) and entry.get("command")}
        order = [entry.get("command") for entry in current if isinstance(entry, dict) and entry.get("command")]
        for entry in updates:
            if not isinstance(entry, dict) or "command" not in entry:
                continue
            command = entry["command"]
            if command in commands_by_name:
                commands_by_name[command] = {**commands_by_name[command], **entry}
            else:
                commands_by_name[command] = entry
                order.append(command)
        return [commands_by_name[name] for name in order if name in commands_by_name]

    def infer_root_cause(self):
        if self.obj.get("confidence", 0) < 0.9:
            return
        if self.obj.get("root_cause"):
            return
        candidates = [h for h in self.obj.get("hypotheses", []) if isinstance(h, dict)]
        if not candidates:
            return
        candidates.sort(key=lambda h: h.get("confidence", 0), reverse=True)
        self.obj["root_cause"] = candidates[0].get("name")

    def ensure_next_goal(self, state):
        if state == "finished" or self.obj.get("status") in {"finished", "resolved", "complete"}:
            self.obj["next_goal"] = "Verify repair"

    def reconcile_state(self, current_state, parsed=None):
        # Returns the reconciled state (may be unchanged)
        state = current_state
        if self.obj.get("confidence", 0) > 0.9:
            state = "solve"

        if state == "understand" and not self.obj.get("executed_commands"):
            state = "diagnose"

        if parsed and parsed.get("decision") == "run_command":
            state = "diagnose"

        if state == "finished":
            self.obj["next_goal"] = "Verify repair"

        return state

    def serialize(self):
        return json.dumps(self.obj, indent=2, sort_keys=True)

    def merge_update(self, update, state):
        if not isinstance(update, dict):
            return

        for key, value in update.items():
            if key == "facts":
                normalized = self._normalize_facts(value)
                current_facts = self.obj.setdefault("facts", {})
                current_facts.update(normalized)
                self.obj["facts"] = current_facts
            elif key == "hypotheses":
                self.obj["hypotheses"] = self.merge_hypotheses(
                    self.obj.get("hypotheses", []), value
                )
            elif key == "executed_commands":
                self.obj["executed_commands"] = self.merge_executed_commands(
                    self.obj.get("executed_commands", []), value
                )
            elif key == "questions":
                if isinstance(value, list):
                    asked = self.obj.setdefault("questions_asked", [])
                    asked.extend([q for q in value if isinstance(q, str)])
                    self.obj["questions_asked"] = self._unique_list(asked)
                    pending = self.obj.get("pending_questions", [])
                    self.obj["pending_questions"] = [q for q in pending if q not in value]
            elif key == "pending_questions":
                if isinstance(value, list):
                    self.obj["pending_questions"] = self._unique_list([q for q in value if isinstance(q, str)])
            else:
                self.obj[key] = value

        if not self.obj.get("summary"):
            self.obj["summary"] = "Reviewing the investigation progress."
        if not self.obj.get("next_goal"):
            self.obj["next_goal"] = "Clarify the next diagnostic or repair step."

        self.infer_root_cause()
        self.ensure_next_goal(state)

    def transition_state(self, decision, current_state):
        # Returns the new state based on the decision (preserves original mapping)
        continue_ = False
        state = current_state
        if decision == "understand":
            state = "understand"
            continue_ = False
        elif decision == "hypothesis":
            state = "hypothesis"
            continue_ = True
        elif decision == "diagnose":
            state = "diagnose"
            continue_ = True
        elif decision == "analyze":
            state = "analyze"
            continue_ = True
        elif decision == "solve":
            state = "solve"
            continue_ = True
        elif decision == "verify":
            state = "verify"
            continue_ = True
        elif decision == "finished":
            state = "finished"
            continue_ = False
        print(continue_)
        return state, continue_

    def apply_controller_transitions(self, parsed, current_state):
        """
        Apply controller-level state transitions.

        Pipeline:
        understand -> hypothesis -> diagnose -> solve -> verify -> finished
        """

        state = current_state

        # If we are confident enough, move to solving.
        if self.obj.get("confidence", 0) >= 0.9:
            state = "solve"

        # After a command has been requested, we are diagnosing.
        if parsed.get("decision") == "run_command":
            state = "diagnose"

        # If we've gathered enough information, move from understand
        # to hypothesis generation.
        if (
            state == "understand"
            and (
                self.obj.get("executed_commands")
                or self.obj.get("facts")
                or self.obj.get("questions_asked")
            )
        ):
            state = "hypothesis"

        # Once at least one hypothesis exists, begin diagnosis.
        if (
            state == "hypothesis"
            and self.obj.get("hypotheses")
        ):
            state = "diagnose"

        # If a root cause has been identified, begin solving.
        if (
            state == "diagnose"
            and self.obj.get("root_cause")
        ):
            state = "solve"

        # If a solution has been generated, verify it.
        if (
            state == "solve"
            and self.obj.get("solution")
        ):
            state = "verify"

        # Verification complete.
        if parsed.get("decision") == "finished":
            state = "finished"
            self.obj["next_goal"] = "Verify repair"

        return state