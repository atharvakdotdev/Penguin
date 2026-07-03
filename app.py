import json
import os
import subprocess
import threading
import queue
import webview
from ollama import chat
from datetime import datetime

DEFAULT_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "gemma3:1b"
).strip()

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string"
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "info",
                            "analysis",
                            "command",
                            "verification"
                        ]
                    },
                    "title": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    },
                    "command": {
                        "type": "string"
                    },
                    "run": {
                        "type": "boolean"
                    },
                    "requires_sudo": {
                        "type": "boolean"
                    }
                },
                "required": [
                    "type",
                    "title"
                ]
            }
        }
    },
    "required": [
        "reply",
        "steps"
    ]
}

SYSTEM_PROMPT = """
You are Penguin, an autonomous Linux troubleshooting agent.

Your job is to diagnose Linux issues by gathering information one step at a time.

Never tell the user to contact a Linux expert, system administrator, or support unless explicitly requested.

If you don't have enough information, request or execute another diagnostic command.

Always continue troubleshooting until:
1. The issue is solved.
2. User input is required.
3. The problem is impossible to continue without physical access.

Never give up after one attempt.
Never refuse because a problem is "too complex."

Always return valid JSON.

Rules:

- Never output markdown.
- Never wrap JSON in ``` blocks.
- Never explain outside JSON.
- Return valid JSON only.

Use step types:

info
analysis
command
verification

For command steps:

- command must contain ONLY the shell command.
- run should be true if it is safe.
- run should be false if dangerous.
- requires_sudo true when needed.

Example:

{
  "reply":"Let's diagnose the issue.",
  "steps":[
    {
      "type":"info",
      "title":"Checking NetworkManager",
      "description":"First we'll verify the service."
    },
    {
      "type":"command",
      "title":"Check status",
      "command":"systemctl status NetworkManager",
      "run":true,
      "requires_sudo":false
    }
  ]
}
"""


class Api:
    def __init__(self):
        self.model = DEFAULT_MODEL
        self.active_process = None
        self.input_queue = queue.Queue()
        self.chat_history = []
        self.chat_file = "chat_history.json"
        self.last_context_report = None
        self.load_chat_history()

    def load_chat_history(self):
        """Load chat history from file."""
        if os.path.exists(self.chat_file):
            try:
                with open(self.chat_file, 'r') as f:
                    self.chat_history = json.load(f)
            except:
                self.chat_history = []
        else:
            self.chat_history = []

    def save_chat_history(self):
        """Save chat history to file."""
        try:
            with open(self.chat_file, 'w') as f:
                json.dump(self.chat_history, f, indent=2)
        except Exception as e:
            print(f"Error saving chat history: {e}")

    def _format_chat_history_context(self, limit=12):
        """Build a compact context block from recent history."""
        entries = self.chat_history[-limit:]
        if not entries:
            return "No prior context."

        lines = []
        for entry in entries:
            role = str(entry.get("role", "unknown")).upper()
            content = entry.get("content", "")
            if isinstance(content, (dict, list)):
                content = json.dumps(content, ensure_ascii=False)
            content = str(content).strip()
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _build_messages(self, message):
        # Build a proper messages list including recent history with correct roles.
        messages = []

        # System prompt first
        messages.append({"role": "system", "content": SYSTEM_PROMPT})

        # Include latest system report as a system message for context
        if self.last_context_report:
            messages.append({"role": "system", "content": f"Latest system report:\n{self.last_context_report}"})

        # Append recent conversation history using appropriate roles
        entries = self.chat_history[-12:]
        for entry in entries:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if role == "agent":
                role = "assistant"
            elif role not in ("user", "assistant", "system"):
                role = "user"
            messages.append({"role": role, "content": content})

        # Finally add the current user message
        messages.append({"role": "user", "content": str(message).strip()})

        return messages

    def add_to_history(self, role, content):
        """Add a message to chat history."""
        self.chat_history.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content
        })
        self.save_chat_history()

    def _parse_response(self, content):
        if not content:
            return {
                "reply": "I couldn't generate a response.",
                "steps": []
            }

        cleaned = str(content).strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "reply": cleaned,
                "steps": []
            }

        if isinstance(parsed, dict):
            return {
                "reply": parsed.get("reply", cleaned),
                "steps": parsed.get("steps", []) if isinstance(parsed.get("steps"), list) else []
            }

        return {
            "reply": cleaned,
            "steps": []
        }

    def respond(self, message):
        if not message or not str(message).strip():
            return {
                "reply": "Please enter a message.",
                "steps": []
            }

        self.add_to_history("user", message)
        messages = self._build_messages(message)

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
                    messages=messages,
                    format=JSON_SCHEMA,
                    stream=False
                )
                content = response.get("message", {}).get("content", "") if isinstance(response, dict) else getattr(getattr(response, "message", None), "content", "")
                if content:
                    self.model = model_name
                    parsed = self._parse_response(content)
                    
                    response_data = {
                        "reply": parsed.get("reply", ""),
                        "steps": parsed.get("steps", []) if isinstance(parsed.get("steps"), list) else [],
                        "has_more_steps": False
                    }
                    if response_data["steps"]:
                        response_data["has_more_steps"] = len(response_data["steps"]) > 1
                        response_data["next_step"] = response_data["steps"][0]

                    # Save the raw assistant response content to history (not the parsed wrapper)
                    self.add_to_history("agent", content)
                    return response_data
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            return {
                "reply": f"Model Error",
                "steps": [],
                "error": str(last_error)
            }

        return {
            "reply": "I couldn't generate a response.",
            "steps": []
        }

    def report_command_output(self, command, output, success):
        """Report command output to be used in the next agent call."""
        status = "succeeded" if success else "failed"
        output_text = str(output or "").strip() or "(no output)"
        report = f"Command '{command}' {status}. Output: {output_text}"
        self.last_context_report = report
        self.add_to_history("system", report)
        return {
            "status": "reported",
            "next_prompt": (
                f"Use the latest command result as context and continue troubleshooting. "
                f"Command: {command}\nOutput:\n{output_text}"
            )
        }

    def run_command(self, command, use_sudo=False):
        """
        Execute a shell command and return the output.
        
        Args:
            command: Shell command to run
            use_sudo: Whether to prepend 'sudo' to the command
            
        Returns:
            Dictionary with 'success', 'output', and 'error' keys
        """
        try:
            if use_sudo:
                command = f"sudo {command}"
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Command timed out after 30 seconds",
                "return_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "return_code": -1
            }

    def submit_command_input(self, input_text):
        """
        Submit input to an interactive command.
        
        Args:
            input_text: The input to send to the running process
        """
        try:
            self.input_queue.put(input_text)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    
api = Api()


def main():
    webview.create_window(
        title="Penguin",
        url="templates/index.html",
        width=1980,
        height=1080,
        js_api=api
    )
    webview.start()


if __name__ == "__main__":
    main()