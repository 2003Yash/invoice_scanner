import json
# gemini_intent_agent_prompt = """Analyze the below email carefully:

# Subject: {subject}

# Content:
# {text}

# Based on the following labels, choose EXACTLY ONE that fits best:
# - po process/new purchase order: For new purchase orders, PO creation requests
# - quotation requirement: For requests for price quotes or estimates
# - invoice inquiry: For questions about invoices or billing
# - PO Cancellation: For emails about canceling or terminating purchase orders
# - PO Change: For emails about modifying or changing existing purchase orders
# - other: For emails that don't fit the above categories

# IMPORTANT INSTRUCTIONS:
# 1. If there is ANY mention of cancellation, termination, or stopping a purchase order, choose "PO Cancellation".
# 2. If there is ANY mention of changing, modifying, amending, or revising a purchase order, choose "PO Change".
# 3. If there is ANY mention of creating, requesting, or submitting a new purchase order, choose "po process/new purchase order".
# 4. Phrases like "Baker Hughes cancelled an order" indicate "PO Cancellation".
# 5. Phrases like "changed the PO", "has changed the PO", "changed an order", or "Purchase Order (Changed)" indicate "PO Change".
# 6. Phrases like "new purchase order", "create PO", "PO request" indicate "po process/new purchase order".
# 7. Only reply with the exact label text, nothing else.

# Choose the label that best matches the intent:"""

gemini_intent_agent_prompt = """Analyze the below email carefully:

Subject: {subject}

Content:
{text}

Based on the following labels, choose EXACTLY ONE that fits best:
{intent_descriptions}

IMPORTANT INSTRUCTIONS:
1. Only reply with the exact label text, nothing else.

Choose the label that best matches the intent:"""

# po_extraction_prompt.py

agent_Prompt = """Extract purchase order information from the following email:

{text}

Please identify:
1. PO Number/Reference Number
2. Determine if this is a NEW purchase order being created or a REFERENCE to an existing purchase order
   - Look for phrases like "new PO", "I'd like to place an order", etc. to identify new orders
   - Look for phrases like "regarding PO", "follow up on", "status of PO" to identify references
3. Part Numbers/Item Codes/MPNs (list all mentioned)
4. Quantities for each item

Look for items in various formats including:
- Lines starting with "QTY-" followed by a number and then an item code
- Bullet points with items and quantities (e.g., "- SS-R4S8: 2 units")
- Table formats with item codes and quantities

DO NOT include email metadata (From, To, Date, Subject) as items.
DO NOT include dates as items.
DO NOT include general text like "I like to place an order" as items.
ONLY include actual product/part numbers or clearly labeled items.

Critical patterns to extract:
- (123x) ITEM-CODE - where 123 is quantity and ITEM-CODE is the item
- (123) ITEM-CODE - where 123 is quantity and ITEM-CODE is the item
- QTY x ITEM-CODE
- ITEM-CODE - QTY pcs
- ITEM-CODE (QTY)

Example line to extract: "(308x) SS-4-VCR-2-BL (make sure they are not silver coated)"
From this line: quantity = 308, item = SS-4-VCR-2-BL

New table format to extract data

| Item Code | Description              | Quantity | Unit Price | Total     |
|-----------|--------------------------|----------|------------|-----------|

EXTRACTION RULES:
- Look for the pattern "(number followed by optional x) followed by item code" 
- For part numbers, look for alphanumeric codes with hyphens like SS-4-VCR-2-BL
- Ignore any text in parentheses that appears after the item code (like specifications or notes)
- DO NOT include email metadata (From, To, Date, Subject) as items
- DO NOT include dates as items
- DO NOT extract dates as PO numbers
- DO NOT include general text like "I like to place an order" as items
- ONLY extract actual product/part numbers or clearly labeled items

Format your response as JSON with the keys "po_number", "is_reference_po" (boolean), "items", and "quantities". 
Only return the JSON object, no additional explanation."""

agent3_prompt = """Extract purchase order information (items and quantities) from the following email:

{text}

Please identify:
1. Part Numbers/Item Codes/MPNs/Catalog Numbers (list all mentioned)
2. Quantities for each item
3. PO Number if present

Look for items in various formats including:
- Lines with Catalog No. or product codes
- Lines containing both product descriptions and quantities
- Structured table formats with columns for items and quantities
- Lines that mention specific quantities with unit indicators (EA, PCS)

Format your response as JSON with the keys "po_number" (if present), "items", and "quantities".
Only return the JSON object, no additional explanation."""

