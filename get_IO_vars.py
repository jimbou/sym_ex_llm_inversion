import re


PROMPT = """
You are provided with the following complete C program:

{full_c_program}

Within this program, there is a specific piece of code or function referred to as the "difficult code", provided below:

{difficult_c_code}

Additionally, you have information about the symbolic path constraints of the variables:

Pre-condition variables (variables available and relevant before the difficult code executes):
{pre_condition_variables}

Post-condition variables (variables affected by the difficult code whose values matter after its execution):
{post_condition_variables}

Your task is to analyze the difficult code and identify:

1. Input Variables: Variables whose values must be concretized before the difficult code executes to influence its behavior.

2. Output Variables: Variables whose values are affected or modified by the difficult code and matter after its execution.

You may explain your reasoning step by step.

However, at the end of your response, always include a clearly marked output section in this exact format using ###VARIABLES### and ###END###:

###VARIABLES###

Input Variables:
variable1
variable2
...

Output Variables:
variable3
variable4
...

###END###

"""
def parse_input_output_variables(llm_response):
    input_vars = set()
    output_vars = set()
    inside_block = False
    current_section = None

    for line in llm_response.splitlines():
        line = line.strip()

        if line == "###VARIABLES###":
            inside_block = True
            continue
        elif line == "###END###":
            break

        if inside_block:
            if line.lower().startswith("input variables:"):
                current_section = "input"
                continue
            elif line.lower().startswith("output variables:"):
                current_section = "output"
                continue

            if line and current_section == "input":
                input_vars.add(line)
            elif line and current_section == "output":
                output_vars.add(line)

    return input_vars, output_vars


def solution_to_string(solution):
    return " ".join(f"{var}={value}" for var, value in solution.items())

# This function handles the core logic for checking program correctness using a naive entailment approach.
def get_io_vars(model, difficult_code, full_code, log_folder, pre_assignments, post_assignments):

    #pre assignment is a dict of variable, vallue pairs
    #turn it into string
    pre_assign_string=solution_to_string(pre_assignments)
    post_assign_string=solution_to_string(post_assignments)
    prompt = PROMPT.format(full_c_program=full_code,
                            difficult_c_code=difficult_code,
                            pre_condition_variables=pre_assign_string,
                            post_condition_variables=post_assign_string)
    
    print(f"Prompt: {prompt}")
    response = model.query(prompt)
    print(f"Response: {response}")
    input_vars, output_vars = parse_input_output_variables(response)
    print(f"Input Variables: {input_vars}")
    print(f"Output Variables: {output_vars}")

    return input_vars, output_vars


# TBD: WHAT OTHER APPROACH CAN BE USED OTHER THAN NAIVE?