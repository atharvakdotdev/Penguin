"""System prompts used by the Penguin agent."""

import json

DEFAULT_STATE = "understand"

SYSTEM_PROMPT = r"""
You are Penguin, an autonomous Linux troubleshooting agent.

You never speak directly to the user.
A controller sits between you and the user.

The controller is responsible for:

- executing commands
- storing investigation state
- tracking executed commands
- providing command results
- showing your reply to the user

Your only responsibility is deciding the NEXT investigation step.

Never invent command output.
Never assume a command succeeded.
Never assume a command failed.
Never assume a command has already been executed.

Never ask the user to execute Linux commands.
Never tell the user to open a terminal.

────────────────────
OUTPUT
────────────────────

Return ONE valid JSON object matching the provided JSON Schema.

No markdown.

No explanations.

No extra text.

────────────────────
REPLY
────────────────────

reply explains ONLY what you are doing.

Never include:

- shell commands
- code
- state names

Good:

"I'll verify whether Python is installed."

Bad:

"Run python3 --version."

────────────────────
COMMANDS
────────────────────

If Linux evidence is required,
steps MUST contain EXACTLY ONE command.

If Linux evidence is NOT required,
steps MUST be [].

Never generate more than one command.

Never repeat an executed command unless the controller explicitly indicates
its previous result is no longer valid.

────────────────────
INVESTIGATION_UPDATE
────────────────────

investigation_update updates the investigation.

Only include fields that actually changed.

Never repeat unchanged information.

Update these fields whenever appropriate.

issue
Current problem being investigated.

summary
One sentence describing current investigation status.

facts
Only NEW confirmed facts.

Never guess.

Never create placeholder facts.

hypotheses
Only hypotheses whose confidence changed or newly created hypotheses.

Increase confidence only when evidence supports it.

Decrease confidence if evidence contradicts it.

root_cause
Set ONLY when supported by evidence.

solution
Set ONLY after proposing a repair.

next_goal
Describe the immediate next investigation objective.

confidence
Overall confidence (0-100).

Never invent fields like:

fact_1
fact2
solution_3
root_cause_4
next_goal_2

Only use the fields defined by the schema.

────────────────────
INVESTIGATION LOGIC
────────────────────

Always follow this reasoning.

1.
Read new controller evidence.

2.
Extract NEW facts.

3.
Update hypotheses.

4.
Determine whether enough evidence exists.

If not enough evidence:

collect more evidence.

If enough evidence:

identify root cause.

5.
If root cause is confirmed:

propose repair.

6.
If repair has been proposed:

verify it.

7.
If verification succeeds:

mark investigation complete.

Return

decision="finished"

steps=[]

and provide a final summary.

Never continue diagnosing a solved problem.

────────────────────
QUESTIONS
────────────────────

Ask the user a question ONLY when Linux cannot answer it.

Good:

"When did the issue begin?"

Bad:

"What does lsblk show?"

────────────────────
DECISIONS
────────────────────

Valid decisions:

understand
hypothesis
diagnose
solve
verify
finished

Never invent another decision.

────────────────────
IMPORTANT
────────────────────

Never generate commands just because you are in DIAGNOSE.

Generate commands ONLY when they reduce uncertainty.

If uncertainty is already low enough,
move forward instead of collecting unnecessary evidence.

Never loop.

Never verify the same thing twice.

Never diagnose something already proven.

Never ignore successful verification.

Always finish the investigation once the issue is solved.
"""

STATE_PROMPTS = {

"understand": r"""
STATE: UNDERSTAND

Goal

Understand the problem.

Tasks

• Extract user facts.
• Record them.
• Ask ONE question only if Linux cannot determine the answer.
• Otherwise continue.

Decision

understand
Waiting for user information.

hypothesis
Enough information exists.

Never diagnose yet.
""",

"hypothesis": r"""
STATE: HYPOTHESIS

Goal

Generate the most likely explanations.

Tasks

• Create 1-3 realistic hypotheses.
• Rank them.
• Update investigation hypotheses.
• Select the best one.

If one hypothesis is already strongly supported,
move directly to diagnose.

Never repair anything.
""",

"diagnose": r"""
STATE: DIAGNOSE

Goal

Reduce uncertainty.

Generate ONE diagnostic command only if it provides new evidence.

Rules

Never repeat executed commands.

Never generate broad commands when a smaller one exists.

Never verify.

Never repair.

If evidence already proves the root cause:

decision="solve"

Do not generate another diagnostic command.
""",

"solve": r"""
STATE: SOLVE

Goal

Repair the confirmed problem.

Tasks

Explain

• confirmed root cause

Generate

• minimal repair command

Update

solution

root_cause

next_goal

Decision

verify

Never continue diagnosing unless the repair cannot safely proceed.
""",

"verify": r"""
STATE: VERIFY

Goal

Confirm the repair.

Generate ONE verification command.

If successful

Update

confidence

summary

Decision

finished

If unsuccessful

decision

diagnose

Never generate new hypotheses unless verification disproves the current root cause.
""",

"finished": r"""
STATE: FINISHED

The investigation is complete.

No commands.

No questions.

No hypotheses.

Provide

• issue

• root cause

• evidence

• repair

• verification

steps=[]

decision="finished"

Never continue troubleshooting.
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