agent4_prompt = """ ExportPublishYou are an intelligent purchase order assistant specializing in change detection.
Your task is to:

Extract structured data from emails about order changes
Identify changes to predefined fields: {fields}
Identify any additional fields that appear to be new or modified in the PO change request
Output a comprehensive JSON response that preserves the original nested structure

Email Content: {text}
Provide a JSON response in the following format:
{{
"po_change_exist": "true",
"po_no": "poxyz",
"recognized_changes": {{
/* Maintain the exact nested structure of the predefined fields.
When a field has changed, replace its simple value with an object containing
"previous_value" and "new_value". Keep other fields as simple values. */
}},
"extra_changes": {{
"<field>": {{
"previous_value": "<value or empty string if none>",
"new_value": "<value>"
}}
}}
}}
Rules:

Preserve the exact nested structure of the predefined fields in your output
For each recognized change, replace the simple string value with an object containing "previous_value" and "new_value"
Fields without changes should remain as simple string values to maintain the structure
For nested structures (like "item" arrays), maintain the array structure and apply changes to the specific items
Add any fields not in the predefined list but clearly modified to "extra_changes"
Include multiple items as separate objects in the "item" array when present
Be precise in your extraction; avoid making assumptions

Pay special attention to:

Changes in delivery dates or schedules
Updates to quantities, prices, or descriptions
Modified payment or shipping terms
Special instructions related to changes

Look for data in tables, formatted sections, and throughout the email body
Return ONLY the completed JSON without additional text or explanations
JSON Output: """

attachment_agent_prompt = """
You are an AI assistant tasked with determining if the provided data is related to a NEW purchase order (PO).
Note : If it is explicitly marked as a 'REPRINT' and includes a past date , then consider it as "is purchase order"
DATA:
```
{text}
```

Task:
1. Carefully analyze if this data represents a new purchase order that is requesting specific items to be purchased.
2. A NEW purchase order MUST include:
   - A PO number (this is mandatory for classification as a purchase order)
   - Specific items to be purchased with quantities
   - Product codes or SKUs
   - Often has order date or delivery date

3. If the document lacks a PO number, it should be classified as a quotation, not a purchase order.

4. The following are NOT new purchase orders:
   - Terms and conditions documents about purchase orders
   - Explanations of purchasing processes
   - Past order summaries or receipts
   - General contract language
   - Meeting notes, emails, or other business documents
   - Quotations (which lack a PO number)

5. Respond in the following JSON format:
{{
    "is_purchase_order": true/false,
    "has_po_number": true/false,
    "po_number": "The PO number if found, otherwise null",
    "document_type": "purchase_order" or "quotation" or "other",
    "summary": "Brief summary of the data including why it was classified as it was"
}}

Your response should ONLY contain valid JSON.
"""

agent5_prompt = """
You are a language model that classifies the urgency level of a purchase order email into one of three levels:
- urgent
- medium
- normal

Given the email message below, analyze the content and intent, and classify its urgency.

Email:
---
{text}
---

Rules:
- If the email contains language indicating urgency like "as soon as possible", "immediate attention", "ASAP", "urgent", "today", "critical", classify it as **urgent**.
- If the email mentions "soon", "early next week", "waiting for your input", but doesn't sound desperate, classify as *medium**.
- If the email is casual, has no clear urgency, or includes language like "whenever possible", "no rush", "just a reminder", classify it as **normal**.

Only return one of: urgent, medium, normal — nothing else.
"""

# po_fields_prompt.py
def Po_parse_agent_prompt(text, field_key, field_structure):
  prompt = f"""
  You are an AI assistant that extracts structured data from a purchase order email. The data is grouped into different categories. If a field is not found, return an empty string for it.

  Email Content:
  ---
  {text}
  ---

  Your task is to extract and return each of the following field groups individually as valid JSON:

  {field_key}: {json.dumps(field_structure, indent=2)}

  Respond with a JSON object in the same structure. Do not add comments or explanation.
  """
  return prompt


