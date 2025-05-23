import json
import re
import pymongo
from pymongo import MongoClient
from typing import Optional, Dict, Any
from bson.objectid import ObjectId
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_models.gemini_client import get_gemini_response
from prompt_library.gemini import get_amendment_prompt, get_extra_changes_amendment_prompt
from datetime import datetime
import copy
from Agents.agent4 import process_email

uri = "mongodb+srv://yaswanth:3GjNnOYbmNxbn0xN@cluster0.b6mzjd0.mongodb.net/"
db_name = "temp_data"
coll_name = "po_data"

def upload_json_to_mongodb(json_list):
    """
    Upload JSON document(s) to a MongoDB collection.
    
    Args:
        mongo_uri (str): MongoDB connection URI
        db_name (str): Database name
        coll_name (str): Collection name
        json_list (list): List of JSON documents to upload
        
    Returns:
        dict: Result of the upload operation with status and details
    """
    try:
        # Connect to MongoDB
        client = MongoClient(uri)
        db = client[db_name]
        collection = db[coll_name]
        
        # Track results
        results = {
            "status": "success",
            "inserted_count": 0,
            "inserted_ids": [],
            "details": []
        }
        
        # Process each document in the list
        for doc in json_list:
            # Make a deep copy to avoid modifying the original
            document = copy.deepcopy(doc)
            
            # Update the 'updated_at' field with current timestamp
            # but preserve the 'created_at' field if it exists
            current_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"
            document['updated_at'] = current_time
            
            # Insert the document
            result = collection.insert_one(document)
            
            # Track result details
            doc_result = {
                "inserted_id": str(result.inserted_id),
                "success": True
            }
            
            results["inserted_count"] += 1
            results["inserted_ids"].append(str(result.inserted_id))
            results["details"].append(doc_result)
        
        # Close the connection
        client.close()
        
        return results
    
    except Exception as e:
        # Handle errors
        return {
            "status": "error",
            "message": f"Error uploading documents: {str(e)}",
            "error": str(e)
        }
    
