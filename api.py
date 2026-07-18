"""API layer for the Penguin troubleshooting agent."""

import copy
import json
import os
import queue
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ollama import chat

from schemas import JSON_SCHEMA
from session_manager import SessionManager
from states import DEFAULT_STATE, STATE_PROMPTS, SYSTEM_PROMPT, InvestigationState

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b").strip()


class Api:
    def __init__(self):
        self.model = DEFAULT_MODEL
        self.state = DEFAULT_STATE
        self.chat_history = []
        self.active_session_id = None
        self.active_process = None
        self.investigation = InvestigationState()
        self.input_queue = queue.Queue()
        self.continue_event = False
        self.session_manager = SessionManager(Path(__file__).resolve().parent / "sessions.db")

    @property
    def investigating_obj(self):
        return self.investigation.obj

    @investigating_obj.setter
    def investigating_obj(self, value):
        if isinstance(value, dict):
            self.investigation.obj = value
        else:
            self.investigation.obj = self.investigation.new_investigation()

    def _reset_runtime_state(self):
        self.state = DEFAULT_STATE
        self.chat_history = []
        self.investigation = InvestigationState()
        self.investigating_obj = self.investigation.new_investigation()
        self.continue_event = False
        self.active_session_id = None

    @staticmethod
    def _is_controller_prompt(message):
        if not isinstance(message, str):
            return False
        cleaned = message.strip()
        return (
            cleaned.startswith("The requested command has finished.")
            and "Choose the next diagnostic step based on the above output." in cleaned
        )

    @staticmethod
    def _is_internal_investigation_payload(message):
        if not isinstance(message, str):
            return False
        cleaned = message.strip()
        if not (cleaned.startswith("{") and cleaned.endswith("}")):
            return False
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return False
        return isinstance(payload, dict) and any(key in payload for key in ["issue", "summary", "facts", "hypotheses", "executed_commands", "next_goal", "confidence"])

    def _sanitize_chat_history(self, history):
        if not isinstance(history, list):
            return []

        cleaned = []
        for entry in history:
            if not isinstance(entry, dict):
                continue
            role = entry.get("role")
            if role == "system":
                continue
            if role == "user":
                content = entry.get("content")
                if self._is_controller_prompt(content):
                    continue
            cleaned.append(copy.deepcopy(entry))
        return cleaned

    def _derive_session_title(self):
        for entry in reversed(self.chat_history):
            if entry.get("role") == "user" and entry.get("content"):
                content = str(entry["content"]).strip()
                return content[:30] + ("..." if len(content) > 30 else "")
        return "New Chat"

    def _session_snapshot(self):
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": self.active_session_id,
            "title": self._derive_session_title(),
            "created": now,
            "modified": now,
            "chatHistory": self._sanitize_chat_history(self.chat_history),
            "investigation": copy.deepcopy(self.investigating_obj),
            "isContinue": bool(self.continue_event),
        }

    def save_current_session(self, title=None):
        snapshot = self._session_snapshot()
        if title:
            snapshot["title"] = title
        if self.active_session_id is None:
            saved = self.session_manager.create_session(snapshot)
            self.active_session_id = saved["id"]
        else:
            snapshot["id"] = self.active_session_id
            saved = self.session_manager.save_session(snapshot)
            self.active_session_id = saved["id"]

        return {
            "session_id": self.active_session_id,
            "id": self.active_session_id,
            "title": saved["title"],
            "updated_at": saved["modified"],
        }

    def list_sessions(self):
        sessions = self.session_manager.list_sessions()
        return [
            {
                "id": session.get("id"),
                "session_id": session.get("id"),
                "title": session.get("title") or "New Chat",
                "created": session.get("created"),
                "modified": session.get("modified"),
                "updated_at": session.get("modified"),
                "chatHistory": self._sanitize_chat_history(session.get("chatHistory", [])),
                "chat_history": self._sanitize_chat_history(session.get("chatHistory", [])),
                "investigation": copy.deepcopy(session.get("investigation", {})),
                "investigating_obj": copy.deepcopy(session.get("investigation", {})),
                "isContinue": bool(session.get("isContinue", False)),
                "continue_event": bool(session.get("isContinue", False)),
            }
            for session in sessions
        ]

    def open_session(self, session_id):
        session = self.session_manager.load_session(str(session_id))
        if session is None:
            return {"status": "not_found", "session_id": session_id}

        self.active_session_id = session["id"]
        self.chat_history = self._sanitize_chat_history(session.get("chatHistory", []))
        self.investigation = InvestigationState()
        self.investigating_obj = copy.deepcopy(session.get("investigation", {}))
        self.continue_event = bool(session.get("isContinue", False))
        self.state = DEFAULT_STATE

        return {
            "status": "opened",
            "session_id": self.active_session_id,
            "title": session.get("title") or "New Chat",
            "chat_history": copy.deepcopy(self.chat_history),
            "investigating_obj": copy.deepcopy(self.investigating_obj),
            "continue_event": self.continue_event,
        }

    def delete_session(self, session_id):
        removed = self.session_manager.delete_session(str(session_id))
        if removed and self.active_session_id == str(session_id):
            self._reset_runtime_state()
        return {"status": "deleted" if removed else "not_found", "session_id": session_id}

    def create_new_session(self):
        if self.active_session_id is not None:
            self.save_current_session()

        created = self.session_manager.create_session(
            {
                "id": None,
                "title": "New Chat",
                "created": datetime.now(timezone.utc).isoformat(),
                "modified": datetime.now(timezone.utc).isoformat(),
                "chatHistory": [],
                "investigation": {},
                "isContinue": False,
            }
        )
        self._reset_runtime_state()
        self.active_session_id = created["id"]
        return {
            "status": "created",
            "session_id": self.active_session_id,
            "id": self.active_session_id,
            "title": created["title"],
        }

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
        investigation_summary = self._serialize_investigation()
        current_state_prompt = STATE_PROMPTS.get(self.state, STATE_PROMPTS[DEFAULT_STATE])
        messages = [
            {"role": "system", "content": current_state_prompt},
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

        normalized_message = str(message).strip()
        if not self._is_controller_prompt(normalized_message) and not self._is_internal_investigation_payload(normalized_message):
            self.chat_history.append({"role": "user", "content": normalized_message})
            self.save_current_session()

        candidate_models = []
        if self.model:
            candidate_models.append(self.model)
        for fallback in ["qwen2.5-coder:3b"]:
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
                    assistant_payload = content
                    try:
                        assistant_payload = json.loads(content)
                    except json.JSONDecodeError:
                        assistant_payload = content

                    self.chat_history.append({"role": "assistant", "content": assistant_payload})
                    self.model = model_name
                    parsed = self.parse_response(content)
                    self.save_current_session()

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
        """Prepare the next prompt without mutating the visible chat history."""
        status = "succeeded" if success else "failed"
        output_text = str(output or "").strip() or "(no output)"

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
        execution = {
            "command": command,
            "success": success,
            "output": output,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        executions.append(execution)

    def _should_run_command(self, command):
        executions = self.investigating_obj.get("executed_commands", [])
        if not executions:
            return True

        last_entry = executions[-1]
        return not (isinstance(last_entry, dict) and last_entry.get("command") == command)

    def run_command(self, command, use_sudo=False):
        """Execute a shell command unless the same command was just run in the immediately previous step."""
        if not self._should_run_command(command):
            return {"success": False, "output": "", "error": "Command already executed consecutively", "return_code": -1}

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