def get_data_field_grouping_prompt(data_fields):
    prompt = f"""You are an expert data analyst working with purchase order information. Your task is to organize extracted field names into logical clusters based on their relationships.

# Input list of data-Fields
{data_fields}

# Task Instructions
Given the list of input fields above, organize them into a structured JSON object following these rules:
1. Group related fields into logical clusters based on field name prefixes and semantic relationships
2. Only use fields that are provided in the input list - do not create new fields
3. Do not include any sample values or data - just organize the field names into a schema
4. payment terms and delivery terms are part of order
5. Donot change the field names, just organize them
6. donot fill the values for data fields

# Output Format
Return a JSON schema that organizes these fields without including any values. The schema should reflect the logical organization of the specific fields given in the input.

For example, if fields include "order_date", "order_number", you might group them under an "order_information" object.

Remember: Only use field names that appear in the input list. Do not create field names that aren't present in the input. and use group_names like po, order, customer, supplier, cost, shipping_details, other_details"""
    return prompt

# item_agent_prompt = """
# ## Instructions
# Extract the Item information from the following PO content.

# Carefully analyze the input content and find the item table and extract the Item information.

# For Item Table, please use the following format exactly:
# - Return "NA" if any required field is not explicitly mentioned in the PO
# - "customer_item_id" for Customer Item ID (unique ID or Material ID for each item)(Present in item ID column)
# - "manufacturer_item_id" for Manufacturer Item ID (if available, else return "NA")(Generally present in item description column)
# - "item_description" for Item Description (preserve all special characters, dimensions, specifications, etc. exactly as they appear)
# - "quantity" for Quantity
# - "unit_price" for Unit Price (preserve currency symbols, commas, periods, and all formatting exactly as they appear)(Just include numeric values and currency symbols nothing else)
# - "total_price" for Total Price (preserve currency symbols, commas, periods, and all formatting exactly as they appear)

# ## Important Rules:
# Make sure manufacturer_item_id should be extracted from the item description column, if available.
# examples of manufacturer_item_id that will be generally present in item description: GDP00500, HC224VCR3S4TB7, SS-8-TA-1-6
# Always look for "Item No.", "Item Number", or similar column headers for customer_item_id
# customer_item_id will not be serial number like 001,002 and so on , it will be unique ID or Material ID for each item.
# Combine multi-line descriptions by removing line breaks
# Ensure each item is extracted, even with identical item_descriptions
# Preserve exact formatting of prices and quantities
# Use contextual clues to distinguish item fields if standard headers are absent
# Do Not return serial number in customer_item_id or manufacturer_item_id fields.
# Follow sample input and output format regarding the customer_item_id, manufacturer_item_id, item_description, quantity, unit_price, and total_price fields.

# Do not modify or remove any special characters from the item_description, unit_price, or total_price fields, as these contain important information about specifications, dimensions, and numerical formatting that varies by language and region.

# Return the output in JSON format with exactly these keys, without any additional information.

# Input:
# {po_content}

# Your task is to extract and return each of the following field groups individually as valid JSON:

# {field_key}: {field_structure}

# DO NOT INCLUDE example output in your response, use it only for reference.
# example for reference:
# Example:
# Sample Input:
# Pos.    Item Nr.                          Menge      Beschreibung                                                            
#                     Preis/Einheit (EUR)                   Wert (EUR)
# 00010   2467341                       10 EA      Stainless Steel Tubing Insert, 12 mm OD                                 
#                             3,84 / 1EA                       38,40
#                                           Ihre Material-Nr.:           SS-12M5-8M
#                                           Tube Fittings and Adapters - Spare Parts and Accessories - Tubing Inserts -
#                                           Stainless Steel Tubing Insert, 12 mm OD x 8 mm ID
# 00020   2543134                       10 EA      Stainless Steel Tubing Insert, 12 mm OD                                 
#                             3,28 / 1EA                       32,80
#                                           Ihre Material-Nr.:           SS-12M5-10M
#                                           Tube Fittings and Adapters - Spare Parts and Accessories - Tubing Inserts -
#                                           Stainless Steel Tubing Insert, 12 mm OD x 10 mm ID

# Sample Output:
# {{
#     "item": [{{
#         "customer_item_part": "2467341",
#         "swagelok_item_part": "SS-12M5-8M",
#         "item_description": "Stainless Steel Tubing Insert, 12 mm OD x 8 mm ID",
#         "quantity": "10 EA",
#         "unit_of_measure": "EA"
#         "unit_price": "3,84 / 1EA",
#         "item_tax_percentage": "",
#         "item_tax_amount": "",
#         "discount": ""
#         "item_total": "38,40"
#     }},
#     {{
#         "customer_item_part": "2467341",
#         "swagelok_item_part": "SS-12M5-10M",
#         "item_description": "Stainless Steel Tubing Insert, 12 mm OD x 10 mm ID",
#         "quantity": "10 EA",
#         "unit_of_measure": "EA"
#         "unit_price": "3,28 / 1EA",
#         "item_tax_percentage": "",
#         "item_tax_amount": "",
#         "discount": ""
#         "item_total": "32,80"
#     }}]
# }}

