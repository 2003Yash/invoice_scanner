import re
import os
import re
import logging
import cohere
from final import run, parse_response, parse_item_response
# from groq import Groq
# from dotenv import load_dotenv
# load_dotenv()
import json
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from models import *


logger = logging.getLogger(__name__)

template = """
## Instructions
Extract the PO number and quotation number from the following PO content.

Carefully analyze the content and extract the PO number and quotation number.

If QUOTATION NUMBER is not mentioned in the content, please put it as "N/A". Do not make any assumptions.

For PO number, please use the following format:
- PO number (for this consider order number and po number in the content.)
- Quotation number(Write NA if QUOTATION NUMBER is not mentioned in the content.)

After extracting the information, Strictly remove any special characters and replace them with an empty string.
Remove any unwanted \\ from the extracted information.
Strictly remove any unwanted blanck spaces in the response fields.

Return the output in JSON format.
{{
    "po": {{
        "po_number": "",
        "quotation_number": ""
    }}
}}

Input:
{po_content}
"""

def quotation_ponumber(input_text):
  
    prompt = PromptTemplate(
        input_variables=["po_content"],
        template=template
    )
    final_prompt = prompt.format(po_content=input_text)

    # Call the OpenAI API with LangChain's built-in run function
    response = parse_response(final_prompt)
    # print(response)

    output_parser = PydanticOutputParser(pydantic_object=POQuotationModel)

    # Parse the response with the output parser
    parsed_response = output_parser.parse(response)
    result = parsed_response.json()
    print(result)
    return result

# answer = quotation_ponumber(input)

template2 = """
## Instructions
Extract and classify the Customer information and Supplier information from the following PO content, using the following rules:

Classification Rules:
1. Customer (Buyer) indicators:
   - Look for terms like: "Bill To", "Ship To", "Buyer", "Customer", "Purchaser", "Sold To" or their equivalents in other languages
   - Usually appears first or at the top of the PO
   - Is the entity receiving/paying for goods/services

2. Supplier (Seller) indicators:
   - Look for terms like: "Vendor", "Seller", "From", "Supplier", "Company Details" or their equivalents in other languages
   - Usually provides the goods/services
   - Often includes tax ID/registration numbers
   - May include bank details

Data Extraction Rules:
1. For each address component:
   - Remove special characters and replace with empty string
   - Remove any escape characters (\)
   - Trim all unnecessary spaces
   - If information is missing, return empty string
   - Standardize formatting across different languages

2. Required Fields Format:
Customer Information:
- Customer name: Extract full legal name
- Customer address: Extract street address and building number
- Customer city: Extract city/municipality
- Customer country: Extract country name

Supplier Information:
- Supplier name: Extract full legal name
- Supplier address: Extract street address and building number
- Supplier city: Extract city/municipality
- Supplier country: Extract country name

Return the output in this exact JSON format:
{{
    "customer": {{
        "customer_name": "",
        "customer_address": "",
        "customer_city": "",
        "customer_country": ""
    }},
    "supplier": {{
        "supplier_name": "",
        "supplier_address": "",
        "supplier_city": "",
        "supplier_country": ""
    }}
}}

If a field cannot be determined with certainty, leave it as an empty string rather than making assumptions.

Input:
{po_content}
"""

def customer_supplier_information(input_text):
    prompt = PromptTemplate(
        input_variables=["po_content"],
        template=template2
    )
    final_prompt = prompt.format(po_content=input_text)

    # Call the OpenAI API with LangChain's built-in run function
    response = parse_response(final_prompt)
    # print(response)

    output_parser = PydanticOutputParser(pydantic_object=CustomerSupplierModel)

    # Parse the response with the output parser
    parsed_response = output_parser.parse(response)
    result = parsed_response.json()
    print(result)
    return result

# answer = customer_supplier_information(input)

