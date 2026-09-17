import sys
import subprocess

from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import states
global facts, hpy,command_outputs

def execute_command(command):
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True
    )

    return {
        "command": command,
        "output": result.stdout.strip(),
        "error": result.stderr.strip(),
        "return_code": result.returncode
    }

userinput= "I tried created a custom Linux command called qwe using the chmod method. I created the script in ~/.local/bin/qwe and made it executable with chmod +x. However, when I run qwe in the terminal, I get command not found."
investigation = states.InvestigationState()

ps = investigation.generateProblemStatement(
    user_request=userinput,
    model_name="qwen2.5-coder:3b"
)
facts = []

def dignosisloop():
    global facts
    hpy= investigation.generateHypothesis(user_request=ps,model_name="qwen2.5-coder:3b")
    i = input()
    investigation.decideOnUerMsg(user_msg=i,model_name="qwen2.5-coder:3b",hypothesis=hpy)
    
    command_outputs = []

    for hypothesis in hpy["hypotheses"]:
        tests = investigation.generateCommandsToTestHypothesis(
            problem_statement=ps,
            hypothesis=hypothesis,
            model_name="qwen2.5-coder:3b"
        )

        # input("Press Enter to execute the tests...")

        for test in tests["tests"]:
            result = execute_command(test["command"])
            command_outputs.append(result)

    # Only runs after ALL commands from ALL hypotheses have finished
    facts = investigation.generateFacts(
        problem_statement=ps,
        facts = facts,
        command_outputs=command_outputs,
        model_name="qwen2.5-coder:3b"
    )

    hpy = investigation.generateHypothesis(user_request=ps,model_name="qwen2.5-coder:3b",facts=facts,command_outputs=command_outputs)

    SOLVER_THRESHOLD = 0.9
    for hypothesis in hpy["hypotheses"]:
        if hypothesis["confidence"] >= SOLVER_THRESHOLD:
            solverloop(command_outputs=command_outputs, facts=facts,hypothesis=hypothesis)
        else:
            dignosisloop()  # Re-run the diagnosis loop if no hypothesis meets the threshold

def solverloop(command_outputs,facts,hypothesis):
    solution = investigation.generateSolution(
        problem_statement=ps,
        facts=facts,
        model_name="qwen3:4b",
        relevant_command_outputs=command_outputs,hypothesis=hypothesis
    )

    input("Press Enter to execute the tests...")

    result = execute_command(solution["step"]["command"])
    if result["return_code"] == 0:
        verification = investigation.verifiRemediation(
        problem_statement=ps,
        facts=facts,
        model_name="qwen3:4b"
        )

        verification_result = execute_command(
            verification["step"]["command"]
        )

        evaluation = investigation.verifiRemediation(
            problem_statement=ps,
            command_output=verification_result,
            model_name="qwen3:4b"
        )
        if not evaluation["solved"]:
            solverloop(command_outputs=result,facts=facts,hypothesis=hypothesis)

    else :
        contradistion_bool= investigation.CheckHypothesisContradiction(
            model_name="qwen3:4b",
            command_outputs=result,
            hypothesis=hypothesis
        )
        if contradistion_bool["contradicts"]:
            dignosisloop()
        else:
            solverloop(command_outputs=result,facts=facts,hypothesis=hypothesis)

dignosisloop()
