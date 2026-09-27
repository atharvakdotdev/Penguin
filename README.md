# 🐧 Penguin

**A local AI-powered Linux troubleshooting agent that investigates system problems, diagnoses their root cause, and helps resolve them.**

Penguin is an experimental Linux troubleshooting agent built around **local AI**. Instead of repeatedly copying terminal output into an LLM and waiting for the next command, Penguin is designed to investigate a problem systematically and manage the troubleshooting process itself.

> **Status: Beta**

## Why Penguin?

When troubleshooting Linux with an LLM, the process can become a repetitive loop:

**Describe the problem → run a command → copy the output → send it back → repeat**

There is also a privacy consideration when system information and command output are sent to remote AI services.

Penguin explores an alternative approach: **run the AI locally and give it a structured troubleshooting system.**

## How it works

Penguin combines a local language model with a diagnostic harness that manages the investigation.

The investigation is divided into stages:

```text
                    USER PROBLEM
                         │
                         ▼
                 Problem Statement
                         │
                         ▼
                  Generate Hypotheses
                         │
                         ▼
                 Test ALL Hypotheses
                         │
                         ▼
                     Generate Facts
                         │
                         ▼
                  Update Hypotheses
                         │
              ┌──────────┴──────────┐
              │                     │
       already_resolved       highest-confidence
              │                hypothesis
              ▼                     │
        Issue Resolved              ▼
                              Solve / Remediation
                                    │
                          ┌─────────┴─────────┐
                          │                   │
                    command succeeds    command fails
                          │                   │
                          ▼                   ▼
                    Verification      Check Contradiction
                          │                   │
                    ┌─────┴─────┐       ┌────┴─────┐
                    │           │       │          │
                  solved      failed  contradicted  valid
                    │           │       │          │
                    ▼           ▼       ▼          ▼
              Issue Resolved   Solve  Update      Solve
```

The harness controls the investigation flow while the local model is used for understanding the problem, reasoning about possible causes, interpreting results, and generating solutions.

This separation also makes it possible to extend the system with additional diagnostic logic in the future.

## Local AI

Penguin currently uses **Qwen2.5-Coder:3B** through Ollama.

I tested different local models against the requirements of the project and found Qwen2.5-Coder:3B to be a suitable balance for my current hardware and use case.

The goal isn't simply to run an LLM locally. The challenge is getting a relatively small local model to perform useful troubleshooting while working within limited hardware resources.

## RAG

A major limitation of smaller local models is their knowledge.

To address this, I'm developing a **Retrieval-Augmented Generation (RAG)** system that can provide the model with relevant Linux troubleshooting knowledge when needed.

The RAG system is **not included in the current beta workflow**. It is still being developed and evaluated separately.

## Current Beta

The current beta focuses on the core investigation architecture:

* Local LLM inference
* Structured troubleshooting workflow
* Problem understanding
* Fact gathering
* Hypothesis generation
* Hypothesis testing
* Diagnosis
* Solution generation
* Verification
* Command execution
* Session management

Penguin is still an experimental project and does not aim to solve every Linux problem yet.

## Requirements

* Linux
* Python 3.14.4
* [Ollama](https://ollama.com/)
* Model: ``` qwen2.5-coder:3b ```
* Sufficient system resources to run the above model

## Running Penguin

Clone the repository:

```bash
git clone https://github.com/atharvakdotdev/Penguin.git
cd Penguin
```

Create and activate a virtual environment:

```bash
python3 -m venv env
source env/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```
Install qwen2.5-coder:3b

```bash
ollama run qwen2.5-coder:3b 
```
Make sure Ollama is running and the required above is available.

Then start Penguin:

```bash
python3 app.py
```

## Project Architecture

At a high level, Penguin consists of three main parts:

### 1. AI Model

The local language model handles natural-language understanding and reasoning.

### 2. Diagnostic Harness

The harness manages the investigation state and determines which stage of troubleshooting should happen next.

### 3. Execution & Verification

Penguin can execute diagnostic commands, interpret their results, update hypotheses, and verify whether the problem has been resolved.

This architecture is intended to reduce the amount of responsibility placed directly on the language model and provide a more predictable troubleshooting process.

## Limitations

Penguin is currently a **beta/experimental project**.

The local model can make incorrect assumptions, generate incorrect commands, or fail to diagnose certain problems. Command execution can also have consequences on the system.

For this reason, Penguin should not be treated as an authoritative source for system administration.

## Why "Penguin"?

Because apparently every Linux project needs a penguin.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
