import streamlit as st
import httpx
import time
from datetime import datetime, timedelta
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from streamlit_option_menu import option_menu
from streamlit_extras.metric_cards import style_metric_cards
import json

# Configure the app
st.set_page_config(
    page_title="Invoice Processing System",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'mailto:support@example.com',
        'Report a bug': 'mailto:bugs@example.com',
        'About': 'Invoice Processing System v1.0'
    }
)

# Apply dark theme
st.markdown("""
    <style>
        .stApp {
            background-color: #0E1117;
            color: #FAFAFA;
        }
        .stButton>button {
            background-color: #262730;
            color: #FAFAFA;
        }
        .stTextInput>div>div>input {
            background-color: #262730;
            color: #FAFAFA;
        }
        .stSelectbox>div>div>select {
            background-color: #262730;
            color: #FAFAFA;
        }
    </style>
""", unsafe_allow_html=True)

# Constants
API_BASE_URL = "http://localhost:8000/api/v1"

# Authentication
def check_auth():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("Invoice Processing System")
            st.markdown("---")
            st.subheader("Login")
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")
                
                if submitted:
                    # Here you would normally verify credentials
                    # For demo, we'll accept any non-empty input
                    if email and password:
                        st.session_state.authenticated = True
                        st.session_state.user = email
                        st.experimental_rerun()
                    else:
                        st.error("Invalid credentials")
            
            # Add Google Sign-in button
            st.markdown("---")
            if st.button("Sign in with Google"):
                # Here you would implement Google OAuth
                st.session_state.authenticated = True
                st.session_state.user = "google_user@example.com"
                st.experimental_rerun()
        
        st.stop()

def upload_invoice(file):
    """Upload an invoice file to the API"""
    try:
        files = {"file": (file.name, file, "application/pdf")}
        with httpx.Client() as client:
            response = client.post(f"{API_BASE_URL}/invoices/upload", files=files)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        st.error(f"Error uploading file: {str(e)}")
        return None

def get_invoice_list():
    """Get list of all invoices"""
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_BASE_URL}/invoices")
            response.raise_for_status()
            return response.json()["invoices"]
    except httpx.HTTPError as e:
        st.error(f"Error fetching invoices: {str(e)}")
        return []

def get_status_color(status):
    """Get color for status badge"""
    colors = {
        "PENDING": "orange",
        "PROCESSING": "blue",
        "COMPLETED": "green",
        "FAILED": "red"
    }
    return colors.get(status, "gray")

def show_dashboard():
    """Show the dashboard page"""
    st.title("Dashboard")
    
    # Get invoice data
    invoices = get_invoice_list()
    if not invoices:
        st.info("No data available")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(invoices)
    
    # Calculate metrics
    total_invoices = len(df)
    completed = len(df[df['status'] == 'COMPLETED'])
    failed = len(df[df['status'] == 'FAILED'])
    success_rate = (completed / total_invoices * 100) if total_invoices > 0 else 0
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Invoices", total_invoices)
    with col2:
        st.metric("Completed", completed)
    with col3:
        st.metric("Failed", failed)
    with col4:
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    style_metric_cards()
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Status distribution
        status_counts = df['status'].value_counts()
        fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Invoice Status Distribution",
            color_discrete_map={
                "COMPLETED": "green",
                "FAILED": "red",
                "PENDING": "orange",
                "PROCESSING": "blue"
            }
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Timeline
        df['upload_time'] = pd.to_datetime(df['upload_time'])
        daily_counts = df.resample('D', on='upload_time').size()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily_counts.index,
            y=daily_counts.values,
            mode='lines+markers',
            name='Invoices'
        ))
        fig.update_layout(
            title="Daily Invoice Volume",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            xaxis_title="Date",
            yaxis_title="Number of Invoices"
        )
        st.plotly_chart(fig, use_container_width=True)

