# import sys
# import subprocess

# from pathlib import Path

# sys.path.append(str(Path(__file__).parent.parent))

# import states
# global facts, hpy,command_outputs

# def execute_command(command):
#     result = subprocess.run(
#         command,
#         shell=True,
#         capture_output=True,
#         text=True
#     )

#     return {
#         "command": command,
#         "output": result.stdout.strip(),
#         "error": result.stderr.strip(),
#         "return_code": result.returncode
#     }

# userinput= "I tried created a custom Linux command called qwe using the chmod method. I created the script in ~/.local/bin/qwe and made it executable with chmod +x. However, when I run qwe in the terminal, I get command not found."
# investigation = states.InvestigationState()

# ps = investigation.generateProblemStatement(
#     user_request=userinput,
#     model_name="qwen2.5-coder:3b"
# )
# facts = []

# def dignosisloop():
#     global facts
#     hpy= investigation.generateHypothesis(user_request=ps,model_name="qwen2.5-coder:3b")
#     i = input()
#     investigation.decideOnUerMsg(user_msg=i,model_name="qwen2.5-coder:3b",hypothesis=hpy)
    
#     command_outputs = []

#     for hypothesis in hpy["hypotheses"]:
#         tests = investigation.generateCommandsToTestHypothesis(
#             problem_statement=ps,
#             hypothesis=hypothesis,
#             model_name="qwen2.5-coder:3b"
#         )

#         # input("Press Enter to execute the tests...")

#         for test in tests["tests"]:
#             result = execute_command(test["command"])
#             command_outputs.append(result)

#     # Only runs after ALL commands from ALL hypotheses have finished
#     facts = investigation.generateFacts(
#         problem_statement=ps,
#         facts = facts,
#         command_outputs=command_outputs,
#         model_name="qwen2.5-coder:3b"
#     )

#     hpy = investigation.generateHypothesis(user_request=ps,model_name="qwen2.5-coder:3b",facts=facts,command_outputs=command_outputs)

#     SOLVER_THRESHOLD = 0.9
#     for hypothesis in hpy["hypotheses"]:
#         if hypothesis["confidence"] >= SOLVER_THRESHOLD:
#             solverloop(command_outputs=command_outputs, facts=facts,hypothesis=hypothesis)
#         else:
#             dignosisloop()  # Re-run the diagnosis loop if no hypothesis meets the threshold

# def solverloop(command_outputs,facts,hypothesis):
#     solution = investigation.generateSolution(
#         problem_statement=ps,
#         facts=facts,
#         model_name="qwen3:4b",
#         relevant_command_outputs=command_outputs,hypothesis=hypothesis
#     )

#     input("Press Enter to execute the tests...")

#     result = execute_command(solution["step"]["command"])
#     if result["return_code"] == 0:
#         verification = investigation.verifiRemediation(
#         problem_statement=ps,
#         facts=facts,
#         model_name="qwen3:4b"
#         )

#         verification_result = execute_command(
#             verification["step"]["command"]
#         )

#         evaluation = investigation.verifiRemediation(
#             problem_statement=ps,
#             command_output=verification_result,
#             model_name="qwen3:4b"
#         )
#         if not evaluation["solved"]:
#             solverloop(command_outputs=result,facts=facts,hypothesis=hypothesis)

#     else :
#         contradistion_bool= investigation.CheckHypothesisContradiction(
#             model_name="qwen3:4b",
#             command_outputs=result,
#             hypothesis=hypothesis
#         )
#         if contradistion_bool["contradicts"]:
#             dignosisloop()
#         else:
#             solverloop(command_outputs=result,facts=facts,hypothesis=hypothesis)

# dignosisloop()
import sys
import subprocess
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import states

MODEL = "qwen2.5-coder:3b"
SOLVER_MODEL = "qwen2.5-coder:3b"
SOLVER_THRESHOLD = 0.9
MAX_ITERATIONS = 15
COMMAND_TIMEOUT = 30

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

investigation = states.InvestigationState()


# ---------------------------------------------------------------------------
# Persistent shell
# ---------------------------------------------------------------------------

