import os
import webview
from ollama import chat

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "orieg/gemma3-tools:4b-ft").strip()


class Api:
    def __init__(self):
        self.model = DEFAULT_MODEL

    def respond(self, message):
        if not message or not str(message).strip():
            return "Please enter a message."

        messages = [
            {
                "role": "system",
                "content": "You are a Linux troubleshooting assistant. Give concise, practical help."
            },
            {
                "role": "user",
                "content": str(message).strip()
            }
        ]

        candidate_models = []
        if self.model:
            candidate_models.append(self.model)
        for fallback in ["orieg/gemma3-tools:4b-ft"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_error = None
        for model_name in candidate_models:
            try:
                response = chat(model=model_name, messages=messages, stream=False)
                if isinstance(response, dict):
                    content = response.get("message", {}).get("content", "")
                else:
                    content = getattr(getattr(response, "message", None), "content", "")
                if content:
                    self.model = model_name
                    return content.strip()
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            return f"Sorry, I couldn't reach the model: {last_error}"
        return "I couldn't generate a response."


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