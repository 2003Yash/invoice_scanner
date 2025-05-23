import re
import unicodedata
import json
from typing import Dict, Any, List, Tuple
#from groq import Groq  # type: ignore
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_models.gemini_client import get_gemini_response
from prompt_library.gemini import agent3_prompt

# Set your Groq API key directly here or load from environment
# GROQ_API_KEY = "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"

# # Setup Groq client
# client = Groq(
#     api_key=GROQ_API_KEY,
# )

def extract_tabular_items(text: str) -> Tuple[List[str], List[str]]:
    items = []
    quantities = []

    # Normalize special unicode dashes to normal hyphens
    text = text.replace('–', '-').replace('—', '-')
    text = unicodedata.normalize('NFKC', text)

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Process each line independently
    for i, line in enumerate(lines):
        # Pattern: (QTYx) ITEM format - like (308x) SS-4-VCR-2-BL
        paren_qty_match = re.match(r'^\((\d+)(?:x|pcs?|units?)?\)\s+([A-Za-z0-9\-_/.\s]+)', line)
        if paren_qty_match:
            quantity = paren_qty_match.group(1).strip()
            item_code = paren_qty_match.group(2).strip()
            item_code = re.sub(r'\s*\([^)]*\)\s*$', '', item_code)
            items.append(item_code)
            quantities.append(quantity)
            continue

        # Pattern 1: QTY- 2 = ITEM
        match_qty_first = re.match(r'^QTY-?\s*(\d+)\s*[=:]\s*([A-Za-z0-9\-_/.\s]+)$', line, re.IGNORECASE)
        if match_qty_first:
            quantity = match_qty_first.group(1).strip()
            item_code = match_qty_first.group(2).strip()
            if re.search(r'[A-Z]', item_code):
                items.append(item_code)
                quantities.append(quantity)
            continue

        # Pattern 2: Item line followed by Quantity line
        if (re.match(r'^[A-Za-z0-9\-_/]{3,}$', line) and
            i < len(lines) - 1 and 
            re.match(r'^\d+$', lines[i + 1])):
            item_code = line.strip()
            quantity = lines[i + 1].strip()
            items.append(item_code)
            quantities.append(quantity)
            continue

        # Pattern 3: Bullet point format: "- ITEM: QTY units" or "- ITEM QTY units"
        bullet_pattern = re.match(r'^[-•*]\s+([A-Za-z0-9\-_/.\s]+)[:]\s*(\d+)\s*(?:units?|pcs?|pieces?)?$', line)
        if bullet_pattern:
            item_code = bullet_pattern.group(1).strip()
            quantity = bullet_pattern.group(2).strip()
            items.append(item_code)
            quantities.append(quantity)
            continue

        # Pattern 4: Bullet point with item and quantity without colon
        bullet_no_colon = re.match(r'^[-•*]\s+([A-Za-z0-9\-_/.\s]+)\s+(\d+)\s*(?:units?|pcs?|pieces?)?$', line)
        if bullet_no_colon:
            item_code = bullet_no_colon.group(1).strip()
            if re.search(r'[A-Z]', item_code) and not re.search(r'\bdate\b|\bsubject\b|\bfrom\b|\bto\b', item_code, re.IGNORECASE):
                quantity = bullet_no_colon.group(2).strip()
                items.append(item_code)
                quantities.append(quantity)
            continue
        
        # Pattern 5: Table format with item code and quantity separated by whitespace
        table_format = re.match(r'^([A-Za-z0-9\-_/.\s]+?)\s{2,}(\d+)(?:\s|$)', line)
        if table_format:
            item_code = table_format.group(1).strip()
            if (re.search(r'[A-Z]', item_code) and 
                not re.search(r'\bdate\b|\bsubject\b|\bfrom\b|\bto\b|\bfwd\b', item_code, re.IGNORECASE) and
                not re.match(r'\d{1,2}/\d{1,2}/\d{2,4}', item_code)):
                quantity = table_format.group(2).strip()
                items.append(item_code)
                quantities.append(quantity)
            continue
            
        # Pattern 6: Extract catalog numbers and quantities from structured table format
        catalog_match = re.search(r'Catalog No\.\s+([A-Za-z0-9\-_/]+)', line, re.IGNORECASE)
        if catalog_match:
            item_code = catalog_match.group(1).strip()
            # Look for quantity in nearby lines
            for j in range(max(0, i-5), min(len(lines), i+5)):
                qty_match = re.search(r'Quantity\s+(\d+)\s+(?:EA|PCS)', lines[j], re.IGNORECASE)
                if qty_match:
                    quantity = qty_match.group(1).strip()
                    items.append(item_code)
                    quantities.append(quantity)
                    break
            continue
            
        # Pattern 7: Look for line items with catalog numbers
        line_item_match = re.search(r'(?:Stainless Steel|Ferrule|[A-Za-z\s]+)\s+[A-Za-z0-9/"-]+\s+([A-Za-z0-9\-_/]+)\s+[A-Za-z]+\s+[\d.]+\s+USD\s+(\d+)\s+[A-Za-z]+', line)
        if line_item_match:
            item_code = line_item_match.group(1).strip()
            quantity = line_item_match.group(2).strip()
            items.append(item_code)
            quantities.append(quantity)
            continue

    return items, quantities

