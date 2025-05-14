import re

PROMPT = """
Given the following C function:

{c_function}

The input variables with their type are:
{input_vars}

The output variables with their type are:
{output_vars}

The target output is:

{target_output}


Please predict plausible input values for the function that will produce approximately the given output.

Explain your reasoning step by step.

Then, provide the input values in the following format:

Input values:
@@@input_variable_1 value_1@@@
@@@input_variable_2 value_2@@@
@@@input_variable_3 value_3@@@
...

Format rules:
- Use the variable names from the C code.
- Only include variables that are inputs.
- Use one line per variable.
- Start and end each line with @@@, with exactly one space between the variable name and the value.
"""


# Parses the model response to see if it responded True or False

def extract_correctness_from_response(response_content: str) -> str:
    pattern = r"Correctness:\s*\*\*(.*?)\*\*|Correctness:\s*(True|False)"
    match = re.findall(pattern, response_content)
    if match:
        if match[-1][0]:
            return match[-1][0].strip()
        elif match[-1][1]:
            return match[-1][1].strip()
    return response_content


import re

def extract_input_pairs(response_text):
    """
    Parses LLM response and extracts input variable-value pairs.
    Returns a dictionary {variable: value}.
    """
    pattern = r'@@@(\w+)\s+([-+]?\d+(?:\.\d+)?)@@@'
    matches = re.findall(pattern, response_text)
    
    if not matches:
        raise ValueError("No input pairs found in the response.")

    inputs = {var.strip(): float(val) if '.' in val else int(val) for var, val in matches}
    return inputs

# This function handles the core logic for checking program correctness using a naive entailment approach.
def inverted_solutions_simple(model, code, target, input_vars, output_vars):
        
    input_vars_str = ', '.join(f"{var} of type {var_type}" for var, var_type in input_vars.items())
    output_vars_str = ', '.join(f"{var} of type {var_type}" for var, var_type in output_vars.items())
    prompt = PROMPT.format(c_function=code,
                            input_vars=input_vars_str,
                            output_vars=output_vars_str,
                            target_output=target)
    
    response = model.query(prompt)
    result = extract_input_pairs(response)

    return result


# TBD: WHAT OTHER APPROACH CAN BE USED OTHER THAN NAIVE?