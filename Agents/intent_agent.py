import pymongo
from pymongo import MongoClient
import sys
import os
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_models.gemini_client import get_gemini_response
from prompt_library.gemini import gemini_intent_agent_prompt


def get_active_intent_labels():
    try:
        client = MongoClient('mongodb+srv://aman:QJqnP4b8dwZlcBeW@cluster0.b6mzjd0.mongodb.net/')
        db = client.get_database('temp_data')
        intent_collection = db.get_collection('intent-action')
        active_intents = intent_collection.find({"is_active": True})
        intent_labels = [doc["action_name"] for doc in active_intents]
        if not intent_labels:
            intent_labels = [
                "po process/new purchase order",
                "quotation requirement",
                "invoice inquiry",
                "PO Cancellation",
                "PO Change",
                "other"
            ]
        if "other" not in intent_labels:
            intent_labels.append("other")
        return intent_labels
    except Exception as e:
        print(f"Error fetching intent labels from database: {e}")
        return [
            "po process/new purchase order",
            "quotation requirement",
            "invoice inquiry",
            "PO Cancellation",
            "PO Change",
            "other"
        ]

def get_intent_keywords():
    try:
        client = MongoClient('mongodb+srv://aman:QJqnP4b8dwZlcBeW@cluster0.b6mzjd0.mongodb.net/')
        db = client.get_database('temp_data')
        intent_collection = db.get_collection('intent-action')
        active_intents = intent_collection.find({"is_active": True})
        keyword_mapping = {}
        for doc in active_intents:
            action_name = doc["action_name"]
            keywords = doc.get("keyword", [])
            keyword_mapping[action_name] = keywords
        if not keyword_mapping:
            keyword_mapping = {}
        if "other" not in keyword_mapping:
            keyword_mapping["other"] = ["miscellaneous", "general", "information", "query"]
        return keyword_mapping
    except Exception as e:
        print(f"Error fetching intent keywords from database: {e}")
        return {}

INTENT_LABELS = get_active_intent_labels()
KEYWORD_MAPPING = get_intent_keywords()

def extract_subject(email_text: str) -> str:
    subject_pattern = re.compile(r'Subject:\s*(.*?)(?=\nTo:|\nFrom:|\n\w+:|$)', re.IGNORECASE | re.DOTALL)
    match = subject_pattern.search(email_text)
    if match:
        subject = match.group(1).strip()
        subject = re.sub(r'\s+', ' ', subject)
        return subject
    return ""

def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def check_for_cancellation_indicators(text: str) -> bool:
    cancel_phrases = [
        "cancelled an order", 
        "baker hughes cancelled",
        "cancel an order",
        "has been cancelled",
        "order cancelled",
        "po cancelled",
        "purchase order cancelled",
        "cancel order",
        "cancellation of",
        "order cancellation"
    ]
    text_lower = text.lower()
    for phrase in cancel_phrases:
        if phrase in text_lower:
            return True
    sentences = re.split(r'[.!?]', text_lower)
    for sentence in sentences:
        if any(term in sentence for term in ["cancel", "cancelled", "canceled"]):
            if any(term in sentence for term in ["order", "po", "purchase"]):
                return True
    return False

def check_for_po_change_indicators(text: str) -> bool:
    change_phrases = [
        "changed the po",
        "has changed the po",
        "changed an order",
        "has changed an order", 
        "purchase order (changed)",
        "po has been changed",
        "order has been modified",
        "order change notification",
        "modified purchase order",
        "amended order",
        "to change",
        "order change",
        "purchase order amendment"
    ]
    text_lower = text.lower()
    for phrase in change_phrases:
        if phrase in text_lower:
            return True
    sentences = re.split(r'[.!?]', text_lower)
    for sentence in sentences:
        if any(term in sentence for term in ["changed", "modified", "amended", "revised"]):
            if any(term in sentence for term in ["order", "po", "purchase"]):
                return True
    if re.search(r'purchase\s+order\s*\(changed\)', text_lower):
        return True
    return False