def extract_po_with_regex(text: str) -> Dict[str, Any]:
    """Extract PO data (items and quantities) using regex patterns."""
    email_parts = text.split("\n\n", 1)
    body_text = email_parts[1] if len(email_parts) > 1 else text

    # Attempt to extract PO number from body
    po_number = None
    po_number_patterns = [
        r'(?:^|\s)PO\s*(?:number|#|no|num)?[:.\s]*\s*([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)(?:purchase\s+order|reference\s+po)[\s:]*([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)(?:ref|reference)\s*(?:number|#|no)?[\s:]*([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)(?:order|confirmation)\s*(?:number|#|no)?[\s:]*([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)purchase\s+order[:\s]*(?:#|no\.?)?[:\s]*([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)use\s+PO\s+([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)new\s+PO\s+([A-Za-z0-9\-_/]{3,})(?:\s|$)'
    ]
    for pattern in po_number_patterns:
        match = re.search(pattern, body_text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if len(candidate) >= 3 and re.search(r'\d', candidate):
                po_number = candidate
                break

    # Check subject line for PO number
    for line in text.splitlines():
        if "subject:" in line.lower():
            for pattern in [r'purchase\s+order\s+(\d+)', r'PO\s*(?:number|#|no|num)?[:\s]*(\d+)', r'ORDER\s+(\d+)']:
                subject_match = re.search(pattern, line, re.IGNORECASE)
                if subject_match:
                    po_number = subject_match.group(1).strip()
                    break
                    
    # Also look specifically for "PO Number:" format
    po_specific = re.search(r'PO\s+Number:\s*([A-Za-z0-9\-_/]{3,})', body_text, re.IGNORECASE)
    if po_specific:
        po_number = po_specific.group(1).strip()

    items, quantities = extract_tabular_items(body_text)

    return {
        "po_number": po_number or "",
        "items": items,
        "quantities": quantities
    }

def extract_po_with_llm(text: str) -> Dict[str, Any]:
    """Use Gemini to extract PO data (items and quantities)."""
    prompt = agent3_prompt.format(text=text)
    response = get_gemini_response(prompt)

    if not response:
        return {"po_number": "", "items": [], "quantities": []}

    try:
        # Clean any JSON formatting like ```json ... ```
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.endswith("```"):
            response = response[:-3]

        result = json.loads(response)
        return {
            "po_number": result.get("po_number", ""),
            "items": result.get("items", []),
            "quantities": result.get("quantities", [])
        }
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response: {response}")
        return {"po_number": "", "items": [], "quantities": []}


def po_inbody_agent(email_text: str) -> Dict[str, Any]:
    """Determine if PO data exists (items/quantities) and return summary."""
    # First try regex extraction
    regex_result = extract_po_with_regex(email_text)
    regex_has_data = len(regex_result["items"]) > 0 and len(regex_result["quantities"]) > 0
    
    print("Regex extraction results:")
    print(f"Items found: {regex_result['items']}")
    print(f"Quantities found: {regex_result['quantities']}")
    print(f"PO number found: {regex_result['po_number']}")

    items = []
    quantities = []
    po_number = ""

    if regex_has_data:
        items = regex_result["items"]
        quantities = regex_result["quantities"]
        po_number = regex_result["po_number"]
    else:
        # Fall back to LLM extraction
        print("Falling back to LLM extraction...")
        llm_result = extract_po_with_llm(email_text)
        items = llm_result["items"]
        quantities = llm_result["quantities"]
        po_number = llm_result["po_number"]
        
        print("LLM extraction results:")
        print(f"Items found: {llm_result['items']}")
        print(f"Quantities found: {llm_result['quantities']}")
        print(f"PO number found: {llm_result['po_number']}")

    # Determine if we have valid PO data
    has_po_data = len(items) > 0 and len(quantities) > 0

    # Format items
    formatted_items = []
    min_length = min(len(items), len(quantities))
    for i in range(min_length):
        try:
            qty_int = int(quantities[i])
        except (ValueError, TypeError):
            qty_int = quantities[i]
        formatted_items.append({
            "item": items[i],
            "quantity": qty_int
        })

    # Generate summary
    summary = ""
    if has_po_data:
        items_summary = ", ".join([f"{item['item']} (Qty: {item['quantity']})" for item in formatted_items])
        summary = f"PO data found with items: {items_summary}"
        if po_number:
            summary = f"PO #{po_number} data found with items: {items_summary}"

    return {
        "has_po_data": has_po_data,
        "summary": summary if has_po_data else "No PO data found in email body.",
        "items": [item["item"] for item in formatted_items],
        "quantities": [item["quantity"] for item in formatted_items],
        "po_number": po_number
    }

# # Example usage
# if __name__ == "__main__":
#     # Example email with PO data
#     email_with_po = """Dear Mr. Rajesh Mehta,

# We are pleased to issue a new Purchase Order (PO) for the supply of
# components as per our recent discussions.

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
# USD"""
#     result = po_inbody_agent(email_with_po)
#     print("\nFinal results:")
#     print(json.dumps(result, indent=2))