import re

PROMPT = """
You are helping solve a constraint satisfaction problem over some code that is part of a program. We have some constraints that must hold before the code and some others for after the code

The  code is:
{difficult_part}

The input variables with their type are:
{input_vars}

The output variables with their type are:
{output_vars}

The pre-constraints on the input variables are:
{pre_constraints}

The post-constraints on the output variables are:
{post_constraints}

Here is one candidate solution that satisfies the pre-constraints:
{pre_candidate}

Here is one candidate solution that satisfies the post-constraints:
{post_candidate}

Your task:
Propose a **complete assignment of input variable values** (one value per input variable) such that:
- The input values satisfy the pre-constraints.
- When these input values are used in the code, the output variables satisfy the post-constraints.

Please output only the variable assignments in this format:

###VARIABLES###
variable1=value1
variable2=value2
...
###END###
Even if you find a set of values that satisfy all pre and post constraints , always respond with some value for all input variables.
Think carefully about the constraints and the program logic. You can use the pre-constraints, the code itself and the post-constraints to guide your reasoning.
"""



def extract_seed_values(response_text, input_vars):
    """
    Extracts input variable values from the LLM response.

    Args:
        response_text (str): The LLM's full response text.
        input_vars (list of str): The list of input variable names.

    Returns:
        dict: A dictionary {var: value} with parsed float values.
    """
    # Extract the section between ###VARIABLES### and ###END###
    pattern = re.compile(r'###VARIABLES###(.*?)###END###', re.DOTALL)
    match = pattern.search(response_text)
    if not match:
        raise ValueError("Could not find ###VARIABLES### ... ###END### block in response.")

    var_block = match.group(1)

    # Parse each line in the block
    values = {}
    for line in var_block.strip().splitlines():
        line = line.strip()
        if '=' in line:
            var, val = line.split('=', 1)
            var = var.strip()
            val = val.strip()
            if var in input_vars:
                try:
                    values[var] = float(val)
                except ValueError:
                    raise ValueError(f"Could not convert value for variable '{var}': {val}")
    
    # Check if we got all input variables
    missing = [v for v in input_vars if v not in values]
    if missing:
        raise ValueError(f"Missing values for variables: {missing}")

    return values

# This function handles the core logic for checking program correctness using a naive entailment approach.
def get_inital_seed(model, difficult_part, input_vars, output_vars, pre_constraints, post_constraints, pre_candidate, post_candidate):
#input vars is a set , lets make them string with comma sparated
   #inputs is a dict of input vars and their type
   #make a string with the inputs and their type
    input_vars_str = ', '.join(f"{var} of type {var_type}" for var, var_type in input_vars.items())
    output_vars_str = ', '.join(f"{var} of type {var_type}" for var, var_type in output_vars.items())

    #pre assignment is a dict of variable, vallue pairs
    #turn it into string
    pre_candidate_str = '\n'.join(f"{var} = {val}" for var, val in pre_candidate.items())
    post_candidate_str = '\n'.join(f"{var} = {val}" for var, val in post_candidate.items())


    prompt = PROMPT.format(difficult_part=difficult_part, input_vars=input_vars_str, output_vars=output_vars_str, pre_constraints=pre_constraints, post_constraints=post_constraints, pre_candidate=pre_candidate_str, post_candidate=post_candidate_str) 
    
    response = model.query(prompt)
    result = extract_seed_values(response, input_vars)

    return result


# TBD: WHAT OTHER APPROACH CAN BE USED OTHER THAN NAIVE?