class PersistentShell:
    """Keeps a single bash process alive across the whole investigation,
    so state changes (exports, cd, source ~/.bashrc, etc.) persist between
    commands — like a real interactive terminal session, instead of a fresh
    subprocess per command."""

    def __init__(self, shell="/bin/bash"):
        self.proc = subprocess.Popen(
            [shell],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merge stderr into stdout stream
            text=True,
            bufsize=1,
        )
        self._lock = threading.Lock()

    def run(self, command, timeout=COMMAND_TIMEOUT):
        with self._lock:
            marker = uuid.uuid4().hex
            end_prefix = f"__END_{marker}_"
            full_cmd = f"{{ {command}\n}} 2>&1; echo {end_prefix}$?__\n"

            try:
                self.proc.stdin.write(full_cmd)
                self.proc.stdin.flush()
            except (BrokenPipeError, ValueError):
                return {
                    "command": command,
                    "output": "",
                    "error": "shell process is no longer alive",
                    "return_code": -1,
                }

            lines = []
            return_code = None
            result_holder = {}

            def reader():
                while True:
                    line = self.proc.stdout.readline()
                    if not line:
                        break
                    if line.startswith(end_prefix):
                        try:
                            result_holder["rc"] = int(
                                line.strip()[len(end_prefix):].rstrip("_")
                            )
                        except ValueError:
                            result_holder["rc"] = -1
                        break
                    lines.append(line)

            t = threading.Thread(target=reader, daemon=True)
            t.start()
            t.join(timeout=timeout)

            if t.is_alive():
                # Command hung. We can't safely kill just the command inside
                # a persistent shell, so restart the whole shell to recover.
                self._restart()
                return {
                    "command": command,
                    "output": "".join(lines).strip(),
                    "error": f"command timed out after {timeout}s; shell was restarted",
                    "return_code": -1,
                }

            return {
                "command": command,
                "output": "".join(lines).strip(),
                "error": "",
                "return_code": result_holder.get("rc", -1),
            }

    def _restart(self):
        try:
            self.proc.kill()
        except Exception:
            pass
        self.proc = subprocess.Popen(
            ["/bin/bash"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def close(self):
        try:
            self.proc.stdin.write("exit\n")
            self.proc.stdin.flush()
        except Exception:
            pass
        try:
            self.proc.terminate()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

class CaseLogger:
    """Logs every step of a run_flow() execution to stdout and a JSONL file."""

    def __init__(self, case_name):
        self.case_name = case_name
        self.log_path = LOG_DIR / f"{case_name}.jsonl"
        self._fh = open(self.log_path, "w", encoding="utf-8")

    def _write(self, record):
        record["ts"] = datetime.now(timezone.utc).isoformat()
        self._fh.write(json.dumps(record, default=str) + "\n")
        self._fh.flush()

    def event(self, label, data):
        print(f"\n--- {label} ---")
        try:
            print(json.dumps(data, indent=2, default=str))
        except (TypeError, ValueError):
            print(data)
        print(f"--- end {label} ---\n")
        self._write({"label": label, "data": data})

    def command_result(self, label, command, result):
        out_preview = (result.get("output") or "")[:500]
        err_preview = (result.get("error") or "")[:500]
        print(
            f"[{label}] {command} -> rc={result.get('return_code')} "
            f"out={out_preview!r} err={err_preview!r}"
        )
        self._write({
            "label": label,
            "command": command,
            "result": result,
        })

    def state_transition(self, from_state, to_state):
        print(f"[state] {from_state} -> {to_state}")
        self._write({"label": "state_transition", "from": from_state, "to": to_state})

    def error(self, message):
        print(f"[ERROR] {message}")
        self._write({"label": "error", "message": message})

    def close(self):
        self._fh.close()


# ---------------------------------------------------------------------------
# Flow steps (mirrors the real Api class methods)
# ---------------------------------------------------------------------------

def testHypothesis(hypotheses, problem_statement, logger, shell):
    """Mirrors testHypothesis() in the real Api class."""
    command_outputs = []

    for hypothesis in hypotheses["hypotheses"]:
        test_commands = investigation.generateCommandsToTestHypothesis(
            problem_statement=problem_statement,
            hypothesis=hypothesis,
            model_name=MODEL
        )
        if test_commands is None:
            logger.error(f"generateCommandsToTestHypothesis returned None for hypothesis: {hypothesis}")
            continue

        logger.event("test_commands_generated", {"hypothesis": hypothesis, "tests": test_commands})

        for test in test_commands.get("tests", []):
            result = shell.run(test["command"])
            command_outputs.append(result)
            logger.command_result("test", test["command"], result)

    return command_outputs


def UpdateHypothesis(problem_statement, facts, command_outputs, logger):
    """Mirrors UpdateHypothesis() in the real Api class."""
    hypotheses = investigation.generateHypothesis(
        user_request=problem_statement,
        model_name=MODEL,
        facts=facts,
        command_outputs=command_outputs
    )
    logger.event("hypotheses_updated", hypotheses)
    return hypotheses


def solver(problem_statement, facts, command_outputs, hypothesis, logger, shell):
    """Mirrors solver() in the real Api class."""
    solution = investigation.generateSolution(
        problem_statement=problem_statement,
        facts=facts,
        model_name=SOLVER_MODEL,
        relevant_command_outputs=command_outputs,
        hypothesis=hypothesis
    )
    if solution is None:
        logger.error("generateSolution returned None")
        return None, None

    logger.event("solution_generated", solution)

    step = solution.get("step")
    result = shell.run(step["command"])
    logger.command_result("solve", step["command"], result)
    return solution, result


def verificationloop(problem_statement, command_outputs, logger, shell):
    """Mirrors verificationloop() in the real Api class."""
    verification = investigation.verifiRemediation(
        problem_statement=problem_statement,
        model_name=SOLVER_MODEL,
        command_outputs=command_outputs,
    )
    if verification is None:
        logger.error("verifiRemediation returned None")
        return None

    logger.event("verification_step_generated", verification)

    step = verification.get("step")
    verification_result = shell.run(step["command"])
    logger.command_result("verify-cmd", step["command"], verification_result)

    evaluation = investigation.verifi(
        problem_statement=problem_statement,
        model_name=SOLVER_MODEL,
        command_outputs=verification_result,
    )
    logger.event("verification_evaluation", evaluation)
    return evaluation


def contradictionloop(hypothesis, result, logger):
    """Mirrors contradictionloop() in the real Api class."""
    contradiction = investigation.CheckHypothesisContradiction(
        model_name=SOLVER_MODEL,
        command_outputs=result,
        hypothesis=hypothesis
    )
    logger.event("contradiction_check", contradiction)
    return contradiction


# ---------------------------------------------------------------------------
# Main state machine loop
# ---------------------------------------------------------------------------

def run_flow(user_input, case_name="adhoc", max_iterations=MAX_ITERATIONS):
    logger = CaseLogger(case_name)
    shell = PersistentShell()
    try:
        print("[state] ProblemStatement")
        problem_statement_raw = investigation.generateProblemStatement(
            user_request=user_input,
            model_name=MODEL
        )
        if problem_statement_raw is None:
            logger.error("generateProblemStatement returned None")
            return {"status": "failed", "reason": "no_problem_statement"}

        problem_statement = json.loads(problem_statement_raw)
        logger.event("problem_statement", problem_statement)

        facts = []
        state = "Hypothesis"
        hypothesis = None
        hypotheses = None
        command_outputs = []
        iteration = 0

        while True:
            iteration += 1
            if iteration > max_iterations:
                logger.error(f"Exceeded {max_iterations} iterations without resolution.")
                return {"status": "aborted", "reason": "max_iterations", "iterations": iteration}

            print(f"\n[state] {state} (iteration {iteration})")

            if state == "Hypothesis":
                hypotheses = investigation.generateHypothesis(
                    user_request=problem_statement,
                    model_name=MODEL
                )
                if hypotheses is None:
                    logger.error("generateHypothesis returned None")
                    return {"status": "failed", "reason": "no_hypotheses"}
                logger.event("hypotheses_generated", hypotheses)
                next_state = "TestingHypothesis"
                logger.state_transition(state, next_state)
                state = next_state

            elif state == "TestingHypothesis":
                command_outputs = testHypothesis(hypotheses, problem_statement, logger, shell)
                next_state = "Facts"
                logger.state_transition(state, next_state)
                state = next_state

            elif state == "Facts":
                facts = investigation.generateFacts(
                    problem_statement=problem_statement,
                    facts=facts,
                    command_outputs=command_outputs,
                    model_name=MODEL
                )
                if facts is None:
                    logger.error("generateFacts returned None")
                    return {"status": "failed", "reason": "no_facts"}
                logger.event("facts_generated", facts)
                next_state = "HypothesisUpdate"
                logger.state_transition(state, next_state)
                state = next_state

            elif state == "HypothesisUpdate":
                hypotheses = UpdateHypothesis(problem_statement, facts, command_outputs, logger)
                if hypotheses is None:
                    return {"status": "failed", "reason": "no_updated_hypotheses"}

                next_state = None
                for h in hypotheses["hypotheses"]:
                    if h["result"] == "already_resolved":
                        next_state = "IssueResolved"
                        break
                    elif h["result"] == "confirmed" and h["confidence"] >= SOLVER_THRESHOLD:
                        hypothesis = h
                        next_state = "Solve"
                        break
                next_state = next_state or "Hypothesis"
                logger.state_transition(state, next_state)
                state = next_state

            elif state == "Solve":
                solution, result = solver(problem_statement, facts, command_outputs, hypothesis, logger, shell)
                if solution is None:
                    return {"status": "failed", "reason": "no_solution"}
                next_state = "Verification" if result["return_code"] == 0 else "CheckHypothesisContradiction"
                logger.state_transition(state, next_state)
                state = next_state

            elif state == "Verification":
                evaluation = verificationloop(problem_statement, command_outputs, logger, shell)
                if evaluation is None:
                    return {"status": "failed", "reason": "no_evaluation"}
                next_state = "IssueResolved" if evaluation.get("solved") is True else "Solve"
                logger.state_transition(state, next_state)
                state = next_state

            elif state == "CheckHypothesisContradiction":
                contradiction = contradictionloop(hypothesis, command_outputs, logger)
                if contradiction is None:
                    return {"status": "failed", "reason": "no_contradiction_result"}
                next_state = "HypothesisUpdate" if contradiction["contradicts"] else "Solve"
                logger.state_transition(state, next_state)
                state = next_state

            elif state == "IssueResolved":
                print("\n[RESOLVED] Issue has been resolved and verified.")
                logger.event("resolved", {"iterations": iteration})
                return {"status": "resolved", "iterations": iteration}

            else:
                logger.error(f"Unknown state: {state}")
                return {"status": "failed", "reason": f"unknown_state:{state}"}

    finally:
        shell.close()
        logger.close()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

TEST_CASES = [
    {
        "name": "custom_command_not_found",
        "user_input": (
            "I tried created a custom Linux command called qwe using the chmod "
            "method. I created the script in ~/.local/bin/qwe and made it "
            "executable with chmod +x. However, when I run qwe in the terminal, "
            "I get command not found."
        ),
    },
    {
        "name": "permission_denied_script",
        "user_input": (
            "I wrote a bash script called deploy.sh in my project folder and "
            "tried to run it with ./deploy.sh, but I get "
            "'Permission denied'. I haven't changed any permissions on it."
        ),
    },
    {
        "name": "python_module_not_found",
        "user_input": (
            "My Python script fails with 'ModuleNotFoundError: No module "
            "named requests' even though I installed it using pip install "
            "requests yesterday and it worked fine before."
        ),
    },
    {
        "name": "port_already_in_use",
        "user_input": (
            "I'm trying to start my Flask app with 'python app.py' but I get "
            "'OSError: [Errno 98] Address already in use' on port 5000. "
            "I didn't intentionally start anything else on that port."
        ),
    },
    {
        "name": "git_push_rejected",
        "user_input": (
            "When I run 'git push origin main' I get an error saying "
            "'Updates were rejected because the remote contains work that "
            "you do not have locally.' I made a small change and just want "
            "to push it."
        ),
    },
    {
        "name": "docker_container_exits_immediately",
        "user_input": (
            "I built a Docker image and ran it with 'docker run myapp', but "
            "the container exits immediately with code 1 and I don't see "
            "any clear error message in the logs."
        ),
    },
    {
        "name": "nginx_502_bad_gateway",
        "user_input": (
            "My website is showing a 502 Bad Gateway error after I restarted "
            "the server. Nginx is running but something seems wrong with the "
            "backend connection."
        ),
    },
    {
        "name": "disk_space_full",
        "user_input": (
            "My application suddenly stopped writing log files and I'm "
            "seeing 'No space left on device' errors, but I checked and my "
            "project folder isn't that big."
        ),
    },
    {
        "name": "ssh_connection_refused",
        "user_input": (
            "I can't SSH into my remote server anymore. I get "
            "'Connection refused' even though it worked yesterday and I "
            "haven't changed my SSH config."
        ),
    },
    {
        "name": "env_variable_not_loading",
        "user_input": (
            "I set an environment variable in my .env file called API_KEY, "
            "but when my Node.js app runs, process.env.API_KEY is undefined."
        ),
    },
]


def run_all_test_cases(case_filter=None):
    results = []
    cases = TEST_CASES
    if case_filter:
        cases = [c for c in TEST_CASES if c["name"] == case_filter]
        if not cases:
            print(f"No test case named '{case_filter}' found.")
            return []

    for case in cases:
        print(f"\n{'=' * 80}")
        print(f"RUNNING TEST CASE: {case['name']}")
        print(f"Log file: {LOG_DIR / (case['name'] + '.jsonl')}")
        print(f"{'=' * 80}")
        try:
            outcome = run_flow(case["user_input"], case_name=case["name"])
            results.append({"name": case["name"], **outcome})
        except Exception as e:
            print(f"[ERROR] Test case '{case['name']}' raised an exception: {e}")
            results.append({"name": case["name"], "status": "exception", "error": str(e)})

    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    for r in results:
        extra = f" ({r.get('reason') or r.get('error')})" if r.get("reason") or r.get("error") else ""
        iters = f" iterations={r['iterations']}" if "iterations" in r else ""
        print(f"{r['name']}: {r['status']}{iters}{extra}")

    summary_path = LOG_DIR / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull summary written to {summary_path}")

    return results


if __name__ == "__main__":
    # Run a single case: python test_flow.py <case_name>
    # Run all cases:     python test_flow.py
    case_filter = sys.argv[1] if len(sys.argv) > 1 else None
    run_all_test_cases(case_filter)