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
    """Display workflow search interface with improved connection handling"""
    try:
        st.subheader("Search Workflows")
        
        # Initialize view mode in session state if not present
        if 'workflow_view_mode' not in st.session_state:
            st.session_state.workflow_view_mode = "Table"
        
        # Update last activity time
        st.session_state.last_activity = time.time()
        
        # Search filters in a form for better performance
        with st.form("workflow_search_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                search_term = st.text_input("Search by ID or document name")
            with col2:
                status_filter = st.multiselect(
                    "Filter by status",
                    ["created", "processing", "completed", "failed", "completed_with_discrepancies"]
                )
            with col3:
                date_range = st.date_input(
                    "Date range",
                    value=(datetime.now() - timedelta(days=7), datetime.now()),
                    max_value=datetime.now()
                )
            
            submitted = st.form_submit_button("Search")
        
        # Store workflows in session state
        if submitted:
            with st.spinner("Fetching workflows..."):
                workflows = workflow_manager.get_workflows(
                    search_term=search_term,
                    status_filter=status_filter,
                    date_range=date_range
                )
                if workflows:
                    st.session_state.current_workflows = workflows
                else:
                    st.session_state.current_workflows = None

        # Display workflows if they exist in session state
        if hasattr(st.session_state, 'current_workflows') and st.session_state.current_workflows:
            workflows = st.session_state.current_workflows
            
            # Display workflows in chunks for better performance
            CHUNK_SIZE = 10
            total_workflows = len(workflows)
            
            if 'workflow_page' not in st.session_state:
                st.session_state.workflow_page = 0
            
            start_idx = st.session_state.workflow_page * CHUNK_SIZE
            end_idx = min(start_idx + CHUNK_SIZE, total_workflows)
            
            current_chunk = workflows[start_idx:end_idx]
            
            # Display workflows in current chunk
            workflow_data = []
            for w in current_chunk:
                # Safely get matching results with proper null checks
                matching_results = w.get('matching_results') or {}
                match_status = "⏳"  # Default status
                if matching_results:
                    match_successful = matching_results.get('match_successful')
                    if match_successful is not None:
                        match_status = "✅" if match_successful else "❌"
                
                # Handle processing time formatting safely
                processing_time = w.get('processing_time')
                if processing_time is not None:
                    processing_time_str = f"{float(processing_time):.2f}s"
                else:
                    processing_time_str = "N/A"
                
                workflow_data.append({
                    "ID": w.get('id', '')[:8] + "...",
                    "Status": w.get('status', 'unknown'),
                    "Document": w.get('document_path', 'unknown'),
                    "Created": datetime.fromisoformat(w.get('created_at', datetime.now().isoformat())).strftime("%Y-%m-%d %H:%M"),
                    "Processing Time": processing_time_str,
                    "Match Status": match_status
                })
            
            if workflow_data:
                # Add view toggle and update session state
                st.session_state.workflow_view_mode = st.radio(
                    "View Mode",
                    ["Table", "Cards"],
                    horizontal=True,
                    key="workflow_view_toggle",
                    index=0 if st.session_state.workflow_view_mode == "Table" else 1
                )
                
                if st.session_state.workflow_view_mode == "Table":
                    st.dataframe(
                        pd.DataFrame(workflow_data),
                        column_config={
                            "ID": st.column_config.TextColumn("ID", width="small"),
                            "Status": st.column_config.TextColumn("Status", width="medium"),
                            "Document": st.column_config.TextColumn("Document", width="large"),
                            "Created": st.column_config.TextColumn("Created", width="medium"),
                            "Processing Time": st.column_config.TextColumn("Processing Time", width="small"),
                            "Match Status": st.column_config.TextColumn("Match", width="small"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    # Card view
                    for w in workflow_data:
                        st.markdown(f"""
                        <div style='padding: 1rem; border-radius: 0.5rem; background-color: #262730; margin-bottom: 1rem;'>
                            <div style='display: flex; justify-content: space-between; align-items: center;'>
                                <h4 style='margin: 0; color: #FFFFFF;'>{w['ID']}</h4>
                                <span style='background-color: {"#28a745" if w["Status"] == "completed" else "#dc3545" if w["Status"] == "failed" else "#17a2b8"}; 
                                            padding: 0.2rem 0.6rem; border-radius: 1rem; color: white;'>
                                    {w["Status"]}
                                </span>
                            </div>
                            <p style='margin: 0.5rem 0; color: #FFFFFF;'>{w["Document"]}</p>
                            <div style='display: flex; justify-content: space-between; font-size: 0.9rem; color: #FFFFFF;'>
                                <span>{w["Created"]}</span>
                                <span>{w["Processing Time"]}</span>
                                <span>{w["Match Status"]}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Pagination controls
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.session_state.workflow_page > 0:
                        if st.button("← Previous"):
                            st.session_state.workflow_page -= 1
                            st.experimental_rerun()
                            
                    st.write(f"Page {st.session_state.workflow_page + 1} of {(total_workflows - 1) // CHUNK_SIZE + 1}")
                    
                    if end_idx < total_workflows:
                        if st.button("Next →"):
                            st.session_state.workflow_page += 1
                            st.experimental_rerun()
                
                # Allow clicking on a workflow to view details
                selected_workflow = st.selectbox(
                    "Select workflow to view details",
                    [w.get('id', '') for w in current_chunk],
                    format_func=lambda x: f"{x[:8]}... - {next((w.get('document_path', '') for w in current_chunk if w.get('id') == x), '')}"
                )
                
                if selected_workflow:
                    st.markdown("---")
                    show_workflow_details(selected_workflow)
        else:
            if submitted:
                st.info("No workflows found matching the criteria")
        
        # Check connection health periodically
        if not check_connection_health():
            st.warning("Connection issues detected. Please refresh the page.")
            return
            
    except Exception as e:
        print(f"Error in workflow search: {str(e)}")
        st.error("An error occurred while searching workflows. Please try again.")
        # Reset page state on error
        if 'workflow_page' in st.session_state:
            del st.session_state.workflow_page

def show_workflow_details(workflow_id: str):
    """Display detailed information about a specific workflow"""
    workflow_data = workflow_manager.get_workflow(workflow_id)
    
    if workflow_data:
        # Initialize results view mode in session state if not present
        if 'results_view_mode' not in st.session_state:
            st.session_state.results_view_mode = "Formatted"
            
        st.subheader("Workflow Details")
        
        # Status Badge
        status_color = {
            "completed": "🟢",
            "failed": "🔴",
            "processing": "🟡",
            "completed_with_discrepancies": "🟠"
        }.get(workflow_data.get('status', ''), "⚪")
        
        # Basic Information in a card-like layout with darker background
        st.markdown(f"""
        <div style='padding: 1rem; border-radius: 0.5rem; background-color: #262730; color: #FFFFFF;'>
            <h3>{status_color} Workflow {workflow_id}</h3>
            <p style='color: #FFFFFF;'>Status: {workflow_data.get('status', 'Unknown').title()}</p>
            <p style='color: #FFFFFF;'>Document: {workflow_data.get('document_path', 'Unknown')}</p>
            <p style='color: #FFFFFF;'>Template: {workflow_data.get('template_id', 'Default')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Timing Information
        created_at = workflow_data.get('created_at')
        updated_at = workflow_data.get('updated_at')
        
        if created_at and updated_at:
            created_time = datetime.fromisoformat(created_at)
            updated_time = datetime.fromisoformat(updated_at)
            processing_duration = updated_time - created_time
            
            timing_col1, timing_col2, timing_col3 = st.columns(3)
            with timing_col1:
                st.metric("Created", created_time.strftime("%H:%M:%S"))
            with timing_col2:
                st.metric("Updated", updated_time.strftime("%H:%M:%S"))
            with timing_col3:
                st.metric("Duration", f"{processing_duration.total_seconds():.2f}s")
        
        # Processing Log with Timeline
        if workflow_data.get('processing_log'):
            st.subheader("Processing Timeline")
            
            # Custom CSS for timeline
            st.markdown("""
            <style>
            .timeline-container {
                display: flex;
                align-items: center;
                gap: 20px;
                padding: 20px;
                background: #262730;
                border-radius: 8px;
                overflow-x: auto;
                position: relative;
                margin-bottom: 20px;
            }
            .timeline-container::after {
                content: '';
                position: absolute;
                top: 50%;
                left: 0;
                right: 0;
                height: 2px;
                background: #4a4a4a;
                z-index: 1;
            }
            .timeline-item {
                display: flex;
                flex-direction: column;
                align-items: center;
                min-width: 120px;
                position: relative;
                z-index: 2;
                background: #262730;
                padding: 0 10px;
            }
            .timeline-dot {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-bottom: 8px;
                border: 2px solid currentColor;
                background: #262730;
            }
            .timeline-label {
                font-size: 0.85em;
                font-weight: 500;
                text-align: center;
                margin-bottom: 4px;
                color: currentColor;
            }
            .timeline-time {
                font-size: 0.75em;
                opacity: 0.8;
                color: #FFFFFF;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Build timeline HTML
            timeline_items = []
            for log_entry in workflow_data['processing_log']:
                entry_time = datetime.fromisoformat(log_entry.get('timestamp', created_at))
                status = log_entry.get('status', '').lower()
                
                # Map status to colors
                status_color = {
                    "completed": "#28a745",
                    "failed": "#dc3545",
                    "processing": "#17a2b8",
                    "loading": "#ffc107",
                    "erp_connection": "#6f42c1",
                    "matching": "#fd7e14",
                    "po_retrieval": "#20c997",
                    "gr_retrieval": "#e83e8c",
                    "completed_with_discrepancies": "#fd7e14"
                }.get(status, "#6c757d")
                
                # Format status label
                status_label = status.replace('_', ' ').title()
                
                # Create timeline item
                timeline_items.append(
                    f'<div class="timeline-item">'
                    f'<div class="timeline-dot" style="border-color: {status_color};"></div>'
                    f'<div class="timeline-label" style="color: {status_color};">{status_label}</div>'
                    f'<div class="timeline-time">{entry_time.strftime("%H:%M:%S")}</div>'
                    f'</div>'
                )
            
            # Combine all items into the container
            timeline_html = f'<div class="timeline-container">{"".join(timeline_items)}</div>'
            
            # Render the timeline
            st.markdown(timeline_html, unsafe_allow_html=True)
            
            # Add expandable details section
            with st.expander("View Details"):
                for log_entry in workflow_data['processing_log']:
                    entry_time = datetime.fromisoformat(log_entry.get('timestamp', created_at))
                    status = log_entry.get('status', '').lower()
                    status_color = {
                        "completed": "#28a745",
                        "failed": "#dc3545",
                        "processing": "#17a2b8",
                        "loading": "#ffc107",
                        "erp_connection": "#6f42c1",
                        "matching": "#fd7e14",
                        "po_retrieval": "#20c997",
                        "gr_retrieval": "#e83e8c",
                        "completed_with_discrepancies": "#fd7e14"
                    }.get(status, "#6c757d")
                    
                    st.markdown(
                        f'<div style="padding: 8px; border-left: 3px solid {status_color}; '
                        f'margin-bottom: 8px; background: #262730; border-radius: 4px;">'
                        f'<div style="color: {status_color}; font-weight: 500;">'
                        f'{entry_time.strftime("%H:%M:%S")} - {status.replace("_", " ").title()}</div>'
                        f'<div style="color: #FFFFFF; margin-top: 4px;">{log_entry.get("message", "")}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
        
        # Toggle between Raw and Formatted Data with session state
        st.subheader("Processing Results")
        st.session_state.results_view_mode = st.radio(
            "View Mode",
            ["Formatted", "Raw"],
            horizontal=True,
            key="results_view_toggle",
            index=0 if st.session_state.results_view_mode == "Formatted" else 1
        )
        
        tab1, tab2 = st.tabs(["Extraction Results", "Matching Results"])
        
        with tab1:
            if workflow_data.get('extraction_results'):
                if st.session_state.results_view_mode == "Raw":
                    st.json(workflow_data['extraction_results'])
                else:
                    # Format extraction results in a table
                    extraction_data = workflow_data['extraction_results']
                    if isinstance(extraction_data, dict):
                        df = pd.DataFrame([
                            {"Field": k, "Value": str(v)} 
                            for k, v in extraction_data.items() 
                            if not isinstance(v, (dict, list))
                        ])
                        st.dataframe(
                            df,
                            column_config={
                                "Field": st.column_config.TextColumn("Field", width="medium"),
                                "Value": st.column_config.TextColumn("Value", width="large")
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                        
                        # Show nested data in expandable sections
                        for k, v in extraction_data.items():
                            if isinstance(v, (dict, list)):
                                with st.expander(f"{k} Details"):
                                    st.json(v)
            else:
                st.info("No extraction results available")
        
        with tab2:
            if workflow_data.get('matching_results'):
                if st.session_state.results_view_mode == "Raw":
                    st.json(workflow_data['matching_results'])
                else:
                    # Format matching results in a table
                    matching_data = workflow_data['matching_results']
                    if isinstance(matching_data, dict):
                        # Summary table
                        summary_data = {
                            "Match Status": "✅ Matched" if matching_data.get('match_successful') else "❌ Not Matched",
                            "PO Number": matching_data.get('po_details', {}).get('number', 'N/A'),
                            "GR Number": matching_data.get('gr_details', {}).get('number', 'N/A'),
                            "Total Amount": matching_data.get('po_details', {}).get('total_amount', 'N/A')
                        }
                        st.dataframe(
                            pd.DataFrame([summary_data]),
                            hide_index=True,
                            use_container_width=True
                        )
                        
                        # Show discrepancies if any
                        if matching_data.get('discrepancies'):
                            st.markdown("### Discrepancies")
                            for disc in matching_data['discrepancies']:
                                st.warning(disc)
                                
                        # Show detailed comparisons in expandable sections
                        with st.expander("View Detailed Comparison"):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.markdown("#### Invoice Data")
                                st.json(matching_data.get('invoice_data', {}))
                            with col2:
                                st.markdown("#### PO Data")
                                st.json(matching_data.get('po_details', {}))
                            with col3:
                                st.markdown("#### GR Data")
                                st.json(matching_data.get('gr_details', {}))
            else:
                st.info("No matching results available")
    else:
        st.error(f"No workflow found with ID: {workflow_id}")

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
    
    # Save the file temporarily
    temp_path = f"temp_{uploaded_file.name}"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    try:
        # Create and display workflow ID
        workflow_id = workflow_manager.create_workflow(
            template_id="default",
            document_path=temp_path,
            user_id=st.session_state.user_info.get("client_id")
        )
        st.info(f"Workflow ID: {workflow_id}")
        
        # Document Loading
        status_container.info("📄 Loading document...")
        workflow_manager.update_workflow_status(
            workflow_id,
            "loading",
            message="Loading document for processing"
        )
        
        # Processing
        status_container.warning("⚙️ Processing invoice...")
        workflow_manager.update_workflow_status(
            workflow_id,
            "processing",
            message="Extracting data from document"
        )
        
        # Process document and store results
        result = invoice_agent.process_document(temp_path)
        workflow_manager.update_workflow(
            workflow_id,
            extraction_results=result
        )
        
        # ERP Connection
        status_container.warning("🔌 Connecting to ERP...")
        workflow_manager.update_workflow_status(
            workflow_id,
            "erp_connection",
            message="Retrieving data from ERP system"
        )
        
        # Extract invoice details for matching
        invoice_number = result.get('invoice_number')
        po_number = result.get('po_number')
        
        # Get PO data from ERP
        status_container.warning("📋 Retrieving Purchase Order...")
        workflow_manager.update_workflow_status(
            workflow_id,
            "po_retrieval",
            message=f"Retrieving PO: {po_number}"
        )
        po_data = invoice_agent.get_purchase_order(po_number)
        
        # Get Goods Receipt data
        status_container.warning("📦 Retrieving Goods Receipt...")
        workflow_manager.update_workflow_status(
            workflow_id,
            "gr_retrieval",
            message=f"Retrieving Goods Receipt for PO: {po_number}"
        )
        gr_data = invoice_agent.get_goods_receipt(po_number)
        
        # Perform three-way match
        status_container.warning("🔍 Performing three-way match...")
        workflow_manager.update_workflow_status(
            workflow_id,
            "matching",
            message="Performing three-way match validation"
        )
        
        match_result = invoice_agent.perform_three_way_match(
            invoice_data=result,
            po_data=po_data,
            gr_data=gr_data
        )
        
        # Store matching results
        workflow_manager.update_workflow(
            workflow_id,
            matching_results=match_result
        )
        
        # Validation based on match results
        if match_result.get('match_successful'):
            status_container.success("✅ Three-way match successful!")
        else:
            discrepancies = match_result.get('discrepancies', [])
            status_container.warning(f"⚠️ Match discrepancies found: {len(discrepancies)} issues")
            for disc in discrepancies:
                st.warning(f"- {disc}")
        
        # Calculate processing time
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Update final status based on match results
        if match_result.get('match_successful'):
            workflow_manager.update_workflow_status(
                workflow_id,
                "completed",
                message="Processing and matching completed successfully"
            )
        else:
            workflow_manager.update_workflow_status(
                workflow_id,
                "completed_with_discrepancies",
                message=f"Processing completed with {len(match_result.get('discrepancies', []))} matching discrepancies"
            )
        
        workflow_manager.update_workflow(
            workflow_id,
            processing_time=processing_time
        )
        
        # Show detailed results
        with result_container.expander("Processing Results", expanded=True):
            st.subheader("Extracted Data")
            st.json(result)
            
            st.subheader("Purchase Order Data")
            st.json(po_data)
            
            st.subheader("Goods Receipt Data")
            st.json(gr_data)
            
            st.subheader("Matching Results")
            st.json(match_result)
            
            st.metric("Processing Time", f"{processing_time:.2f} seconds")
        
    except Exception as e:
        error_message = str(e)
        if 'workflow_id' in locals():
            workflow_manager.update_workflow_status(
                workflow_id,
                "failed",
                message=f"Processing failed: {error_message}",
                error=error_message
            )
            
            # Show detailed error status
            status_container.error(f"""
            ❌ Error processing invoice:
            - Workflow ID: {workflow_id}
            - Error: {error_message}
            - Status: Failed
            """)
            
            # Show workflow details in expander
            with result_container.expander("Workflow Details", expanded=True):
                workflow_data = workflow_manager.get_workflow(workflow_id)
                if workflow_data:
                    st.json(workflow_data)
        else:
            status_container.error(f"❌ Error before workflow creation: {error_message}")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

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
                    st.markdown('<div class="nav-header"><h2>Navigation</h2></div>', unsafe_allow_html=True)
                    
                    # Create container for navigation items
                    nav_container = st.container()
                    
                    with nav_container:
                        pages = {
                            "Dashboard": show_dashboard,
                            "Invoice Processing": show_invoice_processing,
                            "Templates": show_templates
                        }
                        
                        selected_page = st.selectbox(
                            "",
                            list(pages.keys()),
                            key="navigation",
                            format_func=lambda x: f"📍 {x}"
                        )
                    
                    # Add spacing before user info
                    st.markdown("<br>" * 3, unsafe_allow_html=True)
                    
                    # User info and logout in a fixed footer
                    st.markdown(
                        f"""
                        <div class="nav-footer">
                            <div class="user-info">
                                👤 {st.session_state.user_info.get('username', 'Unknown')}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    # Logout button
                    if st.button("🚪 Logout", key="logout_btn"):
                        handle_logout()
                
                # Show selected page
                try:
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