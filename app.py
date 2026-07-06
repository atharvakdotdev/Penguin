"""
Penguin Linux troubleshooting agent.

This module provides a simple wrapper (`Api`) around an LLM chat
client (ollama.chat) to perform stepwise troubleshooting on a Linux
host. The agent builds message context, parses JSON-formatted
responses from the model, and can execute safe shell commands when
instructed.

The comments in this file explain the purpose of each function and
key implementation details to help future maintenance.
"""

import json
import os
import subprocess
import threading
import queue
import webview
from ollama import chat

# Default model identifier. Can be overridden by setting the
# `OLLAMA_MODEL` environment variable before launching the app.
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b").strip()

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

# SYSTEM_PROMPT is sent as the model's system instruction. It guides the
# agent's behavior and output format. Because the prompt is intentionally
# strict (expects JSON-only replies), it can make the model appear
# repetitive; adjust it if you want more flexible natural-language
# responses.
SYSTEM_PROMPT = """
You are Penguin, an autonomous Linux troubleshooting agent.

Your job is to diagnose Linux issues by gathering information one step at a time.

If you don't have enough information, request or execute another diagnostic command.

Always continue troubleshooting until:
1. The issue is solved.
2. User input is required.
3. The problem is impossible to continue without physical access.

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
        # Selected model identifier (may be switched to a working fallback)
        self.model = DEFAULT_MODEL
        self.chat_history = [
                            {
                                "role": "system",
                                "content": SYSTEM_PROMPT
                            }
                        ]
        # If a command is executed interactively, this may hold the process
        self.active_process = None

        # Queue for providing input to interactive commands (not commonly used)
        self.input_queue = queue.Queue()

    def _build_messages(self, message):
        """Build the messages payload for the model without prior history."""
        messages = []
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
        messages.append({"role": "user", "content": str(message).strip()})
        return messages
    def clean_history(self, history):
        for i, item in enumerate(history):
            if isinstance(item, list):
                history[i] = [
                    msg
                    for msg in item
                    if msg.get("role") != "system"
                ]
        return history
    def _parse_response(self, content):
        # Parse the model's textual output into the structured agent
        # response. The model is expected to return JSON, but we handle
        # cases where the model returns plain text or wraps output in
        # markdown code fences.
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

        # Try to load JSON. If parsing fails, fall back to returning the
        # raw text as the reply.
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
        # Entry point: validate input and build messages
        if not message or not str(message).strip():
            return {"reply": "Please enter a message.", "steps": []}

        self.chat_history.append({
            "role": "user",
            "content": str(message).strip()
        })
        # Try the configured model first, then a small set of fallbacks

        candidate_models = []
        if self.model:
            candidate_models.append(self.model)
        for fallback in ["gemma3:1b"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_error = None
        for model_name in candidate_models:
            try:
                # Call the ollama chat client. We expect a dict-like response
                # with the assistant message text under response['message']['content'].
                response = chat(
                    model=model_name,
                    messages=self.chat_history,
                    format=JSON_SCHEMA,
                    stream=False
                )

                # Extract the text content in a defensive manner to support
                # different client return shapes.
                content = (
                    response.get("message", {}).get("content", "")
                    if isinstance(response, dict)
                    else getattr(getattr(response, "message", None), "content", "")
                )

                if content:
                    # Save the assistant response to the conversation history
                    self.chat_history.append({
                        "role": "assistant",
                        "content": content
                    })

                    # Promote the working model
                    self.model = model_name

                    # Parse the JSON for your UI
                    parsed = self._parse_response(content)

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
                # Record the last exception to surface if all models fail
                last_error = exc

        # If we exhausted the model list, return a helpful error payload
        if last_error is not None:
            return {"reply": f"Model Error", "steps": [], "error": str(last_error)}

        return {"reply": "I couldn't generate a response.", "steps": []}

    def report_command_output(self, command, output, success):
        """Report command output to be used in the next agent call."""
        status = "succeeded" if success else "failed"
        output_text = str(output or "").strip() or "(no output)"
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

            # Run the command in a short timeout to avoid stalling the UI.
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
            return {"success": False, "output": "", "error": "Command timed out after 30 seconds", "return_code": -1}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e), "return_code": -1}

    def submit_command_input(self, input_text):
        """
        Submit input to an interactive command.
        
        Args:
            input_text: The input to send to the running process
        """
        try:
            # Put user input into the queue for any interactive
            # processes that may be listening. This is rarely used but
            # keeps the API generic.
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