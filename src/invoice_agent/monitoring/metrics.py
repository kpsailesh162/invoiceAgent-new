from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time
from functools import wraps
from typing import Callable, Dict, Any, List
import prometheus_client as prom
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path

class MetricsCollector:
    def __init__(self, app_name: str = "invoice_agent"):
        self.app_name = app_name
        self.logger = logging.getLogger(__name__)
        
        # Counters
        self.invoice_processed = Counter(
            f'{app_name}_invoices_processed_total',
            'Number of invoices processed',
            ['status']
        )
        self.invoice_errors = Counter(
            f'{app_name}_invoice_errors_total',
            'Number of invoice processing errors',
            ['error_type']
        )
        
        # Histograms
        self.processing_time = Histogram(
            f'{app_name}_processing_duration_seconds',
            'Time spent processing invoices',
            buckets=[10, 30, 60, 120, 300, 600]
        )
        
        # Gauges
        self.active_workers = Gauge(
            f'{app_name}_active_workers',
            'Number of active worker threads'
        )
        self.queue_size = Gauge(
            f'{app_name}_queue_size',
            'Number of items in processing queue'
        )
        
        # New metrics
        self.amount_distribution = prom.Histogram(
            'invoice_amount_distribution',
            'Distribution of invoice amounts',
            buckets=[100, 1000, 5000, 10000, 50000, 100000]
        )
    
    def track_time(self, metric: Histogram) -> Callable:
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    metric.observe(duration)
            return wrapper
        return decorator 

    def record_invoice_processed(self, status: str):
        """Record processed invoice"""
        self.invoice_processed.labels(status=status).inc()
    
    def record_error(self, error_type: str):
        """Record processing error"""
        self.invoice_errors.labels(error_type=error_type).inc()
    
    def update_queue_size(self, size: int):
        """Update queue size"""
        self.queue_size.set(size)
    
    def observe_processing_time(self, start_time: datetime):
        """Record processing time"""
        duration = (datetime.now() - start_time).total_seconds()
        self.processing_time.observe(duration)
    
    def observe_amount(self, amount: float):
        """Record invoice amount"""
        self.amount_distribution.observe(amount) 

class MetricsManager:
    metrics_dir = Path(__file__).parent / 'data'
    
    def __init__(self):
        self.metrics_dir.mkdir(exist_ok=True)
        self.current_metrics = {
            'processed_today': 0,
            'success_rate': 0.0,
            'processing_queue': 0,
            'avg_processing_time': 0.0
        }
        self._load_current_metrics()

    def _load_current_metrics(self) -> None:
        """Load current day's metrics if they exist"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            metrics_file = self.metrics_dir / f"{today}.json"
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    loaded_metrics = json.load(f)
                    # Update only existing keys
                    for key in self.current_metrics:
                        if key in loaded_metrics:
                            self.current_metrics[key] = loaded_metrics[key]
        except Exception as e:
            logging.error(f"Failed to load metrics: {str(e)}")

    def update_metrics(self, metric_name: str, value: float) -> None:
        """Update specific metric"""
        if metric_name in self.current_metrics:
            self.current_metrics[metric_name] = value
            self._save_metrics()

    def get_metrics(self) -> Dict:
        """Get current metrics"""
        try:
            self._load_current_metrics()  # Refresh metrics before returning
            return self.current_metrics
        except Exception as e:
            logging.error(f"Failed to get metrics: {str(e)}")
            return {
                'processed_today': 0,
                'success_rate': 0.0,
                'processing_queue': 0,
                'avg_processing_time': 0.0
            }

    def get_historical_metrics(self, days: int = 30) -> List[Dict]:
        """Get historical metrics for specified number of days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        metrics_files = self.metrics_dir.glob('*.json')
        historical_data = []
        
        for metrics_file in metrics_files:
            file_date = datetime.strptime(metrics_file.stem, '%Y-%m-%d')
            if start_date <= file_date <= end_date:
                with open(metrics_file, 'r') as f:
                    historical_data.append(json.load(f))
        
        return historical_data

    def _save_metrics(self) -> None:
        """Save current metrics to file"""
        today = datetime.now().strftime('%Y-%m-%d')
        metrics_file = self.metrics_dir / f"{today}.json"
        
        with open(metrics_file, 'w') as f:
            json.dump(self.current_metrics, f, indent=2)

metrics_manager = MetricsManager() 