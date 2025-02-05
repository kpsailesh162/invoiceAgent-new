import streamlit as st
import extra_streamlit_components as stx
from datetime import datetime
from pathlib import Path
import json
import uuid
import pandas as pd

from invoice_agent.workflow.workflow_manager import WorkflowManager
from invoice_agent.template.template_manager import TemplateManager
from invoice_agent.metrics.metrics_manager import MetricsManager

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'cookie_manager' not in st.session_state:
    st.session_state.cookie_manager = None

def get_cookie_manager():
    """Get or create cookie manager"""
    if st.session_state.cookie_manager is None:
        cookie_manager = stx.CookieManager(key=f"cookie_manager_{str(uuid.uuid4())}")
        st.session_state.cookie_manager = cookie_manager
    return st.session_state.cookie_manager

def init_managers():
    """Initialize all managers"""
    workflow_manager = WorkflowManager()
    template_manager = TemplateManager()
    metrics_manager = MetricsManager()
    return workflow_manager, template_manager, metrics_manager

def handle_google_auth():
    """Handle Google OAuth authentication"""
    cookie_manager = get_cookie_manager()
    
    # Check if already authenticated
    auth_cookie = cookie_manager.get(cookie="auth_token")
    if auth_cookie:
        st.session_state.authenticated = True
        st.session_state.user_info = json.loads(auth_cookie)
        return
    
    # Add Google Sign-in button
    if st.button("Sign in with Google", key="google_signin"):
        # Simulate successful authentication
        user_info = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "name": "Test User",
            "auth_time": datetime.now().isoformat()
        }
        cookie_manager.set("auth_token", json.dumps(user_info))
        st.session_state.authenticated = True
        st.session_state.user_info = user_info
        st.rerun()

def show_auth_page():
    """Show authentication page"""
    st.title("Invoice Processing Agent")
    st.write("Please sign in to continue")
    
    handle_google_auth()

def show_processing_results(workflow_id: str, workflow_manager: WorkflowManager):
    """Display processing results for a workflow"""
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        st.error("Workflow not found")
        return
    
    st.subheader("Processing Results")
    
    # Status indicator
    status_color = {
        "pending": "blue",
        "created": "blue",
        "extracting": "blue",
        "validating": "blue",
        "matching": "blue",
        "matched": "green",
        "partially_matched": "orange",
        "match_failed": "red",
        "validation_failed": "red",
        "failed": "red"
    }
    
    st.markdown(
        f"**Status:** :{status_color[workflow.get('status', 'pending')]}[{workflow.get('status', 'pending').replace('_', ' ').title()}]"
    )
    
    # Show extraction results if available
    if workflow.get("extraction_results"):
        with st.expander("Extracted Data"):
            st.json(workflow["extraction_results"])
            
            # Show confidence scores if available
            if "confidence_scores" in workflow["extraction_results"]:
                st.subheader("Confidence Scores")
                for field, score in workflow["extraction_results"]["confidence_scores"].items():
                    color = "green" if score >= 0.90 else "orange" if score >= 0.85 else "red"
                    st.markdown(f"- {field}: :{color}[{score:.2%}]")
    
    # Show validation results if available
    if workflow.get("validation_results"):
        with st.expander("Validation Results"):
            if not workflow["validation_results"].get("is_valid", True):
                st.error("Validation Failed")
            
            if workflow["validation_results"].get("missing_fields"):
                st.write("Missing Fields:")
                for field in workflow["validation_results"]["missing_fields"]:
                    st.markdown(f"- {field}")
            
            if workflow["validation_results"].get("low_confidence_fields"):
                st.write("Low Confidence Fields:")
                for field in workflow["validation_results"]["low_confidence_fields"]:
                    st.markdown(f"- {field['field']}: {field['confidence']:.2%}")
            
            if workflow["validation_results"].get("format_issues"):
                st.write("Format Issues:")
                for issue in workflow["validation_results"]["format_issues"]:
                    st.markdown(f"- {issue}")
    
    # Show matching results if available
    if workflow.get("matching_results"):
        with st.expander("3-Way Matching Results"):
            match_status = workflow["matching_results"].get("match_status", "unknown")
            if match_status == "full_match":
                st.success("Full Match - All details match with PO and goods receipt")
            elif match_status == "partial_match":
                st.warning("Partial Match - Some discrepancies found")
            else:
                st.error("Match Failed - Significant discrepancies found")
            
            if workflow["matching_results"].get("discrepancies"):
                st.write("Discrepancies Found:")
                for discrepancy in workflow["matching_results"]["discrepancies"]:
                    st.markdown(f"- {discrepancy}")
            
            # Show matching details
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("PO Match", "✓" if workflow["matching_results"].get("po_match", False) else "✗")
            with col2:
                st.metric("Receipt Match", "✓" if workflow["matching_results"].get("receipt_match", False) else "✗")
            with col3:
                st.metric("Amount Match", "✓" if workflow["matching_results"].get("amount_match", False) else "✗")

