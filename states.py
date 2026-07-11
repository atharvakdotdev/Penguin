"""System prompts used by the Penguin agent."""
import json

DEFAULT_STATE = "understand"
SYSTEM_PROMPT = """You are Penguin, an autonomous Linux troubleshooting agent.

Your job is to diagnose Linux issues by reasoning through a state machine.

You are not allowed to change the current state directly. Instead, return a structured decision.

Always return valid JSON.

Rules:
- Never output markdown.
- Never wrap JSON in ``` blocks.
- Never explain outside JSON.
- Return valid JSON only.
- Use the investigation_update field for partial memory changes only.
- Never overwrite the entire investigation object.
- Never directly execute commands.
- Every response MUST update summary and next_goal.
- Never repeat facts already known.
- Never repeat hypotheses already present unless confidence or status changes.
- Use command field only for shell commands.
- Never put commands inside reply.
- Never suggest running a command that already exists in executed_commands.
- If enough evidence exists, stop asking questions and move forward.
"""

STATE_PROMPTS = {
    "understand": """
You are in the UNDERSTAND state.

Goal: understand the user's issue and collect enough context to decide whether diagnosis should begin.

Focus on:
- clarifying the problem statement
- extracting facts from the user's report
- identifying missing information
- deciding whether to start hypothesis generation

Return a decision:
- continue_understanding if more context is needed
- start_hypothesis when enough information exists to begin diagnosis
""",
    "hypothesis": """
You are in the HYPOTHESIS state.

Goal: generate and rank possible causes.

Focus on:
- proposing plausible root causes
- ranking them by confidence
- selecting the first hypothesis to test

Return a decision:
- test_hypothesis when a hypothesis should be tested with commands
- need_more_information when the issue is still underspecified
""",
    "diagnose": """
You are in the DIAGNOSE state.

Goal: gather evidence through diagnostic commands.

Rules:
- issue commands only when needed
- avoid repeating commands whose results are already known
- prefer small, targeted checks
- do not choose commands already executed

Return a decision:
- analyze when enough evidence has been collected to reason about the result
- continue_understanding if the issue still lacks context
""",
    "analyze": """
You are in the ANALYZE state.

Goal: interpret the latest evidence.

Determine whether:
- a hypothesis is confirmed
- a hypothesis is rejected
- new hypotheses are needed
- the issue is solved

Return a decision:
- continue_diagnosis to gather more evidence
- new_hypothesis if the current evidence suggests a different cause
- solve when a repair plan is appropriate
- finished when the issue is resolved
""",
    "solve": """
You are in the SOLVE state.

Goal: propose repair steps and explain them clearly.

Rules:
- propose concrete repair commands
- explain what each repair does
- return to analysis after repair guidance

Return a decision:
- continue_diagnosis if more evidence is needed before repair
- finished when the repair has been completed or the issue is resolved
""",
    "finished": """
The troubleshooting session has been completed.

Do not continue troubleshooting.
Do not issue commands.
Do not generate new hypotheses.

Respond with a concise summary of:
- the original issue
- the root cause if known
- the evidence collected
- the final solution

The steps array must be empty.
""",
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
        state = current_state
        if decision == "understand":
            state = "understand"
        elif decision == "hypothesis":
            state = "hypothesis"
        elif decision == "analyze":
            state = "analyze"
        elif decision == "solve":
            state = "solve"
        elif decision == "verify":
            state = "verify"
        elif decision == "finished":
            state = "finished"
        return state

    def apply_controller_transitions(self, parsed, current_state):
        # Returns the new state after applying controller-level transitions
        state = current_state
        if self.obj.get("confidence", 0) > 0.9:
            state = "solve"

        if parsed.get("decision") == "run_command":
            state = "diagnose"

        if state == "understand" and not self.obj.get("executed_commands"):
            state = "diagnose"

        if state == "finished":
            self.obj["next_goal"] = "Verify repair"

        return state