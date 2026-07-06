"""API layer for the Penguin troubleshooting agent."""

import json
import os
import queue
import subprocess

from ollama import chat

from schemas import JSON_SCHEMA
from states import DEFAULT_STATE, STATE_PROMPTS,SYSTEM_PROMPT

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b").strip()


class Api:
    def __init__(self):
        # Selected model identifier (may be switched to a working fallback)
        self.model = DEFAULT_MODEL
        self.state = DEFAULT_STATE
        self.chat_history = [
            
        ]
        # If a command is executed interactively, this may hold the process
        self.active_process = None

        # Queue for providing input to interactive commands (not commonly used)
        self.input_queue = queue.Queue()

    def build_messages(self, message):
        """Build the messages payload for the model without prior history."""
        messages = []
        messages.append({"role": "system", "content": STATE_PROMPTS[self.state]})
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
        messages.append({"role": "user", "content": str(message).strip()})
        return messages

    def clean_history(self, history):
        cleaned = []

        for msg in history:
            if msg.get("role") != "system":
                cleaned.append(msg)

        return cleaned
    def parse_response(self, content):
        if not content:
            return {
                "reply": "I couldn't generate a response.",
                "steps": [],
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
                "steps": [],
            }

        if isinstance(parsed, dict):
            # Update agent state if present
            state = parsed.get("status")
            if state in STATE_PROMPTS:
                self.state = state

            return {
                "reply": parsed.get("reply", cleaned),
                "status": state,
                "steps": (
                    parsed.get("steps", [])
                    if isinstance(parsed.get("steps"), list)
                    else []
                ),
            }

        return {
            "reply": cleaned,
            "steps": [],
        }


    def respond(self, message):
        # Entry point: validate input and build messages
        if not message or not str(message).strip():
            return {"reply": "Please enter a message.", "steps": []}
        print(self.state)
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
                    self.chat_history.append({
                        "role": "assistant",
                        "content": content,
                    })

                    self.model = model_name

                    parsed = self.parse_response(content)

                    response_data = {
                        "reply": parsed.get("reply", ""),
                        "steps": parsed.get("steps", [])
                        if isinstance(parsed.get("steps"), list)
                        else [],
                        "has_more_steps": False,
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
        """Report command output to be used in the next agent call."""

        status = "succeeded" if success else "failed"
        output_text = str(output or "").strip() or "(no output)"
        print(output_text)
        next_prompt = f"""
    The requested command has finished.

    Status: {status}

    Command:
    {command}

    Output:
    {output_text}
    Do NOT repeat this command unless the result has changed.

    Choose the next diagnostic step based on the above output.
    Continue troubleshooting based on this result. If the issue is solved, return the finished status. Otherwise, provide the next diagnostic step.
    """
        


        return {
            "status": "reported",
            "next_prompt": next_prompt,
            "command_status": status,
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
                timeout=30,
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Command timed out after 30 seconds",
                "return_code": -1,
            }
        except Exception as e:
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
