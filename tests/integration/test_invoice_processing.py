import pytest
from pathlib import Path
import json
from datetime import datetime
from invoice_agent.workflow.workflow_manager import WorkflowManager, WorkflowStatus
from invoice_agent.templates.template_manager import TemplateManager
from invoice_agent.monitoring.metrics import MetricsManager

class TestInvoiceProcessingWorkflow:
    def test_end_to_end_invoice_processing(self, sample_invoice, sample_template, temp_dir):
        """Test end-to-end invoice processing workflow"""
        # Setup components with test directory
        WorkflowManager.workflow_dir = temp_dir / "workflows"
        TemplateManager.template_dir = temp_dir / "templates"
        MetricsManager.metrics_dir = temp_dir / "metrics"
        
        workflow_manager = WorkflowManager()
        template_manager = TemplateManager()
        metrics_manager = MetricsManager()
        
        # Create template
        template_manager.create_template(sample_template["name"], sample_template["fields"])
        
        # Start workflow
        workflow_id = workflow_manager.create_workflow(
            invoice_id=sample_invoice["invoice_number"],
            workflow_type="invoice_processing"
        )
        
        # Verify workflow created
        workflow = workflow_manager.get_workflow(workflow_id)
        assert workflow is not None
        assert workflow["status"] == WorkflowStatus.PENDING.value
        
        # Update workflow status to processing
        workflow_manager.update_workflow_status(workflow_id, WorkflowStatus.PROCESSING)
        workflow_manager.add_workflow_step(workflow_id, "Template Validation", WorkflowStatus.COMPLETED)
        
        # Update metrics
        metrics_manager.update_metrics("processed_today", 1)
        metrics_manager.update_metrics("success_rate", 100.0)
        
        # Complete workflow
        workflow_manager.update_workflow_status(workflow_id, WorkflowStatus.COMPLETED)
        
        # Verify final state
        final_workflow = workflow_manager.get_workflow(workflow_id)
        assert final_workflow["status"] == WorkflowStatus.COMPLETED.value
        assert len(final_workflow["steps"]) == 1
        
        metrics = metrics_manager.get_metrics()
        assert metrics["processed_today"] == 1
        assert metrics["success_rate"] == 100.0
    
    def test_failed_invoice_processing(self, sample_invoice, sample_template, temp_dir):
        """Test invoice processing workflow with failure"""
        # Setup components with test directory
        WorkflowManager.workflow_dir = temp_dir / "workflows"
        TemplateManager.template_dir = temp_dir / "templates"
        MetricsManager.metrics_dir = temp_dir / "metrics"
        
        workflow_manager = WorkflowManager()
        template_manager = TemplateManager()
        metrics_manager = MetricsManager()
        
        # Create template
        template_manager.create_template(sample_template["name"], sample_template["fields"])
        
        # Start workflow
        workflow_id = workflow_manager.create_workflow(
            invoice_id=sample_invoice["invoice_number"],
            workflow_type="invoice_processing"
        )
        
        # Simulate processing failure
        workflow_manager.update_workflow_status(workflow_id, WorkflowStatus.PROCESSING)
        workflow_manager.add_workflow_step(workflow_id, "Template Validation", WorkflowStatus.FAILED)
        workflow_manager.update_workflow_status(workflow_id, WorkflowStatus.FAILED)
        
        # Update metrics
        metrics_manager.update_metrics("processed_today", 1)
        metrics_manager.update_metrics("success_rate", 0.0)
        
        # Verify final state
        final_workflow = workflow_manager.get_workflow(workflow_id)
        assert final_workflow["status"] == WorkflowStatus.FAILED.value
        assert len(final_workflow["steps"]) == 1
        assert final_workflow["steps"][0]["status"] == WorkflowStatus.FAILED.value
        
        metrics = metrics_manager.get_metrics()
        assert metrics["processed_today"] == 1
        assert metrics["success_rate"] == 0.0
    
    def test_batch_invoice_processing(self, sample_invoice, sample_template, temp_dir):
        """Test batch invoice processing workflow"""
        # Setup components with test directory
        WorkflowManager.workflow_dir = temp_dir / "workflows"
        TemplateManager.template_dir = temp_dir / "templates"
        MetricsManager.metrics_dir = temp_dir / "metrics"
        
        workflow_manager = WorkflowManager()
        template_manager = TemplateManager()
        metrics_manager = MetricsManager()
        
        # Create template
        template_manager.create_template(sample_template["name"], sample_template["fields"])
        
        # Create batch workflow
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        workflow_id = workflow_manager.create_workflow(
            invoice_id=batch_id,
            workflow_type="batch_processing"
        )
        
        # Process multiple invoices
        num_invoices = 3
        successful = 0
        
        for i in range(num_invoices):
            invoice = sample_invoice.copy()
            invoice["invoice_number"] = f"INV-{i+1}"
            
            # Simulate some failures
            status = WorkflowStatus.COMPLETED if i != 1 else WorkflowStatus.FAILED
            workflow_manager.add_workflow_step(
                workflow_id,
                f"Process Invoice {invoice['invoice_number']}",
                status
            )
            
            if status == WorkflowStatus.COMPLETED:
                successful += 1
        
        # Update metrics
        success_rate = (successful / num_invoices) * 100
        metrics_manager.update_metrics("processed_today", num_invoices)
        metrics_manager.update_metrics("success_rate", success_rate)
        
        # Complete batch workflow
        workflow_manager.update_workflow_status(workflow_id, WorkflowStatus.COMPLETED)
        
        # Verify final state
        final_workflow = workflow_manager.get_workflow(workflow_id)
        assert final_workflow["status"] == WorkflowStatus.COMPLETED.value
        assert len(final_workflow["steps"]) == num_invoices
        
        metrics = metrics_manager.get_metrics()
        assert metrics["processed_today"] == num_invoices
        assert metrics["success_rate"] == success_rate 