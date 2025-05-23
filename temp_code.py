import re
import streamlit as st
import tempfile
import os
import base64
import time
from markitdown import MarkItDown
import ocrmypdf
from invoice_extraction import process_attachment, parse_purchase_order, transform_invoice_to_markdown

# --- Helper Functions ---
def get_base64_image(image_path):
    """Convert image to base64 string for embedding in HTML"""
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    return encoded_string

def display_logo():
    """Display logo in the top-left corner"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(script_dir, "logo.png")

    if os.path.exists(logo_path):
        logo_base64 = get_base64_image(logo_path)
        logo_html = f"""
        <div style="position: absolute; top: -3rem; left: -3rem; z-index: 1000 !important;">
            <img src="data:image/png;base64,{logo_base64}" alt="Logo" style="width: 10rem; z-index: 1000 !important;">
        </div>
        """
        st.markdown(logo_html, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="logo-container">
            <div style="color: #bb86fc; font-size: 1.5rem; font-weight: bold;">
                📄 Easework AI
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- Dark Theme Styling ---
st.set_page_config(page_title="Easework AI - Invoice Scanner", layout="wide")

# Clear any existing state when page loads
if 'current_file_name' not in st.session_state:
    st.session_state.current_file_name = None
if 'processed_content' not in st.session_state:
    st.session_state.processed_content = None

st.markdown("""
    <style>
        html, body, .main {
            background-color: #121212 !important;
            color: #e0e0e0 !important;
        }
        .block-container {
            padding-top: 3rem;
        }
            
        .stAppHeader{
            display: none;
        }

        h1, h2, h3, h4, h5, h6 {
            color: #e0e0e0 !important;
        }
        h1 { font-size: 2.5rem !important; font-weight: 700 !important; margin-bottom: 1.5rem !important; }
        h2 { font-size: 2rem !important; font-weight: 600 !important; margin-top: 1.5rem !important; margin-bottom: 1rem !important; }
        h3 { font-size: 1.5rem !important; font-weight: 600 !important; margin-top: 1.2rem !important; margin-bottom: 0.8rem !important; }
        
        .stButton button { 
            background: linear-gradient(135deg, #bb86fc, #6d28d9); 
            color: white !important; 
            border-radius: 8px; 
            padding: 0.6em 1.2em; 
            font-weight: bold; 
            border: none; 
            font-size: 1rem; 
        }
        .stButton button:hover { 
            background: linear-gradient(135deg, #a855f7, #7c3aed); 
            color: white !important; 
        }
        
        .stFileUploader { 
            border: 2px dashed #bb86fc; 
            border-radius: 10px; 
            padding: 20px; 
            margin-bottom: 20px; 
        }
        .stFileUploader label { 
            color: #bb86fc; 
            font-weight: bold; 
            font-size: 1.1rem; 
        }
        
        /* Invoice Display Styles */
        .invoice-header {
            text-align: center;
            font-size: 2.5rem;
            font-weight: bold;
            color: #bb86fc;
            margin-bottom: 2rem;
            padding: 1rem;
            border-bottom: 3px solid #bb86fc;
        }
        
        .invoice-section {
            background-color: #1e1e1e;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }
        
        .invoice-section h3 {
            color: #bb86fc !important;
            margin-bottom: 15px !important;
            font-size: 1.4rem !important;
            border-bottom: 2px solid #bb86fc;
            padding-bottom: 8px;
        }
        
        .invoice-section ul {
            list-style: none;
            padding-left: 0;
        }
        
        .invoice-section li {
            margin-bottom: 10px;
            color: #e0e0e0;
            font-size: 1rem;
        }
        
        .invoice-section strong {
            color: #bb86fc;
            font-weight: 600;
        }
        
        .section-divider {
            border: none;
            height: 2px;
            background: linear-gradient(135deg, #bb86fc, #6d28d9);
            margin: 30px 0;
            border-radius: 1px;
        }
        
        /* Table Styles */
        .invoice-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background-color: #1e1e1e;
            border-radius: 8px;
            overflow: hidden;
        }
        
        .invoice-table th {
            background-color: #2a2a2a;
            color: #bb86fc;
            padding: 15px 8px;
            border: 1px solid #444;
            font-weight: 600;
            text-align: left;
            font-size: 0.95rem;
        }
        
        .invoice-table td {
            padding: 12px 8px;
            border: 1px solid #444;
            color: #e0e0e0;
            font-size: 0.9rem;
        }
        
        .invoice-table tr:nth-child(even) {
            background-color: #252525;
        }
        
        .summary-table {
            width: 100%;
            max-width: 500px;
            margin: 20px auto;
            border-collapse: collapse;
            background-color: #1e1e1e;
            border-radius: 8px;
            overflow: hidden;
        }
        
        .summary-table th, .summary-table td {
            padding: 15px 20px;
            border: 1px solid #444;
            text-align: left;
        }
        
        .summary-table th {
            background-color: #2a2a2a;
            color: #bb86fc;
            font-weight: 600;
        }
        
        .summary-table td {
            color: #e0e0e0;
        }
        
        .summary-table .amount-cell {
            text-align: right;
            font-weight: 500;
        }
        
        .thank-you-section {
            text-align: center;
            margin-top: 40px;
            padding: 25px;
            background: linear-gradient(135deg, #1e1e1e, #2a2a2a);
            border-radius: 15px;
            border: 2px solid #bb86fc;
        }
        
        .thank-you-section h3 {
            color: #bb86fc !important;
            font-size: 1.8rem !important;
            margin: 0 !important;
            font-weight: bold !important;
        }
        
        .status-message { 
            font-size: 1.2rem !important; 
            font-weight: 500 !important; 
            color: #bb86fc !important; 
            text-align: center !important;
            margin-bottom: 1rem !important;
        }
        
        .centered-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        
        .logo-container {
            position: absolute; 
            top: -6rem; 
            left: 10px;
            z-index: 1000;
        }
        
        .full-width-section {
            background-color: #1e1e1e;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            margin-bottom: 25px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
            width: 100%;
        }
        
        .full-width-section h3 {
            color: #bb86fc !important;
            margin-bottom: 20px !important;
            font-size: 1.4rem !important;
            border-bottom: 2px solid #bb86fc;
            padding-bottom: 10px;
        }
        
        .address-format {
            line-height: 1.6;
            white-space: pre-line;
        }
        
        /* Additional Item Information Table */
        .additional-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background-color: #252525;
            border-radius: 8px;
            overflow: hidden;
        }
        
        .additional-table th {
            background-color: #333;
            color: #bb86fc;
            padding: 12px 8px;
            border: 1px solid #555;
            font-weight: 600;
            text-align: left;
            font-size: 0.9rem;
        }
        
        .additional-table td {
            padding: 10px 8px;
            border: 1px solid #555;
            color: #e0e0e0;
            font-size: 0.85rem;
        }
        
        .additional-table tr:nth-child(even) {
            background-color: #2a2a2a;
        }
    </style>
""", unsafe_allow_html=True)

# --- Processing Functions ---
def parse_with_markitdown(path: str):
    try:
        md = MarkItDown()
        result = md.convert(path)
        content = getattr(result, "text_content", "") or ""
        return content.strip() if content else None
    except Exception:
        return None

def process_with_ocrmypdf(input_path: str, output_path: str) -> bool:
    try:
        ocrmypdf.ocr(input_path, output_path, deskew=True, force_ocr=True)
        return os.path.exists(output_path)
    except Exception:
        return False

def clean_markdown_block(text):
    invoice_match = re.search(r'(?i)Invoice', text)
    if invoice_match:
        text = text[invoice_match.start():]

    text = re.sub(r"```.*?\n", "", text, flags=re.DOTALL)
    text = re.sub(r"```", "", text)

    lines = text.splitlines()
    cleaned_lines = []
    buffer_line = ""
    bullet_pattern = re.compile(r"^\s*[-*+]\s+.*")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buffer_line:
                cleaned_lines.append(buffer_line.strip())
                buffer_line = ""
            continue

        if bullet_pattern.match(stripped):
            if buffer_line:
                cleaned_lines.append(buffer_line.strip())
            buffer_line = stripped
        elif buffer_line:
            buffer_line += " " + stripped
        else:
            cleaned_lines.append(stripped)

    if buffer_line:
        cleaned_lines.append(buffer_line.strip())

    return "\n".join(cleaned_lines)

# --- Enhanced Invoice Parsing Functions ---
def parse_markdown_sections(markdown_text):
    """Parse markdown text into structured sections"""
    sections = {}
    current_section = None
    current_content = []
    
    lines = markdown_text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Check for main header (supports multiple formats)
        if re.match(r'^#+\s*\*{2}.*\*{2}$', line):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            
            # Extract section name (handles #, ##, ### with **)
            section_name = re.sub(r'^#+\s*\*{2}|\*{2}$', '', line).strip()
            if line.startswith('# '):
                current_section = 'HEADER'
            else:
                current_section = section_name
            current_content = []
            
        # Check for dividers
        elif line.startswith('---'):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
                current_section = None
                current_content = []
                
        # Regular content
        else:
            if line:
                current_content.append(line)
    
    # Add final section
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()
    
    return sections

def parse_list_items(content):
    """Parse list items in the format - **Key:** Value"""
    items = {}
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if line.startswith('- **') and ':**' in line:
            # Find the end of the key
            key_end = line.find(':**')
            if key_end > 0:
                key = line[4:key_end]  # Remove - **
                value = line[key_end + 3:].strip()  # Remove :** and get value
                if value:  # Only add non-empty values
                    items[key] = value
    
    return items

def parse_table_data(content):
    """Parse markdown table data"""
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    table_data = []
    headers = []
    
    for i, line in enumerate(lines):
        if line.startswith('|') and '**' in line:
            # This is likely the header row
            headers = [cell.strip().replace('**', '') for cell in line.split('|')[1:-1]]
        elif line.startswith('|') and '---' not in line and headers:
            # This is a data row
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if len(cells) == len(headers) and any(cell for cell in cells):  # Skip empty rows
                row_data = dict(zip(headers, cells))
                table_data.append(row_data)
    
    return table_data, headers

def render_invoice_header():
    """Render the main invoice header"""
    return """
    <div class="invoice-header">
        🧾 INVOICE
    </div>
    """

def render_section_with_list(title, content, icon="📋"):
    """Render a section with list items"""
    items = parse_list_items(content)
    if not items:
        return ""
    
    html = f'<div class="invoice-section"><h3>{icon} {title}</h3><ul>'
    for key, value in items.items():
        # Handle address formatting
        if 'address' in key.lower() or 'remit to' in key.lower():
            formatted_value = value.replace('<br>', '\n')
            html += f'<li><strong>{key}:</strong><br><div class="address-format">{formatted_value}</div></li>'
        else:
            html += f'<li><strong>{key}:</strong> {value}</li>'
    html += '</ul></div>'
    return html

def render_item_details_section(content):
    """Render the complete Item Details section with main table and additional info"""
    html = '<div class="full-width-section"><h3>📋 Item Details</h3>'
    
    # Split content to find main table and additional table
    parts = content.split('### **Additional Item Information**')
    main_table_content = parts[0]
    additional_content = parts[1] if len(parts) > 1 else ""
    
    # Parse and render main table
    table_data, headers = parse_table_data(main_table_content)
    if table_data and headers:
        html += '<table class="invoice-table"><thead><tr>'
        for header in headers:
            html += f'<th>{header}</th>'
        html += '</tr></thead><tbody>'
        
        for row in table_data:
            html += '<tr>'
            for header in headers:
                cell_value = row.get(header, "")
                html += f'<td>{cell_value}</td>'
            html += '</tr>'
        html += '</tbody></table>'
    
    # Parse and render additional information table
    if additional_content:
        additional_data, additional_headers = parse_table_data(additional_content)
        if additional_data and additional_headers:
            html += '<h4 style="color: #bb86fc; margin-top: 30px; margin-bottom: 15px;">Additional Item Information</h4>'
            html += '<table class="additional-table"><thead><tr>'
            for header in additional_headers:
                html += f'<th>{header}</th>'
            html += '</tr></thead><tbody>'
            
            for row in additional_data:
                html += '<tr>'
                for header in additional_headers:
                    cell_value = row.get(header, "")
                    html += f'<td>{cell_value}</td>'
                html += '</tr>'
            html += '</tbody></table>'
    
    html += '</div>'
    return html

def render_financial_summary(content):
    """Render the Financial Summary section"""
    table_data, headers = parse_table_data(content)
    if not table_data:
        return ""
    
    html = '<div class="full-width-section"><h3>💰 Financial Summary</h3>'
    html += '<table class="summary-table"><tbody>'
    
    for row in table_data:
        category = row.get('Category', '')
        amount = row.get('Amount', '')
        if category and amount:
            html += f'<tr><td><strong>{category}</strong></td><td class="amount-cell">{amount}</td></tr>'
    
    html += '</tbody></table></div>'
    return html

def render_text_section(title, content, icon="📄"):
    """Render a section with plain text content"""
    if not content.strip():
        return ""
    
    # Format the content properly
    formatted_content = content.replace('\n', '<br>')
    
    return f"""
    <div class="invoice-section">
        <h3>{icon} {title}</h3>
        <div style="line-height: 1.6;">{formatted_content}</div>
    </div>
    """

def render_thank_you_section():
    """Render the thank you section"""
    return """
    <div class="thank-you-section">
        <h3>✨ THANK YOU FOR YOUR BUSINESS ✨</h3>
    </div>
    """

def render_section_divider():
    """Render a section divider"""
    return '<hr class="section-divider">'

def display_parsed_invoice(markdown_content):
    """Display the parsed invoice with proper formatting"""
    sections = parse_markdown_sections(markdown_content)
    
    # Display invoice header
    st.markdown(render_invoice_header(), unsafe_allow_html=True)
    
    # Define section rendering order and icons
    section_config = [
        ('Supplier Information', '🏢'),
        ('Invoice Details', '🧾'),
        ('Customer Information (Bill To)', '👤'),
        ('Shipping Information (Ship To)', '🚚'),
        ('Banking Information', '🏦'),
        ('Item Details', '📋'),
        ('Financial Summary', '💰'),
        ('Payment Information', '💳'),
        ('Instructions', '📝'),
        ('Terms and Conditions', '📜'),
        ('Client Note', '📩'),
        ('Comments', '💬'),
        ('FAQs', '❓')
    ]
    
    # Track which sections need dividers
    sections_with_dividers = [
        'Invoice Details', 'Shipping Information', 'Banking Information', 
        'Financial Summary', 'Instructions'
    ]
    
    # Render sections in order
    for section_name, icon in section_config:
        if section_name in sections:
            content = sections[section_name]
            
            # Special handling for different section types
            if section_name == 'Item Details':
                html = render_item_details_section(content)
            elif section_name == 'Financial Summary':
                html = render_financial_summary(content)
            elif section_name in ['Instructions', 'Terms and Conditions', 'Client Note', 'Comments', 'FAQs']:
                html = render_text_section(section_name, content, icon)
            else:
                html = render_section_with_list(section_name, content, icon)
            
            if html:
                st.markdown(html, unsafe_allow_html=True)
                
                # Add divider after certain sections
                if section_name in sections_with_dividers:
                    st.markdown(render_section_divider(), unsafe_allow_html=True)

# --- Main UI ---
display_logo()
st.title("🧾 Invoice Scanner")

st.markdown("""
    <div class="upload-container">
        <h2>Upload your Invoice</h2>
    </div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("", type=["pdf"])

# Clear state when a new file is uploaded
if uploaded_file and uploaded_file.name != st.session_state.current_file_name:
    st.session_state.current_file_name = uploaded_file.name
    st.session_state.processed_content = None
    # Clear any cache in the invoice_extraction module if it exists
    try:
        import importlib
        import invoice_extraction
        importlib.reload(invoice_extraction)
    except:
        pass

if uploaded_file:
    col1, col2, col3 = st.columns([3, 1, 1])
    with col3:
        scan_button = st.button("Scan PDF", use_container_width=True)
    
    if scan_button:
        st.markdown('<div class="centered-content">', unsafe_allow_html=True)
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        st.markdown('</div>', unsafe_allow_html=True)

        def update(status, progress):
            status_placeholder.markdown(f'<div class="centered-content"><p class="status-message">{status}</p></div>', unsafe_allow_html=True)
            progress_bar.progress(progress)

        # Create a unique temporary file for each processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{int(time.time())}.pdf") as tmp:
            tmp.write(uploaded_file.read())
            src_path = tmp.name

        try:
            update("Analyzing document structure...", 0.1)
            
            # Force fresh extraction by ensuring clean state
            extracted_text = process_attachment(src_path)
            
            # Add debug info to verify we're getting fresh text
            if len(extracted_text) > 100:
                text_preview = extracted_text[:100] + "..."
            else:
                text_preview = extracted_text
            print(f"DEBUG: Processing file {uploaded_file.name}")
            print(f"DEBUG: Extracted text preview: {text_preview}")
            
            update("Extracting invoice data with AI...", 0.4)
            
            # Ensure fresh processing by passing filename context
            agent = parse_purchase_order(extracted_text)
            
            update("Formatting invoice output...", 0.7)
            cleaned_output = transform_invoice_to_markdown(agent)
            
            update("Finalizing results...", 0.9)
            status_placeholder.empty()
            progress_bar.empty()
            st.toast("📄 Invoice processed successfully!")

            # Store processed content in session state
            st.session_state.processed_content = cleaned_output

            # Only show the styled version, not raw markdown
            if cleaned_output and cleaned_output.strip():
                display_parsed_invoice(cleaned_output)
            else:
                st.warning("⚠️ No invoice content available.")
                
        except Exception as e:
            st.error(f"Error processing invoice: {str(e)}")
            print(f"DEBUG: Error details: {str(e)}")
        finally:
            # Clean up temporary file
            if os.path.exists(src_path):
                os.unlink(src_path)

# Display previously processed content if available
elif st.session_state.processed_content:
    display_parsed_invoice(st.session_state.processed_content)