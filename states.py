"""System prompts used by the Penguin agent."""

import json

DEFAULT_STATE = "understand"

SYSTEM_PROMPT = r"""You are Penguin, an autonomous Linux troubleshooting agent.
A controller executes your commands and passes you the command results, the Visible Chat History, and the current Investigation Object.

The Investigation Object is your persistent memory. Every request contains the latest Investigation Object. Read it before responding. Only update information when new evidence supports it. Never recreate information already present. Never remove confirmed facts. Never remove confirmed hypotheses. Never remove a confirmed root cause. The controller merges investigation_update into this object.

You must respond with a single JSON object containing exactly the following keys:
- reply (string): Natural language explanation shown to the user of what you are doing. Do not include commands/code or state names.
- decision (string): The next state/decision you are transitioning to (allowed values: "understand", "hypothesis", "diagnose", "solve", "verify", "finished").
- steps (array): Commands or actions to run. If Linux evidence is required, steps must contain exactly one command object. Otherwise, steps must be [].
- investigation_update (object): Dictionary of updates to merge into the Investigation Object.

For every response, recalculate investigation_update.next_goal from the complete
Investigation Object. Consider the issue, summary, every fact, every hypothesis,
all executed command results, confidence, current state, and the previous next_goal.
Return a specific next goal that reduces the remaining uncertainty or completes the
next required phase. Do not copy the previous next_goal when the evidence changes.

EVIDENCE GATE FOR EVERY DECISION:
Before choosing a decision, inspect the complete Investigation Object and the latest
command result. State internally which existing facts support the decision, which
hypothesis it tests or confirms, and what command result changed the assessment.
Never advance because a step was merely attempted. A command is evidence only after
its recorded output and success status have been reviewed. If the evidence is missing,
contradictory, or inconclusive, remain in diagnose and choose one different command
that tests the highest-value uncertainty. The next_goal must describe that evidence
gap when one remains.

GENERAL RULES:
1. Output MUST be a single JSON object matching the JSON Schema. No markdown, no explanations outside JSON.
2. Never repeat the most recently executed command.
3. Return all fields required by the current state.
4. Never ask the user to execute Linux commands or tell them to open a terminal.
5. Ask the user a question ONLY when Linux cannot determine the answer.
6. Confidence values must be float values between 0.0 and 1.0.
"""

