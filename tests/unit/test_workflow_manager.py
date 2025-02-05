import pytest
from invoice_agent.workflow.workflow_manager import WorkflowManager, WorkflowStatus
from pathlib import Path
from datetime import datetime

def test_create_workflow(sample_workflow, temp_dir):
    """Test workflow creation"""
    manager = WorkflowManager()
    manager.workflow_dir = temp_dir
    
    # Test workflow creation
    workflow_id = manager.create_workflow(
        sample_workflow["id"],
        sample_workflow["type"]
    )
    
    assert workflow_id == sample_workflow["id"]
    
    # Verify workflow was created
    workflow = manager.get_workflow(workflow_id)
    assert workflow is not None
    assert workflow["id"] == sample_workflow["id"]
    assert workflow["type"] == sample_workflow["type"]
    assert workflow["status"] == WorkflowStatus.PENDING.value

def test_update_workflow_status(sample_workflow, temp_dir):
    """Test workflow status update"""
    manager = WorkflowManager()
    manager.workflow_dir = temp_dir
    
    # Create workflow first
    workflow_id = manager.create_workflow(
        sample_workflow["id"],
        sample_workflow["type"]
    )
    
    # Test status update
    assert manager.update_workflow_status(workflow_id, WorkflowStatus.PROCESSING) == True
    
    # Verify status was updated
    workflow = manager.get_workflow(workflow_id)
    assert workflow["status"] == WorkflowStatus.PROCESSING.value
    
    # Test update non-existent workflow
    assert manager.update_workflow_status("non_existent", WorkflowStatus.COMPLETED) == False

def test_add_workflow_step(sample_workflow, temp_dir):
    """Test adding workflow steps"""
    manager = WorkflowManager()
    manager.workflow_dir = temp_dir
    
    # Create workflow first
    workflow_id = manager.create_workflow(
        sample_workflow["id"],
        sample_workflow["type"]
    )
    
    # Add steps
    steps = [
        ("Step 1", WorkflowStatus.COMPLETED),
        ("Step 2", WorkflowStatus.PROCESSING),
        ("Step 3", WorkflowStatus.FAILED)
    ]
    
    for step_name, status in steps:
        assert manager.add_workflow_step(workflow_id, step_name, status) == True
    
    # Verify steps were added
    workflow = manager.get_workflow(workflow_id)
    assert len(workflow["steps"]) == len(steps)
    for i, (step_name, status) in enumerate(steps):
        assert workflow["steps"][i]["name"] == step_name
        assert workflow["steps"][i]["status"] == status.value
    
    # Test add step to non-existent workflow
    assert manager.add_workflow_step("non_existent", "Step", WorkflowStatus.COMPLETED) == False

def test_list_workflows(sample_workflow, temp_dir):
    """Test workflow listing"""
    manager = WorkflowManager()
    manager.workflow_dir = temp_dir
    
    # Create workflows with different statuses
    workflows = [
        {"id": "workflow1", "type": "type1", "status": WorkflowStatus.PENDING},
        {"id": "workflow2", "type": "type1", "status": WorkflowStatus.PROCESSING},
        {"id": "workflow3", "type": "type2", "status": WorkflowStatus.COMPLETED},
        {"id": "workflow4", "type": "type2", "status": WorkflowStatus.FAILED}
    ]
    
    for wf in workflows:
        manager.create_workflow(wf["id"], wf["type"])
        manager.update_workflow_status(wf["id"], wf["status"])
    
    # Test listing all workflows
    all_workflows = manager.list_workflows()
    assert len(all_workflows) == len(workflows)
    
    # Test filtering by status
    completed_workflows = manager.list_workflows(status=WorkflowStatus.COMPLETED)
    assert len(completed_workflows) == 1
    assert completed_workflows[0]["id"] == "workflow3"
    
    failed_workflows = manager.list_workflows(status=WorkflowStatus.FAILED)
    assert len(failed_workflows) == 1
    assert failed_workflows[0]["id"] == "workflow4" 