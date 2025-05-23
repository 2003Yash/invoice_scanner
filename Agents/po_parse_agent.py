# po_fields_agent.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_models.gemini_client import get_gemini_response
from prompt_library.gemini import Po_parse_agent_prompt
import json

def extract_po_grouped_fields(email_text: str, fields: str, strstructure: str):
    prompt = Po_parse_agent_prompt(email_text, fields, strstructure)
    response = get_gemini_response(prompt)

    if not response:
        return {}

    try:
        # Clean JSON block if wrapped in triple backticks
        if response.startswith("```json"):
            response = response.replace("```json", "").strip()
        if response.endswith("```"):
            response = response[:-3].strip()

        parsed = json.loads(response)
        return parsed
    except Exception as e:
        print("Error parsing response:", e)
        print("Raw response:", response)
        return {}
    


# if __name__ == "__main__":
#     sample_email = """
# Dear team,

# Please find the new purchase order attached.

# Bill to: TechNova Corp, Mumbai
# Payment Terms: Net 30 days
# Notes: Please prioritize this order.

# Supplier: Swagelok India Pvt Ltd
# Quotation No: QTN-88234
# Quotation Date: April 12, 2025
# Tax: 18%
# Tax Amount: ₹1,800
# Shipping & Handling: ₹500
# Discount: ₹200
# Freight Charges: ₹150

# Ship to: TechNova Warehouse, Pune

# PO #: TN-PO-4567
# Order Date: April 25, 2025
# Total Amount: ₹12,500

# Line Item:
# Customer Part #: 101-IND-78
# Swagelok Part #: SS-4-VCR-2
# Qty: 10
# Unit: EA
# Unit Price: ₹1,050
# Tax: 18%
# Tax Amount: ₹1,800
# Item Total: ₹10,500
# """
#     grouped_fields = extract_po_grouped_fields(sample_email)
#     print(json.dumps(grouped_fields, indent=2, ensure_ascii=False))


