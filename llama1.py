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
Extract the PO number, quotation number, and order information from the following PO content.

Carefully analyze the content and extract the following information:

1. For PO details:
   - PO number (consider both order number and po number in the content)(PO Number might contain special character like "-",keep those as it is.)
   - Quotation number (Write NA if QUOTATION NUMBER is not mentioned in the content)

2. For Order information:
   - Order Date[dd/mm/yyyy]
   - Delivery Terms
   - Payment Terms
   - Delivery Date

After extracting the information:
- Strictly remove any special characters and replace them with an empty string
- Remove any unwanted / or \\ from the extracted information
- Strictly remove any unwanted blank spaces in the response fields

Return the output in JSON format.
{{
    "po": {{
        "po_number": "",
        "quotation_number": ""
    }},
    "order": {{
        "order_date": "dd/mm/yyyy",
        "delivery_terms": "",
        "payment_terms": "",
        "delivery_date": "dd/mm/yyyy"
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
    print(response)

    output_parser = PydanticOutputParser(pydantic_object=POQuotationModel)

    # Parse the response with the output parser
    parsed_response = output_parser.parse(response)
    result = parsed_response.json()
    print(result)
    return result



# answer = quotation_ponumber(input)

template2 = """
## Instructions
Extract and classify the Customer, Supplier, and Delivery information from the following PO content using the following rules:

Classification Rules:
1. Customer (Buyer) indicators:
   - Look for terms like: "Bill To", "Ship To", "Buyer", "Customer", "Purchaser", "Sold To" or their equivalents
   - Usually appears first or at the top of the PO
   - Is the entity receiving/paying for goods/services

2. Supplier (Seller) indicators:
   - Look for terms like: "Vendor", "Seller", "From", "Supplier", "Company Details" or their equivalents
   - Usually provides the goods/services
   - Often includes tax ID/registration numbers
   - May include bank details

3. Delivery Information indicators:
   Primary Search - Look for sections marked with:
   - "Deliver To"
   - "Ship To"
   - "Delivery Address"
   - "Shipping Address"
   - "Consignee"
   - "Point of Delivery"
   - "Destination"
   Or their equivalents in other languages

Delivery Information Context clues:
   - Often appears after buyer/customer information
   - May include delivery instructions or timing
   - Could contain contact person for delivery
   - Might include loading/unloading times
   - May have special handling instructions
   - Could include warehouse/dock numbers

Delivery Fallback Logic:
   - If no explicit delivery information is found, use customer information as delivery address
   - When using customer info as fallback, maintain the same formatting rules

Data Extraction and Cleaning Rules:
1. For all address components:
   - Remove special characters and replace with empty string
   - Remove any forward slashes (/) or backslashes (\)
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

Delivery Information:
- Delivery name: Extract receiving entity name or department (or customer name if fallback)
- Delivery address: Extract complete street address, building number, floor/unit if available
- Delivery city: Extract city/municipality/town
- Delivery country: Extract country name

Special Handling Instructions:
1. If multiple delivery addresses exist, extract the primary/first listed address
2. For warehouse deliveries, include warehouse number in delivery address
3. For healthcare/sensitive deliveries, maintain any special handling codes in delivery name
4. If city contains postal code, separate and include only city name

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
    }},
    "delivery": {{
        "delivery_name": "",
        "delivery_address": "",
        "delivery_city": "",
        "delivery_country": ""
    }}
}}

Important Notes:
- If a field cannot be determined with certainty, leave it as an empty string rather than making assumptions
- For delivery info, first attempt to find explicit delivery information
- If no delivery information is found, use customer information as delivery address
- If neither delivery nor customer information is found, return empty strings
- Preserve department names or care-of information in delivery name field
- Include any relevant building/floor/unit numbers in delivery address

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


template5 = """
## Instructions
Extract the Item information from the following PO content.

Carefully analyze the input content and find the item table and extract the Item information.

For Item Table, please use the following format exactly:
- Return "NA" if any required field is not explicitly mentioned in the PO
- "customer_item_id" for Customer Item ID (unique ID or Material ID for each item)(Present in item ID column)
- "manufacturer_item_id" for Manufacturer Item ID (if available, else return "NA")(Generally present in item description column)
- "item_description" for Item Description (preserve all special characters, dimensions, specifications, etc. exactly as they appear)
- "quantity" for Quantity
- "unit_price" for Unit Price (preserve currency symbols, commas, periods, and all formatting exactly as they appear)(Just include numeric values and currency symbols nothing else)
- "total_price" for Total Price (preserve currency symbols, commas, periods, and all formatting exactly as they appear)

## Important Rules:
Make sure manufacturer_item_id should be extracted from the item description column, if available.
examples of manufacturer_item_id that will be generally present in item description: GDP00500, HC224VCR3S4TB7, SS-8-TA-1-6
Always look for "Item No.", "Item Number", or similar column headers for customer_item_id
customer_item_id will not be serial number like 001,002 and so on , it will be unique ID or Material ID for each item.
Combine multi-line descriptions by removing line breaks
Ensure each item is extracted, even with identical item_descriptions
Preserve exact formatting of prices and quantities
Use contextual clues to distinguish item fields if standard headers are absent
Do Not return serial number in customer_item_id or manufacturer_item_id fields.
Follow sample input and output format regarding the customer_item_id, manufacturer_item_id, item_description, quantity, unit_price, and total_price fields.

Do not modify or remove any special characters from the item_description, unit_price, or total_price fields, as these contain important information about specifications, dimensions, and numerical formatting that varies by language and region.

Return the output in JSON format with exactly these keys, without any additional information.

Input:
{po_content}

Only return the JSON object in response, using this structure:
{{
    "item": [{{
        "customer_item_id": "",
        "manufacturer_item_id": "",
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
Pos.    Item Nr.                          Menge      Beschreibung                                                            
                    Preis/Einheit (EUR)                   Wert (EUR)
00010   2467341                       10 EA      Stainless Steel Tubing Insert, 12 mm OD                                 
                            3,84 / 1EA                       38,40
                                          Ihre Material-Nr.:           SS-12M5-8M
                                          Tube Fittings and Adapters - Spare Parts and Accessories - Tubing Inserts -
                                          Stainless Steel Tubing Insert, 12 mm OD x 8 mm ID
00020   2543134                       10 EA      Stainless Steel Tubing Insert, 12 mm OD                                 
                            3,28 / 1EA                       32,80
                                          Ihre Material-Nr.:           SS-12M5-10M
                                          Tube Fittings and Adapters - Spare Parts and Accessories - Tubing Inserts -
                                          Stainless Steel Tubing Insert, 12 mm OD x 10 mm ID

Sample Output:
{{
    "item": [{{
        "customer_item_id": "2467341",
        "manufacturer_item_id": "SS-12M5-8M",
        "item_description": "Stainless Steel Tubing Insert, 12 mm OD x 8 mm ID",
        "quantity": "10 EA",
        "unit_price": "3,84 / 1EA",
        "total_price": "38,40"
    }},
    {{
        "customer_item_id": "2467341",
        "manufacturer_item_id": "SS-12M5-10M",
        "item_description": "Stainless Steel Tubing Insert, 12 mm OD x 10 mm ID",
        "quantity": "10 EA",
        "unit_price": "3,28 / 1EA",
        "total_price": "32,80"
    }}]
}}

Sample Input:
BWX Techno log ies,  Inc.

Purchase  Order

Vendor:

DIBERT VALVE & FITTING CO  INC

PO# Revision

4700068092-0

Buyer

XB4

Date

02/11/2025

Line  Material Number

Description

Delivery  I

Qty

I

Date

IUOMI

Unit Price  Extended  Price

Jay Fetherolf
BWXT NUCLEAR OPERATIONS GROUP, INC.
ATTN : RECEIVING  DEPARTMENT
1570 MT. ATHOS  ROAD
LYNCHBURG VA  24504
USA

022

SS-1210-9

102/28/20251

2.000

I EA  I  $70 .29  USO  $140.58  USO

EXEMPT

STAINLESS STEEL SWAGELOK TUBE FITTING , UNION  ELBOW, 3/4  IN. TUBE OD

Charge#: 20364120
Please deliver  2.000  EA to  SHOP 69  (OSO) for FETHEROLFJA

Tracking#: JAF-95118

Ship to:
Jay Fetherolf
BWXT NUCLEAR OPERATIONS GROUP , INC.
ATTN : RECEIVING  DEPARTMENT
1570 MT.  ATHOS  ROAD
LYNCHBURG VA  24504
USA

023

SS-T8-S-049-20

102/28/20251  60.000

I EA  I  $17.92  USO  $1 ,075.20  USO

EXEMPT

SS  1/2" OD  X .049 WALL THICKNESS TUBING
CUT TO  10 ft  LENGTHS

Charge#: 20364120
Please deliver  60.000  EA to  SHOP 69  (OSO) for FETHEROLFJA

Tracking#: JAF-95118

Ship to:
Jay Fetherolf
BWXT NUCLEAR OPERATIONS GROUP , INC.
ATTN : RECEIVING  DEPARTMENT
1570 MT.  ATHOS  ROAD
LYNCHBURG VA  24504
USA

I
I ss-1210-3-12-8 TUBE T 3/4  xlo212812025I

024

I

1.000

I  EA  j  $102 .15USDI  $102 .15  USO

Page  10 of 16
BWX Technologies,  In c

Purchase  Order

Vendor:

DIBERT VALVE & FITTING CO INC

PO# Revision

4700068092-0

Buyer

XB4

Date

02/11/2025

Line  Material Number

Description

Delivery
Date

Qty

UOM  Unit Price  Extended  Price

3/4  X 1/2 TB

EXEMPT

Charge#: 20364120
Please deliver  1.000 EA to  SHOP 69  (OSO)  for J. Fetherolf

Tracking#: JAF-95118

Ship to:
Jay Fetherolf
BWXT NUCLEAR OPERATIONS GROUP, INC.
ATTN : RECEIVING  DEPARTMENT
1570 MT.  ATHOS  ROAD
LYNCHBURG VA  24504
USA

025

SS-1210-R-8

102/28/20251

2.000

I EA  I $38.52  USO

$77 .04  USO
EXEMPT

STAINLESS STEEL SWAGELOK TUBE  FITTING , REDUCER , 3/4  IN . X  1/2 IN.  TUBE OD

Charge #: 20364120
Please deliver  2.000  EA to  SHOP 69  (OSO) for FETHEROLFJA

Tracking#: JAF-95118

Ship to:
Jay Fetherolf
BWXT NUCLEAR OPERATIONS GROUP, INC .
ATTN : RECEIVING  DEPARTMENT
1570 MT.  ATHOS  ROAD
LYNCHBURG VA  24504
USA

026

SS-QF8-B-810 QUICK
CONNECT 1/2 T

102/28/20251

4.000

EA  I  $58.32  USO  $233.28  USO
I
EXEMPT

Charge #: 20364120
Please deliver  4.000  EA to  SHOP 69  (OSO) for J. Fetherolf

Tracking#:  JAF-95118

Ship to:
Jay Fetherolf

Page  11  of 16


BWX Technolog ies,  Inc

Purchase  Order

Vendor:

DIBERT VALVE & FITTING CO  INC

PO# Revision

4700068092-0

Buyer

XB4

Date

02/11/2025

Line  Material Number

Description

Delivery  I

Qty

I

Date

IUOMI

Unit Price  Extended  Price

BWXT NUCLEAR OPERATIONS GROUP, INC.
ATTN : RECEIVING  DEPARTMENT
1570 MT.  ATHOS  ROAD
LYNCHBURG VA  24504
USA

027

SS-QF8-S-600 QUICK
CONNECT 3/8 T

102/28/20251

4.000

I EA  I  $59.41  USO

$237.64  USO
EXEMPT

Charge #: 20364120

Please deliver  4.000 EA to  SHOP 69  (OSO) for J. Fetherolf

Tracking  #: JAF-95118

Ship to:
Jay  Fetherolf
BWXT NUCLEAR OPERATIONS GROUP , INC.
ATTN : RECEIVING  DEPARTMENT
1570 MT. ATHOS  ROAD
LYNCHBURG VA  24504
USA

I

SHIPPING INSTRUCTIONS:
STANDARD CLAUSE 7151-15
ROUTING  INSTRUCTIONS - COLLECT

SECURITY RESTRICTIONS:

Net Order Value:
Sales Tax Total:
Total Order Value:

I
$5,506.60  USO
$0 .00  USO
$5,506 .60  USO

DELIVERING DRIVER MUST BE A U.S. CITIZEN , NO  DUAL CITIZENSHIP ALLOWED.  NO  PASSENGERS      
ALLOWED.  DRIVER  MUST BE  PREPARED TO  HAND OVER ANY CELL PHONES,  PAGERS,  OR

SAMPLE OUTPUT:
{{
    "item": [
        {{
            "customer_item_id": "NA",
            "manufacturer_item_id": "SS-1210-9",
            "item_description": "STAINLESS STEEL SWAGELOK TUBE FITTING, UNION ELBOW, 3/4 IN. TUBE OD",
            "quantity": "2.000",
            "unit_price": "$70.29",
            "total_price": "$140.58"
        }},
        {{
            "customer_item_id": "NA",
            "manufacturer_item_id": "SS-T8-S-049-20",
            "item_description": "SS 1/2\" OD X .049 WALL THICKNESS TUBING CUT TO 10 ft LENGTHS",
            "quantity": "60.000",
            "unit_price": "$17.92",
            "total_price": "$1,075.20"
        }},
        {{
            "customer_item_id": "NA",
            "manufacturer_item_id": "SS-1210-3-12-8",
            "item_description": "3/4 X 1/2 TB",
            "quantity": "1.000",
            "unit_price": "$102.15",
            "total_price": "$102.15"
        }},
        {{
            "customer_item_id": "NA",
            "manufacturer_item_id": "SS-1210-R-8",
            "item_description": "STAINLESS STEEL SWAGELOK TUBE FITTING, REDUCER, 3/4 IN. X 1/2 IN. TUBE OD",
            "quantity": "2.000",
            "unit_price": "$38.52",
            "total_price": "$77.04"
        }},
        {{
            "customer_item_id": "NA",
            "manufacturer_item_id": "SS-QF8-B-810",
            "item_description": "QUICK CONNECT 1/2 T",
            "quantity": "4.000",
            "unit_price": "$58.32",
            "total_price": "$233.28"
        }},
        {{
            "customer_item_id": "NA",
            "manufacturer_item_id": "SS-QF8-S-600",
            "item_description": "QUICK CONNECT 3/8 T",
            "quantity": "4.000",
            "unit_price": "$59.41",
            "total_price": "$237.64"
        }}
    ]
}}

"""
sample2 = """
Sample Input:
Line #

Item number Vendor item No.

Rev.

Reference Description

Delivery Search/Vendor No.Quantity Unit

Unit price

Amount

1.00

HC22­4­VCR­3S­4TB7

3/3/2025

3.00

ea

65.61

196.83

Lead time ::15 2.00

PB­6­BK

Lead time ::60 3.00

6LV­4­VCR­3S­4TB7P

Lead time ::25 4.00

6LV­4­VCR­3S­4TB7P

Lead time ::25 5.00

6LV­8MW­9­6P

Lead time ::25

GLAND,1/4" VCR, 1.10" LG, HASTELOY

14786270_075

2/17/2025

50.00

FEET 3.07

153.50

HOSE 3/8" ID PUSH­ON, BLACK BUNA

14786271_075

2/17/2025

50.00

EACH 14.68

734.00

GLAND, 1/4 VCR, 1.10" LONG* ( USE GDP00535)

14786272_075

3/17/2025

20.00

EACH 14.68

293.60

GLAND, 1/4 VCR, 1.10" LONG* ( USE GDP00535)

14786273_075

3/17/2025

32.00

EACH 60.85

1,947.20

ELBOW,REDUCING,1/2­3/8 6LV­8MW­9­6P NON CANCELLABLE NON RETURNABLE OB CLEVELAND,OH

14786274_075

6.00

6LVV­4­VCR­3S­4TB2

6/16/2025

125.00

EACH 10.13

1,266.25

Lead time ::120

GLAND, 1/4 VCR .60" LG, SST316L VIN/VAR

14786275_075

Sales balance 15,304.60

Total discount 0.00

Misc. charges 0.00

Sales tax 0.00

Round­off 0.00

Total 15,304.60USD

Buyer Name: Javier Cerdan

MDC Precision, LLC 30962 Santana St HAYWARD, CA 94544

Telephone........................: 510­265­3500 Fax...................................: 510­887­0626

1297 SWAGELOK NORTHERN CA 3393 WEST WARREN AVENUE FREMONT, CA 94538

Ph.: 510 933 2500 Fax: 510 933 2525

Attention information

Line #

Item number Vendor item No.

Rev.

Reference Description

Purchase order copy Number ...........................: PO­214301­1

Date .................................: 2/13/2025 Page ................................: 2 of 7 Ship Via ...........................: UPS GRD COL #4FY­281 Terms of payment ............: Net 45

Blanket No:

Blanket PO Date: 10/21/2024

Delivery address MDC Precision, LLC ATTN: GDP 30962 Santana St HAYWARD, CA 94544

Delivery Search/Vendor No.Quantity Unit

Unit price

Amount

2/17/2025

14.00

EACH 22.87

320.18

GLAND, 1/4" X 3/8" HI­FLO, 1.68"LG 6LV­4­HVCR­1­6TB7P

14786276_075

3/10/2025

200.00

EACH 26.02

5,204.00

GLAND,3/8 OD TUBE X 1/4 HVCR,.60 LG.,5RA,316SST 6LV­4­HVCR­3­.60SRP

14786277_075

3/3/2025

100.00

EACH 19.49

1,949.00

GLAND HI­FLOW 1.19L 5RA 6LV­4­HVCR­3­1.19SRP

14786278_075

3/24/2025

25.00

EACH 16.98

424.50

GLAND, 1/4" X 3/8" HI­FLO, 1.31"LG 6LV­4­HVCR­3­1.31SR

14786279_075

3/3/2025

10.00

EACH 60.42

604.20

BULKHEAD, 1/4" X 1.95"LG 6LV­4­VCR­61S­4TB7P

14786280_075

2/17/2025

25.00

EACH 28.70

717.50

GLAND,1/2VCR,1.29,5RA 6LV­8­VCR­3­8TB2P 80PCS MONTHLY USAGE

14786281_075

7.00

GDP00500

Lead time ::25 8.00

GDP00502

Lead time ::25

9.00

GDP00505

Lead time ::25 10.00

GDP00506

Lead time ::25 11.00

GDP00540

Lead time ::40 12.00

GDP00553

Lead time ::15

Sample Output:
{{
    "item": [{{
        "customer_item_id": "HC224VCR3S4TB7",
        "manufacturer_item_id": "14786270_075",
        "item_description": "GLAND,1/4\" VCR, 1.10\" LG, HASTELOY",
        "quantity": "3 EA",
        "unit_price": "65.61",
        "total_price": "196.83"
    }},
    {{
        "customer_item_id": "",
        "item_id": "PB6BK",
        "item_description": "HOSE 3/8\" ID PUSHON, BLACK BUNA",
        "quantity": "50 FEET",
        "unit_price": "3.07",
        "total_price": "153.50"
    }},
    {{
        "customer_item_id": "6LV4VCR3S4TB7P",
        "manufacturer_item_id": "14786271_075",
        "item_description": "GLAND, 1/4 VCR, 1.10\" LONG* (USE GDP00535)",
        "quantity": "50 EA",
        "unit_price": "14.68",
        "total_price": "734.00"
    }},
    {{
        "customer_item_id": "6LV4VCR3S4TB7P",
        "manufacturer_item_id": "14786272_075",
        "item_description": "GLAND, 1/4 VCR, 1.10\" LONG* (USE GDP00535)",
        "quantity": "20 EA",
        "unit_price": "14.68",
        "total_price": "293.60"
    }},
    {{
        "customer_item_id": "6LV8MW96P",
        "manufacturer_item_id": "14786273_075",
        "item_description": "ELBOW,REDUCING,1/2­3/8 6LV8MW96P NON CANCELLABLE NON RETURNABLE OB CLEVELAND,OH",
        "quantity": "32 EA",
        "unit_price": "60.85",
        "total_price": "1947.20"
    }},
    {{
        "customer_item_id": "6LVV4VCR3S4TB2",
        "manufacturer_item_id": "SST316LVIN/VAR",
        "item_description": "GLAND, 1/4 VCR .60\" LG, SST316L VIN/VAR",
        "quantity": "125 EA",
        "unit_price": "10.13",
        "total_price": "1266.25"
    }},
    {{
        "customer_item_id": "GDP00500",
        "manufacturer_item_id": "6LV4HVCR16TB7P",
        "item_description": "GLAND, 1/4\" X 3/8\" HI­FLO, 1.68\"LG",
        "quantity": "14 EA",
        "unit_price": "22.87",
        "total_price": "320.18"
    }},
    {{
        "customer_item_id": "GDP00502",
        "manufacturer_item_id": "316SST6LV4HVCR3.60SRP",
        "item_description": "GLAND,3/8 OD TUBE X 1/4 HVCR,.60 LG.,5RA,316SST",
        "quantity": "200 EA",
        "unit_price": "26.02",
        "total_price": "5204.00"
    }},
    {{
        "customer_item_id": "GDP00505",
        "manufacturer_item_id": "6LV4HVCR31.19SR",
        "item_description": "GLAND HI­FLOW 1.19L 5RA",
        "quantity": "100 EA",
        "unit_price": "19.49",
        "total_price": "1949.00"
    }},
    {{
        "customer_item_id": "GDP00506",
        "manufacturer_item_id": "6LV4HVCR31.31SR",
        "item_description": "GLAND, 1/4\" X 3/8\" HI­FLO, 1.31\"LG",
        "quantity": "25 EA",
        "unit_price": "16.98",
        "total_price": "424.50"
    }},
    {{
        "customer_item_id": "GDP00540",
        "manufacturer_item_id": "6LV4VCR61S4TB7P",
        "item_description": "BULKHEAD, 1/4\" X 1.95\"LG",
        "quantity": "10 EA",
        "unit_price": "60.42",
        "total_price": "604.20"
    }},
    {{
        "customer_item_id": "GDP00553",
        "manufacturer_item_id": "6LV8VCR38TB2P",
        "item_description": "GLAND,1/2VCR,1.29,5RA 80PCS MONTHLY USAGE",
        "quantity": "25 EA",
        "unit_price": "28.70",
        "total_price": "717.50"
    }},
    {{
        "customer_item_id": "GDP01361",
        "manufacturer_item_id": "SS8VCR38MTW",
        "item_description": "GLAND, 1/2 VCR, 1.50 LG, 316 SS",
        "quantity": "8 EA",
        "unit_price": "15.87",
        "total_price": "126.96"
    }},
    {{
        "customer_item_id": "KF4BKK5",
        "manufacturer_item_id": "KF4BKK5",
        "item_description": "Gasket Kit for B Series Bellows Sealed Valve",
        "quantity": "3 EA",
        "unit_price": "3.22",
        "total_price": "9.66"
    }},
    {{
        "customer_item_id": "SS4HVCR1SR",
        "manufacturer_item_id": "SS4HVCR1SR",
        "item_description": "NUT, 1/4\", HI FLO FEMALE",
        "quantity": "100 EA",
        "unit_price": "6.45",
        "total_price": "645.00"
    }},
    {{
        "customer_item_id": "SS60066W",
        "manufacturer_item_id": "SS60066W",
        "item_description": "WELD UNION, 3/8\" TUBE SOCKET",
        "quantity": "28 EA",
        "unit_price": "17.67",
        "total_price": "494.76"
    }},
    {{
        "customer_item_id": "6LVVDPBW4PC",
        "manufacturer_item_id": "6LVVDPBW4PC",
        "item_description": "VALVE 1/4\" PNEU. NC TB STUB",
        "quantity": "1 EA",
        "unit_price": "217.46",
        "total_price": "217.46"
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
    print("ITEM TABLE : ",result)
    return result

# answer = item_table(input)

template6 = """
## Instructions
Extract the Cost related information and Other Details from the following PO content.

Part 1: Cost Information
Carefully analyze the content and extract the Cost related information using these rules:
Net Amount:
- For single item the total price will be net amount
- And for multiple item Calculate by summing (quantity * unit price) for all items
- If either quantity OR unit price is missing for ANY item, return "NA"
Tax:
- Use explicitly stated tax amount from content
- If not found, return "NA"
Total Amount:
- Use explicitly stated total amount from content
- If not found BUT net amount is calculated AND tax amount is found, calculate as: net amount + tax
- If not found AND tax is "NA", use the net amount as total amount
- If net amount is "NA", return "NA"
Currency:
- Extract the currency symbol or code (USD, EUR, INR, £, €, ¥, etc.) that appears with prices
- Check for currency indicators near amounts, in headers, or in payment terms
- If multiple currencies appear, use the one associated with the total amount
- If no currency is explicitly mentioned, return "NA"

Important Cost Rules:
- Do NOT calculate or estimate values if required information is missing
- Return "NA" if any required field is not explicitly mentioned in the PO
- For Net Amount: Only calculate if both quantity and unit price are clearly stated for all items
- For Tax: Only use if explicitly stated in PO content, otherwise return "NA"
- For Total Amount: Only use if explicitly mentioned in PO content
- Do NOT calculate or infer any values - only use explicitly stated amounts

Do not modify or remove any special characters from the net_amount, tax, or total_amount fields, as these contain important information about numerical formatting that varies by language and region.

Part 2: Other Details
Carefully analyze the content for information related to:
- Supplier Instructions
- Invoicing Instructions
- Notes

Important Other Details Rules:
- Look for information outside of these standard fields:
  * Customer details (name, address, city, country)
  * Supplier details (name, address, city, country)
  * Delivery details (name, address, city, country)
  * Cost details (net amount, tax, total amount)
- Keep the information brief and relevant
- Include only information from other sections of the PO

Data Cleaning Rules:
- Strictly remove any special characters and replace them with an empty string
- Remove any / or \\ from the extracted information
- Strictly remove any unwanted blank spaces in the response fields

Return the output in this exact JSON format:
{{
    "cost": {{
        "net_amount": "",
        "tax": "",
        "total_amount": ""
        "currency": ""
    }},
    "other_details": {{
        "supplier_instructions": "",
        "invoicing_instructions": "",
        "notes": ""
    }},
    "shipping_details": {{
        'shipping_method': '',
        'shipping_agent': '',
        'shipping_service': ''
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


import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_all(input, max_retries=5):
    def parallel_attempt():
        # List of functions to execute
        functions = [
            quotation_ponumber,
            customer_supplier_information,
            item_table,
            cost_information
        ]
        
        combined_response = {}
        
        # Run functions in parallel
        with ThreadPoolExecutor(max_workers=1) as executor:
            # Submit all functions
            future_to_func = {
                executor.submit(func, input): func.__name__ 
                for func in functions
            }
            
            # Process results as they complete
            for future in as_completed(future_to_func):
                func_name = future_to_func[future]
                try:
                    response = future.result()
                    response_json = json.loads(response)
                    combined_response.update(response_json)
                except json.JSONDecodeError as e:
                    print(f"Failed to parse response from {func_name}\nError: {e}")
                    raise e
                except Exception as e:
                    print(f"Error executing {func_name}: {str(e)}")
                    raise e
                
        return combined_response

    # Retry logic
    for attempt in range(max_retries):
        try:
            result = parallel_attempt()
            return result
        except (json.JSONDecodeError, Exception) as e:
            print(f"Attempt {attempt + 1} failed. Retrying...")
            if attempt == max_retries - 1:
                print("Max retries reached. All attempts failed.")
                raise
            time.sleep(1)

    return None

# import time
# import json
# from concurrent.futures import ProcessPoolExecutor, as_completed

# def run_all(input, max_retries=5):
#     def parallel_attempt():
#         # List of functions to execute
#         functions = [
#             quotation_ponumber,
#             customer_supplier_information,
#             item_table,
#             cost_information
#         ]
        
#         combined_response = {}
        
#         # Run functions in parallel
#         with ProcessPoolExecutor(max_workers=4) as executor:
#             # Submit all functions
#             future_to_func = {
#                 executor.submit(func, input): func.__name__ 
#                 for func in functions
#             }
            
#             # Process results as they complete
#             for future in as_completed(future_to_func):
#                 func_name = future_to_func[future]
#                 try:
#                     response = future.result()
#                     response_json = json.loads(response)
#                     combined_response.update(response_json)
#                 except json.JSONDecodeError as e:
#                     print(f"Failed to parse response from {func_name}\nError: {e}")
#                     raise e
#                 except Exception as e:
#                     print(f"Error executing {func_name}: {str(e)}")
#                     raise e
                
#         return combined_response

#     # Retry logic
#     for attempt in range(max_retries):
#         try:
#             result = parallel_attempt()
#             return result
#         except (json.JSONDecodeError, Exception) as e:
#             print(f"Attempt {attempt + 1} failed. Retrying...")
#             if attempt == max_retries - 1:
#                 print("Max retries reached. All attempts failed.")
#                 raise
#             time.sleep(1)

#     return None

# answer = cost_information(input)
# import time

# def run_all(input, max_retries=5):
#     def single_attempt():
#         responses = [
#             quotation_ponumber(input),
#             customer_supplier_information(input),
#             item_table(input),
#             cost_information(input)
#         ]
#         print(responses)
#         combined_response = {}
        
#         for response in responses:
#             try:
#                 response_json = json.loads(response)
#                 combined_response.update(response_json)
#             except json.JSONDecodeError as e:
#                 print(f"Failed to parse response: {response}\nError: {e}")
#                 # Raising the error to trigger retry
#                 raise e
                
#         return combined_response

#     # Retry logic
#     for attempt in range(max_retries):
#         try:
#             result = single_attempt()
#             return result
#         except json.JSONDecodeError:
#             print(f"Attempt {attempt + 1} failed. Retrying...")
#             if attempt == max_retries - 1:
#                 print("Max retries reached. All attempts failed.")
#                 raise  # Re-raise the last exception if all retries fail
#             # Optional: Add a small delay between retries
#             time.sleep(1)  # Import time module if you use this

#     return None  # This line won't be reached due to the raise above, but added for completeness

# def run_all(input):
#     responses = [
#         quotation_ponumber(input),
#         customer_supplier_information(input),
#         item_table(input),
#         cost_information(input)
#     ]
#     print(responses)
#     combined_response = {}
#     for response in responses:
#         try:
#             # Parse each response from JSON string to dictionary
#             response_json = json.loads(response)
#             combined_response.update(response_json)
#         except json.JSONDecodeError as e:
#             print(f"Failed to parse response: {response}\nError: {e}")

#     print(combined_response)
#     # return json.dumps(combined_response)
#     return combined_response