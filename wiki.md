# Penguin Project Wiki

## Overview

Penguin is a desktop application for Linux troubleshooting. It combines a Python backend with a web-based UI to let a user ask for help, send the request to an Ollama-hosted model, and receive a structured troubleshooting response that can be rendered in the interface.

The project is intentionally compact. Its main pieces are:

- [app.py](app.py): the Python backend, model integration, and desktop window startup
- [templates/index.html](templates/index.html): the full user interface rendered inside a webview window
- [test.py](test.py): a small standalone script used to test the Ollama chat API directly
- [ref.html](ref.html): a reference HTML file that appears to be a static mockup or design source

This wiki explains how the project works in detail, excluding the virtual environment and Git-related details.

---

## 1. Project Purpose

Penguin is designed to act like an autonomous Linux troubleshooting assistant. In practice, the flow is:

1. The user types a Linux-related problem into the UI.
2. The frontend sends the message to the Python backend through pywebview.
3. The backend prepares a system prompt and sends it, along with the user's message, to an Ollama model.
4. The model returns a structured JSON payload containing:
   - a plain-language reply
   - a list of troubleshooting steps
5. The frontend renders that structured response in the chat area.

The central idea is that the model does not simply answer with free-form text. Instead, it is guided to return a predictable schema so the app can present the result in a consistent, UI-friendly format.

---

## 2. Main Application Entry Point

The main runtime logic lives in [app.py](app.py).

### 2.1 Importing Dependencies

The file begins by importing:

- json: used to work with the structured JSON response schema and parsing
- os: used to read environment variables such as OLLAMA_MODEL
- webview: used to open the desktop window and expose Python objects to the frontend
- chat from ollama: used to send requests to the local Ollama service

### 2.2 Model Configuration

The application defines a default model name:

- DEFAULT_MODEL is read from the OLLAMA_MODEL environment variable if present
- if not present, it falls back to "orieg/gemma3-tools:4b-ft"

This makes the app configurable without editing the source.

### 2.3 App Startup

The app is launched by the main function:

- webview.create_window(...) opens the desktop window
- the window loads the HTML file from templates/index.html
- js_api=api exposes the Python Api class to the frontend
- webview.start() starts the GUI loop

The application runs as a desktop app when executed directly.

---

## 3. Backend Architecture

The backend is centered around a single class called Api.

### 3.1 The Api Class

The Api class is the bridge between the web UI and the Ollama model. Its responsibilities are:

- storing the selected model name
- validating user input
- building the prompt structure
- sending the request to the model
- parsing and normalizing the model output
- returning a data object the UI can display

### 3.2 Initialization

When an Api instance is created, it stores the default model in self.model.

This allows the application to later try the configured model first and then fall back to a hardcoded backup if necessary.

---

## 4. Prompt and Response Schema Design

A key part of the app is the structured contract between the model and the frontend.

### 4.1 JSON Schema Definition

The JSON schema in [app.py](app.py) declares that the model response must be an object with:

- reply: a string
- steps: an array of step objects

Each step object can contain:

- type: one of info, analysis, command, verification
- title: a string
- description: a string
- command: a string
- run: a boolean
- requires_sudo: a boolean

The schema also says that every step must contain at least:

- type
- title

This schema is passed to the Ollama chat call using the format parameter. That tells the model to return JSON that matches that structure.

### 4.2 Why the Schema Matters

This design makes the AI output predictable. Instead of relying on the model to produce arbitrary free text, the app requires a structured output that can be displayed as:

- a summary reply
- a sequence of diagnostic steps
- command suggestions
- verification actions

This is especially useful for troubleshooting because the app can present a staged workflow rather than a single paragraph.

---

## 5. System Prompt Behavior

The system prompt is one of the most important pieces of the application because it shapes the model’s behavior.

### 5.1 Prompt Purpose

The prompt instructs the model to:

