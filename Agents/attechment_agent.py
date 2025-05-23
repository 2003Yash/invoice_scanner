import re
import pandas as pd
import json
from io import StringIO
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_models.gemini_client import get_gemini_response
from prompt_library.gemini import attachment_agent_prompt


def preprocess_data(data):
    """
    Preprocesses the input data to handle different formats.
    """
    try:
        if '\t' in data or '|' in data or re.search(r'\s{2,}', data):
            df = pd.read_csv(StringIO(data), sep=None, engine='python')
            return f"Data appears to be in table format:\n{df.to_string()}"
    except Exception:
        pass
    return data


def create_prompt(processed_data):
    return attachment_agent_prompt.format(text=processed_data)


def call_llm(prompt):
    return get_gemini_response(prompt)


def parse_response(response):
    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            response = json_match.group(0)

        result = json.loads(response)

        document_type = result.get("document_type", "other")
        has_po_number = result.get("has_po_number", False)
        is_po = result.get("is_purchase_order", False)

        if not has_po_number:
            is_po = False
            if document_type == "purchase_order":
                document_type = "quotation"

        return is_po, has_po_number, result.get("po_number"), document_type, result.get("summary", "No summary available.")
    except Exception as e:
        return False, False, None, "other", f"Error parsing response: {str(e)}"


def is_purchase_order(data):
    processed_data = preprocess_data(data)
    prompt = create_prompt(processed_data)
    response = call_llm(prompt)
    is_po, has_po_number, po_number, document_type, summary = parse_response(response)

    if has_po_number and not is_po:
        new_po_indicators = [
            "process the attached po",
            "process the attached purchase order",
            "please process",
            "send an so acknowledgment",
            "new order",
            "new purchase order"
        ]
        indicator_count = sum(1 for indicator in new_po_indicators if indicator.lower() in processed_data.lower())
        if indicator_count >= 1 and "attached" in processed_data.lower() and not any(term.lower() in processed_data.lower() for term in ["cancel", "cancellation", "void"]):
            is_po = True
            document_type = "purchase_order"
            summary = "This is an email requesting to process a new purchase order. " + summary

    po_indicators = [
        "Purchase Order:",
        "Order To:",
        "Ship To:",
        "Line Item/Description",
        "Order Quantity",
        "Net Unit Cost",
        "Extended Cost",
        "Buyer",
        "Ship Via",
        "Deliver To"
    ]
    po_indicator_count = sum(1 for indicator in po_indicators if indicator in processed_data)

    if has_po_number and po_indicator_count >= 4 and not is_po:
        print("[OVERRIDE] Detected REPRINT but document contains valid PO structure.")
        is_po = True
        document_type = "purchase_order"
        summary = f"Overridden: Document is marked as a reprint but has PO number {po_number} and sufficient purchase order structure. Treated as a valid purchase order."

    # ✅ Final override: treat REPRINTs as valid POs
    if has_po_number and po_indicator_count >= 4 and not is_po:
        is_po = True
        document_type = "purchase_order"
        summary = "This document is marked as a reprint but contains a valid PO number and purchase order structure. Treated as a valid purchase order."

    terms_indicators = [
        "terms of purchase",
        "standard terms",
        "agreement",
        "shall be referred to as",
        "shall apply",
        "expressly agrees to be bound",
        "precedence shall apply",
        "order of precedence",
        "frame agreement"
    ]
    terms_indicator_count = sum(1 for indicator in terms_indicators if indicator.lower() in processed_data.lower())

    if terms_indicator_count >= 3 and po_indicator_count <= 2 and document_type != "purchase_order":
        is_po = False
        document_type = "other"
        summary = "This appears to be a terms and conditions document related to purchase orders, not an actual new purchase order."

    if not has_po_number and document_type == "purchase_order":
        is_po = False
        document_type = "quotation"
        summary = "This document lacks a PO number and has been classified as a quotation rather than a purchase order. " + summary

    result = {
        "is_purchase_order": is_po,
        "has_po_number": has_po_number,
        "po_number": po_number,
        "document_type": document_type,
        "summary": summary
    }

    return result