# Sample Input:
# BWX Techno log ies,  Inc.

# Purchase  Order

# Vendor:

# DIBERT VALVE & FITTING CO  INC

# PO# Revision

# 4700068092-0

# Buyer

# XB4

# Date

# 02/11/2025

# Line  Material Number

# Description

# Delivery  I

# Qty

# I

# Date

# IUOMI

# Unit Price  Extended  Price

# Jay Fetherolf
# BWXT NUCLEAR OPERATIONS GROUP, INC.
# ATTN : RECEIVING  DEPARTMENT
# 1570 MT. ATHOS  ROAD
# LYNCHBURG VA  24504
# USA

# 022

# SS-1210-9

# 102/28/20251

# 2.000

# I EA  I  $70 .29  USO  $140.58  USO

# EXEMPT

# STAINLESS STEEL SWAGELOK TUBE FITTING , UNION  ELBOW, 3/4  IN. TUBE OD

# Charge#: 20364120
# Please deliver  2.000  EA to  SHOP 69  (OSO) for FETHEROLFJA

# Tracking#: JAF-95118

# Ship to:
# Jay Fetherolf
# BWXT NUCLEAR OPERATIONS GROUP , INC.
# ATTN : RECEIVING  DEPARTMENT
# 1570 MT.  ATHOS  ROAD
# LYNCHBURG VA  24504
# USA

# 023

# SS-T8-S-049-20

# 102/28/20251  60.000

# I EA  I  $17.92  USO  $1 ,075.20  USO

# EXEMPT

# SS  1/2" OD  X .049 WALL THICKNESS TUBING
# CUT TO  10 ft  LENGTHS

# Charge#: 20364120
# Please deliver  60.000  EA to  SHOP 69  (OSO) for FETHEROLFJA

# Tracking#: JAF-95118

# Ship to:
# Jay Fetherolf
# BWXT NUCLEAR OPERATIONS GROUP , INC.
# ATTN : RECEIVING  DEPARTMENT
# 1570 MT.  ATHOS  ROAD
# LYNCHBURG VA  24504
# USA

# I
# I ss-1210-3-12-8 TUBE T 3/4  xlo212812025I

# 024

# I

# 1.000

# I  EA  j  $102 .15USDI  $102 .15  USO

# Page  10 of 16
# BWX Technologies,  In c

# Purchase  Order

# Vendor:

# DIBERT VALVE & FITTING CO INC

# PO# Revision

# 4700068092-0

# Buyer

# XB4

# Date

# 02/11/2025

# Line  Material Number

# Description

# Delivery
# Date

# Qty

# UOM  Unit Price  Extended  Price

# 3/4  X 1/2 TB

# EXEMPT

# Charge#: 20364120
# Please deliver  1.000 EA to  SHOP 69  (OSO)  for J. Fetherolf

# Tracking#: JAF-95118

# Ship to:
# Jay Fetherolf
# BWXT NUCLEAR OPERATIONS GROUP, INC.
# ATTN : RECEIVING  DEPARTMENT
# 1570 MT.  ATHOS  ROAD
# LYNCHBURG VA  24504
# USA

# 025

# SS-1210-R-8

# 102/28/20251

# 2.000

# I EA  I $38.52  USO

# $77 .04  USO
# EXEMPT

# STAINLESS STEEL SWAGELOK TUBE  FITTING , REDUCER , 3/4  IN . X  1/2 IN.  TUBE OD

# Charge #: 20364120
# Please deliver  2.000  EA to  SHOP 69  (OSO) for FETHEROLFJA

# Tracking#: JAF-95118

# Ship to:
# Jay Fetherolf
# BWXT NUCLEAR OPERATIONS GROUP, INC .
# ATTN : RECEIVING  DEPARTMENT
# 1570 MT.  ATHOS  ROAD
# LYNCHBURG VA  24504
# USA

# 026

# SS-QF8-B-810 QUICK
# CONNECT 1/2 T

# 102/28/20251

# 4.000

# EA  I  $58.32  USO  $233.28  USO
# I
# EXEMPT

# Charge #: 20364120
# Please deliver  4.000  EA to  SHOP 69  (OSO) for J. Fetherolf

# Tracking#:  JAF-95118

# Ship to:
# Jay Fetherolf

# Page  11  of 16


# BWX Technolog ies,  Inc