- act as Penguin, an autonomous Linux troubleshooting assistant
- answer only Linux-related questions
- always use the provided JSON schema
- never output markdown
- never wrap JSON in code fences
- never explain anything outside valid JSON

### 5.2 Constrained Output Style

The prompt makes the assistant return only machine-readable JSON rather than conversational prose. This is important because the frontend expects a structured object.

### 5.3 Step Types

The model is told to use these step types:

- info: informational step
- analysis: reasoning or diagnosis step
- command: an executable shell command step
- verification: a validation or confirmation step

This gives the app a consistent vocabulary for turning model output into UI cards or action items.

### 5.4 Command Guidance

For command steps, the prompt tells the model to include only the shell command in the command field and to set:

- run=true for safe commands
- run=false for dangerous commands
- requires_sudo=true when elevated privileges are needed

This guidance supports future expansion into a more interactive assistant that might actually execute commands.

---

## 6. Request Handling Flow

When the user submits a message, the backend follows a clear flow.

### 6.1 Input Validation

The respond method first checks whether the message is empty or whitespace-only.

If it is empty, the app returns:

- reply: "Please enter a message."
- steps: []

### 6.2 Building Messages

The backend builds a two-message conversation:

1. A system message containing the system prompt
2. A user message containing the actual question

This is the standard pattern for instructing an LLM to behave in a particular way.

### 6.3 Model Attempt Loop

The code creates a candidate list of model names:

- the configured model from self.model
- a fallback model name

It then tries each model in order, catching errors if one fails.

This is a simple resilience mechanism. If one model name is unavailable, the app can try another.

### 6.4 Chat Call

The actual chat call uses:

- model=model_name
- messages=messages
- format=JSON_SCHEMA
- stream=False

The response is expected to contain a message object with content.

### 6.5 Parsing Output

The content is passed into _parse_response, which attempts to:

- trim the response
- remove code fences if present
- parse the content as JSON
- normalize it into a predictable dictionary with reply and steps

If parsing fails, the app falls back to returning the raw content as the reply with no steps.

### 6.6 Error Handling

If the model request fails, the backend returns a structured error payload:

- reply: "Model Error"
- steps: []
- error: the original exception string

That way, the UI can display a consistent error state.

---

## 7. Frontend Structure

The user interface is implemented in [templates/index.html](templates/index.html).

It is a single-page desktop-style app with three major regions:

- sidebar
- main chat area
- right inspector panel

### 7.1 Layout Regions

#### Sidebar
The sidebar contains:

- a logo-like title area
- a new session action
- navigation items
- system overview stats
- an agent status indicator

Although it is largely static in the current version, it gives the app a desktop-style appearance.

#### Main Chat Area
The main chat area contains:

- a top bar with session info
- a scrollable message feed
- a message input box
- send button
- action buttons such as Attach Log, Select Context, and Stop Agent

This is where the conversation happens.

#### Right Inspector
The right panel contains:

- a model selector display
- a set of “plan / steps” items
- a terminal-style command output section
- a button to open a full terminal view

This is mostly presentational in the current implementation, but it reinforces the troubleshooting workflow theme.

---

## 8. Frontend JavaScript Behavior

The UI logic is written inline in a script block near the bottom of [templates/index.html](templates/index.html).

### 8.1 DOM References

The script grabs handles for:

- the chat input box
- the chat message container
- the send button

These references are used to manage the conversation flow.

### 8.2 Time Formatting

A small helper function formats the current time into a readable label for message timestamps.

### 8.3 Message Rendering

The app contains a helper that appends a message to the chat area.

This function:

- creates a wrapper for the message
- creates a header with the sender label and time
- creates a content container
- inserts the message text into the view

The current implementation has been updated to support either:

- plain string messages
- structured objects containing reply and steps

### 8.4 Sending Messages

The sendMessage function is the core interaction path:

