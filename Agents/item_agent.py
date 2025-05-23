import sys
import os
import re
import json
import time
import socket  

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_models.gemini_client import get_gemini_response
from prompt_library.gemini import item_agent_prompt

def extract_po_items_only(email_text: str, field_key: str, field_structure: list):
    """
    Extract product items from purchase order content using Gemini AI.
    
    Args:
        email_text: The full purchase order text content
        field_key: The key for the field (should be 'item')
        field_structure: Template structure for each item with empty field values
        
    Returns:
        List of dictionaries containing extracted item information
    """
    # Format the prompt with the dynamic JSON structure
    prompt = item_agent_prompt.format(
        po_content=email_text,
        field_key=field_key,
        field_structure=field_structure
    )

    # Retry mechanism for timeout handling
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = get_gemini_response(prompt)
            break  # Exit loop if successful
        except (TimeoutError, socket.timeout) as e:
            print(f"Timeout occurred on attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(2)  # Wait before retrying
            else:
                print("Max retry attempts reached. Returning empty result.")
                return []
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return []

    if not response:
        return []

    print(f"Gemini Raw Response for {field_key}:\n", response)

    try:
        # Clean up response to extract JSON
        if response.startswith("```json"):
            response = response.replace("```json", "").strip()
        if response.endswith("```"):
            response = response[:-3].strip()

        # Parse the JSON response
        result = json.loads(response)
        
        # Extract the items array - this is the key fix
        if isinstance(result, dict) and field_key in result:
            return result[field_key]
        elif isinstance(result, list):
            return result
        return []
    except Exception as e:
        print(f"Error parsing {field_key} response:", e)
        print("Raw response:", response)
        return []

    
# if __name__ == "__main__":
#     # For testing purposes
#     sample_email = """
# Roberts Oxygen Company, Inc.
# Roberts Oxygen Company, Inc.

# PURCHASE ORDER
# PURCHASE ORDER

# PO Box 5507
# Rockville, MD 20855
# Rockville, MD 20855

# www.RobertsOxygen.com

# Ship-To: 14
# Manassas - Roberts Oxygen
# 8607 Quarry Road
# Manassas, VA 20110
# (703) 369-0400

# Number

# 926947

# Date

# 05/08/2025

# Page

# 1

# Site Contact

# Site Phone

# Site Ref#

# Vendor: DIBE01
# DIBERT VALVE & FITTING CO.INC.
# P.O. BOX 79828
# RICHMOND, VA 23231

# Buyer

# Terms

# Ship Via

# FOB

# Freight

# Expected

# Customer

# JJR

# Net 30

# UPS COLLECT

# ORIGIN

# Collect

# 05/08/2025

# Vendor-Item #

# Item

# Description

# Units UM

# Cost UM

# Extension

# MS-HTB-4T

# MSHTB4T

# UPS14

# DIBERT HAND TUBE BENDER
# 1/4" TUBE OD, 9/16" RADIUS
# ** USE SHIPPER # 3817AE **

# 8 EA

# 1 EA

# 258.3900 EA

# 2067.12

# .0000 EA

# .00

# PURCHASE ORDER

# Amount

# Tax

# Freight

# Total

# MUST EMAIL CONFIRMATION OF PRICES AND SHIP DATES

# Vendor Copy

# ... Last Page

# 2067.12

# .00

# .00

# 2067.12
# """
#     # Define your field structure
#     # field_structure = [{
#     #     "customer_item_id": "",
#     #     "manufacturer_item_id": "",
#     #     "item_description": "",
#     #     "quantity": "",
#     #     "unit_price": "",
#     #     "total_price": ""
#     # }]
#     field_structure = [
#         {
#             "customer_item_part": "",
#             "swagelok_item_part": "",
#             "item_description": "",
#             "quantity": "",
#             "unit_of_measure": "",
#             "unit_price": "",
#             "item_tax_percentage": "",
#             "item_tax_amount": "",
#             "discount": "",
#             "item_total": ""
#         }
#     ]

#     field_key = "item"
    
#     items = extract_po_items_only(sample_email, field_key, field_structure)
#     print("Parsed Items:\n", items)
#     print("\nStructured Output:\n", json.dumps(items, indent=2, ensure_ascii=False))