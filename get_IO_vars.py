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

1. Input Variables: Variables whose values must be concretized before the difficult code executes to influence its behavior.They are part of the pre-condition variables.

2. Output Variables: Variables whose values are affected or modified by the difficult code and matter after its execution. They are part of the post-condition variables. 
We dont care about some internal variables that are not part of the pre or post-condition variables.
You also need to identify the type of these variables. choose the best fitting one but all vars must have a type .The types can be:
- int
- float
- char
- double
- long
- string
- bool
- array

You may explain your reasoning step by step.

However, at the end of your response, always include a clearly marked output section in this exact format using ###VARIABLES### and ###END###:

###VARIABLES###

Input Variables:
variable1 type1
variable2 type2
...

Output Variables:
variable3 type3
variable4 type4
...

###END###

"""

PROMPT_total = """
You are provided with the following complete C program:

{full_c_program}



Your task is to analyze the code and identify all the variables and their type
Assign to the variables the best fitting of the following types:
- int
- float
- char
- double
- long
- string
- bool
- array

You may explain your reasoning step by step.

However, at the end of your response, always include a clearly marked output section in this exact format using ###VARIABLES### and ###END###:

###VARIABLES###

variable1 type1
variable2 type2
variable3 type3
variable4 type4
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
                # Extract variable name and type
                match = re.match(r"(\w+)\s+(\w+)", line)
                if match:
                    var_name, var_type = match.groups()
                    # Add variable name and type to the set
                    input_vars.add((var_name, var_type))
                else:
                    # If no match, remove preceding and leading spaces 
                    no_spaces = line.strip()
                    # Split by spaces and add to input_vars
                    parts = no_spaces.split()
                    if len(parts) >= 2:
                        input_vars.add((parts[0], parts[-1]))
            elif line and current_section == "output":
                match = re.match(r"(\w+)\s+(\w+)", line)
                if match:
                    var_name, var_type = match.groups()
                    output_vars.add((var_name, var_type))
                else:

                    no_spaces = line.strip()

                    parts = no_spaces.split()
                    if len(parts) >= 2:
                        output_vars.add((parts[0], parts[-1]))

    return input_vars, output_vars

def parse_total_variables(llm_response):
    """
    Parses an LLM response to extract a dictionary of variable names and their types
    from the section between ###VARIABLES### and ###END###.

    Args:
        llm_response (str): The full response from the LLM.

    Returns:
        dict: A dictionary where keys are variable names and values are types (as strings).
    """
    start_tag = "###VARIABLES###"
    end_tag = "###END###"

    start_idx = llm_response.find(start_tag)
    end_idx = llm_response.find(end_tag)

    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise ValueError("Missing or malformed ###VARIABLES### section in LLM response.")

    lines = llm_response[start_idx + len(start_tag):end_idx].strip().splitlines()
    var_type_dict = {}

    for line in lines:
        parts = line.strip().split()
        if len(parts) == 2:
            var, var_type = parts
            var_type_dict[var] = var_type
        else:
            print(f"Skipping malformed line: {line}")

    return var_type_dict

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

def get_total_vars(model, full_code):

  
    
    prompt = PROMPT_total.format(full_c_program=full_code)
    
    
    response = model.query(prompt)
    total_vars= parse_total_variables(response)
    print(f"Total Variables: {total_vars}")

    return total_vars


# TBD: WHAT OTHER APPROACH CAN BE USED OTHER THAN NAIVE?