def process_single_invoice(uploaded_file, template, workflow_manager):
    """Process a single invoice file"""
    if uploaded_file is None:
        return
    
    # Save uploaded file
    save_path = Path("uploads") / uploaded_file.name
    save_path.parent.mkdir(exist_ok=True)
    save_path.write_bytes(uploaded_file.getvalue())
    
    # Create workflow
    workflow_id = workflow_manager.create_workflow(
        template_id=template["id"],
        document_path=str(save_path)
    )
    
    st.success(f"Invoice processing started! Workflow ID: {workflow_id}")
    
    # Show processing results
    show_processing_results(workflow_id, workflow_manager)
    
    return workflow_id

def process_batch_invoices(uploaded_files, template, workflow_manager):
    """Process multiple invoice files"""
    if not uploaded_files:
        return
    
    workflow_ids = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, uploaded_file in enumerate(uploaded_files):
        # Save uploaded file
        save_path = Path("uploads") / uploaded_file.name
        save_path.parent.mkdir(exist_ok=True)
        save_path.write_bytes(uploaded_file.getvalue())
        
        # Create workflow
        workflow_id = workflow_manager.create_workflow(
            template_id=template["id"],
            document_path=str(save_path)
        )
        workflow_ids.append(workflow_id)
        
        # Update progress
        progress = (i + 1) / len(uploaded_files)
        progress_bar.progress(progress)
        status_text.text(f"Processing {i + 1} of {len(uploaded_files)} invoices...")
        
        # Show processing results for each invoice
        show_processing_results(workflow_id, workflow_manager)
    
    status_text.text(f"Successfully processed {len(workflow_ids)} invoices!")
    return workflow_ids

