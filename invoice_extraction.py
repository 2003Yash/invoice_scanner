import os
import logging
from llama_parse import LlamaParse
from markitdown import MarkItDown
from llama2 import parse_purchase_order
import json

# Colors for debug prints
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def color_print(text, color):
    """Print text with color"""
    print(f"{color}{text}{Colors.ENDC}")

# Initialize parsers
parser = LlamaParse(
    api_key="llx-3QXRc1fhsxmTssxbzaJdXTUI6QHLgFeV4MTIY93Hdpo1Pnqv",
    result_type="text",
    verbose=True,
)
color_print("✅ LlamaParse initialized", Colors.GREEN)

md = MarkItDown()
color_print("✅ MarkItDown initialized", Colors.GREEN)

def process_attachment(attachment_path):
    """Process a single attachment and return extracted text."""
    color_print(f"📄 Processing attachment at {attachment_path}...", Colors.CYAN)
    
    if not os.path.exists(attachment_path):
        color_print(f"❌ File not found: {attachment_path}", Colors.RED)
        return None

    attachment_data = None

    try:
        res = parser.load_data(attachment_path)
        attachment_data = ""
        for doc in res:
            attachment_data += doc.text
        color_print("✅ LlamaParse parsing successful", Colors.GREEN)
    except Exception as e:
        color_print(f"❌ Error using LlamaParse: {e}", Colors.RED)
        logging.error(f"Error using LlamaParse: {e}", exc_info=True)
        attachment_data = None
    
    return attachment_data

import json
from typing import Dict, List, Any, Union

