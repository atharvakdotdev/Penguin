class AI:
    def __init__(self):
        pass
    def respond(self,prompt, json_scheme, system_prompt):
        pass
        
userInput="x doesn't Work"

def generateProblemStatement(userInput):
    # This function generates a problem statement based on the user input
    sysPrompt= "based on the given user and opitionally a log, generate a ccleane problem statement that is clear and concise, and can be used to generate a solution. The problem statement should be in the form of a question."

    json_scheme = {
        "type": "object",
        "properties": {
            "problem_statement": {
                "type": "string",
                "description": "A clear and concise problem statement in the form of a question."
            }
        }
        }

    problem_statement = AI.respond(userInput, json_scheme=json_scheme, system_prompt=sysPrompt)
    return problem_statement

def generateHypothesis(problem_statement):
    # This function generates a hypothesis based on the problem statement
    sysPrompt= "based on the given problem statement, generate a hypothesis that can be tested. The hypothesis should be in the form of a statement that can be proven or disproven."

    json_scheme = {
        "type": "object",
        "properties": {
            "hypothesis": {
                "type": "object",
                "id":1,
                "description": "A testable hypothesis based on the problem statement."
            }
            # multipal hypothesis are allowed
        }
        }

    hypothesis = AI.respond(problem_statement, json_scheme=json_scheme, system_prompt=sysPrompt)
    return hypothesis
def generateCommandToTestHypothesis(hypothesis):
    # This function generates a command to test the hypothesis
    sysPrompt= "based on the given hypothesis, generate a command that can be used to test the hypothesis. The command should be in the form of a statement that can be executed."

    json_scheme = {
        "type": "object",
        "properties": {
            "command_to_test_hypothesis": {
                "type": "string",
                "description": "A command that can be used to test the hypothesis."
            }
        }
        }

    commands_to_test_hypothesis = []
    for h in hypothesis:
        command_to_test_hypothesis = AI.respond(h, json_scheme=json_scheme, system_prompt=sysPrompt)
        commands_to_test_hypothesis.append(command_to_test_hypothesis)

    return commands_to_test_hypothesis

def generateFacts(command_output):
    # This function generates facts based on the command to test the hypothesis
    sysPrompt= "based on the given command to test the hypothesis, generate a list of facts. The facts should be in the form of statements that can be proven or disproven."

    json_scheme = {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "A list of facts that can be used to support or refute the hypothesis."
            }
        }
        }

    facts = AI.respond(command_output, json_scheme=json_scheme, system_prompt=sysPrompt)
    return facts

def UpdateHypothesisWithFacts(hypothesis, facts,command_output):
    # This function updates the hypothesis based on the facts
    sysPrompt= "based on the given hypothesis and facts, update the hypothesis to reflect the new information. The updated hypothesis should be in the form of a statement that can be proven or disproven."

    json_scheme = {
        "type": "object",
        "properties": {
            "updated_hypothesis": {
                "type": "string",
                "description": "An updated hypothesis based on the facts."
            }
        }
        }
    # teh AI wwill update the hypotheis irrattatively lookig at eacch one with all the faccts and ommand output. 
    updated_hypothesis = AI.respond({"hypothesis": hypothesis, "facts": facts}, json_scheme=json_scheme, system_prompt=sysPrompt)
    return updated_hypothesis


def generateSolution(updated_hypothesis):
    # This function generates a solution based on the updated hypothesis
    sysPrompt= "based on the given updated hypothesis, generate a solution that can be implemented. The solution should be in the form of a statement that can be executed."

    json_scheme = {
        "type": "object",
        "properties": {
            "solution": {
                "type": "string",
                "description": "A solution that can be implemented based on the updated hypothesis."
            }
        }
        }

    solution = AI.respond(updated_hypothesis, json_scheme=json_scheme, system_prompt=sysPrompt)
    return solution




"""
the ai will generate a problem statement based on the user input.
then the problem statenmt e will be given to the ai to generate a list of hypothesis.
then the hypothesis will be given to the ai to generate a commands to test all recercively hypothesis.
i.e the ai will be given one hypotheis at a time and will generate a command to test that hypothesis.
then the command will be given to the ai to generate a list of facts based on the command
then the facts,command outputs and will be given to the ai to update the hypothesis based on the facts.
updating will be done recursively for each hypothesis and all the facts and command outputs at a time.
the AI will return id and a flag to update hypotheis or a compleate new hypotheis 

if the hypopteis is confiremed then the AI will be aked to generate a command to furthere olve the problem any fail in this tage wil be redirected to the prevous loop of generating hypothesis and testing them 



"""



