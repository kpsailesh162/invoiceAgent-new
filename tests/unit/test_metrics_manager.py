import pytest
from invoice_agent.monitoring.metrics import MetricsManager
from pathlib import Path
from datetime import datetime, timedelta
import json

def test_update_metrics(sample_metrics, temp_dir):
    """Test metrics update"""
    manager = MetricsManager()
    manager.metrics_dir = temp_dir
    
    # Test updating each metric
    for metric_name, value in sample_metrics.items():
        manager.update_metrics(metric_name, value)
        assert manager.current_metrics[metric_name] == value
    
    # Test updating invalid metric
    original_metrics = manager.current_metrics.copy()
    manager.update_metrics("invalid_metric", 100)
    assert manager.current_metrics == original_metrics

def test_get_metrics(sample_metrics, temp_dir):
    """Test getting current metrics"""
    manager = MetricsManager()
    manager.metrics_dir = temp_dir
    
    # Set initial metrics
    for metric_name, value in sample_metrics.items():
        manager.update_metrics(metric_name, value)
    
    # Test getting metrics
    current_metrics = manager.get_metrics()
    assert current_metrics == sample_metrics

def test_get_historical_metrics(sample_metrics, temp_dir):
    """Test getting historical metrics"""
    manager = MetricsManager()
    manager.metrics_dir = temp_dir
    
    # Create historical metrics for the last 5 days
    dates = []
    for i in range(5):
        date = datetime.now() - timedelta(days=i)
        dates.append(date.strftime('%Y-%m-%d'))
        
        # Modify metrics slightly for each day
        day_metrics = sample_metrics.copy()
        day_metrics['processed_today'] += i
        
        metrics_file = temp_dir / f"{dates[-1]}.json"
        with open(metrics_file, 'w') as f:
            json.dump(day_metrics, f)
    
    # Test getting historical metrics
    historical_data = manager.get_historical_metrics(days=3)
    assert len(historical_data) == 3
    
    # Test getting all historical metrics
    all_historical_data = manager.get_historical_metrics(days=10)
    assert len(all_historical_data) == 5
    
    # Test getting metrics for period with no data
    old_historical_data = manager.get_historical_metrics(days=30)
    assert len(old_historical_data) == 5

def test_metrics_persistence(sample_metrics, temp_dir):
    """Test metrics are properly saved to files"""
    # Set metrics directory before creating manager
    MetricsManager.metrics_dir = temp_dir
    manager = MetricsManager()
    
    # Update metrics
    for metric_name, value in sample_metrics.items():
        manager.update_metrics(metric_name, value)
    
    # Check if metrics file was created
    today = datetime.now().strftime('%Y-%m-%d')
    metrics_file = temp_dir / f"{today}.json"
    assert metrics_file.exists()
    
    # Verify file contents
    with open(metrics_file, 'r') as f:
        saved_metrics = json.load(f)
    assert saved_metrics == sample_metrics
    
    # Create new manager instance and verify it loads the same metrics
    new_manager = MetricsManager()
    loaded_metrics = new_manager.get_metrics()
    assert loaded_metrics == sample_metrics 