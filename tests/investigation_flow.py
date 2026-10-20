import json
import os
import subprocess

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

import states


MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
COMMAND_TIMEOUT = 30


def run_diagnostic_command(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
        )
        return {
            "command": command,
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired as error:
        return {
            "command": command,
            "success": False,
            "output": str(error.stdout or ""),
            "error": f"Command timed out after {COMMAND_TIMEOUT} seconds.",
            "return_code": -1,
        }


def approve_command(description, command):
    print(f"\n{description}:\n{command}")
    return input("Run this command? Type 'yes' to continue: ").strip().lower() == "yes"


def main():
    investigation = states.InvestigationState()
    user_problem = input("Describe the Linux problem to investigate: ").strip()
    if not user_problem:
        print("No problem provided.")
        return

    problem_result = investigation.generateProblemStatement(user_problem, MODEL)
    if not problem_result:
        print("Problem statement generation failed.")
        return

    problem = json.loads(problem_result)
    problem_statement = problem["problem_statement"]
    verification_command = problem.get("verification_command")
    print(f"\nProblem statement:\n{problem_statement}")

    hypotheses = investigation.generateHypothesis(
        user_request=problem_statement,
        model_name=MODEL,
    )
    if not hypotheses:
        print("Hypothesis generation failed.")
        return

    if not verification_command:
        print("No verification command was generated; stopping before remediation.")
        return

    print("\nInitial hypotheses:")
    print(json.dumps(hypotheses, indent=2, ensure_ascii=False))

    planned_tests = []
    command_outputs = []
    facts = []

    for hypothesis in hypotheses.get("hypotheses", []):
        generated = investigation.generateCommandsToTestHypothesis(
            problem_statement=problem_statement,
            hypothesis=hypothesis,
            facts=facts,
            relevant_command_outputs=command_outputs,
            model_name=MODEL,
        )
        if not generated:
            print(f"Could not generate tests for: {hypothesis['hypothesis']}")
            continue

        for test in generated.get("tests", []):
            planned_tests.append((hypothesis, test))

    if planned_tests:
        print("\nDiagnostic commands to review:")
        for index, (hypothesis, test) in enumerate(planned_tests, start=1):
            print(f"{index}. Hypothesis: {hypothesis['hypothesis']}")
            print(f"   Purpose: {test['purpose']}")
            print(f"   Command: {test['command']}")

        approval = input("Run these diagnostic commands? Type 'yes' to continue: ")
        if approval.strip().lower() != "yes":
            print("Stopped before running diagnostic commands.")
            return

        for _, test in planned_tests:
            result = run_diagnostic_command(test["command"])
            result["purpose"] = test["purpose"]
            command_outputs.append(result)
            print(f"\nResult for: {test['command']}")
            print(json.dumps(result, indent=2, ensure_ascii=False))

    facts_result = investigation.generateFacts(
        problem_statement=problem_statement,
        facts=facts,
        command_outputs=command_outputs,
        model_name=MODEL,
    )
    if not facts_result:
        print("Fact generation failed.")
        return

    facts = facts_result.get("facts", [])
    print("\nObserved facts:")
    print(json.dumps(facts_result, indent=2, ensure_ascii=False))

    updated_hypotheses = investigation.generateHypothesis(
        user_request=problem_statement,
        model_name=MODEL,
        facts=facts,
        command_outputs=command_outputs,
    )
    print("\nUpdated hypotheses:")
    print(json.dumps(updated_hypotheses, indent=2, ensure_ascii=False))

    if not updated_hypotheses:
        print("Hypothesis update failed.")
        return

    confirmed_hypotheses = [
        hypothesis
        for hypothesis in updated_hypotheses.get("hypotheses", [])
        if hypothesis.get("result") == "confirmed"
        and hypothesis.get("confidence", 0) >= 0.7
    ]
    if not confirmed_hypotheses:
        print("No confirmed hypothesis is ready for remediation.")
        return

    hypothesis = max(confirmed_hypotheses, key=lambda item: item["confidence"])
    solution = investigation.generateSolution(
        problem_statement=problem_statement,
        hypothesis=hypothesis,
        facts=facts,
        relevant_command_outputs=command_outputs,
        model_name=MODEL,
    )
    if not solution or not isinstance(solution.get("step"), dict):
        print("Solution generation failed.")
        return

    solve_command = solution["step"].get("command")
    if not solve_command:
        print("The solver did not provide a command.")
        return

    if not approve_command("Proposed remediation", solve_command):
        print("Stopped before running the remediation command.")
        return

    solve_output = run_diagnostic_command(solve_command)
    print("\nRemediation result:")
    print(json.dumps(solve_output, indent=2, ensure_ascii=False))

    if not approve_command("Verification command", verification_command):
        print("Stopped before running the verification command.")
        return

    verification_output = run_diagnostic_command(verification_command)
    print("\nVerification result:")
    print(json.dumps(verification_output, indent=2, ensure_ascii=False))

    analysis = investigation.AnalyseResult(
        model_name=MODEL,
        solve_command=solve_command,
        solve_output=solve_output,
        verification_command=verification_command,
        verification_output=verification_output,
        problem_statement=problem_statement,
        hypothesis=hypothesis,
    )
    print("\nInvestigation analysis:")
    print(json.dumps(analysis, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()