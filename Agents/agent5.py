import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_models.gemini_client import get_gemini_response
from prompt_library.gemini import agent5_prompt

def classify_po_urgency(email_text: str) -> str:
    prompt = agent5_prompt.format(text=email_text)
    response = get_gemini_response(prompt)

    if not response:
        return "normal"

    response = response.strip().lower()
    if response in {"urgent", "medium", "normal"}:
        return response

    # Fallback based on keyword analysis
    if any(word in response for word in ["asap", "immediate", "urgent", "today"]):
        return "urgent"
    elif any(word in response for word in ["soon", "waiting", "earliest"]):
        return "medium"
    else:
        return "normal"
    
# if __name__ == "__main__":
#     sample_email = """
# Dear Mr. Rajesh Mehta,

# We are pleased to issue a new Purchase Order (PO) for the supply of
# components as per our recent discussions please process this soon.

# **Purchase Order Details:**
# - PO Number: JK45678
# - PO Date: May 2, 2025
# - Vendor: Mehta Industrial Supplies
# - Delivery Location: TechNova Solutions Pvt. Ltd., Plot 12, MIDC Industrial
# Area, Navi Mumbai, Maharashtra - 400710
# - Expected Delivery Date: May 15, 2025
# Line No. Product Description Catalog No. Size / Packaging Unit Price
# Quantity Ext. Price 1 of 2 Stainless Steel Union 1/16" SS-100-6 EA 19.25
# USD 20 EA 385.00 USD ADDITIONAL INFO Catalog No. SS-100-6 Packaging EA Unit
# Price 19.25 Taxable Yes Quote number 169887 Note for Supplier 2 of 2
# Ferrule Set 1/16" Sold in multiples of 10 SS-100-SET EA 4.54 USD 10 EA
# 45.40 USD ADDITIONAL INFO Catalog No. SS-100-SET Packaging EA Unit Price
# 4.54 Taxable Yes Quote number 169887 Note for Supplier Shipping, Handling
# and Tax charges are calculated and charged by each supplier. Total 430.40
# USD
# """

#     urgency = classify_po_urgency(sample_email)
#     print(f"Urgency Level: {urgency}")