template3 = """
## Instructions
Extract the Delivery information from the following PO content using the following rules:

Classification Rules for Delivery Information:
1. Primary Search - Look for sections marked with indicators such as:
   - "Deliver To"
   - "Ship To"
   - "Delivery Address"
   - "Shipping Address"
   - "Consignee"
   - "Point of Delivery"
   - "Destination"
   Or their equivalents in other languages

2. Context clues for delivery information:
   - Often appears after buyer/customer information
   - May include delivery instructions or timing
   - Could contain contact person for delivery
   - Might include loading/unloading times
   - May have special handling instructions
   - Could include warehouse/dock numbers

3. Fallback Logic:
   - If no explicit delivery information is found, use customer information as delivery address
   - Look for customer information marked with:
     * "Bill To"
     * "Customer"
     * "Buyer"
     * "Sold To"
   - When using customer info as fallback, maintain the same formatting rules

Data Extraction and Cleaning Rules:
1. For each address component:
   - Remove all special characters and replace with empty string
   - Remove any forward slashes (/) or backslashes (\)
   - Remove all unnecessary spaces and trim results
   - If information is missing or uncertain, return empty string
   - Standardize formatting across different languages

2. Required Fields Format:
Delivery Information:
- Delivery name: Extract receiving entity name or department (or customer name if fallback)
- Delivery address: Extract complete street address, building number, floor/unit if available
- Delivery city: Extract city/municipality/town
- Delivery country: Extract country name

Special Handling Instructions:
1. If multiple delivery addresses exist, extract the primary/first listed address
2. For warehouse deliveries, include warehouse number in delivery address
3. For healthcare/sensitive deliveries, maintain any special handling codes in delivery name
4. When using customer information as fallback:
   - Clearly transfer all available customer address components
   - Maintain the same cleaning and formatting rules
   - Ensure all available fields are populated

Return the output in this exact JSON format:
{{
    "delivery": {{
        "delivery_name": "",
        "delivery_address": "",
        "delivery_city": "",
        "delivery_country": ""
    }}
}}

Important Notes:
- First attempt to find explicit delivery information
- If no delivery information is found, use customer information as delivery address
- If neither delivery nor customer information is found, return empty strings
- Preserve department names or care-of information in delivery name field
- Include any relevant building/floor/unit numbers in delivery address
- If city contains postal code, separate and include only city name

Input:
{po_content}
"""

def delivery_information(input_text):
  
    prompt = PromptTemplate(
        input_variables=["po_content"],
        template=template3
    )
    final_prompt = prompt.format(po_content=input_text)

    # Call the OpenAI API with LangChain's built-in run function
    response = parse_response(final_prompt)
    # print(response)

    output_parser = PydanticOutputParser(pydantic_object=DeliveryInformationModel)

    # Parse the response with the output parser
    parsed_response = output_parser.parse(response)
    result = parsed_response.json()
    print(result)
    return result

# answer = delivery_information(input)

template4 = """
## Instructions
Extract the Order information from the following PO content.

Carefully analyze the content and extract the Order information.

For Delivery information, please use the following format:
- Order Date
- Delivery Terms
- Payment Terms

After extracting the information, Strictly remove any special characters and replace them with an empty string.
Remove any unwanted / or \\ from the extracted information.
Strictly remove any unwanted blanck spaces in the response fields.
Return the output in JSON format.
{{
    "order": {{
        "order_date": "",
        "delivery_terms": "",
        "payment_terms": ""
    }}
}}

Input:
{po_content}
"""

def order_information(input_text):
  
    prompt = PromptTemplate(
        input_variables=["po_content"],
        template=template4
    )
    final_prompt = prompt.format(po_content=input_text)

    # Call the OpenAI API with LangChain's built-in run function
    response = parse_response(final_prompt)
    # print(response)

    output_parser = PydanticOutputParser(pydantic_object=OrderInformationModel)

    # Parse the response with the output parser
    parsed_response = output_parser.parse(response)
    result = parsed_response.json()
    print(result)
    return result


