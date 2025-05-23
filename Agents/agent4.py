import json
from bson import ObjectId
import re
import datetime
from typing import Dict, List, Optional, Union, Any
import sys
import os
from pymongo import MongoClient
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_models.gemini_client import get_gemini_response
from prompt_library.gemini import agent4_prompt


class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


def is_order_change_email(email_content: str) -> bool:
    if isinstance(email_content, dict):
        if "email_body" in email_content:
            email_content = email_content["email_body"]
        else:
            return False
    
    order_change_keywords = [
        "order change", 
        "changed the order", 
        "changed an order",
        "order modification", 
        "modified order",
        "update to order", 
        "order update",
        "order amendment", 
        "revised order",
        "order revision", 
        "order changed",
        "(Changed)",
        "revised po",
        "po revision",
        "po modification",
        "purchase order modification",
        "has been modified",
        "order has been changed"
    ]
    
    email_lower = email_content.lower()
    return any(keyword.lower() in email_lower for keyword in order_change_keywords)


def is_likely_po_number(number_str: str) -> bool:
    if re.search(r'\d{1,4}[-/\.]\d{1,4}[-/\.]\d{1,4}', number_str):
        return False
    
    if re.search(r'\(\d{3}\)\s*\d{3}-\d{4}', number_str):
        return False
    
    if re.search(r'\+\d', number_str):
        return False
    
    digit_count = sum(c.isdigit() for c in number_str)
    if digit_count < 5 or digit_count > 15:
        return False
    
    date_patterns = [
        r'\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}',
        r'\d{2,4}[-/\.]\d{1,2}[-/\.]\d{1,2}'
    ]
    if any(re.search(pattern, number_str) for pattern in date_patterns):
        return False
    
    return True


def extract_po_number(email_content: str) -> str:
    if isinstance(email_content, dict):
        if "email_body" in email_content:
            email_content = email_content["email_body"]
        else:
            return ""
    
    po_contexts = [
        (r"Purchase Order\s*(?:\(Changed\))?\s*(\d+)", 1),
        (r"PO\s*(?:Number|#|No\.?|No:)\s*[#:]?\s*(\d+)", 1),
        (r"Purchase Order\s*(?:Number|#|No\.?|No:)?\s*[#:]?\s*(\d+)", 1),
        (r"Order\s*(?:Number|#|No\.?|No:)\s*[#:]?\s*(\d+)", 1),
        (r"P\.?O\.?\s*(?:Number|#|No\.?|No:)?\s*[#:]?\s*(\d+)", 1),
        (r"(?:Subject|RE|FW):\s*.*?(?:PO|Purchase Order)\s*[#:]?\s*(\d+)", 1),
        (r"^PO:?\s*(\d+)$", 1, re.MULTILINE),
        (r"^Purchase Order:?\s*(\d+)$", 1, re.MULTILINE)
    ]
    
    for pattern_info in po_contexts:
        pattern = pattern_info[0]
        group = pattern_info[1]
        flags = pattern_info[2] if len(pattern_info) > 2 else 0
        
        match = re.search(pattern, email_content, flags)
        if match:
            po_candidate = match.group(group).strip()
            if is_likely_po_number(po_candidate):
                return po_candidate
    
    po_lines = []
    for line in email_content.split("\n"):
        if re.search(r'(?:PO|Purchase Order|Order Number)', line, re.IGNORECASE):
            po_lines.append(line)
    
    for line in po_lines:
        numbers = re.findall(r'(?<!\d)(\d{5,10})(?!\d)', line)
        for num in numbers:
            if is_likely_po_number(num):
                return num
    
    if "Version:" in email_content and "Purchase Order" in email_content:
        section = re.search(r'Purchase Order.*?Version:', email_content, re.DOTALL)
        if section:
            numbers = re.findall(r'(?<!\d)(\d{5,10})(?!\d)', section.group(0))
            for num in numbers:
                if is_likely_po_number(num):
                    return num
    
    return ""


def create_extraction_prompt(fields: str, email_content: str) -> str:
    return agent4_prompt.format(fields=fields, text=email_content)
    

def create_empty_response() -> Dict[str, Any]:
    timestamp = datetime.datetime.now().isoformat()
    empty_schema = {
        "po_change_exist": "false",
        "po_no": "",
        "recognized_changes": {},
        "extra_changes": {},
        "timestamp": timestamp,
    }
    return empty_schema