# Purchase  Order

# Vendor:

# DIBERT VALVE & FITTING CO  INC

# PO# Revision

# 4700068092-0

# Buyer

# XB4

# Date

# 02/11/2025

# Line  Material Number

# Description

# Delivery  I

# Qty

# I

# Date

# IUOMI

# Unit Price  Extended  Price

# BWXT NUCLEAR OPERATIONS GROUP, INC.
# ATTN : RECEIVING  DEPARTMENT
# 1570 MT.  ATHOS  ROAD
# LYNCHBURG VA  24504
# USA

# 027

# SS-QF8-S-600 QUICK
# CONNECT 3/8 T

# 102/28/20251

# 4.000

# I EA  I  $59.41  USO

# $237.64  USO
# EXEMPT

# Charge #: 20364120

# Please deliver  4.000 EA to  SHOP 69  (OSO) for J. Fetherolf

# Tracking  #: JAF-95118

# Ship to:
# Jay  Fetherolf
# BWXT NUCLEAR OPERATIONS GROUP , INC.
# ATTN : RECEIVING  DEPARTMENT
# 1570 MT. ATHOS  ROAD
# LYNCHBURG VA  24504
# USA

# I

# SHIPPING INSTRUCTIONS:
# STANDARD CLAUSE 7151-15
# ROUTING  INSTRUCTIONS - COLLECT

# SECURITY RESTRICTIONS:

# Net Order Value:
# Sales Tax Total:
# Total Order Value:

# I
# $5,506.60  USO
# $0 .00  USO
# $5,506 .60  USO

# DELIVERING DRIVER MUST BE A U.S. CITIZEN , NO  DUAL CITIZENSHIP ALLOWED.  NO  PASSENGERS      
# ALLOWED.  DRIVER  MUST BE  PREPARED TO  HAND OVER ANY CELL PHONES,  PAGERS,  OR

# SAMPLE OUTPUT:
# {{
#     "item": [
#         {{
#             "customer_item_id": "NA",
#             "manufacturer_item_id": "SS-1210-9",
#             "item_description": "STAINLESS STEEL SWAGELOK TUBE FITTING, UNION ELBOW, 3/4 IN. TUBE OD",
#             "quantity": "2.000",
#             "unit_of_measure": "EA"
#             "unit_price": "$70.29",
#             "item_tax_percentage": "",
#             "item_tax_amount": "",
#             "discount": ""
#             "item_total": "$140.58"
#         }},
#         {{
#             "customer_item_id": "NA",
#             "manufacturer_item_id": "SS-T8-S-049-20",
#             "item_description": "SS 1/2\" OD X .049 WALL THICKNESS TUBING CUT TO 10 ft LENGTHS",
#             "quantity": "60.000",
#             "unit_of_measure": "EA"
#             "unit_price": "$17.92",
#             "item_tax_percentage": "",
#             "item_tax_amount": "",
#             "discount": ""
#             "item_total": "$1,075.20"
#         }},
#         {{
#             "customer_item_id": "NA",
#             "manufacturer_item_id": "SS-1210-3-12-8",
#             "item_description": "3/4 X 1/2 TB",
#             "quantity": "1.000",
#             "unit_of_measure": "EA"
#             "unit_price": "$102.15",
#             "item_tax_percentage": "",
#             "item_tax_amount": "",
#             "discount": ""
#             "item_total": "$102.15"
#         }},
#         {{
#             "customer_item_id": "NA",
#             "manufacturer_item_id": "SS-1210-R-8",
#             "item_description": "STAINLESS STEEL SWAGELOK TUBE FITTING, REDUCER, 3/4 IN. X 1/2 IN. TUBE OD",
#             "quantity": "2.000",
#             "unit_of_measure": "EA"
#             "unit_price": "$38.52",
#             "item_tax_percentage": "",
#             "item_tax_amount": "",
#             "discount": ""
#             "item_total": "$77.04"
#         }},
#         {{
#             "customer_item_id": "NA",
#             "manufacturer_item_id": "SS-QF8-B-810",
#             "item_description": "QUICK CONNECT 1/2 T",
#             "quantity": "4.000",
#             "unit_of_measure": "EA"
#             "unit_price": "$58.32",
#             "item_tax_percentage": "",
#             "item_tax_amount": "",
#             "discount": ""
#             "item_total": "$233.28"
#         }},
#         {{
#             "customer_item_id": "NA",
#             "manufacturer_item_id": "SS-QF8-S-600",
#             "item_description": "QUICK CONNECT 3/8 T",
#             "quantity": "4.000",
#             "unit_of_measure": "EA"
#             "unit_price": "$59.41",
#             "item_tax_percentage": "",
#             "item_tax_amount": "",
#             "discount": ""
#             "item_total": "$237.64"
#         }}
#     ]
# }}

