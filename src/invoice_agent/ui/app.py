import streamlit as st
import yaml
from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import date, timedelta, datetime
import json
import pandas as pd
from typing import Any
import webbrowser
import warnings
import time
import atexit
import sys
import logging
import threading
import signal
import numpy as np
from streamlit_option_menu import option_menu
from invoice_agent.database.db_manager import DatabaseManager

# Configure logging to file instead of stdout
logging.basicConfig(
    filename='invoice_agent.log',
    level=logging.ERROR,  # Only log errors
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load environment variables first
load_dotenv()

# Import and initialize all required components
try:
    from invoice_agent.core.invoice_processor import InvoiceAgent
    from invoice_agent.config import config_loader
    from invoice_agent.security.auth import AuthManager
    from invoice_agent.template.template_manager import TemplateManager
    from invoice_agent.workflow.workflow_manager import WorkflowManager
    from invoice_agent.monitoring.metrics import MetricsManager
    
    # Initialize all managers globally
    auth_manager = AuthManager()
    metrics_manager = MetricsManager()
    invoice_agent = InvoiceAgent()
    workflow_manager = WorkflowManager()
    template_manager = TemplateManager()
except Exception as e:
    print(f"Failed to initialize components: {str(e)}")
    sys.exit(1)

# Suppress all warnings and debug output
warnings.filterwarnings('ignore')
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['PYTHONWARNINGS'] = 'ignore'

# Force Streamlit to use specific server settings
os.environ['STREAMLIT_SERVER_ADDRESS'] = 'localhost'
os.environ['STREAMLIT_SERVER_PORT'] = '8502'
os.environ['STREAMLIT_BROWSER_SERVER_ADDRESS'] = 'localhost'
os.environ['STREAMLIT_SERVER_MAX_SIZE'] = '200'
os.environ['STREAMLIT_SERVER_COOKIE_SECRET'] = os.urandom(24).hex()
os.environ['STREAMLIT_SERVER_WEBSOCKET_PING_TIMEOUT'] = '300'
os.environ['STREAMLIT_SERVER_WEBSOCKET_PING_FREQUENCY'] = '30'
os.environ['STREAMLIT_LOG_LEVEL'] = 'error'
os.environ['STREAMLIT_CLIENT_RECONNECT_RATE_LIMIT'] = '300'
os.environ['STREAMLIT_CLIENT_RETRY_CONNECT_DELAY'] = '1'
os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'

# Create a flag to track the application state
app_running = True

def signal_handler(signum, frame):
    """Handle process signals gracefully"""
    global app_running
    app_running = False
    cleanup_resources()
    sys.exit(0)

# Register signal handlers if we're in the main thread
if threading.current_thread() is threading.main_thread():
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except ValueError:
        pass  # Ignore if we can't set signal handlers

# Configure server settings
st.set_page_config(
    page_title="Invoice Processing Agent",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Disable Streamlit's default menu
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

def cleanup_resources():
    """Clean up temporary resources"""
    global app_running
    try:
        # Clear any temporary files
        temp_files = Path(".").glob("temp_*")
        for temp_file in temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as e:
                logging.error(f"Error removing temp file {temp_file}: {str(e)}")
    except Exception as e:
        logging.error(f"Error during cleanup: {str(e)}")
    finally:
        app_running = False

# Register cleanup function to run on exit
atexit.register(cleanup_resources)

def run_streamlit():
    """Run the Streamlit app in a separate thread"""
    try:
        if not app_running:
            return
            
        # Add custom CSS for navigation and layout
        st.markdown("""
            <style>
                /* Navigation Header */
                .nav-header {
                    padding: 1rem;
                    text-align: center;
                    border-bottom: 1px solid rgba(255,255,255,0.1);
                    margin-bottom: 1rem;
                }
                .nav-header h2 {
                    color: #FF4B4B;
                    margin: 0;
                    font-size: 1.5rem;
                }
                
                /* Navigation Menu */
                section[data-testid="stSidebar"] {
                    background-color: #262730;
                    border-right: 1px solid rgba(255,255,255,0.1);
                }
                
                /* User Info Footer */
                .nav-footer {
                    position: fixed;
                    bottom: 0;
                    left: 0;
                    width: 100%;
                    background-color: #1E1E1E;
                    padding: 1rem;
                    border-top: 1px solid rgba(255,255,255,0.1);
                }
                
                .user-info {
                    color: #FFFFFF;
                    font-size: 0.9rem;
                    text-align: center;
                    margin-bottom: 0.5rem;
                }
                
                /* Option Menu Customization */
                .stOptionMenu {
                    margin-top: 1rem;
                }
                
                .stOptionMenu div[role="button"] {
                    transition: all 0.3s ease;
                }
                
                .stOptionMenu div[role="button"]:hover {
                    transform: translateX(5px);
                }
                
                /* Main Content Area */
                .main .block-container {
                    padding-top: 2rem;
                }
                
                /* Streamlit's default padding adjustments */
                .block-container {
                    padding-top: 2rem;
                    padding-bottom: 0rem;
                    max-width: 95%;
                }
                
                /* Hide Streamlit's default footer */
                footer {
                    visibility: hidden;
                }
            </style>
        """, unsafe_allow_html=True)
            
        # Start the main application
        main()

    except Exception as e:
        logging.error(f"Error in Streamlit thread: {str(e)}")
        if app_running:
            st.error("Application error occurred. Please refresh the page.")

def init_session_state():
    """Initialize session state variables"""
    try:
        if "initialized" not in st.session_state:
            st.session_state.initialized = False
            st.session_state.authenticated = False
            st.session_state.user_info = None
            st.session_state.page = "Dashboard"
            st.session_state.auth_error = None
            st.session_state.last_activity = time.time()
            st.session_state.connection_attempts = 0
            st.session_state.initialized = True
        else:
            # Update last activity time
            st.session_state.last_activity = time.time()
            
            # Reset connection attempts if needed
            if time.time() - st.session_state.last_activity > 300:  # 5 minutes
                st.session_state.connection_attempts = 0
    except Exception as e:
        print(f"Session state initialization error: {str(e)}")
        st.error("Error initializing session. Please refresh the page.")

def check_connection_health():
    """Check connection health and handle reconnection"""
    try:
        if not hasattr(st.session_state, 'last_activity'):
            st.session_state.last_activity = time.time()
            st.session_state.connection_attempts = 0
            return True
            
        current_time = time.time()
        time_since_last_activity = current_time - st.session_state.last_activity
        
        # If no activity for more than 5 minutes
        if time_since_last_activity > 300:
            st.session_state.connection_attempts += 1
            
            # If too many reconnection attempts, ask user to refresh
            if st.session_state.connection_attempts > 3:
                st.error("Connection issues detected. Please refresh the page.")
                return False
                
            # Update last activity time
            st.session_state.last_activity = current_time
            
            # Try to reconnect
            st.experimental_rerun()
            
        return True
    except Exception as e:
        print(f"Connection health check error: {str(e)}")
        return False

def handle_google_auth():
    """Handle Google OAuth authentication flow"""
    try:
        # Check if this is a callback
        query_params = st.experimental_get_query_params()
        code = query_params.get('code', [None])[0]
        state = query_params.get('state', [None])[0]
        
        if code:
            print("Received auth code, attempting to exchange for tokens...")
            auth_result = auth_manager.handle_google_auth()
            if auth_result:
                print("Authentication successful, updating session state...")
                st.session_state.authenticated = True
                st.session_state.user_info = auth_result
                st.session_state.auth_error = None
                st.experimental_set_query_params()  # Clear query params
                st.rerun()
                return True
            else:
                st.session_state.auth_error = "Authentication failed"
                return False

        # Generate auth URL and redirect
        print("Initiating Google OAuth flow...")
        auth_url = auth_manager.get_google_auth_url()
        print(f"Generated auth URL: {auth_url}")
        
        # Set auth flow started before redirect
        st.session_state.auth_flow_started = True
        
        # Redirect using JavaScript
        st.markdown(f'<meta http-equiv="refresh" content="0;url={auth_url}">', unsafe_allow_html=True)
        st.stop()
        
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        st.session_state.auth_error = f"Authentication error: {str(e)}"
        return False

def handle_logout():
    """Handle user logout"""
    auth_manager.clear_cached_credentials()
    st.session_state.authenticated = False
    st.session_state.user_info = None
    st.session_state.page = "Dashboard"
    st.rerun()

def show_auth_page():
    """Display authentication page with signup and login options"""
    # Center align the title
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Invoice Processing Agent")
    
    # Add some vertical spacing
    st.write("")
    st.write("")
    
    # Show any auth errors
    if st.session_state.get("auth_error"):
        st.error(st.session_state.auth_error)
        st.session_state.auth_error = None
    
    # Create tabs for Login and Signup
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Login")
            
            if submit_login:
                if username and password:
                    user_info = auth_manager.authenticate_user(username, password)
                    if user_info:
                        st.session_state.user_info = user_info
                        st.session_state.authenticated = True
                        st.session_state.auth_error = None
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.error("Please enter both username and password")
    
    with tab2:
        with st.form("signup_form", clear_on_submit=True):
            new_username = st.text_input("Username")
            new_email = st.text_input("Email")
            new_password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit_signup = st.form_submit_button("Sign Up")
            
            if submit_signup:
                if new_username and new_email and new_password and confirm_password:
                    if new_password != confirm_password:
                        st.error("Passwords do not match")
                    elif len(new_password) < 8:
                        st.error("Password must be at least 8 characters long")
                    elif auth_manager.user_exists(username=new_username):
                        st.error("Username already exists")
                    elif auth_manager.user_exists(email=new_email):
                        st.error("Email already exists")
                    else:
                        if auth_manager.register_user(new_username, new_email, new_password):
                            st.success("Registration successful! Please login.")
                        else:
                            st.error("Registration failed. Please try again.")
                else:
                    st.error("Please fill in all fields")

def show_dashboard():
    st.title("Dashboard")
    st.write(f"Welcome! You are authenticated via {st.session_state.user_info['auth_method']}")
    
    # Get current metrics
    current_metrics = metrics_manager.get_metrics()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Processed Today", current_metrics['processed_today'])
        st.metric("Success Rate", f"{current_metrics['success_rate']}%")
    
    with col2:
        st.metric("Processing Queue", current_metrics['processing_queue'])
        st.metric("Average Processing Time", f"{current_metrics['avg_processing_time']}s")

def show_workflow_search():
    st.title("Search Workflows")
    db_manager = DatabaseManager()
    
    try:
        # Search filters
            col1, col2, col3 = st.columns(3)
        
            with col1:
                status_filter = st.multiselect(
                "Status",
                ["pending", "processing", "completed", "completed_with_discrepancies", "failed"]
                )
        
        with col2:
                date_range = st.date_input(
                "Date Range",
                value=(datetime.now() - timedelta(days=30), datetime.now())
            )
        
        # Get invoices from database
        invoices = db_manager.get_all_invoices(
            status=status_filter[0] if status_filter else None,
            date_from=date_range[0] if len(date_range) > 0 else None,
            date_to=date_range[1] if len(date_range) > 1 else None
        )
        
        if invoices:
            # Display results
            st.subheader(f"Found {len(invoices)} invoices")
            
            # Create DataFrame
            df = pd.DataFrame(invoices)
            
            # Add status badges
            def status_badge(status):
                colors = {
                    'pending': 'blue',
                    'processing': 'orange',
                    'completed': 'green',
                    'completed_with_discrepancies': 'yellow',
                    'failed': 'red'
                }
                return f'<span style="color: {colors.get(status, "gray")}">●</span> {status.title()}'
            
            df['status'] = df['status'].apply(status_badge)
            
            # Display table
            st.markdown("""
                <style>
                    .dataframe td { text-align: left !important }
                </style>
            """, unsafe_allow_html=True)
            
                    st.dataframe(
                df,
                        column_config={
                    "id": "ID",
                    "invoice_number": "Invoice Number",
                    "vendor_name": "Vendor",
                    "total_amount": st.column_config.NumberColumn("Amount", format="%.2f"),
                    "status": st.column_config.Column("Status", help="Current status of the invoice"),
                    "created_at": "Created",
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # Show details for selected invoice
            selected_invoice = st.selectbox(
                "Select invoice to view details",
                [inv['id'] for inv in invoices],
                format_func=lambda x: f"Invoice {x} - {next((inv['invoice_number'] for inv in invoices if inv['id'] == x), '')}"
            )
            
            if selected_invoice:
                invoice_details = db_manager.get_invoice(selected_invoice)
                if invoice_details:
                    show_invoice_details(invoice_details)
        
        else:
            st.info("No invoices found matching the criteria")
    
    finally:
        db_manager.close()

def show_invoice_details(invoice_details):
    """Show detailed information about an invoice"""
                    st.markdown("---")
    st.subheader("Invoice Details")
    
    # Basic Information
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Invoice Number", invoice_details['invoice']['invoice_number'])
    with col2:
        st.metric("Vendor", invoice_details['invoice']['vendor_name'])
    with col3:
        st.metric("Amount", f"{invoice_details['invoice']['total_amount']:.2f}")
    
    # Status Timeline
    st.subheader("Processing Timeline")
    for status in invoice_details['workflow_status']:
        st.markdown(f"""
            <div style="padding: 10px; border-left: 3px solid {'green' if status['status'] == 'completed' else 'red' if status['status'] == 'failed' else 'orange'};">
                <strong>{status['status'].title()}</strong><br>
                {status['created_at']}<br>
                {status['message'] if status['message'] else ''}
        </div>
        """, unsafe_allow_html=True)
        
    # Extracted Data
    if invoice_details['extracted_data']:
        st.subheader("Extracted Data")
        extracted_df = pd.DataFrame(invoice_details['extracted_data'])
        st.dataframe(extracted_df)
    
    # Matching Results
    if invoice_details['matching_result']:
        st.subheader("Matching Results")
        match_result = invoice_details['matching_result']
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("PO Match", "✅" if match_result['po_match_status'] else "❌")
        with col2:
            st.metric("GR Match", "✅" if match_result['gr_match_status'] else "❌")
        
        if match_result['discrepancies']:
            st.warning("Discrepancies Found:")
            for disc in json.loads(match_result['discrepancies']):
                st.write(f"- {disc}")
                
    # Document Preview
    if invoice_details['invoice']['file_path']:
        st.subheader("Document Preview")
        try:
            with open(invoice_details['invoice']['file_path'], "rb") as file:
                st.download_button(
                    "Download Original Document",
                    file,
                    file_name=os.path.basename(invoice_details['invoice']['file_path']),
                    mime="application/pdf"
                )
        except Exception as e:
            st.error(f"Error loading document: {str(e)}")

def show_invoice_processing():
    st.title("Invoice Processing")
    
    # Add tabs for different sections
    tab1, tab2, tab3 = st.tabs(["Upload & Process", "Search Workflows", "Recent Activity"])
    
    with tab1:
        st.subheader("Invoice Upload")
        
        # Create two columns for upload options
        col1, col2 = st.columns(2)
        
        # Single Invoice Upload Section
        with col1:
            st.markdown("### Single Invoice")
            uploaded_file = st.file_uploader("Choose Invoice", type=["pdf", "png", "jpg", "jpeg"], key="single_upload")
            single_upload_button = st.button("Process Invoice", key="single_process_btn", disabled=not uploaded_file)
        
        # Batch Upload Section
        with col2:
            st.markdown("### Batch Upload")
            batch_files = st.file_uploader("Choose Multiple Invoices", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True, key="batch_upload")
            batch_upload_button = st.button("Process All", key="batch_process_btn", disabled=not batch_files)
        
        # Progress container for both single and batch processing
        progress_container = st.empty()
        result_container = st.empty()
        
        # Handle Single Invoice Upload
        if uploaded_file and single_upload_button:
            process_single_invoice(uploaded_file, progress_container, result_container)
        
        # Handle Batch Upload
        if batch_files and batch_upload_button:
            process_batch_invoices(batch_files, progress_container, result_container)

def process_single_invoice(uploaded_file, status_container, result_container):
    """Process a single invoice file"""
    start_time = datetime.now()
    db_manager = DatabaseManager()
    
    # Save the file temporarily
    temp_path = f"temp_{uploaded_file.name}"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    try:
        status_container.info("📄 Processing invoice...")
        
        # Process invoice
        result = invoice_agent.process_invoice(temp_path)
        invoice_id = result['invoice_id']
        workflow_id = result['workflow_id']
        
        # Get complete invoice details from database
        invoice_details = db_manager.get_invoice(invoice_id)
        
        if invoice_details:
            # Show success message with workflow ID
            status_message = f"Workflow ID: {workflow_id}"
            if invoice_details['invoice']['status'] == 'completed':
                status_container.success(f"✅ Invoice processed successfully! {status_message}")
            elif invoice_details['invoice']['status'] == 'completed_with_discrepancies':
                status_container.warning(f"⚠️ Invoice processed with discrepancies. {status_message}")
            else:
                status_container.error(f"❌ Invoice processing failed. {status_message}")
            
            # Show detailed results
            with result_container.expander("Processing Results", expanded=True):
                # Workflow Information
                st.subheader("Workflow Information")
                st.info(f"Workflow ID: {workflow_id}")
                
                # Invoice Details
                st.subheader("Invoice Details")
                invoice_df = pd.DataFrame([invoice_details['invoice']])
                st.dataframe(invoice_df)
                
                # Extracted Data
                st.subheader("Extracted Data")
                extracted_df = pd.DataFrame(invoice_details['extracted_data'])
                st.dataframe(extracted_df)
                
                # Workflow Status
                st.subheader("Processing Timeline")
                for status in invoice_details['workflow_status']:
                    st.markdown(f"""
                        **{status['status'].title()}** - {status['created_at']}  
                        {status['message'] if status['message'] else ''}
                    """)
                
                # Matching Results
                if invoice_details['matching_result']:
                    st.subheader("Matching Results")
                    match_result = invoice_details['matching_result']
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("PO Match", "✅" if match_result['po_match_status'] else "❌")
                    with col2:
                        st.metric("GR Match", "✅" if match_result['gr_match_status'] else "❌")
                    
                    if match_result['discrepancies']:
                        st.warning("Discrepancies Found:")
                        for disc in json.loads(match_result['discrepancies']):
                            st.write(f"- {disc}")
                
                # Processing Time
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
            st.metric("Processing Time", f"{processing_time:.2f} seconds")
        
    except Exception as e:
        status_container.error(f"❌ Error processing invoice: {str(e)}")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        db_manager.close()

def process_batch_invoices(batch_files, status_container, result_container):
    """Process multiple invoice files"""
    total_files = len(batch_files)
    start_time = datetime.now()
    
    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Create containers for success and error summaries
    success_container = st.container()
    error_container = st.container()
    
    successful_files = []
    failed_files = []
    
    for index, uploaded_file in enumerate(batch_files):
        current_progress = (index + 1) / total_files
        progress_bar.progress(current_progress)
        status_text.text(f"Processing file {index + 1} of {total_files}: {uploaded_file.name}")
        
        # Save the file temporarily
        temp_path = f"temp_batch_{uploaded_file.name}"
        try:
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Create workflow for this file
            workflow_id = workflow_manager.create_workflow(
                template_id="default",
                document_path=temp_path,
                user_id=st.session_state.user_info.get("client_id")
            )
            
            # Process the document
            result = invoice_agent.process_document(temp_path)
            po_number = result.get('po_number')
            
            # Get related data
            po_data = invoice_agent.get_purchase_order(po_number)
            gr_data = invoice_agent.get_goods_receipt(po_number)
            
            # Perform matching
            match_result = invoice_agent.perform_three_way_match(
                invoice_data=result,
                po_data=po_data,
                gr_data=gr_data
            )
            
            # Update workflow with results
            workflow_manager.update_workflow(
                workflow_id,
                extraction_results=result,
                matching_results=match_result
            )
            
            # Update final status
            if match_result.get('match_successful'):
                workflow_manager.update_workflow_status(
                    workflow_id,
                    "completed",
                    message="Processing completed successfully"
                )
                successful_files.append({
                    'filename': uploaded_file.name,
                    'workflow_id': workflow_id,
                    'status': 'Success'
                })
            else:
                workflow_manager.update_workflow_status(
                    workflow_id,
                    "completed_with_discrepancies",
                    message=f"Completed with {len(match_result.get('discrepancies', []))} discrepancies"
                )
                successful_files.append({
                    'filename': uploaded_file.name,
                    'workflow_id': workflow_id,
                    'status': 'Completed with discrepancies'
                })
            
        except Exception as e:
            error_message = str(e)
            if 'workflow_id' in locals():
                workflow_manager.update_workflow_status(
                    workflow_id,
                    "failed",
                    message=f"Processing failed: {error_message}",
                    error=error_message
                )
            failed_files.append({
                'filename': uploaded_file.name,
                'error': error_message
            })
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    # Calculate total processing time
    total_time = (datetime.now() - start_time).total_seconds()
    
    # Show summary
    with result_container:
        st.markdown("### Batch Processing Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Files", total_files)
        with col2:
            st.metric("Successful", len(successful_files))
        with col3:
            st.metric("Failed", len(failed_files))
        with col4:
            st.metric("Processing Time", f"{total_time:.2f}s")
        
        # Show successful files
        if successful_files:
            with st.expander("Successfully Processed Files", expanded=True):
                st.table(pd.DataFrame(successful_files))
        
        # Show failed files
        if failed_files:
            with st.expander("Failed Files", expanded=True):
                st.table(pd.DataFrame(failed_files))

def show_templates():
    st.title("Templates")
    st.write("Manage your invoice templates here.")
    
    # Add tabs for different template operations
    tab1, tab2, tab3 = st.tabs(["View Templates", "Create Template", "Edit Template"])
    
    with tab1:
        templates = template_manager.list_templates()
        if templates:
            selected_template = st.selectbox("Select Template", templates, key="view_template")
            if selected_template:
                template_data = template_manager.get_template(selected_template)
                st.json(template_data)
                if st.button("Delete Template", key="delete_btn"):
                    if template_manager.delete_template(selected_template):
                        st.success("Template deleted successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to delete template!")
        else:
            st.info("No templates found")
    
    with tab2:
        st.subheader("Create New Template")
        new_template_name = st.text_input("Template Name")
        
        # Template fields
        st.subheader("Template Fields")
        col1, col2 = st.columns(2)
        
        with col1:
            vendor_name = st.text_input("Vendor Name Pattern")
            invoice_number = st.text_input("Invoice Number Pattern")
            date_pattern = st.text_input("Date Pattern", value=r"\d{2}/\d{2}/\d{4}")
            amount_pattern = st.text_input("Amount Pattern", value=r"\$?\d+,?\d*\.?\d*")
        
        with col2:
            tax_pattern = st.text_input("Tax Pattern", value=r"\$?\d+\.?\d*")
            po_number = st.text_input("PO Number Pattern")
            custom_field = st.text_input("Custom Field Name")
            custom_pattern = st.text_input("Custom Field Pattern")
        
        if st.button("Create Template", key="create_btn"):
            if new_template_name:
                template_data = {
                    "name": new_template_name,
                    "patterns": {
                        "vendor_name": vendor_name,
                        "invoice_number": invoice_number,
                        "date": date_pattern,
                        "amount": amount_pattern,
                        "tax": tax_pattern,
                        "po_number": po_number
                    }
                }
                if custom_field and custom_pattern:
                    template_data["patterns"][custom_field] = custom_pattern
                
                if template_manager.create_template(new_template_name, template_data):
                    st.success("Template created successfully!")
                    st.rerun()
                else:
                    st.error("Failed to create template!")
            else:
                st.warning("Please enter a template name")
    
    with tab3:
        templates = template_manager.list_templates()
        if templates:
            selected_template = st.selectbox("Select Template to Edit", templates, key="edit_template")
            if selected_template:
                template_data = template_manager.get_template(selected_template)
                
                st.subheader("Edit Template Fields")
                col1, col2 = st.columns(2)
                
                patterns = template_data.get("patterns", {})
                with col1:
                    vendor_name = st.text_input("Vendor Name Pattern", value=patterns.get("vendor_name", ""))
                    invoice_number = st.text_input("Invoice Number Pattern", value=patterns.get("invoice_number", ""))
                    date_pattern = st.text_input("Date Pattern", value=patterns.get("date", r"\d{2}/\d{2}/\d{4}"))
                    amount_pattern = st.text_input("Amount Pattern", value=patterns.get("amount", r"\$?\d+,?\d*\.?\d*"))
                
                with col2:
                    tax_pattern = st.text_input("Tax Pattern", value=patterns.get("tax", r"\$?\d+\.?\d*"))
                    po_number = st.text_input("PO Number Pattern", value=patterns.get("po_number", ""))
                    custom_field = st.text_input("Custom Field Name")
                    custom_pattern = st.text_input("Custom Field Pattern")
                
                if st.button("Save Changes", key="save_btn"):
                    updated_data = {
                        "name": selected_template,
                        "patterns": {
                            "vendor_name": vendor_name,
                            "invoice_number": invoice_number,
                            "date": date_pattern,
                            "amount": amount_pattern,
                            "tax": tax_pattern,
                            "po_number": po_number
                        }
                    }
                    if custom_field and custom_pattern:
                        updated_data["patterns"][custom_field] = custom_pattern
                    
                    if template_manager.update_template(selected_template, updated_data):
                        st.success("Template updated successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to update template!")
        else:
            st.info("No templates found to edit")

def show_reports():
    st.title("Reports")
    
    # Report type selection
    report_type = st.selectbox(
        "Select Report Type",
        ["Processing Summary", "Error Analysis", "Performance Metrics"]
    )
    
    # Date range selection
    st.subheader("Select Date Range")
    
    min_date = date(2020, 1, 1)
    max_date = date.today()
    
    start_date = st.date_input(
        "Start Date",
        value=max_date - timedelta(days=30),
        min_value=min_date,
        max_value=max_date,
        key="start_date"
    )
    
    end_date = st.date_input(
        "End Date",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key="end_date"
    )
    
    if start_date and end_date:
        if start_date <= end_date:
            # Get historical metrics
            historical_data = metrics_manager.get_historical_metrics(
                (end_date - start_date).days
            )
            
            if historical_data:
                st.success(f"Generating {report_type} report")
                st.line_chart(historical_data)
            else:
                st.info("No data available for the selected date range")
        else:
            st.error("Error: End date must be after start date")

def show_settings():
    """Show settings page"""
    st.title("⚙️ Settings")
    
    # Create tabs for different settings categories
    tab1, tab2, tab3 = st.tabs(["General", "Notifications", "API Configuration"])
    
    with tab1:
        st.subheader("General Settings")
        
        # Theme settings
        theme = st.selectbox(
            "Theme",
            ["Dark", "Light", "System Default"],
            index=0
        )
        
        # Language settings
        language = st.selectbox(
            "Language",
            ["English", "Spanish", "French", "German"],
            index=0
        )
        
        # Time zone settings
        timezone = st.selectbox(
            "Time Zone",
            ["UTC", "US/Pacific", "US/Eastern", "Europe/London"],
            index=0
        )
        
        if st.button("Save General Settings"):
            st.success("Settings saved successfully!")
    
    with tab2:
        st.subheader("Notification Settings")
        
        # Email notifications
        st.checkbox("Email notifications", value=True)
        st.checkbox("Processing completion alerts", value=True)
        st.checkbox("Error notifications", value=True)
        
        # Notification frequency
        st.select_slider(
            "Notification frequency",
            options=["Real-time", "Hourly", "Daily", "Weekly"],
            value="Daily"
        )
        
        if st.button("Save Notification Settings"):
            st.success("Notification settings saved!")
    
    with tab3:
        st.subheader("API Configuration")
        
        # API credentials
        api_key = st.text_input("API Key", type="password")
        api_secret = st.text_input("API Secret", type="password")
        
        # API endpoints
        api_url = st.text_input("API URL", value="https://api.example.com")
        
        if st.button("Save API Settings"):
            st.success("API settings saved successfully!")

def show_analytics():
    """Show analytics page"""
    st.title("📈 Analytics")
    
    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date")
    with col2:
        end_date = st.date_input("End Date")
    
    # Metrics overview
    st.subheader("Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Processed", "1,234")
    with col2:
        st.metric("Success Rate", "95%")
    with col3:
        st.metric("Avg. Processing Time", "2.3s")
    with col4:
        st.metric("Error Rate", "5%")
    
    # Processing volume chart
    st.subheader("Processing Volume")
    chart_data = pd.DataFrame({
        'Date': pd.date_range(start='2024-01-01', end='2024-01-31', freq='D'),
        'Volume': np.random.randint(50, 200, size=31)
    })
    st.line_chart(chart_data.set_index('Date'))
    
    # Error analysis
    st.subheader("Error Analysis")
    error_data = pd.DataFrame({
        'Error Type': ['Validation', 'Processing', 'Network', 'Other'],
        'Count': [45, 23, 12, 8]
    })
    st.bar_chart(error_data.set_index('Error Type'))

def show_help():
    """Show help page"""
    st.title("❓ Help & Support")
    
    # FAQ section
    st.subheader("Frequently Asked Questions")
    
    with st.expander("How do I process an invoice?"):
        st.write("""
            1. Navigate to the Invoice Processing page
            2. Upload your invoice file
            3. Select the appropriate template
            4. Click 'Process Invoice'
            5. Review the results
        """)
    
    with st.expander("What file formats are supported?"):
        st.write("""
            We support the following file formats:
            - PDF
            - PNG/JPEG images
            - TIFF files
            - Scanned documents
        """)
    
    with st.expander("How do I create a custom template?"):
        st.write("""
            1. Go to the Templates page
            2. Click 'Create New Template'
            3. Define the fields and patterns
            4. Save your template
        """)
    
    # Contact support
    st.subheader("Contact Support")
    
    with st.form("support_form"):
        st.text_input("Subject")
        st.text_area("Message")
        st.selectbox("Priority", ["Low", "Medium", "High"])
        submitted = st.form_submit_button("Submit Ticket")
        
        if submitted:
            st.success("Support ticket submitted successfully! We'll get back to you soon.")
    
    # Documentation
    st.subheader("Documentation")
    st.markdown("""
        - [User Guide](https://example.com/docs/user-guide)
        - [API Documentation](https://example.com/docs/api)
        - [Best Practices](https://example.com/docs/best-practices)
        - [Troubleshooting](https://example.com/docs/troubleshooting)
    """)

def main():
    """Main application entry point with improved error handling"""
    try:
        # Initialize session state
        init_session_state()
        
        # Check connection health
        if not check_connection_health():
            return
        
        # Show appropriate page based on authentication status
        if not st.session_state.authenticated:
            show_auth_page()
        else:
            try:
                # Custom CSS for navigation
                st.markdown("""
                <style>
                    .sidebar-content {
                        padding: 1rem;
                    }
                    .nav-header {
                        color: #FFFFFF;
                        padding: 1rem 0;
                        margin-bottom: 2rem;
                        border-bottom: 1px solid #4a4a4a;
                    }
                    .nav-item {
                        padding: 0.5rem 1rem;
                        margin: 0.5rem 0;
                        border-radius: 0.5rem;
                        background: #262730;
                        cursor: pointer;
                        transition: background-color 0.3s;
                    }
                    .nav-item:hover {
                        background: #31343a;
                    }
                    .nav-footer {
                        position: fixed;
                        bottom: 0;
                        left: 0;
                        width: 100%;
                        padding: 1rem;
                        background: #262730;
                        border-top: 1px solid #4a4a4a;
                        z-index: 1000;
                    }
                    .user-info {
                        font-size: 0.9rem;
                        color: #FFFFFF;
                        opacity: 0.8;
                        margin-bottom: 0.5rem;
                    }
                </style>
                """, unsafe_allow_html=True)

                # Navigation sidebar
                with st.sidebar:
                    st.markdown('<div class="nav-header"><h2>Invoice Agent</h2></div>', unsafe_allow_html=True)
                    
                    # Create container for navigation items
                    nav_container = st.container()
                    
                    with nav_container:
                        pages = {
                            "📊 Dashboard": show_dashboard,
                            "📄 Invoice Processing": show_invoice_processing,
                            "🔍 Workflow Search": show_workflow_search,
                            "📝 Templates": show_templates,
                            "⚙️ Settings": show_settings,
                            "📈 Analytics": show_analytics,
                            "❓ Help": show_help
                        }
                        
                        # Replace dropdown with option_menu
                        selected_page = option_menu(
                            menu_title=None,
                            options=list(pages.keys()),
                            icons=[icon.split()[0] for icon in pages.keys()],  # Extract emojis as icons
                            menu_icon="cast",
                            default_index=0,
                            styles={
                                "container": {"padding": "0!important", "background-color": "#262730"},
                                "icon": {"color": "orange", "font-size": "20px"}, 
                                "nav-link": {
                                    "font-size": "16px",
                                    "text-align": "left",
                                    "margin": "0px",
                                    "--hover-color": "#31343a",
                                },
                                "nav-link-selected": {"background-color": "#FF4B4B"},
                            }
                        )
                    
                    # Add spacing before user info
                    st.markdown("<br>" * 3, unsafe_allow_html=True)
                    
                    # User info and logout in a fixed footer
                    st.markdown(
                        f"""
                        <div class="nav-footer">
                            <div class="user-info">
                                👤 {st.session_state.user_info.get('username', 'Unknown')}
                                <br>
                                <small style="opacity: 0.7;">Last login: {datetime.now().strftime('%Y-%m-%d %H:%M')}</small>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    # Logout button with improved styling
                    st.markdown("""
                        <style>
                            div[data-testid="stButton"] button {
                                background-color: #FF4B4B;
                                color: white;
                                border: none;
                                padding: 0.5rem 1rem;
                                border-radius: 4px;
                                cursor: pointer;
                                width: 100%;
                                margin-top: 0.5rem;
                            }
                            div[data-testid="stButton"] button:hover {
                                background-color: #FF3333;
                            }
                        </style>
                    """, unsafe_allow_html=True)
                    if st.button("🚪 Logout", key="logout_btn"):
                        handle_logout()
                
                # Show selected page
                try:
                    # Remove the emoji from the selected page name to get the function
                    page_name = " ".join(selected_page.split()[1:])
                    pages[selected_page]()
                except Exception as e:
                    st.error(f"Error displaying page {selected_page}: {str(e)}")
                    print(f"Page error: {str(e)}")
                
            except Exception as e:
                st.error("Navigation error occurred. Please try refreshing the page.")
                print(f"Navigation error: {str(e)}")
                
    except Exception as e:
        st.error(f"""
        An error occurred while running the application:
        {str(e)}
        
        Please try:
        1. Refreshing the page
        2. Clearing your browser cache
        3. Using a different browser
        """)
        print(f"Application error: {str(e)}")

if __name__ == "__main__":
    try:
        # Start the Streamlit app in the main thread
        run_streamlit()
    except KeyboardInterrupt:
        cleanup_resources()
    except Exception as e:
        logging.error(f"Critical error: {str(e)}")
        st.error("Critical error occurred. Please restart the application.") 