def check_for_new_po_indicators(text: str) -> bool:
    new_po_phrases = [
        "new purchase order",
        "create purchase order",
        "create po",
        "new po",
        "po creation",
        "po request",
        "submit po",
        "request for purchase order",
        "purchase order request",
        "requesting a purchase order",
        "need to create po",
        "need to submit po",
        "new order request",
        "create a new order",
        "process an order",  
        "please process an order",  
        "order from",  
        "this is an order"  
    ]
    text_lower = text.lower()
    for phrase in new_po_phrases:
        if phrase in text_lower:
            return True
    sentences = re.split(r'[.!?]', text_lower)
    for sentence in sentences:
        if any(term in sentence for term in ["new", "create", "submit", "request", "need", "process"]):
            if any(term in sentence for term in ["order", "po", "purchase"]):
                if not any(term in sentence for term in ["cancel", "chang", "modif", "amend"]):
                    return True
    if re.search(r'(process|place|submit)\s+.{0,20}\s*order', text_lower) and not re.search(r'(changed|cancelled|canceled|modified|amended)', text_lower):
        return True
    if re.search(r'purchase\s+order', text_lower) and not re.search(r'(changed|cancelled|canceled|modified|amended)', text_lower):
        return True
    return False

def keyword_based_detection(text: str, subject: str = "") -> str:
    global INTENT_LABELS, KEYWORD_MAPPING
    INTENT_LABELS = get_active_intent_labels()
    KEYWORD_MAPPING = get_intent_keywords()
    
    cleaned_subject = clean_text(subject)
    cleaned_text = clean_text(text)
    
    # First check for specific indicators
    if check_for_cancellation_indicators(text) or check_for_cancellation_indicators(subject):
        if "PO Cancellation" in INTENT_LABELS:
            return "PO Cancellation"
        if "PO Cancellation" in INTENT_LABELS:
            return "PO Cancellation"
    
    if check_for_po_change_indicators(text) or check_for_po_change_indicators(subject):
        if "PO Change" in INTENT_LABELS:
            return "PO Change"
        if "PO Change" in INTENT_LABELS:
            return "PO Change"
    
    if check_for_new_po_indicators(text) or check_for_new_po_indicators(subject):
        new_po_intent = "po process/new purchase order"
        if new_po_intent in INTENT_LABELS:
            return new_po_intent
    
    # Then try keyword-based scoring
    combined_text = cleaned_subject + " " + cleaned_subject + " " + cleaned_text
    intent_scores = {intent: 0 for intent in INTENT_LABELS}
    
    for intent, keywords in KEYWORD_MAPPING.items():
        if intent not in INTENT_LABELS:
            continue
        
        for keyword in keywords:
            if keyword in cleaned_subject:
                if intent == "PO Cancellation":
                    intent_scores[intent] += 5
                elif intent == "PO Change":
                    intent_scores[intent] += 4
                elif intent == "po process/new purchase order":
                    intent_scores[intent] += 3
                else:
                    intent_scores[intent] += 3
            
            if keyword in cleaned_text:
                if intent == "PO Cancellation":
                    intent_scores[intent] += 3
                elif intent == "PO Change":
                    intent_scores[intent] += 2
                elif intent == "po process/new purchase order":
                    intent_scores[intent] += 2
                else:
                    intent_scores[intent] += 1
    
    max_score = max(intent_scores.values()) if intent_scores else 0
    if max_score > 0:
        top_intents = [intent for intent, score in intent_scores.items() if score == max_score]
        
        if "PO Cancellation" in top_intents and "PO Cancellation" in INTENT_LABELS:
            return "PO Cancellation"
        if "PO Change" in top_intents and "PO Change" in INTENT_LABELS:
            return "PO Change"
        if "po process/new purchase order" in top_intents and "po process/new purchase order" in INTENT_LABELS:
            return "po process/new purchase order"
        
        return top_intents[0]
    
    return "other" if "other" in INTENT_LABELS else INTENT_LABELS[0]

