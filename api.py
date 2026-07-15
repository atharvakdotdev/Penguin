"""API layer for the Penguin troubleshooting agent."""

import json
import os
import queue
import subprocess
from datetime import datetime, timezone

from ollama import chat

from schemas import JSON_SCHEMA
from states import DEFAULT_STATE, STATE_PROMPTS, SYSTEM_PROMPT, InvestigationState

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b-q4_K_M").strip()


class Api:
    def __init__(self):
        self.model = DEFAULT_MODEL
        self.state = DEFAULT_STATE
        self.chat_history = []
        self.active_process = None
        self.investigation = InvestigationState()
        self.input_queue = queue.Queue()
        self.continue_event = False
    @property
    def investigating_obj(self):
        return self.investigation.obj

    @investigating_obj.setter
    def investigating_obj(self, value):
        # preserve external assignment behavior by replacing the internal object
        if isinstance(value, dict):
            self.investigation.obj = value
        else:
            self.investigation.obj = self.investigation.new_investigation()

    def _new_investigation(self):
        return self.investigation.new_investigation()

    def _unique_list(self, items):
        return self.investigation._unique_list(items)

    def _normalize_facts(self, facts):
        return self.investigation._normalize_facts(facts)

    def _merge_hypotheses(self, current, updates):
        return self.investigation.merge_hypotheses(current, updates)

    def _merge_executed_commands(self, current, updates):
        return self.investigation.merge_executed_commands(current, updates)

    def _infer_root_cause(self):
        return self.investigation.infer_root_cause()

    def _ensure_next_goal(self):
        return self.investigation.ensure_next_goal(self.state)

    def _reconcile_state(self, parsed=None):
        self.state = self.investigation.reconcile_state(self.state, parsed)

    def _serialize_investigation(self):
        return self.investigation.serialize()

    def build_messages(self, message):
        """Build the messages payload for the model without prior history."""
        self._reconcile_state()
        investigation_summary = self._serialize_investigation()
        messages = [
            {"role": "system", "content": STATE_PROMPTS[self.state]},
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": investigation_summary},
            {"role": "user", "content": str(message).strip()},
        ]
        return messages

    def _merge_investigation_update(self, update):
        # delegate to InvestigationState and keep local reference in sync
        self.investigation.merge_update(update, self.state)
        self.investigating_obj = self.investigation.obj

    def _transition_state(self, decision):
        # kept for backward compatibility; delegate to InvestigationState
        self.state , self.continue_event = self.investigation.transition_state(decision, self.state)

    def _apply_controller_transitions(self, parsed):
        # kept for backward compatibility; delegate to InvestigationState
        self.state = self.investigation.apply_controller_transitions(parsed, self.state)
        self.investigating_obj = self.investigation.obj

    def parse_response(self, content):
        if not content:
            return {"reply": "I couldn't generate a response.", "steps": []}

        cleaned = str(content).strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {"reply": cleaned, "steps": []}

        if isinstance(parsed, dict):
            # honor is_continue provided by the model in the parsed response
            try:
                self.continue_event = bool(parsed.get("is_continue", False))
            except Exception:
                self.continue_event = False
            decision = parsed.get("decision")
            if isinstance(decision, str):
                self._transition_state(decision)
            update = parsed.get("investigation_update")
            if isinstance(update, dict):
                self._merge_investigation_update(update)
            self._apply_controller_transitions(parsed)
            command = parsed.get("command")
            if decision == "run_command" and isinstance(command, str):
                if not self._should_run_command(command):
                    return {
                        "reply": "This command has already been executed. Choose a different diagnostic action.",
                        "decision": "need_more_information",
                        "steps": [],
                        "investigation_update": {},
                    }
            return {
                "reply": parsed.get("reply", cleaned),
                "decision": decision,
                "command": command,
                "requires_sudo": parsed.get("requires_sudo", False),
                "steps": parsed.get("steps", []) if isinstance(parsed.get("steps"), list) else [],
                "investigation_update": update,
                "is_continue": self.continue_event,
            }

        return {"reply": cleaned, "steps": []}

    def respond(self, message):
        if not message or not str(message).strip():
            return {"reply": "Please enter a message.", "steps": []}
        # print(self.investigating_obj)
        self.chat_history.extend(self.build_messages(message))

        with open("chat_history.json", "w") as f:
            json.dump(self.chat_history, f, indent=4)

        candidate_models = []
        if self.model:
            candidate_models.append(self.model)
        for fallback in ["qwen3:8b-q4_K_M"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)
        # print(self.chat_history)
        last_error = None
        for model_name in candidate_models:
            try:
                response = chat(
                    model=model_name,
                    messages=self.build_messages(message),
                    format=JSON_SCHEMA,
                    stream=False,
                    think=False,
                    keep_alive=-1,
                    options = {
    "num_thread": 4
}
                )

                content = (
                    response.get("message", {}).get("content", "")
                    if isinstance(response, dict)
                    else getattr(getattr(response, "message", None), "content", "")
                )

                if content:
                    self.chat_history.extend([{"role": "assistant", "content": content}])
                    self.model = model_name
                    parsed = self.parse_response(content)

                    response_data = {
                        "reply": parsed.get("reply", ""),
                        "steps": parsed.get("steps", []) if isinstance(parsed.get("steps"), list) else [],
                        "has_more_steps": False,
                        "decision": parsed.get("decision"),
                        "investigation_update": self.investigating_obj,
                        "is_continue": self.continue_event,
                    }

                    if response_data["steps"]:
                        response_data["has_more_steps"] = len(response_data["steps"]) > 1
                        response_data["next_step"] = response_data["steps"][0]
                    print(response_data)
                    return response_data
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            return {"reply": "Model Error", "steps": [], "error": str(last_error)}

        return {"reply": "I couldn't generate a response.", "steps": []}

    def report_command_output(self, command, output, success):
        """Record command execution and prepare the next prompt without mutating chat history."""
        status = "succeeded" if success else "failed"
        output_text = str(output or "").strip() or "(no output)"
        self._record_command(command, success, output_text)

        next_prompt = f"""
The requested command has finished.

Status: {status}

Command:
{command}

Output:
{output_text}

Do NOT repeat this command unless the result has changed.
Choose the next diagnostic step based on the above output.
"""
        return {
            "status": "reported",
            "next_prompt": next_prompt,
            "command_status": status,
        }

    def _record_command(self, command, success, output):
        executions = self.investigating_obj.setdefault("executed_commands", [])
        for entry in executions:
            if entry.get("command") == command:
                return

        execution = {
            "command": command,
            "success": success,
            "output": output,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        executions.append(execution)

    def _should_run_command(self, command):
        for entry in self.investigating_obj.get("executed_commands", []):
            if entry.get("command") == command:
                return False
        return True

    def run_command(self, command, use_sudo=False):
        """Execute a shell command once per investigation object state."""
        if not self._should_run_command(command):
            return {"success": False, "output": "", "error": "Command already executed", "return_code": -1}

        try:
            if use_sudo:
                command = f"sudo {command}"

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout or result.stderr or ""
            self._record_command(command, result.returncode == 0, output)
            return {
                "success": result.returncode == 0,
                "output": output,
                "error": result.stderr,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            self._record_command(command, False, "Command timed out after 30 seconds")
            return {
                "success": False,
                "output": "",
                "error": "Command timed out after 30 seconds",
                "return_code": -1,
            }
        except Exception as e:
            self._record_command(command, False, str(e))
            return {"success": False, "output": "", "error": str(e), "return_code": -1}