def show_upload():
    """Show the upload page"""
    st.title("Upload Invoice")
    
    # Template selection
    templates = [
        "Standard Invoice",
        "Tech Services Invoice",
        "Consulting Invoice"
    ]
    selected_template = st.selectbox("Select Template", templates)
    
    # Display template info
    if selected_template:
        st.info(f"Using template: {selected_template}")
        st.markdown("### Required Fields")
        st.markdown("""
        - Invoice Number
        - Date
        - Vendor Information
        - Line Items
        - Total Amount
        """)
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        help="Upload a PDF invoice file"
    )
    
    if uploaded_file:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Process Invoice"):
                with st.spinner("Uploading invoice..."):
                    result = upload_invoice(uploaded_file)
                    if result:
                        st.success(f"Invoice uploaded successfully! Workflow ID: {result['workflow_id']}")
        with col2:
            if st.button("Preview"):
                st.info("Preview functionality coming soon")

def show_invoices():
    """Show the invoices page"""
    st.title("Invoices")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.multiselect(
            "Status",
            ["PENDING", "PROCESSING", "COMPLETED", "FAILED"],
            default=["PENDING", "PROCESSING"]
        )
    with col2:
        date_range = st.date_input(
            "Date Range",
            value=(datetime.now() - timedelta(days=30), datetime.now())
        )
    with col3:
        search = st.text_input("Search", placeholder="Search by filename or ID...")
    
    # Get and filter invoices
    invoices = get_invoice_list()
    if not invoices:
        st.info("No invoices found")
        return
    
    # Display invoices
    for invoice in invoices:
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 1, 2, 3])
            
            with col1:
                st.write(f"📄 {invoice['filename']}")
            
            with col2:
                status_color = get_status_color(invoice['status'])
                st.markdown(
                    f"<span style='background-color: {status_color}; padding: 0.2rem 0.6rem; "
                    f"border-radius: 1rem; color: white; font-size: 0.8rem'>{invoice['status']}</span>",
                    unsafe_allow_html=True
                )
            
            with col3:
                upload_time = datetime.fromisoformat(invoice['upload_time'])
                st.write(f"📅 {upload_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            with col4:
                if invoice.get('error_message'):
                    st.write(f"❌ {invoice['error_message']}")
            
            st.markdown("---")

def show_templates():
    """Show the templates page"""
    st.title("Templates")
    
    # Template management
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Available Templates")
        templates = [
            {
                "name": "Standard Invoice",
                "fields": ["invoice_number", "date", "vendor", "items", "total"],
                "created": "2024-02-01"
            },
            {
                "name": "Tech Services",
                "fields": ["invoice_number", "date", "vendor", "service_type", "hours", "rate", "total"],
                "created": "2024-02-01"
            }
        ]
        
        for template in templates:
            with st.expander(template["name"]):
                st.write(f"Created: {template['created']}")
                st.write("Fields:")
                for field in template["fields"]:
                    st.write(f"- {field}")
                col1, col2 = st.columns(2)
                with col1:
                    st.button("Edit", key=f"edit_{template['name']}")
                with col2:
                    st.button("Delete", key=f"delete_{template['name']}")
    
    with col2:
        st.subheader("Add Template")
        with st.form("new_template"):
            st.text_input("Template Name")
            st.text_area("Fields (one per line)")
            st.form_submit_button("Create Template")

def main():
    # Check authentication
    check_auth()
    
    # Sidebar
    with st.sidebar:
        st.image("https://via.placeholder.com/150", width=150)
        st.write(f"Welcome, {st.session_state.user}")
        st.markdown("---")
        
        selected = option_menu(
            "Main Menu",
            ["Dashboard", "Upload", "Invoices", "Templates"],
            icons=['house', 'cloud-upload', 'file-text', 'gear'],
            menu_icon="cast",
            default_index=0,
        )
        
        st.markdown("---")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.experimental_rerun()
    
    # Main content
    if selected == "Dashboard":
        show_dashboard()
    elif selected == "Upload":
        show_upload()
    elif selected == "Invoices":
        show_invoices()
    elif selected == "Templates":
        show_templates()

if __name__ == "__main__":
    main() 