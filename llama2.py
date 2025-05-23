import json
import concurrent.futures
import traceback
from typing import Dict, Any, List
from Agents.po_parse_agent import extract_po_grouped_fields
from Agents.item_agent import extract_po_items_only
# from Agents.agent5 import classify_po_urgency

def flatten_json(nested_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts all leaf values from a nested JSON structure into a flat dictionary,
    preserving only the leaf keys without any prefixes.
    """
    flattened = {}
    
    def extract_leaves(data):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    extract_leaves(value)
                else:
                    flattened[key] = value
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    extract_leaves(item)
    
    extract_leaves(nested_json)
    return flattened

def load_product_fields():
    """
    Load product fields from the purchase_order_data_fields.json file.
    Returns the complete structure from the file as well as the item template.
    """
    try:
        with open('purchase_order_data_fields.json', 'r') as file:
            data = json.load(file)
            
        # Get the item template
        item_template = data.get('item', [])
        
        return data, item_template
    except Exception as e:
        print(f"Error loading purchase_order_data_fields.json: {str(e)}")
        return {}, []

# Fallback function to extract items if the main agent fails
def fallback_extract_items(po_content: str, item_template: list) -> list:
    """
    A simple fallback extractor for items when the main agent fails.
    This is a basic implementation that should be enhanced with your specific logic.
    """
    print("Using fallback item extraction method")
    
    # Create a basic empty structure based on the template
    # In a real implementation, you would add logic to parse the PO content
    # and extract items based on your specific requirements
    
    # For now, just return an empty array that matches the template structure
    return []

# Main function to parse a purchase order in parallel and return flattened result
def parse_purchase_order(po_content: str) -> Dict[str, Any]:
    # Load fields directly from purchase_order_data_fields.json
    result_structure, item_template = load_product_fields()
    print("Result structure:", result_structure)
    
    # Create tasks for parallel processing
    tasks = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Process all non-item fields with extract_po_grouped_fields
        for field_key, field_structure in result_structure.items():
            if field_key != 'item':  # Process all fields except 'item'
                task = executor.submit(extract_po_grouped_fields, po_content, field_key, field_structure)
                tasks.append((field_key, task))
        
        # Process urgency/priority classification
        # priority_task = executor.submit(classify_po_urgency, po_content)
        
        # Collect results from non-item fields
        regular_fields_result = {}
        for field_key, task in tasks:
            try:
                field_result = task.result()
                regular_fields_result.update(field_result)
            except Exception as e:
                print(f"Error processing {field_key}: {str(e)}")
                # Use empty structure as fallback
                regular_fields_result[field_key] = result_structure[field_key]
        
        # Try different approaches for item extraction
        item_result = []
        
        # Method 1: Try with three parameters (as in original code)
        try:
            item_result = extract_po_items_only(po_content, 'item', item_template)
            print(f"[+]Item extraction succeeded with 3 parameters-----[+]\n{item_result}")
        except Exception as e:
            print(f"Method 1 - Error processing items with 3 parameters: {str(e)}")
            traceback.print_exc()
            
            # Method 2: Try with two parameters (field_key omitted)
            try:
                item_result = extract_po_items_only(po_content, item_template)
                print(f"[+]Item extraction succeeded with 2 parameters-----[+]\n{item_result}")
            except Exception as e:
                print(f"Method 2 - Error processing items with 2 parameters: {str(e)}")
                traceback.print_exc()
                
                # Method 3: Use fallback method as last resort
                try:
                    item_result = fallback_extract_items(po_content, item_template)
                    print(f"[+]Item extraction used fallback method-----[+]\n{item_result}")
                except Exception as e:
                    print(f"Method 3 - Error using fallback method: {str(e)}")
                    traceback.print_exc()
                    item_result = []  # Final fallback
            
        # Get priority result
        # try:
        #     priority_result = priority_task.result()
        #     print(f"[+]Priority-----[+]\n{priority_result}")
        # except Exception as e:
        #     print(f"Error determining priority: {str(e)}")
        #     priority_result = "normal"  # Default to normal if classification fails
    
    # Flatten only the regular fields (non-item fields)
    flattened_regular_fields = flatten_json(regular_fields_result)
    
    # Combine flattened regular fields with the unflattened item result and priority
    final_result = flattened_regular_fields
    final_result['item'] = item_result
    # final_result['is_priority'] = priority_result
    
    print(json.dumps(final_result, indent=2))
    return final_result

# Example usage
# def main():
#     sample_po_content = """
# DIBERT VALVE & FITTING COMPANY
# 5119 PEGASUS CT
# SUITE K
# FREDERICK, MD 21704
# United States of America

# Purchase Order: 2500937

# Tax ID: 54-1255705

# 10112

# Ship To:

# FIBERTEK, INC.
# 13605 Dulles Technology Drive
# Attention: Receiving Department
# Herndon, VA 20171
# United States of America

# Page 1 of 3

# Date Printed: 05/12/25

# Trans Currency: USD

# Buyer

# Terms

# FOB

# Sales
# Order

# Ship Via

# Deliver To

# Smeltzer, Haley A

# NET 30

# ORIGIN PPY&ADD

# GROUND

# Item/Description

# Rev

# Due
# Date

# Desired
# Date

# U/M

# Order
# Quantity

# STOCK JIM BEATTIE
# Net Unit
# Cost

# Extended
# Cost

# Order To:

# Fax: FLIGHT
# Order
# Date
# 05/12/2025

# Line

# 05/16/25

# 05/16/25

# EA

# 10

# 17.27

# $172.70

# 1 SS-600-1-4ST

# Stainless Steel Swagelok Tube Fitting, Male Connector, 3/8
# Cert of Conf Required

# Prime Contract #: Withheld
# N/A - Internal LMMF

# 100.00%

# AOP:4200    01.02    0879.001.01.000003.01

# "Seller's signature below hereby certifies and provides on date of award,
# in accordance with FAR 52.209-6, Seller and its principals are not
# debarred, suspended, or proposed for debarment by the U.S. Federal
# Government.  Seller further attests, written disclosures concerning
# Payment to Influence per FAR 52.203-11 and FAR 52.203-12.  In addition, by
# signing this agreement, Seller hereby certifies to the best of its
# knowledge and belief that no federal appropriated funds have been paid or
# will be paid to any person for influencing or attempting to influence an
# officer or employee of any agency, a Member of Congress, an officer or
# employee of Congress, or an employee of a Member of Congress on its behalf
# in connection with the awarding of this Subcontract.  In addition, in
# accordance with FAR 52,211-15 - DPAS Rated Order, if this order exceeds
# $75,000 and reflects a DPAS rating, this acknowledgment attests to
# Seller's compliance to DPAS obligations."

# In witness whereof, the duly authorized representatives of Buyer and
# Seller have executed this Order on the Dates shown.


# DIBERT VALVE & FITTING COMPANY
# 5119 PEGASUS CT
# SUITE K
# FREDERICK, MD 21704
# United States of America

# Purchase Order: 2500937

# Tax ID: 54-1255705

# 10112

# Ship To:

# FIBERTEK, INC.
# 13605 Dulles Technology Drive
# Attention: Receiving Department
# Herndon, VA 20171
# United States of America

# Page 2 of 3

# Date Printed: 05/12/25

# Trans Currency: USD

# Buyer

# Terms

# FOB

# Sales
# Order

# Ship Via

# Deliver To

# Smeltzer, Haley A

# NET 30

# ORIGIN PPY&ADD

# GROUND

# Item/Description

# Rev

# Due
# Date

# Desired
# Date

# U/M

# Order
# Quantity

# STOCK JIM BEATTIE
# Net Unit
# Cost

# Extended
# Cost

# Order To:

# Fax: FLIGHT
# Order
# Date
# 05/12/2025

# Line

# ======================P L E A S E   N O T E==========================
# 1) The following documents are hereby incorporated by reference and made
# a material part of this Order.  In the event of an inconsistency or
# conflict between provisions of this Order, the inconsistency or conflict
# shall be resolved by giving precedence in the following order:
# A)   Purchase Order content;
# B)   Doc 70000185 REV G  Standard Terms and Conditions;
# C)   Exhibits and Attachments (Inclusive of attachments provided with
# email at time of order)
# D)   Quality Assurance Document 70000024 Rev P (If Applicable)
# E)   Specifications and/or drawings.
# 2) THIS IS A CONFIRMING PURCHASE ORDER. DO NOT DUPLICATE.
# 3) SUBSTITUTIONS FOR ANY PART OF THIS ORDER ARE NOT ACCEPTABLE.
# 4) VENDOR IS REQUIRED TO PROVIDE ACKNOWLEDGEMENT OF THIS PURCHASE ORDER
#  VIA FAX, EMAIL, OR TELEPHONE.
# 5) VENDOR MUST BE AN AUTHORIZED MANUFACTURER OR DISTRIBUTOR OF THE PARTS
#   HERE IN. IF NOT, VENDOR IS REQUIRED TO IMPLEMENT AND MAINTAIN A
# COUNTERFEIT PARTS PROGRAM USING SAE-AS5553 AS A GUIDELINE.
# 6) NO 3RD PARTY BILLINGS WILL BE ACCEPTED.
# 7) THIS CONTRACTOR AND SUBCONTRACTOR SHALL ABIDE BY THE REQUIREMENTS OF
#  41 CFR 60-741.5(a). THIS REGULATION PROHIBITS DISCRIMINATION AGAINST
# QUALIFIED INDIVIDUALS ON THE BASIS OF DISABILITY, AND REQUIRES AFFIRMATIVE
#    ACTION BY COVERED PRIME CONTRACTORS AND SUBCONTRACTORS TO EMPLOY AND
# ADVANCE IN EMPLOYMENT QUALIFIED INDIVIDUALS WITH DISABILITIES.
# 8) THIS CONTRACTOR AND SUBCONTRACTOR SHALL ABIDE BY THE REQUIREMENTS OF
#  41 CFR 60-300.5(a). THIS REGULATION PROHIBITS DISCRIMINATION AGAINST
# QUALIFIED PROTECTED VETERANS, AND REQUIRES AFFIRMATIVE ACTION BY COVERED
#  PRIME CONTRACTORS AND SUBCONTRACTORS TO EMPLOY AND ADVANCE IN EMPLOYMENT
#   QUALIFIED PROTECTED VETERANS.
# 9) FOR ALL ORDERS BEING DELIVERED TO MILITARY BASES, YOU MUST BE A US
# CITIZEN AND COORDINATE ADDITIONAL PERSONNEL DETAILS BEFORE ARRIVAL WITH
# THE ORDER POC OR FACILITIES COORDINATOR.
# ===========================================================================


# DIBERT VALVE & FITTING COMPANY
# 5119 PEGASUS CT
# SUITE K
# FREDERICK, MD 21704
# United States of America

# Purchase Order: 2500937

# Tax ID: 54-1255705

# 10112

# Ship To:

# FIBERTEK, INC.
# 13605 Dulles Technology Drive
# Attention: Receiving Department
# Herndon, VA 20171
# United States of America

# Page 3 of 3

# Date Printed: 05/12/25

# Trans Currency: USD

# Buyer

# Terms

# FOB

# Sales
# Order

# Ship Via

# Deliver To

# Smeltzer, Haley A

# NET 30

# ORIGIN PPY&ADD

# GROUND

# Item/Description

# Rev

# Due
# Date

# Desired
# Date

# U/M

# Order
# Quantity

# STOCK JIM BEATTIE
# Net Unit
# Cost

# Extended
# Cost

# Order To:

# Fax: FLIGHT
# Order
# Date
# 05/12/2025

# Line

# * FOR PROMPT PAYMENT, SUBMIT ALL INVOICES IN PDF FORMAT BY EMAIL
# TO ACCOUNTSPAYABLE@FIBERTEK.COM OR MAIL TO FIBERTEK INC.
# AT 13605 DULLES TECHNOLOGY DRIVE HERNDON, VA 20171.
#  * ALL INVOICES MUST REFERENCE CORRESPONDING PURCHASE ORDER # OR PAYMENT
# CANNOT BE PROCESSED.

# Bill To:

# FIBERTEK, INC.
# 13605 Dulles Technology Drive
# Attention: Accounts Payable
# Herndon, VA 20171
# United States of America

# PO Total Amt:

# $172.70

# Authorized Signature(s)
#     """
    
#     result = parse_purchase_order(sample_po_content)
#     # print(json.dumps(result, indent=2))

# if __name__ == "__main__":
#     main()