# """
item_agent_prompt = """
## Instructions
You are an AI assistant that extracts structured item data from a invoice.
The data is grouped into different categories. If a field is not found, return an empty string for it.

make sure you replace the values correctly

Input:
{po_content}

Your task is to extract and return each of the following field groups individually as valid JSON:

{field_key}: {field_structure}

DO NOT INCLUDE example output in your response, use it only for reference.
example for reference:
Example:
Sample Input:
TOPOCEAN CONSOLIDATION SERVICE INC CHICAGO
                                           DIVISION
                 13300 CROSSROADS PKWY NORTH, SUITE 300,CITY OF INDUSTRY, CA 91746_
                                 PH: 562-908-1688 FAX: 562-908-1699
                                             INVOICE *
To     FELLOWES INC                            INVOICE NO.     0125050034
        1789 NORWOOD AVE                        FILE NO        6x25030131
                                                LOT NO         SITOORD25050117
        ITASCA, FL, 60143                      INVOICE DATE    05/01/2025
                                               DUE DATE        05/31/2025
ATTN     MAUREEN SEEBACHER SUE WILEY           PREPARED BY       CATHERINE LOPEZ
         MAUREEN SEEBACHER  SUE WILEY          VESSEL/VOYAGE    CMA CGM ALMAVIVA VOPGKFELMA
TEL#     16305395688                             GATE IN DATE  03/07/2025
 FAX#                                           ETD             03/09/2025
                                                 ATD           05/01/2025
                                                 ETA
                                                M B/L           EGLV093500056847
                                                 BIL NO.         TCS6XP30964
                                                ISF NO_         LL-FILE
                                                 CARGO TYPE     VIGORHOOD MACAO COMMERCIAL OFFSHORE CO
                                                 SHIPPER
                                                                 LTD
 Customer                                        PLACE OF REC   TANJUNG PELEPAS,MY
                                                 ORIGIN           TANJUNG PELEPAS,MY
 FELLOWES DI                                      DESTINATION  MOBILE, AL
                                                  FINAL DEST    MOBILE, AL
                                                 COMMODITY
                                                  PIECES           65
                                                  WEIGHT          807.3/KGS 1779.774/LBS
                                                  VOLUME          4.0220/CBM
                                                 CONTAINER SIZE    1X4OHD
 DESCRIPTION                                                   UNIT PRICE  QTY    UNIT      USD TOTAL
 DOCUMENT FEE                                           USD         70.00 1.0000  CTNR           70,00
  EDI CHARGES                                           USD         15.00 1,0000    HBL          15.00
 LOGISTICS PLUS HANDLING FEE                            USD         30.00 1.0000  CTNR           30.00
                                                         PLEASE PAY THIS AMOUNT--> USD          115.00
  CONTAINERS                  PO#
  EITU0034750/40HD            0883781317 667330
  CLIENT NOTE                                                                      [9qw_-0z?
   PLEASE REMIT THE INDICATED AMOUNT ONIBEFORE
   IF ANY DISCREPANCY FOUND IN ANY ITEMS HEREIN, PLEASE KINDLY
   NOTIFY US IMMEDIATELY, THANK YOUI
   PLEASE NOTE EXAM CHARGES MAY BE BILLED LATER EVEN AFTER SHIPMENT IS PICKED UP:

Sample Output:
{{
   item:[
            {{
                "item_number": "",
                "description": "DOCUMENT FEE",
                "customer_part": "",
                "quantity_ord": "",
                "quantity_shp": "",
                "quantity_bo": "",
                "unit_price": "70.00",
                "unit": "CTNR",
                "amount": "70.00",
                "currency": "USD",
                "freight": "",
                "asin": "",
                "order": "",
                "um": "",
                "mfg": "",
                "extended": ""
            }},
            {{
                "item_number": "",
                "description": "EDI CHARGES",
                "customer_part": "",
                "quantity_ord": "",
                "quantity_shp": "",
                "quantity_bo": "",
                "unit_price": "15.00",
                "unit": "HBL",
                "amount": "15.00",
                "currency": "USD",
                "freight": "",
                "asin": "",
                "order": "",
                "um": "",
                "mfg": "",
                "extended": ""
            }},
            {{
                "item_number": "",
                "description": "LOGISTICS PLUS HANDLING FEE",
                "customer_part": "",
                "quantity_ord": "",
                "quantity_shp": "",
                "quantity_bo": "",
                "unit_price": "30.00",
                "unit": "CTNR",
                "amount": "30.00",
                "currency": "USD",
                "freight": "",
                "asin": "",
                "order": "",
                "um": "",
                "mfg": "",
                "extended": ""
            }}
        ]
}}

Sample Input:
 WAREHOUSE DIRECL                                                                       INVOICE
 Workplace Solutioms                                                          5/1/2025       5921468-0
2001 S. Mount Prospect Rd.                                                      DATE          NUMBER
Des Plaines, IL 60018
(847) 952-1925  Fax: (847) 956-5815
www.warehousedirect.com
         Billing Address                                      Shipping Address
         FELLOWES INC                                         FELLOWES INC
         ATTN ACCOUNTS PAYABLE                                DEL TO N DOCK 6AM 5PM
         1789 NORWOOD AVENUE                                  1789 NORWOOD AVENUE
         ITASCA, IL 60143                                     ITASCA, IL 60143
 Customer Number       Dept     Customer Purchase Order        Salesrep       Writer       Terms
       164154          1789                           671545     6234          5042  NET 10 DAYS VIA
                                                                                      EFT OR CHECK
Order UM  BO  Ship   MFG       Stock Number                  Description                             Unit Price  Extended
                                           **Attention :Dan Austin
    6  CT        6 WHD      CXC32H            LINER,CAN,24X32,CLR,65MIL,500                              $28.79              $172.74
    6  CT        6 WHD      TGG47XH           LINER,CAN,43X47,1.35MIL,100                                $30.89              $185.34
    1  CT        1 HOS      260               LINER,NAPKIN RECEPTACLE                                    $19.14               $19.14
    1  CT        1 HOS      MT4               SANITARY,MAXITHINS PAD                                     $52.06               $52.06
   10  CT       10 WHD      19920             TISSUE,TOILET,9INCH,2PLY CS/12                             $35.14              $351.40
    4  CT   4    0 GPC      21000             TOWEL,MLTFLD 2PLY,125PKWE                                  $49.76                $0.00
    7  CT        7 GPC      26100             TOWEL,ROLL,HC,1000FT,WHT                                   $57.67              $403.69
                                                                                      SubTotal                             $1,184.37
                                                                                          Tax                                $118.44
                                                                                                          Total            $1,302.81
                                                                              Remit to:
                                                                              Warehouse Direct, Inc.
                                                                              PO Box 772570
                                                                              Chicago, IL 60677-2570
  Please do not change our payment information. This includes any banking or mailing information. If you get any request to do this,
             please don’t change anything and immediately contact our Accounting Department at our main number.
                                   THANK YOU FOR YOUR ORDER
                                         Page 1 of 1

SAMPLE OUTPUT:
{{
    "item": [
    {{
        "item_number": "",
        "description": "LINER,CAN,24X32,CLR,65MIL,500",
        "customer_part": "CXC32H",
        "quantity_ord": "6,
        "quantity_shp": "6",
        "quantity_bo": "",
        "unit_price": "28.79",
        "unit": "CT",
        "amount": "172.74",
        "currency": "USD",
        "freight": "",
        "asin": "",
        "order": "",
        "um": "WHD",
        "mfg": "",
        "extended": "172.74"
    }},
    {{
        "item_number": "",
        "description": "LINER,CAN,43X47,1.35MIL,100",
        "customer_part": "TGG47XH",
        "quantity_ord": "6,
        "quantity_shp": "6",
        "quantity_bo": "",
        "unit_price": "30.89",
        "unit": "CT",
        "amount": "185.34",
        "currency": "USD",
        "freight": "",
        "asin": "",
        "order": "",
        "um": "WHD",
        "mfg": "",
        "extended": "185.34"
    }},
    {{
        "item_number": "",
        "description": "LINER,NAPKIN RECEPTACLE",
        "customer_part": "260",
        "quantity_ord": "1,
        "quantity_shp": "1",
        "quantity_bo": "",
        "unit_price": "19.14",
        "unit": "CT",
        "amount": "19.14",
        "currency": "USD",
        "freight": "",
        "asin": "",
        "order": "",
        "um": "HOS",
        "mfg": "",
        "extended": "19.14"
    }},
    {{
        "item_number": "",
        "description": "SANITARY,MAXITHINS PAD",
        "customer_part": "MT4",
        "quantity_ord": "1,
        "quantity_shp": "1",
        "quantity_bo": "",
        "unit_price": "52.06",
        "unit": "CT",
        "amount": "52.06",
        "currency": "USD",
        "freight": "",
        "asin": "",
        "order": "",
        "um": "HOS",
        "mfg": "",
        "extended": "52.06"
    }},
    {{
        "item_number": "",
        "description": "TISSUE,TOILET,9INCH,2PLY CS/12",
        "customer_part": "19920",
        "quantity_ord": "10
        "quantity_shp": "10",
        "quantity_bo": "",
        "unit_price": "35.14",
        "unit": "CT",
        "amount": "351.40",
        "currency": "USD",
        "freight": "",
        "asin": "",
        "order": "",
        "um": "WHD",
        "mfg": "",
        "extended": "351.40"
    }},
    {{
        "item_number": "",
        "description": "TOWEL,MLTFLD 2PLY,125PKWE",
        "customer_part": "21000",
        "quantity_ord": "4,
        "quantity_shp": "0",
        "quantity_bo": "4",
        "unit_price": "49.76",
        "unit": "CT",
        "amount": "0.00",
        "currency": "USD",
        "freight": "",
        "asin": "",
        "order": "",
        "um": "GPC",
        "mfg": "",
        "extended": "0.00"
    }},
    {{
        "item_number": "",
        "description": "TOWEL,ROLL,HC,1000FT,WHT",
        "customer_part": "26100",
        "quantity_ord": "7,
        "quantity_shp": "7",
        "quantity_bo": "",
        "unit_price": "57.67",
        "unit": "CT",
        "amount": "403.69",
        "currency": "USD",
        "freight": "",
        "asin": "",
        "order": "",
        "um": "GPC",
        "mfg": "",
        "extended": "403.69"
    }}
    ]
}}
field :   "item": [{{
        "item_number": "",
        "description": "",
        "customer_part": "",
        "quantity_ord": "",
        "quantity_shp": "",
        "quantity_bo": "",
        "unit_price": "",
        "unit": "",
        "amount": "",
        "currency":"",
        "freight": "",
        "asin": "",
        "order": "",
        "um": "",
        "mfg": "",
        "extended": ""
    }}]
note :  the above field format for item should be returned for complusory 

"""

