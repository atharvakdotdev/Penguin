from ollama import chat

MODEL = "orieg/gemma3-tools:4b-ft "  # Change to your preferred model

response = chat(
    model=MODEL,
    messages=[
        {
            "role": "system",
            "content": "You are a Linux troubleshooting assistant."
        },
        {
            "role": "user",
            "content": "How do I list running services?"
        }
    ]
)

# print(response["message"]["content"])