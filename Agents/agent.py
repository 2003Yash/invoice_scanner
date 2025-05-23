import re
import unicodedata
import json
from typing import Dict, Any, Optional, List, Tuple
from groq import Groq
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_models.gemini_client import get_gemini_response
from prompt_library.gemini import agent_Prompt

#GROQ_API_KEY = "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"
MONGODB_CONNECTION_STRING = "mongodb+srv://easework-access:mHQ1ndxROj82KQql@po-email-automation.yitjt.mongodb.net/?retryWrites=true&w=majority&appName=PO-Email-Automation"

# client = Groq(
#     api_key=GROQ_API_KEY,
# )

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

def extract_tabular_items(text: str) -> Tuple[List[str], List[str]]:
    items = []
    quantities = []
    text = text.replace('–', '-').replace('—', '-')
    text = unicodedata.normalize('NFKC', text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        picarro_part_match = re.search(r'Picarro part number (\d+)', line)
        if picarro_part_match:
            picarro_part = picarro_part_match.group(1).strip()
            
            if i + 1 < len(lines):
                vendor_part_match = re.search(r'^([A-Za-z0-9\-_/]+)', lines[i + 1].strip())
                if vendor_part_match:
                    vendor_part = vendor_part_match.group(1).strip()
                    
                    qty_found = False
                    for j in range(i + 1, min(i + 4, len(lines))):
                        qty_match = re.search(r'\b(\d+)\s+0\s+\d{2}/\d{2}/\d{4}', lines[j])
                        if qty_match:
                            quantity = qty_match.group(1).strip()
                            items.append(vendor_part)
                            quantities.append(quantity)
                            qty_found = True
                            break
                    
                    if not qty_found:
                        for j in range(i + 1, min(i + 4, len(lines))):
                            alt_qty_match = re.search(r'\b(\d+)\s+(?:units?|pcs?|pieces?)?(?:\s|$)', lines[j])
                            if alt_qty_match:
                                quantity = alt_qty_match.group(1).strip()
                                items.append(vendor_part)
                                quantities.append(quantity)
                                break

    if not items:
        for i, line in enumerate(lines):
            match_qty_first = re.match(r'^QTY-?\s*(\d+)\s*[=:]\s*([A-Za-z0-9\-_/.\s]+)$', line, re.IGNORECASE)
            if match_qty_first:
                quantity = match_qty_first.group(1).strip()
                item_code = match_qty_first.group(2).strip()
                if re.search(r'[A-Z]', item_code):
                    items.append(item_code)
                    quantities.append(quantity)
                continue

            if (re.match(r'^[A-Za-z0-9\-_/]{3,}$', line) and
                i < len(lines) - 1 and 
                re.match(r'^\d+$', lines[i + 1])):
                item_code = line.strip()
                quantity = lines[i + 1].strip()
                items.append(item_code)
                quantities.append(quantity)
                continue

            bullet_pattern = re.match(r'^[-•*]\s+([A-Za-z0-9\-_/.\s]+)[:]\s*(\d+)\s*(?:units?|pcs?|pieces?)?$', line)
            if bullet_pattern:
                item_code = bullet_pattern.group(1).strip()
                quantity = bullet_pattern.group(2).strip()
                items.append(item_code)
                quantities.append(quantity)
                continue

            bullet_no_colon = re.match(r'^[-•*]\s+([A-Za-z0-9\-_/.\s]+)\s+(\d+)\s*(?:units?|pcs?|pieces?)?$', line)
            if bullet_no_colon:
                item_code = bullet_no_colon.group(1).strip()
                if re.search(r'[A-Z]', item_code) and not re.search(r'\bdate\b|\bsubject\b|\bfrom\b|\bto\b', item_code, re.IGNORECASE):
                    quantity = bullet_no_colon.group(2).strip()
                    items.append(item_code)
                    quantities.append(quantity)
                continue
            
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

            qty_x_pattern = re.search(r'\(\s*(\d+)x?\s*\)\s+([A-Za-z0-9\-_/.\s]+?)(?:\s+\([^)]*\))?(?:\s|$)', line)
            if qty_x_pattern:
                quantity = qty_x_pattern.group(1).strip()
                item_code = qty_x_pattern.group(2).strip()
                if re.search(r'[A-Z]', item_code):
                    items.append(item_code)
                    quantities.append(quantity)
                    print(f"Found item in (QTYx) format: {item_code} with quantity {quantity}")
                continue
    
    return items, quantities

def extract_table_data(text: str) -> Tuple[List[Dict[str, str]], str]:
    items = []
    
    table_pattern = r'\*\*Items Ordered:\*\*.*?(?=\*\*Total PO Value:|$)'
    table_match = re.search(table_pattern, text, re.DOTALL)
    if not table_match:
        return [], ""
    
    table_text = table_match.group(0)
    
    total_pattern = r'\*\*Total PO Value:\*\*\s*([\d₹,\.]+)'
    total_match = re.search(total_pattern, text)
    if total_match:
        total_po_value = total_match.group(1).strip()
    
    lines = [line.strip() for line in table_text.splitlines() if line.strip()]
    
    header_idx = -1
    for i, line in enumerate(lines):
        if '|' in line and any(header in line.lower() for header in ['item code', 'description', 'quantity', 'unit price', 'total']):
            header_idx = i
            break
    
    if header_idx == -1:
        return [], total_po_value
    
    headers = [h.strip().lower() for h in lines[header_idx].split('|')[1:-1]]
    
    if header_idx + 1 < len(lines) and all(c in '-|' for c in lines[header_idx + 1]):
        separator_idx = header_idx + 1
    else:
        return [], total_po_value
    
    for i in range(separator_idx + 1, len(lines)):
        line = lines[i]
        
        if '|' not in line or line.count('|') != len(headers) + 1:
            continue
        
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        
        if len(cells) == len(headers):
            row_dict = {headers[j]: cells[j] for j in range(len(headers))}
            items.append(row_dict)
    
    return items, total_po_value

def determine_po_type(text: str, po_number: str) -> Dict[str, Any]:
    text_lower = text.lower()
    
    po_index = text_lower.find(po_number.lower())
    if po_index == -1:
        for line in text.splitlines():
            if po_number.lower() in line.lower():
                context = line.lower()
                break
        else:
            context = text_lower
    else:
        start = max(0, po_index - 50)
        end = min(len(text_lower), po_index + len(po_number) + 50)
        context = text_lower[start:end]
    
    new_po_indicators = [
        r'buy\s',
        r'new\s+po\b',
        r'new\s+purchase\s+order\b',
        r'(?:would|want|wish)\s+to\s+(?:place|submit|create)\s+(?:an?|the)?\s+order',
        r'(?:would|want|wish)\s+to\s+order',
        r'(?:placing|submitting|creating)\s+(?:an?|the)?\s+(?:new)?\s+order',
        r'(?:please|kindly)\s+process\s+this\s+order',
        r'attached\s+(?:is|are)\s+(?:an?|the|our)\s+(?:new)?\s+order',
    ]
    
    reference_po_indicators = [
        r'(?:referring|reference|regarding)\s+to\s+(?:po|purchase\s+order)',
        r'with\s+reference\s+to\s+(?:po|purchase\s+order)',
        r'follow(?:[-\s]?up)?\s+(?:on|regarding|about)\s+(?:po|purchase\s+order)',
        r'status\s+(?:of|on|for|about)\s+(?:po|purchase\s+order)',
        r'update\s+(?:on|for|about)\s+(?:po|purchase\s+order)',
        r'(?:existing|previous|prior|earlier)\s+(?:po|purchase\s+order)',
        r'track(?:ing)?\s+(?:po|purchase\s+order)',
        r'(?:^|\s)use\s+PO\s+([A-Za-z0-9-_/]{3,})(?:\s|$)',
        r'(?:inquiry|enquiry|question)\s+(?:about|on|regarding)\s+(?:po|purchase\s+order)',
    ]
    
    if "new po" in context or "new purchase order" in context:
        print(f"Found 'new PO' indicator in context: '{context}'")
        return {"is_reference_po": False, "po_number": po_number}
    
    for pattern in new_po_indicators:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            print(f"Found new PO indicator with pattern '{pattern}': '{match.group(0)}'")
            return {"is_reference_po": False, "po_number": po_number}
    
    for pattern in reference_po_indicators:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            print(f"Found reference PO indicator with pattern '{pattern}': '{match.group(0)}'")
            return {"is_reference_po": True, "po_number": po_number}
    
    ordering_phrases = [
        r'i\s+(?:am|\'m)\s+(?:placing|submitting)\s+(?:an?|the)?\s+order',
        r'(?:please|kindly)\s+find\s+(?:an?|the|our|attached)?\s+order',
        r'(?:please|kindly)\s+process\s+(?:an?|the|this|our)?\s+order',
        r'i\s+(?:would|want|wish)\s+to\s+order\b',
        r'(?:please|kindly)\s+(?:consider|treat)\s+this\s+(?:as|like)\s+(?:an?|the)?\s+order',
        r'(?:here|attached)\s+is\s+(?:an?|the|our)?\s+order',
    ]
    
    for phrase in ordering_phrases:
        match = re.search(phrase, text_lower, re.IGNORECASE)
        if match:
            print(f"Found ordering phrase: '{match.group(0)}'")
            return {"is_reference_po": False, "po_number": po_number}
    
    if any(phrase in text_lower for phrase in ["placing an order", "place an order", "new order", "i like to order"]):
        print("Found direct new order phrase")
        return {"is_reference_po": False, "po_number": po_number}
    
    print("No clear indicators found, defaulting to reference PO")
    return {"is_reference_po": True, "po_number": po_number}

def extract_po_with_regex(text: str) -> Dict[str, Any]:
    email_parts = text.split("\n\n", 1)
    body_text = email_parts[1] if len(email_parts) > 1 else text
    
    # First, check for explicit PO number format
    explicit_po_pattern = r'PO\s+number:?\s+([A-Za-z0-9\-_/]{3,})'
    explicit_match = re.search(explicit_po_pattern, body_text, re.IGNORECASE)
    if explicit_match:
        po_number = explicit_match.group(1).strip()
        print(f"Found explicit PO number: {po_number}")
        po_info = determine_po_type(body_text, po_number)
        items, quantities = extract_tabular_items(body_text)
        table_items, _ = extract_table_data(body_text)
        for row in table_items:
            if "item code" in row and "quantity" in row:
                items.append(row["item code"])
                quantities.append(row["quantity"])
        
        # Check directly for items in bullet point format
        bullet_items = re.findall(r'[-•*]\s+([A-Za-z0-9\-_/]+):\s*(\d+)\s+(?:units?|pcs?|pieces?)', body_text)
        for item, qty in bullet_items:
            if item not in items:
                items.append(item)
                quantities.append(qty)
        
        return {
            "po_number": po_info["po_number"],
            "is_reference_po": po_info["is_reference_po"],
            "items": items,
            "quantities": quantities
        }
    
    # Then try other patterns
    po_number_patterns = [
        r'(?:^|\s)PO\s*(?:number|#|no|num)?[:.\s]*\s*([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)(?:purchase\s+order|reference\s+po)[\s:]*([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)(?:ref|reference)\s*(?:number|#|no)?[\s:]*([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)(?:order|confirmation)\s*(?:number|#|no)?[\s:]*([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)purchase\s+order[:\s]*(?:#|no\.?)?[:\s]*([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)use\s+PO\s+([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)new\s+PO\s+([A-Za-z0-9\-_/]{3,})(?:\s|$)',
        r'(?:^|\s)new\s+order\s+([A-Za-z0-9\-_/]{3,})(?:\s|$)'
    ]
    
    # Check subject line for PO number
    subject_match = None
    for line in text.splitlines():
        if "subject:" in line.lower():
            print(f"Found subject line: {line}")
            for pattern in [
                r'purchase\s+order\s+([A-Za-z0-9\-_/]+)', 
                r'PO\s*(?:number|#|no|num)?[:\s]*([A-Za-z0-9\-_/]+)', 
                r'ORDER\s+([A-Za-z0-9\-_/]+)',
                r'PO\s+([A-Za-z0-9\-_/]+)'
            ]:
                subject_match = re.search(pattern, line, re.IGNORECASE)
                if subject_match:
                    print(f"Found PO in subject: {subject_match.group(1)}")
                    break
    
    po_number = None
    for pattern in po_number_patterns:
        match = re.search(pattern, body_text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if len(candidate) >= 3 and re.search(r'\d', candidate):
                po_number = candidate
                print(f"Found PO with pattern '{pattern}': {po_number}")
                break
    
    if not po_number and subject_match:
        po_number = subject_match.group(1).strip()
        print(f"Using PO from subject: {po_number}")
    
    if not po_number:
        print("No PO number found after all extraction attempts")
        return {"po_number": "", "is_reference_po": True, "items": [], "quantities": []}
    
    po_info = determine_po_type(body_text, po_number)
    
    items, quantities = extract_tabular_items(body_text)

    # Check for bullet point format items
    bullet_items = re.findall(r'[-•*]\s+([A-Za-z0-9\-_/]+):\s*(\d+)\s+(?:units?|pcs?|pieces?)', body_text)
    for item, qty in bullet_items:
        if item not in items:
            items.append(item)
            quantities.append(qty)

    table_items, _ = extract_table_data(body_text)
    for row in table_items:
        if "item code" in row and "quantity" in row:
            items.append(row["item code"])
            quantities.append(row["quantity"])
    
    return {
        "po_number": po_info["po_number"],
        "is_reference_po": po_info["is_reference_po"],
        "items": items,
        "quantities": quantities
    }

def extract_po_with_llm(text: str) -> Dict[str, Any]:
    from json import JSONDecodeError
    prompt = agent_Prompt.format(text=text)
    response = get_gemini_response(prompt)

    if not response:
        return {"po_number": "", "is_reference_po": True, "items": [], "quantities": []}

    try:
        result = json.loads(response)
        result["po_number"] = result.get("po_number", "")
        result["is_reference_po"] = result.get("is_reference_po", True)
        result["items"] = result.get("items", [])
        result["quantities"] = result.get("quantities", [])
        return result
    except (JSONDecodeError, Exception):
        return {"po_number": "", "is_reference_po": True, "items": [], "quantities": []}


def fetch_po_data_from_mongodb(po_number: str) -> Optional[Dict[str, Any]]:
    try:
        client = MongoClient(MONGODB_CONNECTION_STRING)
        db = client["PO_Data"]
        
        po_data_collection = db["po_data"]
        
        possible_queries = [
            {"po_number": po_number},
            {"po.po_number": po_number},
            {"po": {"po_number": po_number}}
        ]
        
        po_data = None
        for query in possible_queries:
            po_data = po_data_collection.find_one(query)
            if po_data:
                break
        
        if po_data:
            print(f"Found PO data in po_data collection for PO: {po_number}")
            return po_data
        
        sales_order_collection = db["Sales Order"]
        
        so_possible_queries = [
            {"purchase_order": po_number},
            {"header_information.purchase_order": po_number}
        ]
        
        sales_order = None
        for query in so_possible_queries:
            sales_order = sales_order_collection.find_one(query)
            if sales_order:
                break
        
        if sales_order:
            print(f"Found Sales Order data for PO: {po_number}")
            return {"sales_order": sales_order}
        
        print(f"No data found in MongoDB for PO: {po_number}")
        return None
    
    except Exception as e:
        print(f"MongoDB Error: {str(e)}")
        return None
    finally:
        if 'client' in locals():
            client.close()

def extract_sender_email(email_text: str) -> str:
    """Extract sender email from the email text."""
    from_pattern = r'^\s*From:\s*(?:.*?<)?([^<>\s]+@[^<>\s]+)>?'
    match = re.search(from_pattern, email_text, re.MULTILINE | re.IGNORECASE)
    #print(f"Regex pattern: {from_pattern}")
    #print(f"From line: {[line for line in email_text.split('\n') if 'From:' in line]}")
    if match:
        sender_email = match.group(1).strip()
        print(f"Extracted sender email: {sender_email}")
        return sender_email
    print("No sender email found")
    return ""

def fetch_customer_data_by_email(sender_email: str) -> Optional[Dict[str, Any]]:
    """Fetch customer data from MongoDB using sender email."""
    try:
        client = MongoClient(MONGODB_CONNECTION_STRING)
        db = client["temp_data_2"]
        
        customer_collection = db["customer_master_data"]
        
        customer_data = customer_collection.find_one({"customer_email": sender_email})
        
        if customer_data:
            print(f"Found customer data for email: {sender_email}")
            return customer_data
        
        print(f"No customer data found for email: {sender_email}")
        return None
    
    except Exception as e:
        print(f"MongoDB Error: {str(e)}")
        return None
    finally:
        if 'client' in locals():
            client.close()

def fetch_additional_po_data(customer_id: str) -> Optional[Dict[str, Any]]:
    """Fetch additional PO data using customer_id from po_data collection."""
    try:
        client = MongoClient(MONGODB_CONNECTION_STRING)
        db = client["temp_data_2"]
        
        po_data_collection = db["po_data"]
        
        po_data = po_data_collection.find_one({"customer.customer_id": customer_id})
        
        if po_data:
            print(f"Found additional PO data for customer ID: {customer_id}")
            return po_data
        
        print(f"No additional PO data found for customer ID: {customer_id}")
        return None
    
    except Exception as e:
        print(f"MongoDB Error: {str(e)}")
        return None
    finally:
        if 'client' in locals():
            client.close()

def create_new_po_from_email(po_number: str, email_text: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a new PO structure from email data and customer data."""
    today_date = datetime.now().strftime("%m%d%Y")
    sender_email = extract_sender_email(email_text)
    customer_data = fetch_customer_data_by_email(sender_email)
    
    new_po = {
        "po": {
            "po_number": po_number,
            "quotation_number": "NA",
        },
        "order": {
            "order_date": today_date,
            "delivery_terms": "DAPDESTINATION",
            "payment_terms": "Net60Days",
            "delivery_date": ""
        },
        "customer": {
            "customer_name": "",
            "customer_address": "",
            "customer_city": "",
            "customer_country": "",
            "customer_id": ""
        },
        "supplier": {
            "supplier_name": "",
            "supplier_address": "",
            "supplier_city": "",
            "supplier_country": ""
        },
        "delivery": {
            "delivery_name": "",
            "delivery_address": "",
            "delivery_city": "",
            "delivery_country": ""
        },
        "item": [],
        "cost": {
            "net_amount": "",
            "tax": "NA",
            "total_amount": "",
            "currency": "USD"
        },
        "other_details": {
            "supplier_instructions": "",
            "invoicing_instructions": "",
            "notes": ""
        },
        "shipping_details": {
            "shipping_method": "",
            "shipping_agent": "",
            "shipping_service": ""
        }
    }
    
    # Add items to the PO
    for item in items:
        new_item = {
            "customer_item_id": "",
            "manufacturer_item_id": item["item"],
            "item_description": "",
            "quantity": str(item["quantity"]),
            "unit_price": "",
            "total_price": ""
        }
        new_po["item"].append(new_item)
    
    # Fill in customer data if available
    if customer_data:
        new_po["customer"]["customer_id"] = customer_data.get("customer_id", "")
        new_po["customer"]["customer_name"] = customer_data.get("customer_name", "")
        new_po["customer"]["customer_address"] = customer_data.get("customer_address", "")
        new_po["customer"]["customer_city"] = customer_data.get("customer_city", "")
        new_po["customer"]["customer_country"] = customer_data.get("customer_country", "")
        
        # Set delivery info to same as customer info if available
        new_po["delivery"]["delivery_name"] = customer_data.get("customer_name", "")
        new_po["delivery"]["delivery_address"] = customer_data.get("customer_address", "")
        new_po["delivery"]["delivery_city"] = customer_data.get("customer_city", "")
        new_po["delivery"]["delivery_country"] = customer_data.get("customer_country", "")
        
        # Try to get additional info from po_data using customer_id
        customer_id = customer_data.get("customer_id", "")
        if customer_id:
            additional_po_data = fetch_additional_po_data(customer_id)
            if additional_po_data:
                # Update supplier info if available
                if "supplier" in additional_po_data:
                    new_po["supplier"] = additional_po_data["supplier"]
                
                # Update other fields from the additional PO data
                if "other_details" in additional_po_data:
                    new_po["other_details"] = additional_po_data["other_details"]
                
                if "shipping_details" in additional_po_data:
                    new_po["shipping_details"] = additional_po_data["shipping_details"]
    
    return new_po

def save_new_po_to_mongodb(new_po: Dict[str, Any]) -> str:
    """Save the new PO to MongoDB and return the inserted document ID."""
    try:
        client = MongoClient(MONGODB_CONNECTION_STRING)
        db = client["temp_data_2"]
        
        collection = db["test1"]
        
        result = collection.insert_one(new_po)
        
        print(f"Saved new PO to MongoDB with ID: {result.inserted_id}")
        return str(result.inserted_id)
    
    except Exception as e:
        print(f"MongoDB Error when saving new PO: {str(e)}")
        return ""
    finally:
        if 'client' in locals():
            client.close()

def mongo_to_serializable(obj):
    if isinstance(obj, dict):
        return {k: mongo_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [mongo_to_serializable(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj

def merge_po_data(email_items: List[Dict[str, Any]], mongodb_data: Dict[str, Any]) -> Dict[str, Any]:
    mongodb_data = mongo_to_serializable(mongodb_data)
    
    merged_data = json.loads(json.dumps(mongodb_data))
    
    if "item" in merged_data:
        merged_data["item"] = email_items
    
    elif "po" in merged_data:
        if isinstance(merged_data["po"], dict) and "po_number" in merged_data["po"]:
            if "item" in merged_data:
                merged_data["item"] = email_items
            else:
                merged_data["item"] = email_items
    
    elif "sales_order" in merged_data:
        so_data = merged_data["sales_order"]
        if "order_details" in so_data:
            if "item_list" in so_data["order_details"]:
                so_data["order_details"]["item_list"] = email_items
            else:
                so_data["order_details"]["item_list"] = email_items
        else:
            so_data["order_details"] = {"item_list": email_items}
    
    elif "header_information" in merged_data:
        if "order_details" in merged_data:
            if "item_list" in merged_data["order_details"]:
                merged_data["order_details"]["item_list"] = email_items
            else:
                merged_data["order_details"]["item_list"] = email_items
        else:
            merged_data["order_details"] = {"item_list": email_items}
    
    return merged_data

def process_email(email_text: str) -> Dict[str, Any]:
    regex_extract = extract_po_with_regex(email_text) or {"po_number": "", "is_reference_po": True, "items": [], "quantities": []}
    llm_extract = extract_po_with_llm(email_text) or {"po_number": "", "is_reference_po": True, "items": [], "quantities": []}
    
    combined_extract = {
        "po_number": regex_extract.get("po_number", "") or llm_extract.get("po_number", ""),
        "is_reference_po": regex_extract.get("is_reference_po", True) and llm_extract.get("is_reference_po", True),
        "items": [],
        "quantities": []
    }
    
    all_items = set()
    item_qty_map = {}
    
    for i, item in enumerate(regex_extract.get("items", [])):
        if item not in all_items and i < len(regex_extract.get("quantities", [])):
            all_items.add(item)
            item_qty_map[item] = regex_extract["quantities"][i]
    
    for i, item in enumerate(llm_extract.get("items", [])):
        if item not in all_items and i < len(llm_extract.get("quantities", [])):
            all_items.add(item)
            item_qty_map[item] = llm_extract["quantities"][i]
    
    combined_extract["items"] = list(all_items)
    combined_extract["quantities"] = [item_qty_map[item] for item in combined_extract["items"]]
    
    po_number = combined_extract["po_number"]
    is_reference_po = combined_extract["is_reference_po"]
    
    if not po_number:
        return {"error": "No PO number found in email"}
    
    mongodb_data = fetch_po_data_from_mongodb(po_number)
    
    email_item_objects = []
    for i, item in enumerate(combined_extract["items"]):
        if i < len(combined_extract["quantities"]):
            email_item_objects.append({
                "item": item,
                "quantity": combined_extract["quantities"][i]
            })
    
    if mongodb_data:
        merged_data = merge_po_data(email_item_objects, mongodb_data)
        return {"po_data": merged_data, "is_existing_po": True}
    elif is_reference_po:
        # Create new PO since reference PO wasn't found
        structured_items = []
        for i, item in enumerate(combined_extract["items"]):
            if i < len(combined_extract["quantities"]):
                structured_items.append({
                    "item": item,
                    "quantity": combined_extract["quantities"][i]
                })
        
        new_po = create_new_po_from_email(po_number, email_text, structured_items)
        doc_id = save_new_po_to_mongodb(new_po)
        
        if doc_id:
            return {"po_data": new_po, "is_existing_po": False, "new_doc_id": doc_id}
        else:
            return {"error": "Failed to save new PO to MongoDB"}
    else:
        # For new PO from email
        structured_items = []
        for i, item in enumerate(combined_extract["items"]):
            if i < len(combined_extract["quantities"]):
                structured_items.append({
                    "item": item,
                    "quantity": combined_extract["quantities"][i]
                })
        
        new_po = create_new_po_from_email(po_number, email_text, structured_items)
        doc_id = save_new_po_to_mongodb(new_po)
        
        if doc_id:
            return {"po_data": new_po, "is_existing_po": False, "new_doc_id": doc_id}
        else:
            return {"error": "Failed to save new PO to MongoDB"}

def main(email_text: str) -> Dict[str, Any]:
    try:
        result = process_email(email_text)

        if "error" in result:
            return {
                "PO_Found": False,
                "Is_New_PO": False,
                "Is_Reference_PO": False,
                "PO_Number": None,
                "Items": [],
                "MongoDB_Data": {}
            }

        is_existing_po = result.get("is_existing_po", False)
        po_data = result.get("po_data", {})
        po_number = po_data.get("po", {}).get("po_number") or po_data.get("purchase_order") or ""

        # Ensure it's safe to cast to int
        try:
            po_number_val = int(po_number)
        except (ValueError, TypeError):
            po_number_val = po_number

        return {
            "PO_Found": True,
            "Is_New_PO": not is_existing_po,
            "Is_Reference_PO": po_data.get("is_reference_po", True),
            "PO_Number": po_number_val,
            "Items": po_data.get("item", []),
            "MongoDB_Data": json.loads(json.dumps(po_data, cls=MongoJSONEncoder))
        }

    except Exception as e:
        return {
            "PO_Found": False,
            "Is_New_PO": False,
            "Is_Reference_PO": False,
            "PO_Number": None,
            "Items": [],
            "MongoDB_Data": {},
            "error": f"Processing error: {str(e)}"
        }


# if __name__ == "__main__":
#     # Direct email text input
#     email_text = """use reference po for new order
#     From: aslam <aslam@gmail.com>
#     Subject: PO L21335
    
#     Hello,
#     Please process the following order:
#     PO number: L21335
#     Items:
#     - stainless steel rod bar: 110 units
#     - iron rod bar: 1500 units
    
#     Thank you,
#     Customer
#     """
    
#     result = main(email_text)
#     print(json.dumps(result, indent=2, cls=MongoJSONEncoder))