def get_amendment_prompt(amendments, po_data):
    prompt = f"""You are a helpful assistant that updates purchase order data based on recognized changes. Your task is to:

1. Take a PO data object and a change log object as inputs
2. Apply the changes from the change log to the PO data
3. Return the updated PO data as a JSON object

Here is the change log that contains the recognized changes:
{amendments}

Here is the PO data that needs to be updated:
{po_data}

Follow these rules when applying changes:
- If a field in the change log exactly matches a field in the PO data, update that field with the new value
- If a field in the change log doesn't exactly match but is logically similar to a field in the PO data, update the logically similar field
- If a field in the change log doesn't exist in the PO data at all, then add it to the PO data
- Preserve the original structure of the PO data
- Do not remove or modify any fields that aren't mentioned in the change log
- Use the field names that already exist in the PO data whenever possible
- for updates over "instructions" datafield, take the new data and append it to already existing data, instead of removing old data and updating with new data

When looking for logically similar fields, consider these mappings (but don't limit yourself to only these):
- "DeliveryDate" might map to fields in "delivery_details" section
- "payment_terms" might map to "payment_terms" in "order_details" section
- Item-specific changes might map to entries in the "items" array



Your response should contain only the updated PO data as a valid JSON object, with no additional explanation or commentary.
"""

    return prompt

def get_extra_changes_amendment_prompt(changes, po_data):
    prompt = f"""You are a JSON processor for purchase order data. Process the provided change_log = {changes} and po_data = {po_data} as follows:

Your task is to:

1. Take a PO data object and a change log object as inputs
2. Apply the changes from the change log to the PO data
3. Return the updated PO data as a JSON object

Follow these rules when applying changes:
- Check if each field from change_log exists in the "extra_changes" field of po_data, then update their values from given change_log
- if data fields not exist in "extra_changes" field of po_data then create new data fields in "extra_changes" field of po_data with the mentioned name from change_log, then update their values from given change_log
- donot modify the any-other fields from po_data and keep the data_fields names from change_log without changes them

Your response should contain only the updated po_data as a valid JSON object, with no additional explanation or commentary.
"""

    return prompt
