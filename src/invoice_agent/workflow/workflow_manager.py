from typing import Dict, List, Optional
import uuid
from datetime import datetime, timedelta
import json
from pathlib import Path
import logging
from ..core.advanced_matcher import advanced_matcher
from ..config.settings import config
from ..audit.audit_logger import audit_logger

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(config.LOG_DIR / 'workflow.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WorkflowManager:
    def __init__(self):
        self.workflows_dir = config.BASE_DIR / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.workflows: Dict[str, Dict] = self._load_workflows()
        self.logger = logging.getLogger(__name__)
    
    def _load_workflows(self) -> Dict[str, Dict]:
        """Load existing workflows from disk"""
        workflows = {}
        for workflow_file in self.workflows_dir.glob("*.json"):
            try:
                with open(workflow_file, "r") as f:
                    workflow = json.load(f)
                    workflows[workflow["id"]] = workflow
            except Exception as e:
                self.logger.error(f"Error loading workflow {workflow_file}: {str(e)}")
                audit_logger.log_event(
                    "workflow_load_error",
                    {"file": str(workflow_file), "error": str(e)},
                    level=logging.ERROR
                )
        return workflows
    
    def _save_workflow(self, workflow_id: str):
        """Save workflow to disk"""
        try:
            workflow_path = self.workflows_dir / f"{workflow_id}.json"
            with open(workflow_path, "w") as f:
                json.dump(self.workflows[workflow_id], f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving workflow {workflow_id}: {str(e)}")
            audit_logger.log_event(
                "workflow_save_error",
                {"workflow_id": workflow_id, "error": str(e)},
                level=logging.ERROR
            )
    
    def create_workflow(
        self,
        template_id: str,
        document_path: str,
        user_id: Optional[str] = None
    ) -> str:
        """Create a new workflow"""
        workflow_id = str(uuid.uuid4())
        
        workflow = {
            "id": workflow_id,
            "template_id": template_id,
            "document_path": document_path,
            "status": "created",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "created_by": user_id,
            "extraction_results": None,
            "validation_results": None,
            "matching_results": None,
            "analysis_results": None,
            "processing_log": [],
            "retry_count": 0,
            "processing_time": None,
            "error": None
        }
        
        self.workflows[workflow_id] = workflow
        self._save_workflow(workflow_id)
        
        audit_logger.log_workflow_event(
            workflow_id,
            "created",
            {
                "template_id": template_id,
                "document_path": document_path
            },
            user_id
        )
        
        return workflow_id
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """Get workflow by ID"""
        workflow = self.workflows.get(workflow_id)
        if workflow:
            audit_logger.log_data_access(
                "workflow",
                workflow_id,
                "read",
                workflow.get("created_by")
            )
        return workflow
    
    def update_workflow_status(
        self,
        workflow_id: str,
        status: str,
        message: str = None,
        error: str = None
    ):
        """Update workflow status and add to processing log"""
        if workflow_id not in self.workflows:
            self.logger.error(f"Workflow not found: {workflow_id}")
            return
        
        workflow = self.workflows[workflow_id]
        previous_status = workflow["status"]
        workflow["status"] = status
        workflow["updated_at"] = datetime.now().isoformat()
        
        if error:
            workflow["error"] = error
        
        if message:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "message": message,
                "error": error
            }
            workflow["processing_log"].append(log_entry)
        
        self._save_workflow(workflow_id)
        
        audit_logger.log_workflow_event(
            workflow_id,
            "status_change",
            {
                "previous_status": previous_status,
                "new_status": status,
                "message": message,
                "error": error
            },
            workflow.get("created_by")
        )
    
    def process_workflow(
        self,
        workflow_id: str,
        extracted_data: Dict,
        user_id: Optional[str] = None
    ):
        """Process workflow with extracted data"""
        if workflow_id not in self.workflows:
            self.logger.error(f"Workflow not found: {workflow_id}")
            return
        
        workflow = self.workflows[workflow_id]
        start_time = datetime.now()
        
        try:
            # Check retry limit
            if workflow["retry_count"] >= config.processing.MAX_RETRIES:
                self.update_workflow_status(
                    workflow_id,
                    "failed",
                    "Maximum retry limit reached",
                    "MAX_RETRIES_EXCEEDED"
                )
                return
            
            workflow["retry_count"] += 1
            
            # Update status to processing
            self.update_workflow_status(
                workflow_id,
                "processing",
                "Starting data processing"
            )
            
            # Store extraction results
            workflow["extraction_results"] = extracted_data
            
            # Validate required fields
            missing_fields = []
            for field in config.validation.REQUIRED_FIELDS:
                if "." in field:
                    parent, child = field.split(".")
                    if parent not in extracted_data or child not in extracted_data[parent]:
                        missing_fields.append(field)
                elif field not in extracted_data:
                    missing_fields.append(field)
            
            if missing_fields:
                workflow["validation_results"] = {
                    "is_valid": False,
                    "missing_fields": missing_fields
                }
                self.update_workflow_status(
                    workflow_id,
                    "validation_failed",
                    f"Missing required fields: {', '.join(missing_fields)}"
                )
                return
            
            # Match with ERP data using advanced matcher
            matching_results = advanced_matcher.match_invoice_with_erp(extracted_data)
            workflow["matching_results"] = matching_results
            
            # Analyze results
            analysis_results = advanced_matcher.analyze_matching_results(
                extracted_data,
                matching_results
            )
            workflow["analysis_results"] = analysis_results
            
            # Update final status based on matching and analysis results
            if matching_results["match_status"] == "full_match":
                final_status = "matched"
                message = "All data matched successfully"
            elif matching_results["match_status"] == "partial_match":
                final_status = "partially_matched"
                message = f"Partial match with {len(matching_results['discrepancies'])} discrepancies"
            else:
                final_status = "match_failed"
                message = f"Matching failed with {len(matching_results['discrepancies'])} discrepancies"
            
            self.update_workflow_status(workflow_id, final_status, message)
            
            # Update processing time
            workflow["processing_time"] = (datetime.now() - start_time).total_seconds()
            self._save_workflow(workflow_id)
        
        except Exception as e:
            self.logger.error(f"Error processing workflow {workflow_id}: {str(e)}")
            self.update_workflow_status(
                workflow_id,
                "failed",
                f"Processing error: {str(e)}",
                str(e)
            )
            
            audit_logger.log_event(
                "workflow_processing_error",
                {
                    "workflow_id": workflow_id,
                    "error": str(e)
                },
                level=logging.ERROR,
                user_id=user_id
            )
    
    def get_workflow_history(self, workflow_id: str) -> List[Dict]:
        """Get workflow processing history"""
        if workflow_id not in self.workflows:
            self.logger.error(f"Workflow not found: {workflow_id}")
            return []
        
        return self.workflows[workflow_id]["processing_log"]
    
    def list_workflows(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """List workflows with filtering and pagination"""
        workflows = list(self.workflows.values())
        
        # Apply filters
        if status:
            workflows = [w for w in workflows if w["status"] == status]
        if user_id:
            workflows = [w for w in workflows if w.get("created_by") == user_id]
        
        # Sort by creation date
        workflows.sort(key=lambda w: w["created_at"], reverse=True)
        
        # Apply pagination
        return workflows[offset:offset + limit]
    
    def cleanup_old_workflows(self):
        """Clean up workflows older than retention period"""
        retention_days = config.security.DATA_RETENTION_DAYS
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        for workflow_id, workflow in list(self.workflows.items()):
            created_at = datetime.fromisoformat(workflow["created_at"])
            if created_at < cutoff_date:
                try:
                    # Delete workflow file
                    workflow_path = self.workflows_dir / f"{workflow_id}.json"
                    if workflow_path.exists():
                        workflow_path.unlink()
                    
                    # Remove from memory
                    del self.workflows[workflow_id]
                    
                    audit_logger.log_event(
                        "workflow_cleanup",
                        {"workflow_id": workflow_id},
                        level=logging.INFO
                    )
                
                except Exception as e:
                    self.logger.error(f"Error cleaning up workflow {workflow_id}: {str(e)}")
                    audit_logger.log_event(
                        "workflow_cleanup_error",
                        {
                            "workflow_id": workflow_id,
                            "error": str(e)
                        },
                        level=logging.ERROR
                    )
    
    def update_workflow(self, workflow_id: str, **kwargs):
        """Update workflow with additional data"""
        if workflow_id not in self.workflows:
            self.logger.error(f"Workflow not found: {workflow_id}")
            return
        
        workflow = self.workflows[workflow_id]
        updated = False
        
        # Update allowed fields
        allowed_fields = [
            "extraction_results",
            "validation_results",
            "matching_results",
            "analysis_results",
            "processing_time",
            "batch_results"
        ]
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                workflow[field] = value
                updated = True
        
        if updated:
            workflow["updated_at"] = datetime.now().isoformat()
            self._save_workflow(workflow_id)
            
            audit_logger.log_workflow_event(
                workflow_id,
                "updated",
                {
                    "updated_fields": list(kwargs.keys())
                },
                workflow.get("created_by")
            )

    def add_workflow_step(
        self,
        workflow_id: str,
        step_name: str,
        status: str,
        message: str = None,
        error: str = None
    ):
        """Add a step to the workflow processing log"""
        if workflow_id not in self.workflows:
            self.logger.error(f"Workflow not found: {workflow_id}")
            return
        
        workflow = self.workflows[workflow_id]
        
        step = {
            "timestamp": datetime.now().isoformat(),
            "step_name": step_name,
            "status": status,
            "message": message,
            "error": error
        }
        
        if "processing_log" not in workflow:
            workflow["processing_log"] = []
        
        workflow["processing_log"].append(step)
        workflow["updated_at"] = datetime.now().isoformat()
        
        if error:
            workflow["error"] = error
        
        self._save_workflow(workflow_id)
        
        audit_logger.log_workflow_event(
            workflow_id,
            "step_added",
            {
                "step_name": step_name,
                "status": status,
                "message": message
            },
            workflow.get("created_by")
        )

    def get_workflows(
        self,
        search_term: str = None,
        status_filter: List[str] = None,
        date_range: tuple = None
    ) -> List[Dict]:
        """Get workflows based on search and filter criteria"""
        filtered_workflows = []
        
        for workflow_id, workflow in self.workflows.items():
            # Search term filter
            if search_term:
                search_term = search_term.lower()
                if not (search_term in workflow_id.lower() or 
                       search_term in workflow['document_path'].lower()):
                    continue
            
            # Status filter
            if status_filter and workflow['status'] not in status_filter:
                continue
            
            # Date range filter
            if date_range:
                start_date, end_date = date_range
                workflow_date = datetime.fromisoformat(workflow['created_at']).date()
                if not (start_date <= workflow_date <= end_date):
                    continue
            
            filtered_workflows.append(workflow)
        
        # Sort by created_at in descending order (newest first)
        filtered_workflows.sort(
            key=lambda x: datetime.fromisoformat(x['created_at']),
            reverse=True
        )
        
        return filtered_workflows

    def get_recent_workflows(self, limit: int = 10) -> List[Dict]:
        """Get the most recent workflows"""
        all_workflows = list(self.workflows.values())
        all_workflows.sort(
            key=lambda x: datetime.fromisoformat(x['created_at']),
            reverse=True
        )
        return all_workflows[:limit] 