def transform_invoice_to_markdown(json_data: Dict[str, Any]) -> str:
    """
    Transform invoice JSON data into comprehensive structured markdown format.
    Processes ALL non-empty fields from the JSON structure.
    
    Args:
        json_data (dict): Invoice data in JSON format
        
    Returns:
        str: Formatted markdown string with all available information
    """
    
    def is_non_empty(value: Any) -> bool:
        """Check if a value is non-empty and meaningful"""
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != '' and value.strip().lower() not in ['n/a', 'null', 'none']
        if isinstance(value, (list, dict)):
            return len(value) > 0
        if isinstance(value, bool):
            return True  # Include boolean values
        if isinstance(value, (int, float)):
            return True  # Include numeric values
        return True
    
    def format_address(address: str) -> str:
        """Format address by replacing newlines with proper formatting"""
        if not address:
            return ''
        return address.replace('\n', '<br>')
    
    def format_currency(value: str) -> str:
        """Format currency values consistently"""
        if not value:
            return ''
        value_str = str(value).strip()
        if value_str and not value_str.startswith('$'):
            try:
                float_val = float(value_str.replace(',', ''))
                return f"${float_val:,.2f}"
            except (ValueError, TypeError):
                return value_str
        return value_str
    
    def add_field_if_exists(markdown_list: List[str], label: str, value: Any, is_currency: bool = False):
        """Add field to markdown list if value exists"""
        if is_non_empty(value):
            if is_currency:
                formatted_value = format_currency(value)
            else:
                formatted_value = str(value)
            markdown_list.append(f"- **{label}:** {formatted_value}")
    
    markdown = []
    markdown.append('# **INVOICE**')
    markdown.append('')
    
    # ================== COMPANY/SUPPLIER INFORMATION ==================
    markdown.append('## **Supplier Information**')
    markdown.append('')
    
    company_fields = []
    add_field_if_exists(company_fields, "Company Name", json_data.get('company_name'))
    add_field_if_exists(company_fields, "Address", format_address(json_data.get('company_address', '')))
    add_field_if_exists(company_fields, "Phone", json_data.get('company_phone'))
    add_field_if_exists(company_fields, "Sold by", json_data.get('sold_by'))
    add_field_if_exists(company_fields, "Fax", json_data.get('company_fax'))
    add_field_if_exists(company_fields, "Website", json_data.get('company_website'))
    # Get 'order' from the first item if available
    first_item_order = ""
    items = json_data.get('item', [])
    if isinstance(items, list) and items and isinstance(items[0], dict):
        first_item_order = items[0].get('order', '')
    add_field_if_exists(company_fields, "Order", first_item_order)
    
    if company_fields:
        markdown.extend(company_fields)
        markdown.append('')
    
    # ================== INVOICE METADATA ==================
    markdown.append('## **Invoice Details**')
    markdown.append('')
    
    invoice_fields = []
    add_field_if_exists(invoice_fields, "Invoice Number", json_data.get('invoice_no'))
    add_field_if_exists(invoice_fields, "Invoice Date", json_data.get('invoice_date'))
    add_field_if_exists(invoice_fields, "Due Date", json_data.get('due_date'))
    add_field_if_exists(invoice_fields, "Order Number", json_data.get('order_no'))
    add_field_if_exists(invoice_fields, "Order Date", json_data.get('order_date'))
    add_field_if_exists(invoice_fields, "Customer Number", json_data.get('cust_no'))
    add_field_if_exists(invoice_fields, "PO Number", json_data.get('po_number'))
    add_field_if_exists(invoice_fields, "Page", json_data.get('page'))
    add_field_if_exists(invoice_fields, "Number", json_data.get('number'))
    add_field_if_exists(invoice_fields, "Terms", json_data.get('terms'))
    add_field_if_exists(invoice_fields, "Purchased By", json_data.get('prepared_by'))
    add_field_if_exists(invoice_fields, "File Number", json_data.get('file_no'))
    
    if invoice_fields:
        markdown.extend(invoice_fields)
        markdown.append('')
    
    markdown.append('---')
    markdown.append('')
    
    # ================== CUSTOMER INFORMATION ==================
    markdown.append('## **Customer Information (Bill To)**')
    markdown.append('')
    
    customer_fields = []
    add_field_if_exists(customer_fields, "Customer Name", json_data.get('customer_name'))
    add_field_if_exists(customer_fields, "Customer Address", format_address(json_data.get('customer_address', '')))
    add_field_if_exists(customer_fields, "Attention", json_data.get('customer_attn'))
    add_field_if_exists(customer_fields, "Customer Phone", json_data.get('customer_tel'))
    add_field_if_exists(customer_fields, "Customer Fax", json_data.get('customer_fax'))
    add_field_if_exists(customer_fields, "Customer Number", json_data.get('customer_number'))
    add_field_if_exists(customer_fields, "Department", json_data.get('dept'))
    add_field_if_exists(customer_fields, "Sales Representative", json_data.get('salesrep'))
    add_field_if_exists(customer_fields, "Writer", json_data.get('writer'))
    
    if customer_fields:
        markdown.extend(customer_fields)
        markdown.append('')
    
    # ================== SHIPPING INFORMATION ==================
    ship_fields = []
    add_field_if_exists(ship_fields, "Ship To Name", json_data.get('ship_to_name'))
    add_field_if_exists(ship_fields, "Ship To Address", format_address(json_data.get('ship_to_address', '')))
    add_field_if_exists(ship_fields, "Ship Via", json_data.get('ship_via'))
    add_field_if_exists(ship_fields, "Vessel/Voyage", json_data.get('vessel_voyage'))
    add_field_if_exists(ship_fields, "Gate In Date", json_data.get('gate_in_date'))
    add_field_if_exists(ship_fields, "ETD", json_data.get('e_t_d'))
    add_field_if_exists(ship_fields, "ATD", json_data.get('a_t_d'))
    add_field_if_exists(ship_fields, "ETA", json_data.get('e_t_a'))
    add_field_if_exists(ship_fields, "MBL", json_data.get('m_b_l'))
    add_field_if_exists(ship_fields, "B/L Number", json_data.get('b_l_no'))
    add_field_if_exists(ship_fields, "ISF Number", json_data.get('isf_no'))
    add_field_if_exists(ship_fields, "Cargo Type", json_data.get('cargo_type'))
    add_field_if_exists(ship_fields, "Place of Receipt", json_data.get('place_of_rec'))
    add_field_if_exists(ship_fields, "Origin", json_data.get('origin'))
    add_field_if_exists(ship_fields, "Destination", json_data.get('destination'))
    add_field_if_exists(ship_fields, "PO", json_data.get('PO'))    
    add_field_if_exists(ship_fields, "Final Destination", json_data.get('final_dest'))
    add_field_if_exists(ship_fields, "Commodity", json_data.get('commodity'))
    add_field_if_exists(ship_fields, "Pieces", json_data.get('pieces'))
    add_field_if_exists(ship_fields, "Weight", json_data.get('weight'))
    add_field_if_exists(ship_fields, "Volume", json_data.get('volume'))
    add_field_if_exists(ship_fields, "Container Size", json_data.get('container_size'))
    add_field_if_exists(ship_fields, "Containers", json_data.get('containers'))
    add_field_if_exists(ship_fields, "Shipment Tracking Number", json_data.get('shipment_tracking_number'))
    add_field_if_exists(ship_fields, "Lot Numbers", json_data.get('lot_numbers'))
    add_field_if_exists(ship_fields, "Lot Quantity UOM", json_data.get('lot_quantity_uom'))
    
    if ship_fields:
        markdown.append('## **Shipping Information (Ship To)**')
        markdown.append('')
        markdown.extend(ship_fields)
        markdown.append('')
    
    markdown.append('---')
    markdown.append('')
    
    # ================== BANKING INFORMATION ==================
    banking_fields = []
    add_field_if_exists(banking_fields, "Bank Name", json_data.get('bank_name'))
    add_field_if_exists(banking_fields, "ACH Routing", json_data.get('ach_routing'))
    add_field_if_exists(banking_fields, "Bank Account", json_data.get('bank_account'))
    add_field_if_exists(banking_fields, "SWIFT Code", json_data.get('swift_code'))
    add_field_if_exists(banking_fields, "Account Name", json_data.get('account_name'))
    add_field_if_exists(banking_fields, "Remit To", format_address(json_data.get('remit_to', '')))
    
    if banking_fields:
        markdown.append('## **Banking Information**')
        markdown.append('')
        markdown.extend(banking_fields)
        markdown.append('')
        markdown.append('---')
        markdown.append('')
    
    # ================== ITEMS SECTION ==================
    items = json_data.get('item', [])
    if not isinstance(items, list):
        items = [items] if items else []
    
    if items and any(is_non_empty(item) for item in items):
        markdown.append('## **Item Details**')
        markdown.append('')
        
        # Define all possible item fields with their display names
        item_field_mappings = {
            'item_number': 'Item #',
            'description': 'Description',
            'customer_part': 'Customer Part',
            'quantity_ord': 'Qty Ordered',
            'quantity_shp': 'Qty Shipped',
            'quantity_bo': 'Qty B/O',
            'unit_price': 'Unit Price',
            'unit': 'Unit',
            'amount': 'Amount',
            'currency': 'Currency',
            'freight': 'Freight',
            'asin': 'ASIN',
            'sold_by': 'Sold By',
            'order': 'Order',
            'um': 'UM',
            'bo': 'BO',
            'ship': 'Ship',
            'mfg': 'MFG',
            'stock_number': 'Stock Number',
            'extended': 'Extended'
        }
        
        # Find which columns have non-empty values across all items
        columns_with_data = []
        for field_key, display_name in item_field_mappings.items():
            has_data = False
            for item in items:
                if isinstance(item, dict) and is_non_empty(item.get(field_key)):
                    has_data = True
                    break
            if has_data:
                columns_with_data.append((field_key, display_name))
        
        if columns_with_data:
            # Create table header
            header = '| ' + ' | '.join([f'**{display_name}**' for _, display_name in columns_with_data]) + ' |'
            divider = '| ' + ' | '.join(['---' for _ in columns_with_data]) + ' |'
            
            markdown.append(header)
            markdown.append(divider)
            
            # Add data rows
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                row_data = []
                for field_key, _ in columns_with_data:
                    value = item.get(field_key, '')
                    
                    # Format currency fields
                    if field_key in ['unit_price', 'amount', 'freight', 'extended'] and is_non_empty(value):
                        formatted_value = format_currency(value)
                    else:
                        formatted_value = str(value) if is_non_empty(value) else ''
                    
                    row_data.append(formatted_value)
                
                row = '| ' + ' | '.join(row_data) + ' |'
                markdown.append(row)
            
            markdown.append('')
        
        markdown.append('---')
        markdown.append('')
    
    # ================== FINANCIAL SUMMARY ==================
    markdown.append('## **Financial Summary**')
    markdown.append('')
    
    # Create financial summary table
    markdown.append('| **Category** | **Amount** |')
    markdown.append('|--------------|------------|')
    
    financial_fields = [
        ('Total Before Tax', json_data.get('total_before_tax')),
        ('Total Sales Tax', json_data.get('total_sales_tax')),
        ('Item Subtotal Before Tax', json_data.get('item_subtotal_before_tax')),
        ('Total Amount', json_data.get('total_amount')),
        ('Tax', json_data.get('tax')),
        ('Less Payment', json_data.get('less_payment')),
        ('Less Payment Discount', json_data.get('less_pmt_disc')),
        ('Amount Due', json_data.get('amount_due')),
        ('Promos/Discounts', json_data.get('promos_discounts')),
        ('Shipping & Handling', json_data.get('shipping_handling'))
    ]
    
    for field_name, field_value in financial_fields:
        if is_non_empty(field_value):
            formatted_amount = format_currency(field_value)
            markdown.append(f'| {field_name} | {formatted_amount} |')
    
    markdown.append('')
    markdown.append('---')
    markdown.append('')
    
    # ================== PAYMENT INFORMATION ==================
    markdown.append('## **Payment Information**')
    markdown.append('')
    
    payment_fields = []
    add_field_if_exists(payment_fields, "Payment Due By", json_data.get('payment_due_by'))
    add_field_if_exists(payment_fields, "Payment Method", json_data.get('pay_by'))
    add_field_if_exists(payment_fields, "Electronic Funds Transfer", json_data.get('electronic_funds_transfer'))
    add_field_if_exists(payment_fields, "Check Payment", json_data.get('check'))
    add_field_if_exists(payment_fields, "Include Invoice Number", json_data.get('include_invoice_number'))
    add_field_if_exists(payment_fields, "Email for Remittance", json_data.get('email_for_remittance'))
    
    if payment_fields:
        markdown.extend(payment_fields)
        markdown.append('')
    
    # ================== NOTES AND INSTRUCTIONS ==================
    notes_sections = [
        ('Instructions', json_data.get('instructions')),
        ('Client Note', json_data.get('client_note')),
        ('Comments', json_data.get('comments')),
        ('Terms and Conditions', json_data.get('terms_and_conditions')),
        ('FAQs', json_data.get('faqs'))
    ]
    
    for section_name, section_content in notes_sections:
        if is_non_empty(section_content):
            markdown.append(f'## **{section_name}**')
            markdown.append('')
            markdown.append(str(section_content))
            markdown.append('')
            markdown.append('---')
            markdown.append('')
    
    # ================== FOOTER ==================
    markdown.append('### **THANK YOU FOR YOUR BUSINESS**')
    
    return '\n'.join(markdown)


# Example usage function
def example_usage():
    """Example of how to use the transformation function"""
    # Example usage
    attachment_path = "D:\AI_team\invoice_AI\invoices\Invoice4.pdf"
    extracted_text = process_attachment(attachment_path)

    if extracted_text:
        color_print("Extracted text:", Colors.YELLOW)
        print(extracted_text)

    "Agent:"
    color_print("Agent:",Colors.RED)
    agent = parse_purchase_order(extracted_text)
    print(json.dumps(agent, indent=2))
    # Transform to markdown
    markdown_output = transform_invoice_to_markdown(agent)
    print(markdown_output)


if __name__ == "__main__":
    # Run example
    example_usage()