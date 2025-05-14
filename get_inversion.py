import re
import os
from pathlib import Path

# This is the final step after the final post condition has been generated. This is the prompt template that will be filled in with the problem description, the program,
# and the final output hints (postcondition). It instructs the model to determine whether the program
# satisfies the description and output specification, and asks it to return either "True" or "False".

PROMPT = """
You are given the following C function:

{difficult_c_code}

This function takes the following input variables (with types):
{input_vars}

It produces the following output variables (with types):
{output_vars}

Your task is to generate an approximate inverse function, which:
1. Takes the previous output variables as input.
2. Computes and assigns plausible values to the original input variables.

Then, generate a minimal compilable C program that:

- Includes the inverse function.
- Contains a main() function where:
  - The new inputs (i.e., former outputs) are assigned placeholder values named like: var_placeholder.
    Example: double result = result_placeholder;
    Don't use actual values, we will replace them later. as values use variable name + _placeholder. SO that after we replace witrh actual value the script will compile and run.
  - The inverse function is called.
  - After execution, print the inferred input variables using the format:
    ###RESULT### x=value y=value ...
  - Exit the program using `exit(0);`.

IMPORTANT:
- Keep all code compilable.
- Use correct C types and format specifiers (e.g., %d, %f).
- Do not include comments or extra explanation.
- Keep the code minimal and runnable.


Wrap the code section between the following tags so it can be parsed:

###BEGIN_CODE###
<your valid compilable C code here>
###END_CODE###

"""

# Parses the model response to see if it responded True or False
def extract_code_block(response_text):
    """
    Extracts the code section between ###BEGIN_CODE### and ###END_CODE### from LLM response.

    Args:
        response_text (str): Full LLM response including explanation and tagged code block.

    Returns:
        str: The extracted C code, or None if not found.
    """
    begin_tag = "###BEGIN_CODE###"
    end_tag = "###END_CODE###"
    
    start = response_text.find(begin_tag)
    end = response_text.find(end_tag)
    
    if start == -1 or end == -1 or end < start:
        return None
    
    code = response_text[start + len(begin_tag):end]
    return code.strip()



def save_c_code(response, output_file):
    """
    Saves the LLM response as a C source file.

    Args:
        response (str): The LLM-provided C code.
        output_file (str or Path): Path where the .c file will be saved.
    """
    output_file = Path(output_file)
    with output_file.open("w", encoding="utf-8") as f:
        f.write(response)

def invert_code(model, code,  input_vars, output_vars, log_folder):
    """
    This function handles the core logic for checking program correctness using a naive entailment approach.
    It generates a prompt for the model to create an inverse function and checks the response.
    """
    
    # Prepare the input variables string
    input_vars_str = ', '.join(f"{var} of type {var_type}" for var, var_type in input_vars.items())
    
    # Prepare the output variables string
    output_vars_str = ', '.join(f"{var} of type {var_type}" for var, var_type in output_vars.items())
    
    # Fill in the prompt template
    prompt = PROMPT.format(difficult_c_code=code, input_vars=input_vars_str, output_vars=output_vars_str)
    
    # Call the model with the prompt
    response = model.query(prompt)
    
    # Extract the code block from the response
    code_block = extract_code_block(response)
    #create file for the code in the log folder
    log_folder = Path(log_folder)
    log_folder.mkdir(parents=True, exist_ok=True)

    # Save the code block to a file
    save_c_code(code_block, log_folder / "inverted_solution.c")
    
    if not code_block:
        raise ValueError("No valid C code block found in the model's response.")
    
    return code_block
      


# TBD: WHAT OTHER APPROACH CAN BE USED OTHER THAN NAIVE?