def gemini_classify_intent(text: str, subject: str = "") -> str:
    global INTENT_LABELS
    INTENT_LABELS = get_active_intent_labels()
    
    # First check for specific indicators
    if check_for_cancellation_indicators(text) or check_for_cancellation_indicators(subject):
        if "PO Cancellation" in INTENT_LABELS:
            return "PO Cancellation"
    
    if check_for_po_change_indicators(text) or check_for_po_change_indicators(subject):
        if "PO Change" in INTENT_LABELS:
            return "PO Change"
    
    if check_for_new_po_indicators(text) or check_for_new_po_indicators(subject):
        new_po_intent = "po process/new purchase order"
        if new_po_intent in INTENT_LABELS:
            return new_po_intent
    
    # Then use Gemini for classification
    intent_labels_str = ", ".join(f'"{label}"' for label in INTENT_LABELS)
    prompt = gemini_intent_agent_prompt.format(
        subject=subject, 
        text=text,
        intent_labels=intent_labels_str
    )
    
    reply = get_gemini_response(prompt)
    if not reply:
        return "other" if "other" in INTENT_LABELS else INTENT_LABELS[0]
    
    reply = reply.strip()
    if reply in INTENT_LABELS:
        return reply
    
    for intent in INTENT_LABELS:
        if intent.lower() in reply.lower():
            return intent
    
    # Last resort, check for key terms in the response
    if any(term in reply.lower() for term in ["cancel", "terminat", "revoke"]):
        if "PO Cancellation" in INTENT_LABELS:
            return "PO Cancellation"
    
    if any(term in reply.lower() for term in ["change", "modify", "amend", "revise"]):
        if "PO Change" in INTENT_LABELS:
            return "PO Change"
    
    if any(term in reply.lower() for term in ["new", "create", "request", "submit"]):
        new_po_intent = "po process/new purchase order"
        if new_po_intent in INTENT_LABELS:
            return new_po_intent
    
    return "other" if "other" in INTENT_LABELS else INTENT_LABELS[0]

def detect_email_intent(email_text: str) -> str:
    global INTENT_LABELS
    INTENT_LABELS = get_active_intent_labels()
    
    subject = extract_subject(email_text)
    
    # First check for specific indicators in the full email
    if check_for_cancellation_indicators(email_text):
        if "PO Cancellation" in INTENT_LABELS:
            return "PO Cancellation"
        if "PO Cancellation" in INTENT_LABELS:
            return "PO Cancellation"
    
    if check_for_po_change_indicators(email_text):
        if "PO Change" in INTENT_LABELS:
            return "PO Change"
        if "PO Change" in INTENT_LABELS:
            return "PO Change"
    
    if check_for_new_po_indicators(email_text):
        new_po_intent = "po process/new purchase order"
        if new_po_intent in INTENT_LABELS:
            return new_po_intent
        new_po_intent = "po process/new purchase order"
        if new_po_intent in INTENT_LABELS:
            return new_po_intent
    
    # Then try keyword-based detection
    intent = keyword_based_detection(email_text, subject)
    if intent:
        return intent
    
    # Finally use Gemini
    return gemini_classify_intent(email_text, subject)

def extract_email_body(email_text: str) -> str:
    header_end = re.search(r'\n\s*\n', email_text)
    if header_end:
        return email_text[header_end.end():].strip()
    return email_text

def is_purchase_order_intent(text: str) -> bool:
    intent = detect_email_intent(text)
    return intent == "po process/new purchase order"

def is_po_change_intent(text: str) -> dict:
    """
    Returns a dictionary with all intents and their detection status.
    This is a more generalized version that replaces is_po_change_intent.
    """
    global INTENT_LABELS
    INTENT_LABELS = get_active_intent_labels()
    
    intent = detect_email_intent(text)
    result = {label: False for label in INTENT_LABELS}
    
    if intent in result:
        result[intent] = True
        
    return result


# # Test with the example email
# example_email = """
# From: Dibert Valve and Fitting Co., Inc <support@swagelok4767.zendesk.com>
# Date: Fri, May 9, 2025 at 11:07 PM
# Subject: Fwd: Dominion Darbytown Order
# To: Ratha <ratha@easeworkai.com>


# Hi, 

# This is an order from an excel spreadsheet. 

# Thanks, 
# Alexis

# ---------- Forwarded message ---------
# From: Dibert Valve and Fitting Co., Inc <support@swagelok4767.zendesk.com>
# Date: 5/9/2025, 12:19:28 PM
# Please process an order for the attached sheet.

 

# Thanks,.

# Ben"""


# print("\nTesting with example email - using get_email_intent:")
# all_intents_result = is_po_change_intent(example_email)
# print(all_intents_result)