STATE_PROMPTS = {

"understand": r"""STATE = UNDERSTAND

INPUT
User request

OUTPUT
investigation_update
{
    issue
    summary
    next_goal
}
steps=[]

Allowed decisions
understand
hypothesis

Forbidden
commands
hypotheses
solution
root_cause""",

"hypothesis": r"""STATE = HYPOTHESIS

INPUT
User request and/or current investigation

OUTPUT
investigation_update
{
    facts: [at least one fact from the user request or current investigation]
        {
            key
            value
        }
    hypotheses: [at least one hypothesis]
        {
            name
            confidence
            status ("possible", "likely", "confirmed", "rejected")
        }
    ]
    next_goal
}
steps=[]

Allowed decisions
hypothesis
diagnose (Forbidden unless at least one hypothesis exists)

Forbidden
commands
root_cause
solution""",

"diagnose": r"""STATE = DIAGNOSE

INPUT
Latest command output and/or current investigation

DECISION CHECK
Use facts from the Investigation Object, the active hypothesis, and the output/status
of the most recent executed command. Do not choose solve unless that output confirms
the hypothesis. If it does not, update the hypothesis status and diagnose again.

OUTPUT
investigation_update
{
    next_goal
    facts: [at least one fact]
    hypotheses: [at least one hypothesis, update confidence/status]
    confidence (optional, overall confidence)
}
steps=[
    {
        type: "command"
        title
        description (must explain how this reduces uncertainty)
        command
        run: true
        requires_sudo
    }
]

Allowed decisions
diagnose
solve (only if command confirms the hypothesis)

Forbidden
None""",

"solve": r"""STATE = SOLVE

INPUT
Confirmed hypothesis

DECISION CHECK
The hypothesis must be confirmed by a recorded command result, not by confidence
alone. Reconcile the command's success status and output with every relevant fact
before selecting the repair. If confirmation is absent, choose diagnose instead.

OUTPUT
investigation_update
{
    root_cause (must not be null)
    solution (array of repair commands/steps)
    next_goal
}
steps=[
    {
        type: "command"
        title
        description
        command
        run: true
        requires_sudo
    }
]

Allowed decisions
verify

Forbidden
None""",

"verify": r"""STATE = VERIFY

INPUT
Repair command results

DECISION CHECK
Review the recorded repair result and its output against the original facts and root
cause. A successful process exit is not proof that the issue is fixed. Verification
must test the user-visible behavior or the specific root-cause condition.

OUTPUT
investigation_update
{
    next_goal
}
steps=[
    {
        type: "command"
        title
        description
        command
        run: true
    }
] (or steps=[] if verifying via reasoning)

Allowed decisions
verify
finished
diagnose

Forbidden
None""",

"finished": r"""STATE = FINISHED

INPUT
Successful verification

DECISION CHECK
Only finish when a recorded verification result confirms the fix, and the reply can
be supported by the issue, root cause, repair, and verification evidence. Otherwise
return to verify or diagnose.

OUTPUT
reply (Summary of: issue, root_cause, repair, and verification)
investigation_update
{
    hypotheses=[]
    next_goal
}
steps=[]

Allowed decisions
finished

Forbidden
commands
hypotheses"""
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
            return {str(k).strip(): v for k, v in facts.items()}
        if isinstance(facts, list):
            normalized = {}
            for item in facts:
                if isinstance(item, dict):
                    norm_item = {str(k).strip(): v for k, v in item.items()}
                    if "key" in norm_item and "value" in norm_item:
                        normalized[str(norm_item["key"]).strip()] = norm_item["value"]
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

        merged = list(current)
        for entry in updates:
            if isinstance(entry, dict) and "command" in entry:
                merged.append(entry)
        return merged



    def ensure_next_goal(self, state):
        return self.obj.get("next_goal")

    def reconcile_state(self, current_state, parsed=None):
        """Keep the state aligned to the LLM's own decision flow.

        The controller must not infer or override investigation states from
        evidence snapshots. Only the model should move the investigation
        between understand -> hypothesis -> diagnose -> solve -> verify -> finished.
        """
        state = current_state

        return state

    def serialize(self):
        return json.dumps(self.obj, indent=2, sort_keys=True)

    def merge_update(self, update, state):
        if not isinstance(update, dict):
            return

        # Normalize the update dictionary keys by stripping whitespaces
        normalized_update = {}
        for k, v in update.items():
            normalized_update[str(k).strip()] = v

        for key, value in normalized_update.items():
            if key == "facts":
                normalized = self._normalize_facts(value)
                current_facts = self.obj.setdefault("facts", {})
                current_facts.update(normalized)
                self.obj["facts"] = current_facts
            elif key == "hypotheses":
                # Ensure each hypothesis dictionary also has normalized keys
                normalized_hypotheses = []
                if isinstance(value, list):
                    for hyp in value:
                        if isinstance(hyp, dict):
                            normalized_hyp = {str(hk).strip(): hv for hk, hv in hyp.items()}
                            normalized_hypotheses.append(normalized_hyp)
                        else:
                            normalized_hypotheses.append(hyp)
                else:
                    normalized_hypotheses = value

                self.obj["hypotheses"] = self.merge_hypotheses(
                    self.obj.get("hypotheses", []), normalized_hypotheses
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
        self.ensure_next_goal(state)

    def transition_state(self, decision, current_state):
        # Returns the new state based on the decision (preserves original mapping)
        continue_ = False
        state = current_state
        if current_state == "understand":
            state = "hypothesis"
            continue_ = False
        elif current_state == "hypothesis":
            state = "diagnose"
            continue_ = True
        elif current_state == "diagnose":
            state = decision
            continue_ = True
        elif current_state == "solve":
            state = decision
            continue_ = True
        elif current_state == "verify":
            state = decision
            continue_ = True
        elif current_state == "finished":
            state = decision
            continue_ = False
        print(continue_)
        return state, continue_

    # def apply_controller_transitions(self, parsed, current_state):
    #     print(parsed)
    #     return current_state