def get_po_document_from_change_log(uri, db_name, coll_name,
    change_log_document: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Checks if po_change_exist is True in the change log document, then extracts
    the corresponding PO document from MongoDB by matching po_no with purchase_order_number.
    
    Args:
        change_log_document (Dict[str, Any]): The change log document containing po_change_exist and po_no
        mongo_uri (str): MongoDB connection string
        database_name (str): Name of the database to search in
        collection_name (str): Name of the collection to search in
        
    Returns:
        Optional[Dict[str, Any]]: The complete PO document if found and po_change_exist is True, None otherwise
    """
    try:
        # Check if po_change_exist is True
        # Note: Handling both possible key names (po_change_exist and po_change_exists)
        po_change_exists = change_log_document.get("po_change_exist", False) or change_log_document.get("po_change_exists", False)
        
        if not po_change_exists:
            logging.info("No PO change exists in the change log document")
            return None
        
        # Extract po_no from the change log document
        po_number = change_log_document.get("po_no")
        if not po_number:
            logging.error("PO number not found in change log document")
            return None
        
        # Connect to MongoDB
        client = MongoClient(uri)
        db = client[db_name]
        collection = db[coll_name]
        
        # Query for the document with matching purchase order number
        query = {"purchase_order_number": po_number}
        matched_docs = collection.find(query)

        documents = list(matched_docs)
        
        # Close the MongoDB connection
        client.close()
        
        if not documents:
            logging.info(f"PO document with number {po_number} not found in the database")
            
        return documents
    except Exception as e:
        logging.error(f"Error processing change log or finding purchase order: {str(e)}")
        return None

def get_latest_version(documents):
    """
    Function to get the latest version document from a list of document dictionaries.
    Version format is expected to be 'V1', 'V2', 'V3', etc.
    
    Args:
        documents (list): List of document dictionaries
        
    Returns:
        dict: Document dictionary with the latest version
    """
    # If only one document is present, return it directly
    if len(documents) <= 1:
        return documents[0] if documents else None
    
    # Function to extract the version number from a version string (e.g., 'V1' -> 1)
    def extract_version_number(doc):
        version = doc.get('version', '')
        if version and version.startswith('V'):
            try:
                return int(version[1:])
            except ValueError:
                return 0
        return 0
    
    # Sort documents by version number (descending) and return the first one
    return sorted(documents, key=extract_version_number, reverse=True)[0]


def extract_recognized_changes(json_data):
    # Check if recognized_changes exists in the input JSON data
    if "recognized_changes" in json_data:
        return json_data["recognized_changes"]
    return {}

def extract_extra_changes(json_data):
    # Check if recognized_changes exists in the input JSON data
    if "extra_changes" in json_data:
        return json_data["extra_changes"]
    return {}

def extract_json_from_string(text):
    """
    Extract complete JSON objects from a string and return them as a list of dictionaries.
    
    Args:
        text (str): The input string containing JSON objects
        
    Returns:
        list: A list of dictionaries parsed from the JSON objects found in the string
    """
    # List to store extracted JSON objects
    extracted_json_objects = []
    
    # First, let's try to find code blocks with json
    code_block_pattern = r'```(?:json)?\s*({[\s\S]*?})\s*```'
    code_blocks = re.findall(code_block_pattern, text)
    
    # Process any code blocks found
    for block in code_blocks:
        try:
            json_obj = json.loads(block)
            extracted_json_objects.append(json_obj)
        except json.JSONDecodeError:
            pass  # Skip invalid JSON in code blocks
    
    # Find standalone JSON objects (not in code blocks)
    # We'll look for balanced pairs of { and }
    remaining_text = re.sub(code_block_pattern, '', text)  # Remove already processed code blocks
    
    # Track positions of potential complete JSON objects
    pos = 0
    while pos < len(remaining_text):
        # Find next opening brace
        start = remaining_text.find('{', pos)
        if start == -1:
            break
            
        # Keep track of brace nesting
        depth = 1
        end = start + 1
        
        # Find matching closing brace
        while end < len(remaining_text) and depth > 0:
            if remaining_text[end] == '{':
                depth += 1
            elif remaining_text[end] == '}':
                depth -= 1
            end += 1
            
        if depth == 0:  # We found a balanced JSON object
            potential_json = remaining_text[start:end]
            try:
                json_obj = json.loads(potential_json)
                extracted_json_objects.append(json_obj)
            except json.JSONDecodeError:
                pass  # Skip invalid JSON
                
        pos = end  # Move past this JSON object
    
    return extracted_json_objects

def upgrade_so_versions(json_list):
    """
    Process a list of JSON objects according to these rules:
    - If an item has a non-empty 'so_number' field (not empty string, None, or 'None'):
        1. Remove the '_id' field
        2. Increment the 'version' field (from V1 to V2, V2 to V3, etc.)
    - Otherwise, leave the item unchanged
    
    Args:
        json_list (list): List of dictionaries representing JSON objects
        
    Returns:
        list: Processed list of dictionaries
    """
    result = []
    
    for item in json_list:
        # Create a copy of the item to avoid modifying the original
        processed_item = item.copy()
        
        # Check if so_number exists and has a valid value
        so_number = processed_item.get('so_number')
        if so_number and so_number != '' and so_number != 'None' and so_number is not None:
            # Remove _id field if it exists
            if '_id' in processed_item:
                del processed_item['_id']
            
            # Increment version if it exists
            if 'version' in processed_item:
                current_version = processed_item['version']
                if current_version.startswith('V'):
                    try:
                        version_num = int(current_version[1:])
                        processed_item['version'] = f'V{version_num + 1}'
                    except ValueError:
                        # If version format is not as expected, leave it unchanged
                        pass
        
        result.append(processed_item)
    
    return result

def delete_document_by_id(id_value):
    """
    Delete a document from a MongoDB collection by its _id value.
    
    Args:
        mongo_uri (str): MongoDB connection URI
        db_name (str): Database name
        coll_name (str): Collection name
        id_value (str): The _id value of the document to delete
    
    Returns:
        dict: Result of the delete operation with status and message
    """
    try:
        # Connect to MongoDB
        client = MongoClient(uri)
        db = client[db_name]
        collection = db[coll_name]
        
        # Convert id_value to ObjectId if it's a string that looks like an ObjectId
        if isinstance(id_value, str) and len(id_value) == 24:
            try:
                id_query = ObjectId(id_value)
            except:
                # If conversion fails, use the original string
                id_query = id_value
        else:
            id_query = id_value
        
        # Delete the document
        result = collection.delete_one({"_id": id_query})
        
        # Close the connection
        client.close()
        
        # Check if document was deleted
        if result.deleted_count == 1:
            return {
                "status": "success",
                "message": f"Document with _id {id_value} successfully deleted.",
                "deleted_count": result.deleted_count
            }
        else:
            return {
                "status": "not_found",
                "message": f"No document found with _id {id_value}.",
                "deleted_count": 0
            }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error deleting document: {str(e)}",
            "error": str(e)
        }
    

def remove_null_data_fields(data):
    """
    Remove null values from a JSON object recursively.
    Null values are considered to be empty strings ('') or None.
    
    Args:
        data: JSON object (dict, list, or primitive)
    
    Returns:
        JSON object with null values removed
    """
    if isinstance(data, dict):
        # Create a new dictionary to store non-null values
        result = {}
        for key, value in data.items():
            # If value is an empty string or None, skip it
            if value == '' or value is None:
                continue
            # Recursively process nested objects
            processed_value = remove_null_data_fields(value)
            # Only add non-null values to the result
            if processed_value != '' and processed_value is not None:
                result[key] = processed_value
        return result
    elif isinstance(data, list):
        # Process each item in the list
        result = []
        for item in data:
            processed_item = remove_null_data_fields(item)
            if processed_item != '' and processed_item is not None:
                result.append(processed_item)
        return result
    else:
        # Return primitive values as is
        return data
    

change_log = {
  "_id": {
    "$oid": "6828702c4332c47835c2ed2e"
  },
  "po_change_exist": "true",
  "po_no": "9876543",
  "recognized_changes": {
    "DeliveryDate": {
      "previous_value": '',
      "new_value": "July 10, 2025"
    },
    "payment_terms": {
      "previous_value": "NET 30 CIP Carriage and insurance paid",
      "new_value": "Net 75 Days to pay the bill"
    },
    "tax_percentage": {
      "previous_value": '',
      "new_value": "0"
    },
    "instructions": {
      "previous_value": '',
      "new_value": "please add a invoice"
    },
  },
  "extra_changes": {
    "ShippingMethod": {
      "previous_value": '',
      "new_value": "Expedited"
    },
    "SupplierInstructions": {
      "previous_value": '',
      "new_value": "Please include PO number on all packages and documentation"
    },
    "InvoicingInstructions": {
      "previous_value": '',
      "new_value": "Reference PO 9876543 Version 2"
    },
    "Notes": {
      "previous_value": '',
      "new_value": "All other terms and conditions remain unchanged"
    }
  },
  "timestamp": "2025-05-17T16:46:59.789020"
}

po_data = {
  "_id": {
    "$oid": "6826d6d1ffb66489ba04393e"
  },
  "purchase_order_number": "9876543",
  "order_date": "22-APR-25",
  "quotation_number": "",
  "quotation_date": "",
  "payment_terms": "NET 30 CIP Carriage and insurance paid",
  "instructions": "Time is of the essence for this order and failure to comply with the delivery schedule as shown herein may be cause for termination. Early shipments are not acceptable unless Buyer's prior written approval is obtained. Early shipments are defined as any shipment received three (3) days in advance of the scheduled receipt date. A complete packing slip indicating Purchase Order number, KLA part number and/or item number must accompany each shipment. Unless otherwise specified on this PO, contact your responsible KLA buyer for preferred carrier information.",
  "customer_name": "KLA Corporation",
  "bill_to": "P.O. Box 54970\nSanta Clara, CA  95056-4970\nUnited States",
  "vendor_name": "SWAGELOK NORTHERN CALIFORNIA",
  "tax_percentage": "",
  "tax_amount": "",
  "shipping_charges": "",
  "total_amount": "378.16",
  "ship_to": "KLA - Victor Galande\nBuilding 5\nFive Technology Drive\nMilpitas CA 95035",
  "carrier": "",
  "item": [
    {
      "customer_item_id": "NA",
      "manufacturer_item_id": "SS-811-PC",
      "item_description": "Port Connector 1/2\"",
      "quantity": "5",
      "unit_price": "18.89",
      "total_price": "94.45"
    },
    {
      "customer_item_id": "NA",
      "manufacturer_item_id": "SS-8-TA-7-4",
      "item_description": "Female Tube Adapter 1/2TA x 1/4FNPT",
      "quantity": "3",
      "unit_price": "21.86",
      "total_price": "65.58"
    },
    {
      "customer_item_id": "NA",
      "manufacturer_item_id": "SS-810-3",
      "item_description": "Union Tee 1/2\"",
      "quantity": "3",
      "unit_price": "72.71",
      "total_price": "218.13"
    }
  ],
  "customer_id": "CUST434",
  "version": "V1",
  "intent_type": "new",
  "bucket_id": "bucket_2",
  "ticket_number": "ticket_14",
  "so_number": "so_214",
  "created_at": "2025-04-22T14:32:17.824Z",
  "updated_at": "2025-04-23T08:45:33.102Z",
  "is_priority": "True",
  "extra_changes": ""
}

def change_intent_type(json_data):
    for item in json_data:
        if 'intent_type' in item:
            item['intent_type'] = 'changed_po'
    return json_data


def process_amendment(change_log):

    # Get PO document from change log
    po_datas = get_po_document_from_change_log(uri, db_name, coll_name, change_log)
    po_data = get_latest_version(po_datas)
    print("Extracted PO to Amend")

    # extract datafields from json
    amendments = extract_recognized_changes(change_log)
    extra_changes = extract_extra_changes(change_log)

    # remove null valued datafields - to reduce llm hallucination
    amendments = remove_null_data_fields(amendments)
    extra_changes = remove_null_data_fields(extra_changes)

    # for recognised_changes
    prompt = get_amendment_prompt(amendments, po_data)
    print(prompt)
    result = get_gemini_response(prompt)
    print("Gemini response:", result)

    if result is None:
        print("❌ Gemini returned None for recognized_changes. Skipping amendment processing.")
        return

    updated_po_data = extract_json_from_string(result)
    print("Extracted JSON:", updated_po_data)

    # for extra_changes
    prompt2 = get_extra_changes_amendment_prompt(extra_changes, updated_po_data)
    print(prompt2)
    result2 = get_gemini_response(prompt2)
    print("Gemini response:", result2)

    if result2 is None:
        print("❌ Gemini returned None for extra_changes. Skipping amendment processing.")
        return

    updated_po_data = extract_json_from_string(result2)
    print("Extracted JSON:", updated_po_data)

    updated_po_data = change_intent_type(updated_po_data)

    updated_po_data = upgrade_so_versions(updated_po_data) 
    print(updated_po_data)

    # MONGO CONNECTION FOR AMENDMENT UPLOADS
    for item in updated_po_data:
        if isinstance(item, dict):
            if "_id" in item:
                print(f"About to delete: {item['_id']} and upload amended version in its place")
                delete_document_by_id(item['_id'])
                item.pop('_id', None)
                upload_json_to_mongodb([item])
            else:
                print("Uploading new version of purchase order")
                upload_json_to_mongodb([item])
        else:
            print("Item is not a dictionary")




# # Example usage:
# if __name__ == "__main__":
    
#     # # MongoDB connection details
#     # uri = "mongodb+srv://yaswanth:3GjNnOYbmNxbn0xN@cluster0.b6mzjd0.mongodb.net/"
#     # db_name = "temp_data"
#     # coll_name = "po_data"

#     process_amendment(change_log)