template5 = """
## Instructions
Extract the Item information from the following PO content.

Carefully analyze the input content and find the item table and extract the Item information.

For Item Table, please use the following format exactly:
- Return "NA" if any required field is not explicitly mentioned in the PO
- "item_id" for Item ID (unique ID or Material ID for each item)
- "item_description" for Item Description
- "quantity" for Quantity
- "unit_price" for Unit Price
- "total_price" for Total Price (Quantity * Unit Price)

Remove any special characters and replace them with an empty string. Remove all backslashes (\\) from the extracted information.
Return the output in JSON format with **exactly** these keys, without any additional information.

Input:
{po_content}

Only return the JSON object in response, using this structure:
{{
    "item": [{{
        "item_id": "",
        "item_description": "",
        "quantity": "",
        "unit_price": "",
        "total_price": ""
    }}]
}}

DO NOT INCLUDE example output in your response, use it only for reference.
example for reference:
Example:
Sample Input:
Pos.                          Menge      Beschreibung                                                            
               Preis/Einheit (EUR)                   Wert (EUR)
00010                          10 EA      Stainless Steel Tubing Insert, 12 mm OD                                 
                            3,84 / 1EA                       38,40
                                          Ihre Material-Nr.:           SS-12M5-8M
                                          Tube Fittings and Adapters - Spare Parts and Accessories - Tubing Inserts -
                                          Stainless Steel Tubing Insert, 12 mm OD x 8 mm ID
00020                          10 EA      Stainless Steel Tubing Insert, 12 mm OD                                 
                            3,28 / 1EA                       32,80
                                          Ihre Material-Nr.:           SS-12M5-10M
                                          Tube Fittings and Adapters - Spare Parts and Accessories - Tubing Inserts -
                                          Stainless Steel Tubing Insert, 12 mm OD x 10 mm ID

Sample Output:
```json
{{
    "item": [{{
        "item_id": "SS-12M5-8M",
        "item_description": "Stainless Steel Tubing Insert, 12 mm OD x 8 mm ID",
        "quantity": "10 EA",
        "unit_price": "3,84 / 1EA",
        "total_price": "38,40"
    }},
    {{
        "item_id": "SS-12M5-10M",
        "item_description": "Stainless Steel Tubing Insert, 12 mm OD x 10 mm ID",
        "quantity": "10 EA",
        "unit_price": "3,28 / 1EA",
        "total_price": "32,80"
    }}]
}}
"""


def item_table(input_text):
  
    prompt = PromptTemplate(
        input_variables=["po_content"],
        template=template5
    )
    final_prompt = prompt.format(po_content=input_text)
    
    # Call the OpenAI API with LangChain's built-in run function
    response = parse_item_response(final_prompt)
    output_parser = PydanticOutputParser(pydantic_object=ItemExtractedData)
    
    # Parse the response with the output parser
    parsed_response = output_parser.parse(response)
    result = parsed_response.json()
    print(result)
    return result

# answer = item_table(input)

template6 = """
## Instructions
Extract the Cost related information from the following PO content.

Carefully analyze the content and extract the Cost related information.

For Cost related information, please use the following format:
- Net Amount (First check net amount in the content if it is not there then calculate ONLY if both quantity AND unit price are explicitly mentioned for all items. If either is missing for any item, return "NA")
- Tax (Use explicitly stated tax amount from PO. If not found, return "NA")
- Total Amount (Use explicitly stated total amount from PO. If not found, return "NA")

Important:
- Do NOT calculate or estimate values if required information is missing
- Return "NA" if any required field is not explicitly mentioned in the PO
- For Net Amount: Only calculate if both quantity and unit price are clearly stated for all items
- For Tax: Only use if explicitly stated in PO content, otherwise return "NA"
- For Total Amount: Only use if explicitly mentioned in PO content
- Do NOT calculate or infer any values - only use explicitly stated amounts

After extracting the information:
- Strictly remove any special characters and replace them with an empty string
- Remove any / or \\ from the extracted information
- Strictly remove any unwanted blank spaces in the response fields

Return the output in JSON format:
{{
    "cost": {{
        "net_amount": "",
        "tax": "",
        "total_amount": ""
    }}
}}

Input:
{po_content}
"""

