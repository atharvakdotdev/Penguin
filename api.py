"""API layer for the Penguin troubleshooting agent."""

import json
import os
import queue
import subprocess
from datetime import datetime, timezone

from ollama import chat

from schemas import JSON_SCHEMA
from states import DEFAULT_STATE, STATE_PROMPTS, SYSTEM_PROMPT

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b").strip()


class Api:
    def __init__(self):
        self.model = DEFAULT_MODEL
        self.state = DEFAULT_STATE
        self.chat_history = []
        self.active_process = None
        self.investigating_obj = self._new_investigation()
        self.input_queue = queue.Queue()

    def _new_investigation(self):
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

    def build_messages(self, message):
        """Build the messages payload for the model without prior history."""
        investigation_summary = self._serialize_investigation()
        messages = []
        messages.append({"role": "system", "content": STATE_PROMPTS[self.state]})
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
        messages.append({"role": "system", "content": investigation_summary})
        messages.append({"role": "user", "content": str(message).strip()})
        return messages

    def clean_history(self, history):
        return [msg for msg in history if msg.get("role") != "system"]

    def _serialize_investigation(self):
        return json.dumps(self.investigating_obj, indent=2, sort_keys=True)

    def _merge_investigation_update(self, update):
        if not isinstance(update, dict):
            return
        for key, value in update.items():
            if key in {"facts", "hypotheses", "executed_commands", "questions_asked", "pending_questions"}:
                current = self.investigating_obj.get(key, []) if key != "facts" else self.investigating_obj.get(key, {})
                if isinstance(current, list) and isinstance(value, list):
                    current.extend(value)
                    self.investigating_obj[key] = current
                elif isinstance(current, dict) and isinstance(value, dict):
                    current.update(value)
                    self.investigating_obj[key] = current
                else:
                    self.investigating_obj[key] = value
            else:
                self.investigating_obj[key] = value

    def _transition_state(self, decision):
        if decision == "start_hypothesis":
            self.state = "hypothesis"
        elif decision == "test_hypothesis":
            self.state = "diagnose"
        elif decision == "analyze":
            self.state = "analyze"
        elif decision == "solve":
            self.state = "solve"
        elif decision == "finished":
            self.state = "finished"
        elif decision == "continue_understanding":
            self.state = "understand"
        elif decision == "need_more_information":
            self.state = "understand"
        elif decision == "continue_diagnosis":
            self.state = "diagnose"
        elif decision == "new_hypothesis":
            self.state = "hypothesis"
        else:
            self.state = self.state

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
            decision = parsed.get("decision")
            if isinstance(decision, str):
                self._transition_state(decision)
            update = parsed.get("investigation_update")
            if isinstance(update, dict):
                self._merge_investigation_update(update)
            return {
                "reply": parsed.get("reply", cleaned),
                "decision": decision,
                "steps": parsed.get("steps", []) if isinstance(parsed.get("steps"), list) else [],
                "investigation_update": update,
            }

        return {"reply": cleaned, "steps": []}

    def respond(self, message):
        if not message or not str(message).strip():
            return {"reply": "Please enter a message.", "steps": []}

        self.chat_history = self.clean_history(self.chat_history)
        self.chat_history.extend(self.build_messages(message))
        with open("chat_history.json", "w") as f:
            json.dump(self.chat_history, f, indent=4)

        candidate_models = []
        if self.model:
            candidate_models.append(self.model)
        for fallback in ["gemma3:1b"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_error = None
        for model_name in candidate_models:
            try:
                response = chat(
                    model=model_name,
                    messages=self.chat_history,
                    format=JSON_SCHEMA,
                    stream=False,
                )

                content = (
                    response.get("message", {}).get("content", "")
                    if isinstance(response, dict)
                    else getattr(getattr(response, "message", None), "content", "")
                )

                if content:
                    self.chat_history.append({"role": "assistant", "content": content})
                    self.model = model_name
                    parsed = self.parse_response(content)

                    response_data = {
                        "reply": parsed.get("reply", ""),
                        "steps": parsed.get("steps", []) if isinstance(parsed.get("steps"), list) else [],
                        "has_more_steps": False,
                        "decision": parsed.get("decision"),
                    }

                    if response_data["steps"]:
                        response_data["has_more_steps"] = len(response_data["steps"]) > 1
                        response_data["next_step"] = response_data["steps"][0]

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

    # def submit_command_input(self, input_text):
    #     """
    #     Submit input to an interactive command.

    #     Args:
    #         input_text: The input to send to the running process
    #     """
    #     try:
    #         self.input_queue.put(input_text)
    #         return {"success": True}
    #     except Exception as e:
    #         return {"success": False, "error": str(e)}