# # Example usage
# if __name__ == "__main__":
#     # Example 1: Test with a terms and conditions document (not a purchase order)
#     test_data1 = """
#  Purchase Order: 2500937 Page 1 of 3
# Date Printed: 05/12/25

# Tax ID: 54-1255705

# Trans Currency: USD

# Order To: DIBERT VALVE & FITTING COMPANY 10112 Ship To: FIBERTEK, INC.

# 5119 PEGASUS CT 13605 Dulles Technology Drive
# SUITE K Attention: Receiving Department
# FREDERICK, MD 21704 Herndon, VA 20171
# United States of America United States of America

# Fax: FLIGHT
# Order
# Date Buyer Terms FOB Sales

# Order Ship Via Deliver To
# 05/12/2025 Smeltzer, Haley A NET 30 ORIGIN PPY&ADD GROUND STOCK JIM BEATTIE
# Line Item/Description Rev Due
# Date
# Desired
# Date U/M Order
# Quantity

# Net Unit
# Cost

# Extended
# Cost

# 1 SS-600-1-4ST 05/16/25 05/16/25 EA 10 17.27 $172.70
# Stainless Steel Swagelok Tube Fitting, Male Connector, 3/8
# Cert of Conf Required
# Prime Contract #: Withheld
# N/A - Internal LMMF
# 100.00% AOP:4200 01.02 0879.001.01.000003.01

# "Seller's signature below hereby certifies and provides on date of award,
# in accordance with FAR 52.209-6, Seller and its principals are not
# debarred, suspended, or proposed for debarment by the U.S. Federal
# Government. Seller further attests, written disclosures concerning
# Payment to Influence per FAR 52.203-11 and FAR 52.203-12. In addition, by
# signing this agreement, Seller hereby certifies to the best of its
# knowledge and belief that no federal appropriated funds have been paid or
# will be paid to any person for influencing or attempting to influence an
# officer or employee of any agency, a Member of Congress, an officer or
# employee of Congress, or an employee of a Member of Congress on its behalf
# in connection with the awarding of this Subcontract. In addition, in
# accordance with FAR 52,211-15 - DPAS Rated Order, if this order exceeds
# $75,000 and reflects a DPAS rating, this acknowledgment attests to
# Seller's compliance to DPAS obligations."
# In witness whereof, the duly authorized representatives of Buyer and
# Seller have executed this Order on the Dates shown.

# Purchase Order: 2500937 Page 2 of 3
# Date Printed: 05/12/25

# Tax ID: 54-1255705

# Trans Currency: USD

# Order To: DIBERT VALVE & FITTING COMPANY 10112 Ship To: FIBERTEK, INC.

# 5119 PEGASUS CT 13605 Dulles Technology Drive
# SUITE K Attention: Receiving Department
# FREDERICK, MD 21704 Herndon, VA 20171
# United States of America United States of America

# Fax: FLIGHT
# Order
# Date Buyer Terms FOB Sales

# Order Ship Via Deliver To
# 05/12/2025 Smeltzer, Haley A NET 30 ORIGIN PPY&ADD GROUND STOCK JIM BEATTIE
# Line Item/Description Rev Due
# Date
# Desired
# Date U/M Order
# Quantity

# Net Unit
# Cost

# Extended
# Cost

