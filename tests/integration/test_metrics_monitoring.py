import pytest
import time
from datetime import datetime, timedelta
from pathlib import Path
import redis
from invoice_agent.metrics.metrics_manager import MetricsManager
from invoice_agent.workflow.workflow_manager import WorkflowManager
from invoice_agent.template.template_manager import TemplateManager

@pytest.fixture
def redis_client():
    client = redis.Redis(host='localhost', port=6379, db=0)
    yield client
    client.flushdb()  # Clean up after tests
    client.close()

@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path

@pytest.fixture
def metrics_manager(temp_dir, redis_client):
    MetricsManager.metrics_dir = temp_dir
    manager = MetricsManager(redis_client=redis_client)
    return manager

@pytest.fixture
def workflow_manager(temp_dir):
    WorkflowManager.workflows_dir = temp_dir / "workflows"
    return WorkflowManager()

@pytest.fixture
def template_manager(temp_dir):
    TemplateManager.templates_dir = temp_dir / "templates"
    return TemplateManager()

class TestMetricsMonitoring:
    def test_workflow_metrics_collection(self, metrics_manager, workflow_manager, template_manager):
        """Test metrics collection during workflow processing"""
        # Create a template
        template_id = template_manager.create_template(
            name="Test Template",
            fields=["invoice_number", "amount", "date"]
        )
        
        # Start workflows
        workflow_ids = []
        for i in range(5):
            workflow_id = workflow_manager.create_workflow(
                template_id=template_id,
                document_path=f"test_doc_{i}.pdf"
            )
            workflow_ids.append(workflow_id)
            
            # Simulate processing time
            time.sleep(0.1)
            
            if i < 3:
                # Mark as success
                workflow_manager.update_workflow_status(
                    workflow_id=workflow_id,
                    status="completed",
                    extracted_data={"invoice_number": f"INV-{i}"}
                )
                metrics_manager.record_success()
            else:
                # Mark as failure
                workflow_manager.update_workflow_status(
                    workflow_id=workflow_id,
                    status="failed",
                    error="Test error"
                )
                metrics_manager.record_failure()
            
            metrics_manager.record_processing_time(0.1)
        
        # Verify metrics
        metrics = metrics_manager.get_current_metrics()
        assert metrics["success_rate"] == 0.6  # 3 successes out of 5
        assert metrics["processed_today"] == 5
        assert metrics["processing_queue"] == 0
        assert 0.09 <= metrics["avg_processing_time"] <= 0.11
        
    def test_historical_metrics_collection(self, metrics_manager, redis_client):
        """Test collection and retrieval of historical metrics"""
        # Simulate metrics for past 5 days
        today = datetime.now()
        
        for days_ago in range(5):
            date = today - timedelta(days=days_ago)
            date_str = date.strftime("%Y-%m-%d")
            
            # Simulate different success rates and processing times
            success_rate = 0.7 + (days_ago * 0.05)  # Increasing success rate trend
            avg_time = 0.15 - (days_ago * 0.01)  # Decreasing processing time trend
            
            metrics = {
                "success_rate": success_rate,
                "processed_today": 10 + days_ago,
                "processing_queue": 0,
                "avg_processing_time": avg_time
            }
            
            # Store metrics in Redis
            redis_client.hset(f"metrics:{date_str}", mapping=metrics)
        
        # Verify historical metrics
        historical_metrics = metrics_manager.get_historical_metrics(days=5)
        assert len(historical_metrics) == 5
        
        # Verify trends
        success_rates = [m["success_rate"] for m in historical_metrics]
        processing_times = [m["avg_processing_time"] for m in historical_metrics]
        
        # Success rates should be increasing (reverse chronological order)
        assert all(success_rates[i] <= success_rates[i+1] for i in range(len(success_rates)-1))
        
        # Processing times should be decreasing (reverse chronological order)
        assert all(processing_times[i] >= processing_times[i+1] for i in range(len(processing_times)-1))
    
    def test_prometheus_metrics_collection(self, metrics_manager):
        """Test collection of Prometheus metrics"""
        # Record some test metrics
        for _ in range(3):
            metrics_manager.record_success()
        for _ in range(2):
            metrics_manager.record_failure()
        
        metrics_manager.record_processing_time(0.1)
        metrics_manager.record_processing_time(0.2)
        metrics_manager.record_processing_time(0.3)
        
        # Get Prometheus metrics
        prometheus_metrics = metrics_manager.get_prometheus_metrics()
        
        # Verify counters
        assert prometheus_metrics["invoice_processing_total"] == 5
        assert prometheus_metrics["invoice_processing_success"] == 3
        assert prometheus_metrics["invoice_processing_failure"] == 2
        
        # Verify histogram
        processing_times = prometheus_metrics["processing_time_histogram"]
        assert len(processing_times) > 0
        assert 0.1 <= processing_times["avg"] <= 0.3
        
        # Verify gauge
        assert prometheus_metrics["processing_queue_size"] >= 0 