1. Read the current input text
2. Ignore empty input
3. Append the user’s message to the chat feed
4. Disable the input while waiting for the backend
5. Show a temporary “Thinking...” message from the agent
6. Call the Python API method respond(text)
7. Render the returned result in the agent message bubble
8. Re-enable the UI and refocus the input box

### 8.5 Communication with Python

The frontend communicates with the backend through pywebview.

The script checks whether:

- window.pywebview exists
- the api object exists
- the respond method exists

If that API is unavailable, it shows an error message.

This is how the HTML page interacts with the Python object exposed by webview.create_window(..., js_api=api).

---

## 9. Rendering Structured Responses

One of the most important UI behaviors is how the app displays the model’s structured output.

### 9.1 Reply Rendering

If the backend returns an object with a reply field, the frontend displays that text in the agent message bubble.

### 9.2 Step Rendering

If the backend returns steps, the frontend creates a visual list of cards. Each card displays:

- the step title
- a description if available
- a command if the step is a command-type step

This makes the troubleshooting plan more readable than a single plain-text response.

### 9.3 Why This Matters

The UI is not just a chat window. It is designed to present a structured troubleshooting plan, which better matches the app’s purpose.

---

## 10. Static Reference File

The repository also includes [ref.html](ref.html).

This file appears to be a reference or mockup version of the UI. It contains much of the same layout and styling as the live interface, but it is not the active application entry point.

Its likely purpose is one of the following:

- a design reference for the real UI
- a static prototype used during development
- a backup or comparison file for the current implementation

The active app loads [templates/index.html](templates/index.html), not ref.html.

---

## 11. Test Script

The file [test.py](test.py) is a small example script for testing the Ollama API directly.

### 11.1 What It Does

It imports the chat function from the ollama package and then:

- sets a model name
- sends a simple system prompt and user prompt to the model
- prints the model’s reply to the terminal

### 11.2 Role in the Project

This file is useful for quickly verifying that:

- Ollama is installed and reachable
- the configured model is available
- the chat API is working before launching the full GUI

It is more of a minimal smoke test than a formal test suite.

---

## 12. Data Flow Summary

A complete request looks like this:

1. The user types a prompt in the UI.
2. The frontend calls the Python API method respond(text).
3. The backend constructs a system prompt and user message.
4. The backend sends the request to Ollama.
5. The model returns JSON matching the required schema.
6. The backend parses that response into a dictionary with reply and steps.
7. The frontend renders the reply and steps in the chat UI.

That is the core loop of the application.

---

## 13. Current Implementation Notes

### 13.1 Strengths

- clear separation between backend and UI
- structured model output for better usability
- desktop app experience through pywebview
- simple and understandable code layout

### 13.2 Current Limitations

- the UI is mostly presentational and not yet fully dynamic for every step type
- the right-side inspector panel is mostly static content
- command steps are displayed visually but are not executed automatically
- there is no formal test framework or automated test suite yet

### 13.3 Likely Extension Points

Future improvements could include:

- executing safe commands from command steps
- showing real terminal output in the inspector panel
- supporting more detailed step states like pending, running, done, or failed
- adding persistent conversation history
- adding more robust validation for model output

---

## 14. How to Understand the Project Quickly

If you want to understand the project fast, read the files in this order:

1. [app.py](app.py): the backend logic and model contract
2. [templates/index.html](templates/index.html): the UI and how it talks to Python
3. [test.py](test.py): a simple API check
4. [ref.html](ref.html): optional design reference

That sequence gives you the best mental model of how the project works.

---

## 15. Practical Mental Model

A good way to think about Penguin is:

- Python provides the intelligence and API bridge
- HTML/CSS/JavaScript provides the desktop-like interface
- Ollama supplies the language model
- the model is constrained to output troubleshooting steps in a structured JSON form
- the UI turns that structure into a readable troubleshooting experience

In short, Penguin is a small but focused desktop assistant for Linux help, built around a structured AI response pipeline.