def cost_information(input_text):
  
    prompt = PromptTemplate(
        input_variables=["po_content"],
        template=template6
    )
    final_prompt = prompt.format(po_content=input_text)

    # Call the OpenAI API with LangChain's built-in run function
    response = parse_response(final_prompt)
    # print(response)

    output_parser = PydanticOutputParser(pydantic_object=CostInformationModel)

    # Parse the response with the output parser
    parsed_response = output_parser.parse(response)
    result = parsed_response.json()
    print(result)
    return result

# answer = cost_information(input)

template7 = """
## Instructions
Carefully analyze the content and  information related to Supplier Instructions, Invoicing Instructions and any other information in a Notes section.
Provide information other than these fields in the PO data:
- Customer name
- Customer address
- Customer city
- Customer country
- Supplier name
- Supplier address
- Supplier city
- Supplier country
- Delivery name
- Delivery address
- Delivery city
- Delivery country
- Net Amount
- Tax
- Total Amount

Look for that information mentioned in the other sections of the PO than these mentioned fields.
Keep the information brief.
For Cost related information, please use the following format:
- Supplier Instructions
- Invoicing Instructions
- Notes

After extracting the information, Strictly remove any special characters and replace them with an empty string.
Strictly remove any unwanted blanck spaces in the response fields.
Return the output in JSON format.
{{
    "other_details": {{
        "supplier_instructions": "",
        "invoicing_instructions": "",
        "notes": ""
    }}
}}

Input:
{po_content}
"""

def other_information(input_text):
  
    prompt = PromptTemplate(
        input_variables=["po_content"],
        template=template7
    )
    final_prompt = prompt.format(po_content=input_text)

    # Call the OpenAI API with LangChain's built-in run function
    response = parse_response(final_prompt)
    # print(response)

    output_parser = PydanticOutputParser(pydantic_object=OtherInformationModel)

    # Parse the response with the output parser
    parsed_response = output_parser.parse(response)
    result = parsed_response.json()
    print(result)
    return result

def run_all(input):
    responses = [
        quotation_ponumber(input),
        customer_supplier_information(input),
        delivery_information(input),
        order_information(input),
        item_table(input),
        cost_information(input),
        other_information(input)
    ]
    print(responses)
    combined_response = {}
    for response in responses:
        # Fix invalid escape sequences by replacing backslashes
        # response = response.replace('\\', '\\\\')
        try:
            # Parse each response from JSON string to dictionary
            response_json = json.loads(response)
            combined_response.update(response_json)
        except json.JSONDecodeError as e:
            print(f"Failed to parse response: {response}\nError: {e}")

    print(combined_response)
    # return json.dumps(combined_response)
    return combined_response

# def run_all(input):
#     responses = [
#         quotation_ponumber(input),
#         customer_supplier_information(input),
#         delivery_information(input),
#         order_information(input),
#         item_table(input),
#         cost_information(input),
#         other_information(input)
#     ]
    
#     combined_response = {}
    
#     for response in responses:
#         # Remove any control characters
#         response = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', response)
        
#         # Fix invalid escape sequences
#         response = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', response)
        
#         try:
#             # Parse each response from JSON string to dictionary
#             response_json = json.loads(response)
            
#             # Recursively update the combined_response
#             def update_dict(d, u):
#                 for k, v in u.items():
#                     if isinstance(v, dict):
#                         d[k] = update_dict(d.get(k, {}), v)
#                     else:
#                         d[k] = v
#                 return d
            
#             update_dict(combined_response, response_json)
#         except json.JSONDecodeError as e:
#             print(f"Failed to parse response: {response}\nError: {e}")
#             # Attempt to salvage partial data
#             try:
#                 partial_data = json.loads(response + "}")
#                 update_dict(combined_response, partial_data)
#             except:
#                 pass
    
#     print(combined_response)
#     return combined_response

# run_all(input)