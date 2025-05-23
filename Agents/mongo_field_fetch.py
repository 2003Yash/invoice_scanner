import pymongo
import sys
import os
from pymongo import MongoClient
from bson.objectid import ObjectId
from typing import List, Dict, Any, Optional
import logging
import json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Agents.data_fields_structuring_agent import group_like_wise_data_fields

def get_schema_by_org_and_table(
    mongo_uri: str,
    db_name: str,
    coll_name: str,
    organization_id: str,
    table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a document from MongoDB that matches the specified organization_id and table_name.
    
    Args:
        mongo_uri (str): MongoDB connection URI
        db_name (str): Database name
        coll_name (str): Collection name
        organization_id (str): Organization ID to match
        table_name (str): Table name to match
        
    Returns:
        Optional[Dict[str, Any]]: The matching document, or None if not found
        
    Raises:
        Exception: If there is an error connecting to MongoDB or executing the query
    """
    try:
        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[coll_name]
        
        # Create query filter
        query = {
            "org_id": organization_id,
            "table_name": table_name
        }
        
        # Execute query and get document
        document = collection.find_one(query)
        
        # Close connection
        client.close()
        
        return document
    
    except Exception as e:
        logging.error(f"Error retrieving document: {str(e)}")
        raise
        

def extract_fields(data) -> List[Dict[str, Any]]:
    """
    Extracts fields data from input which can be:
    - A JSON string representing a complete document or just fields list
    - A dictionary representing a complete document (including MongoDB output)
    - A list already containing fields
    
    Args:
        data: Input data that may be a JSON string, dict, or list
        
    Returns:
        List[Dict[str, Any]]: The extracted fields data
        
    Raises:
        ValueError: If the input format is invalid or fields cannot be extracted
    """
    # Debug: Print what we received
    print("DEBUG: Type of input data:", type(data))
    print("DEBUG: Input data keys (if dict):", list(data.keys()) if isinstance(data, dict) else "Not a dict")
    print("DEBUG: First few characters of data:", str(data)[:200] + "..." if len(str(data)) > 200 else str(data))
    
    # Convert string input to Python object if needed
    if isinstance(data, str):
        try:
            # Try to eval first for Python literal syntax (with ObjectId, datetime)
            try:
                # Add necessary context for eval
                context = {
                    'ObjectId': ObjectId,
                    'datetime': datetime
                }
                data = eval(data, {"__builtins__": {}}, context)
            except (SyntaxError, NameError):
                # Fall back to json if eval fails
                data = json.loads(data)
        except Exception as e:
            raise ValueError(f"Invalid input string: {str(e)}")
    
    # Case 1: Input is already a list of fields
    if isinstance(data, list):
        # Validate that it looks like a list of field objects
        if all(isinstance(item, dict) and 'field_key' in item for item in data):
            return data
    
    # Case 2: Input is a dictionary (complete document)
    elif isinstance(data, dict):
        # Check if it's a document with fields
        if 'fields' in data and isinstance(data['fields'], list):
            return data['fields']
        
        # Debug: Print all keys in the document to help identify the correct field
        print("DEBUG: All keys in the document:", list(data.keys()))
        
        # Check for common variations of field names
        possible_field_keys = ['fields', 'field_list', 'schema', 'columns', 'attributes', 'properties']
        for key in possible_field_keys:
            if key in data and isinstance(data[key], list):
                print(f"DEBUG: Found potential fields under key '{key}'")
                return data[key]
        
        # If no standard field key found, check if any value is a list that looks like fields
        for key, value in data.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                # Check if the first item has field-like properties
                first_item = value[0]
                if any(field_prop in first_item for field_prop in ['field_key', 'name', 'column_name', 'key']):
                    print(f"DEBUG: Found potential fields under key '{key}' based on structure")
                    return value
    
    # If we get here, the format wasn't recognized
    raise ValueError("Could not extract fields from the input. Expected a JSON document with 'fields' key or a list of field objects.")

def extract_json_structure(input_list):
    """
    Extract fields from input list where is_active is True,
    preserving the structure of the data.
    
    Args:
        input_list (list): List of dictionaries representing JSON data
        
    Returns:
        dict: JSON structure with extracted fields
    """
    result = {}
    
    for item in input_list:
        # Skip if not active for extraction
        if not item.get('is_active', False):
            continue
            
        field_key = item.get('field_key')
        field_type = item.get('field_type')
        children = item.get('children')
        
        # Handle different field types
        if field_type == 'array' and children:
            # Create a list with one item representing the structure of array elements
            child_structure = {}
            for child in children:
                if child.get('is_active', False):
                    child_key = child.get('field_key')
                    child_structure[child_key] = ""
            
            result[field_key] = [child_structure]
        else:
            # For non-array fields, just add an empty string
            result[field_key] = ""
    
    return result



def get_data_fields():
    """
    Retrieves data fields for the specified organization and table and optionally saves to JSON file
    
    Args:
        organisation_id (str): Organization ID to query
        table_name (str): Table name to query
        output_file (str, optional): If provided, saves the output to this JSON file
        
    Returns:
        dict: The extracted data fields
    """
    # Example connection parameters (replace with your actual values)
    mongo_url = "mongodb+srv://yaswanth:3GjNnOYbmNxbn0xN@cluster0.b6mzjd0.mongodb.net/"
    db_name = "temp_data"
    coll_name = "business-object"
    organisation_id = "Easework"
    table_name = "po_data"
    output_file = "purchase_order_data_fields.json"
    
    try:
        # Get documents with the specified user_id
        document = get_schema_by_org_and_table(mongo_url, db_name, coll_name, organisation_id, table_name)
        
        # Debug: Check if document was found
        if document is None:
            print(f"DEBUG: No document found for organization_id='{organisation_id}' and table_name='{table_name}'")
            return None
        else:
            print(f"DEBUG: Document found with keys: {list(document.keys())}")
            
    except Exception as e:
        print(f"Error: {e}")
        return None

    fields = extract_fields(document)
    data_fields = extract_json_structure(fields)
    
    # Extract items array if present
    items_array = None
    if "item" in data_fields and isinstance(data_fields["item"], list):
        items_array = data_fields["item"]
        
    # Create a copy of data_fields without the items array
    non_item_fields = {k: v for k, v in data_fields.items() if k != "item"}
    grouped_fields = group_like_wise_data_fields(non_item_fields)
    
    # Create the final output by combining grouped fields and items array
    final_output = grouped_fields
    if items_array:
        final_output["item"] = items_array
    
    # Save to JSON file if output_file is provided
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_output, f, indent=4)
            print(f"Data fields successfully saved to {output_file}")
        except Exception as e:
            print(f"Error saving data to JSON file: {str(e)}")
    
    return final_output


# Example usage
if __name__ == "__main__":
    # Define parameters
    organisation_id = "Easework"
    table_name = "po_data"
    output_file = "purchase_order_data_fields.json"
    
    # Get data fields and save to JSON file
    data = get_data_fields()
    
    if data:
        # Print the data to console for verification
        print("Data fields extracted:")
        print(json.dumps(data, indent=4))
    else:
        print("No data could be extracted.")