# ======================P L E A S E N O T E==========================
# 1) The following documents are hereby incorporated by reference and made
# a material part of this Order. In the event of an inconsistency or
# conflict between provisions of this Order, the inconsistency or conflict
# shall be resolved by giving precedence in the following order:
# A) Purchase Order content;
# B) Doc 70000185 REV G Standard Terms and Conditions;
# C) Exhibits and Attachments (Inclusive of attachments provided with
# email at time of order)
# D) Quality Assurance Document 70000024 Rev P (If Applicable)
# E) Specifications and/or drawings.
# 2) THIS IS A CONFIRMING PURCHASE ORDER. DO NOT DUPLICATE.
# 3) SUBSTITUTIONS FOR ANY PART OF THIS ORDER ARE NOT ACCEPTABLE.
# 4) VENDOR IS REQUIRED TO PROVIDE ACKNOWLEDGEMENT OF THIS PURCHASE ORDER
# VIA FAX, EMAIL, OR TELEPHONE.
# 5) VENDOR MUST BE AN AUTHORIZED MANUFACTURER OR DISTRIBUTOR OF THE PARTS
# HERE IN. IF NOT, VENDOR IS REQUIRED TO IMPLEMENT AND MAINTAIN A
# COUNTERFEIT PARTS PROGRAM USING SAE-AS5553 AS A GUIDELINE.
# 6) NO 3RD PARTY BILLINGS WILL BE ACCEPTED.
# 7) THIS CONTRACTOR AND SUBCONTRACTOR SHALL ABIDE BY THE REQUIREMENTS OF
# 41 CFR 60-741.5(a). THIS REGULATION PROHIBITS DISCRIMINATION AGAINST
# QUALIFIED INDIVIDUALS ON THE BASIS OF DISABILITY, AND REQUIRES AFFIRMATIVE
# ACTION BY COVERED PRIME CONTRACTORS AND SUBCONTRACTORS TO EMPLOY AND
# ADVANCE IN EMPLOYMENT QUALIFIED INDIVIDUALS WITH DISABILITIES.
# 8) THIS CONTRACTOR AND SUBCONTRACTOR SHALL ABIDE BY THE REQUIREMENTS OF
# 41 CFR 60-300.5(a). THIS REGULATION PROHIBITS DISCRIMINATION AGAINST
# QUALIFIED PROTECTED VETERANS, AND REQUIRES AFFIRMATIVE ACTION BY COVERED
# PRIME CONTRACTORS AND SUBCONTRACTORS TO EMPLOY AND ADVANCE IN EMPLOYMENT
# QUALIFIED PROTECTED VETERANS.
# 9) FOR ALL ORDERS BEING DELIVERED TO MILITARY BASES, YOU MUST BE A US
# CITIZEN AND COORDINATE ADDITIONAL PERSONNEL DETAILS BEFORE ARRIVAL WITH
# THE ORDER POC OR FACILITIES COORDINATOR.
# ===========================================================================

# Purchase Order: 2500937 Page 3 of 3
# Date Printed: 05/12/25

# Tax ID: 54-1255705

# Trans Currency: USD

# Order To: DIBERT VALVE & FITTING COMPANY 10112 Ship To: FIBERTEK, INC.

# 5119 PEGASUS CT 13605 Dulles Technology Drive
# SUITE K Attention: Receiving Department
# FREDERICK, MD 21704 Herndon, VA 20171
# United States of America United States of America

# Fax: FLIGHT
# Order
# Date Buyer Terms FOB Sales

# Order Ship Via Deliver To
# 05/12/2025 Smeltzer, Haley A NET 30 ORIGIN PPY&ADD GROUND STOCK JIM BEATTIE
# Line Item/Description Rev Due
# Date
# Desired
# Date U/M Order
# Quantity

# Net Unit
# Cost

# Extended
# Cost

# * FOR PROMPT PAYMENT, SUBMIT ALL INVOICES IN PDF FORMAT BY EMAIL
# TO ACCOUNTSPAYABLE@FIBERTEK.COM OR MAIL TO FIBERTEK INC.
# AT 13605 DULLES TECHNOLOGY DRIVE HERNDON, VA 20171.
# * ALL INVOICES MUST REFERENCE CORRESPONDING PURCHASE ORDER # OR PAYMENT
# CANNOT BE PROCESSED.
# Bill To: FIBERTEK, INC.

# 13605 Dulles Technology Drive
# Attention: Accounts Payable
#     """
    
#     result = is_purchase_order(test_data1)
#     print(json.dumps(result, indent=4))
