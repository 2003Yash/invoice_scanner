import sys
import os
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import re
from ai_models.gemini_client import get_gemini_response
from prompt_library.gemini import get_data_field_grouping_prompt


def extract_json_schema(text):
    """
    Extracts and parses JSON schema from a text string that contains JSON within triple backticks.
    
    Args:
        text (str): A string containing JSON within triple backticks
        
    Returns:
        dict: The parsed JSON schema as a Python dictionary
    """
    # Find the content between ```json and ``` using regex
    json_pattern = r'```json\s*(.*?)\s*```'
    match = re.search(json_pattern, text, re.DOTALL)
    
    if not match:
        # If no match with ```json, try matching just the triple backticks
        json_pattern = r'```\s*(.*?)\s*```'
        match = re.search(json_pattern, text, re.DOTALL)
        
    if match:
        json_str = match.group(1).strip()
        try:
            # Parse the JSON string into a Python dictionary
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
    else:
        # If no JSON is found between triple backticks, try to find JSON directly
        try:
            # Look for JSON-like content in the string
            json_pattern = r'\{\s*"[^"]+"\s*:'
            match = re.search(json_pattern, text)
            if match:
                start_idx = match.start()
                # Extract from the first { to the last }
                json_candidate = text[start_idx:]
                # Count open and close braces to find the end
                open_braces = 0
                for i, char in enumerate(json_candidate):
                    if char == '{':
                        open_braces += 1
                    elif char == '}':
                        open_braces -= 1
                        if open_braces == 0:
                            json_str = json_candidate[:i+1]
                            return json.loads(json_str)
            
            raise ValueError("No JSON structure found in the text")
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Could not extract valid JSON: {e}")



def group_like_wise_data_fields(data_fields):
    prompt = get_data_field_grouping_prompt(data_fields)
    response = get_gemini_response(prompt)
    result = extract_json_schema(response)
    return result



# def get_data_fields_json():
#     user_id = "EaseworkAdmin"
#     data_fields = get_data_fields(user_id)
#     response = group_like_wise_data_fields(data_fields).strip()
#     result = extract_json_schema(response)
#     return result



# print(group_like_wise_data_fields())