def parse_llm_output(response_text: str) -> Dict[str, Any]:
    if not response_text or not isinstance(response_text, str):
        return {}
    
    cleaned_text = response_text.strip()
    
    json_patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
        r'{[\s\S]*}',
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, cleaned_text)
        if matches:
            for potential_json in matches:
                try:
                    return json.loads(potential_json.strip())
                except json.JSONDecodeError:
                    continue
    
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        pass
    
    try:
        first_brace = cleaned_text.find('{')
        last_brace = cleaned_text.rfind('}')
        if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
            json_candidate = cleaned_text[first_brace:last_brace+1]
            return json.loads(json_candidate)
    except json.JSONDecodeError:
        pass
    
    return {}


def process_json_structure(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    timestamp = datetime.datetime.now().isoformat()
    result = {
        "po_change_exist": "true",
        "po_no": "",
        "recognized_changes": {},
        "extra_changes": {},
        "timestamp": timestamp
    }
    
    if "po_no" in parsed_data:
        result["po_no"] = parsed_data["po_no"]
    elif "purchase_order_number" in parsed_data:
        result["po_no"] = parsed_data["purchase_order_number"]
    elif "recognized_changes" in parsed_data and "purchase_order_number" in parsed_data["recognized_changes"]:
        result["po_no"] = parsed_data["recognized_changes"]["purchase_order_number"]
    
    if "recognized_changes" in parsed_data and isinstance(parsed_data["recognized_changes"], dict):
        result["recognized_changes"] = parsed_data["recognized_changes"]
    
    if "extra_changes" in parsed_data and isinstance(parsed_data["extra_changes"], dict):
        result["extra_changes"] = parsed_data["extra_changes"]
    
    if "recognized_changes" in parsed_data and "item" in parsed_data["recognized_changes"]:
        result["recognized_changes"]["item"] = parsed_data["recognized_changes"]["item"]
    
    if not result["recognized_changes"] and not result["extra_changes"]:
        for key, value in parsed_data.items():
            if isinstance(value, dict) and "previous_value" in value and "new_value" in value:
                result["recognized_changes"][key] = value
            elif key == "item" and isinstance(value, list):
                result["recognized_changes"]["item"] = value
    
    return result


def store_in_mongodb(data: Dict[str, Any]) -> None:
    try:
        client = MongoClient("mongodb+srv://aslam:ktlxaqeuMm8wAnP4@cluster0.b6mzjd0.mongodb.net/")
        db = client["temp_data"]
        collection = db["po_change_logs"]
        
        collection.insert_one(data)
        print("Data successfully stored in MongoDB")
        print(data)
        
    except Exception as e:
        print(f"Error storing data in MongoDB: {str(e)}")


def flatten_purchase_order(json_file_path):
    try:
        with open(json_file_path, 'r') as file:
            data = json.load(file)
        
        result = {}
        
        items = data.get('item', [])
        
        for category in data:
            if category != 'item':
                nested_dict = data[category]
                
                for key, value in nested_dict.items():
                    result[key] = value
        
        result['item'] = items
        
        return result
    
    except FileNotFoundError:
        print(f"Error: File '{json_file_path}' not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Unable to parse '{json_file_path}' as JSON.")
        return {}
    except Exception as e:
        print(f"Error: {str(e)}")
        return {}


def extract_changes_from_email(email_text: str) -> Dict[str, Any]:
    recognized_changes = {}
    
    change_patterns = [
        (r"price updated to \$(\d+\.\d+)", "price", "unit_price"),
        (r"quantity updated to (\d+)", "quantity", "quantity"),
        (r"delivery date changed to (\d+ \w+ \d{4})", "delivery_date", "delivery_date"),
        (r"(?:Edited|Changed).*?(\d+ \w+ \d{4}).*?(\d+ \w+ \d{4})", "delivery_date", "delivery_date")
    ]
    
    for pattern_info in change_patterns:
        pattern = pattern_info[0]
        change_type = pattern_info[1]
        field_name = pattern_info[2]
        
        matches = re.findall(pattern, email_text, re.IGNORECASE)
        if matches:
            if change_type == "delivery_date" and len(matches[0]) > 1:
                previous_date, new_date = matches[0]
                recognized_changes[field_name] = {
                    "previous_value": previous_date.strip(),
                    "new_value": new_date.strip()
                }
            else:
                if field_name in ["quantity", "unit_price"]:
                    recognized_changes[field_name] = {
                        "previous_value": "",
                        "new_value": matches[0]
                    }
    
    if "Line Items" in email_text:
        item_section = re.search(r'Line Items.*?(?:Transport Terms|Sub-total)', email_text, re.DOTALL)
        if item_section:
            item_text = item_section.group(0)
            if "Edited" in item_text:
                item_changes = []
                
                line_items = re.findall(r'Line #\s*(\d+).*?(\$[\d.,]+)\s+USD.*?(\$[\d.,]+)\s+USD', item_text, re.DOTALL)
                for line in line_items:
                    line_number, unit_price, subtotal = line
                    item_changes.append({
                        "line_number": line_number.strip(),
                        "unit_price": {
                            "previous_value": "",
                            "new_value": unit_price.strip()
                        }
                    })
                
                if item_changes:
                    recognized_changes["item"] = item_changes
    
    return recognized_changes


def extract_data_from_email(email_content: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    email_text = ""
    if isinstance(email_content, dict):
        email_text = email_content.get("email_body", "")
        if "attachment_data" in email_content:
            email_text += "\n\n" + email_content["attachment_data"]
    else:
        email_text = email_content

    po_change_exist = is_order_change_email(email_text)
    po_no = extract_po_number(email_text)

    if not po_change_exist:
        empty_response = create_empty_response()
        empty_response["po_no"] = po_no
        store_in_mongodb(empty_response)
        return empty_response

    fields = {}
    try:
        fields = flatten_purchase_order('purchase_order_data_fields.json')
    except Exception as e:
        print(f"Error loading fields: {str(e)}")
        fields = {"item": []}
    
    # Try to get a response from Gemini API
    max_retries = 3
    retry_delay = 5
    response_text = ""
    
    for attempt in range(max_retries):
        try:
            prompt = create_extraction_prompt(str(fields), email_text)
            print(f"Attempt {attempt+1} to get Gemini response")
            response_text = get_gemini_response(prompt) or ""
            if response_text:
                break
        except Exception as e:
            print(f"Error in Gemini API call (attempt {attempt+1}): {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
    
    # Parse the response if we got one
    parsed_data = parse_llm_output(response_text)
    
    # If Gemini failed or returned bad data, extract changes directly from email
    if not parsed_data or not parsed_data.get("recognized_changes"):
        print("Using fallback extraction method...")
        recognized_changes = extract_changes_from_email(email_text)
        
        transformed_data = {
            "po_change_exist": "true",
            "po_no": po_no,
            "recognized_changes": recognized_changes,
            "extra_changes": {},
            "timestamp": datetime.datetime.now().isoformat()
        }
    else:
        # Process the parsed data into the required structure
        transformed_data = process_json_structure(parsed_data)
        # Ensure the PO number is set
        if not transformed_data["po_no"]:
            transformed_data["po_no"] = po_no
    
    store_in_mongodb(transformed_data)
    return transformed_data


def process_email(email_input: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    return extract_data_from_email(email_input)


def main():
    example_email = """
Baker Hughes changed an order
If more than one email address is associated with your organization for PO delivery, then the copy of this purchase order would be sent to them as well.
Message from your customer Baker Hughes
In need of training on how to process your order and set up your Ariba Network account, view the Frequently Asked Questions at https://support.ariba.com/item/view/193052 or visit the Supplier Information Portal at https://support.ariba.com/item/view/191407

Process order		
SAP Business Network

This purchase order was delivered by SAP Business Network.   For more information about Ariba and SAP Business Network, visit https://www.ariba.com.

From:
OS Operations, LLC
Bently Parkway South-1631
Minden, NV 89423
United States
Phone:   
Fax:   
To: 
Swagelok Northern California
3393 W Warren Ave.
Fremont, CA 94538
United States
Phone: +1 (510) 9332500
Fax: +1 (510) 933-2525
Email: info@norcal.swagelok.com
Purchase Order
(Changed)
5052437547
Amount:
 $
109.28
 USD
Version: 3
 
Comments
Header Text (Print&Ariba) :FW17 24Apr25 Revised order, price updated to $109.28 each, PO resent **PLEASE DO NOT DUPLICATE**. WSZF
Contact Information
Supplier Address
IMD FLUID SYSTEM TECHNOLOGIES INC
3393 WEST WARREN AVE
FREMONT, CA 94538-6424
United States
Email:  Susan.Juliano@norcal.swagelok.com
Phone:  +1 () 5109336222
Fax:   
Address ID:  0005519317
Buyer Headquarter Address
Email:  Wendy.Zuniga@Bakerhughes.com
Address ID:  1000
Supplier ID:	0005519317
Other Information
Purchase Group:	610
Purchase Organization:	0001
Party Additional ID:	0005519317
Plant:	1000
Requester:	zuniwen
Place of Supply:	US-NV
PO Special Instructions:	This Purchase Order is governed by the Terms and Conditions of Purchase and other Purchase requirements listed in the full PO PDF attachment below.
Attachments
5052437547.pdf (application/pdf; charset=UTF-8)  
 
Ship All Items To
OS Operations, LLC
1631 Bently Parkway South
MINDEN, NV 89423
United States
Ship To Code:  1000
Email:  Wendy.Zuniga@Bakerhughes.com
Location Code:	1000
Storage Location ID:	0276
 	
Bill To
OS Operations, LLC
Bently Parkway South-1631
Minden, NV 89423
United States
Phone:   
Fax:   
Buyer ID:	1000
 	
Deliver To
Line Items
Line #	No. Schedule Lines	Change	Part # / Description		Customer Part #		Type	Return	Revision Level	Qty (Unit)	Need By	Unit Price	Subtotal	Customer Location
10
1	Edited	Not Available		181018B	 	
Material
 	NC	1.000 (EA)	24 Jun 2025
10 Apr 2025	$109.28 USD	$109.28 USD	 
 	 	 	
MISC PRES GUAGE 100PSI 1/4T SWG ^
 	 	 
Control Keys
Order Confirmation:  allowed
Ship Notice:  not allowed
Invoice:  is not ERS
Schedule Lines
Schedule Line #	Change	Delivery Date	Ship Date	Quantity (Unit)	Customer Proposed Qty (Unit)	Customer Proposed Delivery Date
1	Edited	24 Jun 2025 1:00 PM PDT
10 Apr 2025 1:00 PM PDT	 	1.000 (EA)		
Other Information
Item Category:	Standard Order
Account Category:	I
PurchaseOrg:	0001
External Line Number:	10
No. Schedule Lines:	NC
Estimated days for inspection:	2
Manufacturer Part ID:	PGI-63C-PG160-LAQ1
Manufacturer Name:	0002000740
Classification Domain:	ERPCommodityCode
Classification Code:	MPN PARTS
Classification Domain:	ERPCommodityCodeDescription
Classification Code:	Fittings
Transport Terms Information
Order submitted on: Tuesday 15 Apr 2025 1:00 PM GMT-07:00
Received by SAP Business Network on: Thursday 24 Apr 2025 9:02 AM GMT-07:00
This Purchase Order was sent by Baker Hughes AN01015927430 and delivered by SAP Business Network.
 
Sub-total:
 $
109.28
 USD
Total Tax:
 $
0.00
 USD
Est. Grand Total:
 $
109.28
 USD
Process order	
About this email
If you have any questions, contact Baker Hughes. If you're not the correct person to receive this email, forward it to the appropriate person in your company.
Note: All transactions relating to your customer's purchase orders are solely between you and your customer and are subject to the terms of your existing agreement(s) with your customer. Ariba is not an agent for your customer, and is not responsible for anything contained in the purchase order submitted on behalf of your customer.
   
Go Mobile
Ariba, Inc., 3420 Hillview Ave, Bldg3, Palo Alto, CA 94304, USA
SAP Business Network Privacy Statement | Ariba Data Policy | Help Center

--
Thank you,

Bree Turpin
Customer Service Manager
"""

    extracted_data = process_email(example_email)
    print(json.dumps(extracted_data, indent=2, cls=MongoJSONEncoder))


if __name__ == "__main__":
    main()