def show_dashboard(workflow_manager, template_manager, metrics_manager):
    """Show main dashboard"""
    st.title("Invoice Processing Dashboard")
    
    # User info
    st.sidebar.write(f"Welcome, {st.session_state.user_info['name']}")
    if st.sidebar.button("Sign Out", key="signout_button"):
        cookie_manager = get_cookie_manager()
        cookie_manager.delete("auth_token")
        st.session_state.authenticated = False
        st.session_state.user_info = None
        st.rerun()
    
    # Tabs for different sections
    tab1, tab2, tab3 = st.tabs(["Process Invoice", "Templates", "Metrics"])
    
    with tab1:
        st.header("Process Invoice")
        
        # Upload mode selection
        upload_mode = st.radio(
            "Select Upload Mode",
            ["Single Invoice", "Batch Upload"],
            key="upload_mode"
        )
        
        # Template selection
        templates = template_manager.list_templates()
        template_names = [t["name"] for t in templates]
        selected_template = st.selectbox(
            "Select Template",
            template_names,
            key="template_selector"
        )
        
        if upload_mode == "Single Invoice":
            # Single file upload
            st.subheader("Upload Single Invoice")
            uploaded_file = st.file_uploader(
                "Upload Invoice",
                type=["pdf", "csv", "xlsx", "docx"],
                key="single_invoice_uploader",
                help="Supported formats: PDF, CSV, Excel, Word"
            )
            
            if uploaded_file and selected_template:
                if st.button("Process Invoice", key="process_single_invoice_button"):
                    template = next(t for t in templates if t["name"] == selected_template)
                    process_single_invoice(uploaded_file, template, workflow_manager)
        
        else:  # Batch Upload
            # Multiple file upload
            st.subheader("Upload Multiple Invoices")
            uploaded_files = st.file_uploader(
                "Upload Invoices",
                type=["pdf", "csv", "xlsx", "docx"],
                accept_multiple_files=True,
                key="batch_invoice_uploader",
                help="Supported formats: PDF, CSV, Excel, Word"
            )
            
            if uploaded_files and selected_template:
                if st.button("Process Batch", key="process_batch_button"):
                    template = next(t for t in templates if t["name"] == selected_template)
                    process_batch_invoices(uploaded_files, template, workflow_manager)
        
        # Show processing history
        st.subheader("Recent Processing History")
        history_container = st.container()
        with history_container:
            # TODO: Implement processing history display
            st.info("Processing history will be displayed here")
    
    with tab2:
        st.header("Invoice Templates")
        
        # Create new template
        with st.expander("Create New Template"):
            template_name = st.text_input("Template Name", key="new_template_name")
            fields = st.text_area("Fields (one per line)", key="new_template_fields")
            
            if st.button("Create Template", key="create_template_button"):
                field_list = [f.strip() for f in fields.split("\n") if f.strip()]
                template_id = template_manager.create_template(template_name, field_list)
                st.success(f"Template created! ID: {template_id}")
        
        # List existing templates
        st.subheader("Existing Templates")
        for i, template in enumerate(templates):
            with st.expander(template["name"]):
                st.write("Fields:")
                for field in template["fields"]:
                    st.write(f"- {field}")
                st.write(f"Created: {template['created_at']}")
                
                # Add edit and delete buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Edit Template", key=f"edit_btn_{template['id']}"):
                        st.session_state.editing_template = template
                        st.session_state.editing_template_fields = "\n".join(template["fields"])
                
                with col2:
                    if st.button("Delete Template", key=f"delete_btn_{template['id']}"):
                        if template_manager.delete_template(template["id"]):
                            st.success(f"Template '{template['name']}' deleted successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to delete template")
        
        # Edit template form
        if hasattr(st.session_state, 'editing_template') and st.session_state.editing_template:
            st.subheader(f"Edit Template: {st.session_state.editing_template['name']}")
            
            new_name = st.text_input(
                "Template Name",
                value=st.session_state.editing_template["name"],
                key="edit_template_name"
            )
            
            new_fields = st.text_area(
                "Fields (one per line)",
                value=st.session_state.editing_template_fields,
                key="edit_template_fields"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Changes", key="save_template_changes"):
                    field_list = [f.strip() for f in new_fields.split("\n") if f.strip()]
                    if template_manager.update_template(
                        st.session_state.editing_template["id"],
                        new_name,
                        field_list
                    ):
                        st.success("Template updated successfully!")
                        st.session_state.editing_template = None
                        st.session_state.editing_template_fields = None
                        st.rerun()
                    else:
                        st.error("Failed to update template")
            
            with col2:
                if st.button("Cancel Edit", key="cancel_template_edit"):
                    st.session_state.editing_template = None
                    st.session_state.editing_template_fields = None
                    st.rerun()
    
    with tab3:
        st.header("Processing Metrics")
        
        # Get current metrics
        metrics = metrics_manager.get_current_metrics()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Success Rate", f"{metrics['success_rate']*100:.1f}%")
        with col2:
            st.metric("Processed Today", metrics["processed_today"])
        with col3:
            st.metric("Queue Size", metrics["processing_queue"])
        with col4:
            st.metric("Avg. Processing Time", f"{metrics['avg_processing_time']:.2f}s")
        
        # Historical metrics
        st.subheader("Historical Performance")
        historical = metrics_manager.get_historical_metrics(days=7)
        if historical:
            dates = [m["date"] for m in historical]
            success_rates = [m["success_rate"] * 100 for m in historical]
            st.line_chart({"Success Rate (%)": success_rates}, x=dates, key="historical_chart")

def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="Invoice Processing Agent",
        page_icon="📄",
        layout="wide"
    )
    
    if not st.session_state.authenticated:
        show_auth_page()
    else:
        workflow_manager, template_manager, metrics_manager = init_managers()
        show_dashboard(workflow_manager, template_manager, metrics_manager)

if __name__ == "__main__":
    main() 