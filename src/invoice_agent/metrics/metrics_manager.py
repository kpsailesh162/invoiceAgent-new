from datetime import datetime, timedelta
from pathlib import Path
import json
import redis
from typing import Dict, List, Any, Optional

class MetricsManager:
    """Manages metrics collection and storage for the invoice processing system"""
    
    metrics_dir = Path(__file__).parent / 'data'
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize the metrics manager"""
        self.metrics_dir.mkdir(exist_ok=True)
        self.redis_client = redis_client or redis.Redis(host='localhost', port=6379, db=0)
        
        # Initialize counters
        self._success_count = 0
        self._failure_count = 0
        self._processing_times = []
        self._queue_size = 0
        
    def record_success(self):
        """Record a successful invoice processing"""
        self._success_count += 1
        self._update_metrics()
        
    def record_failure(self):
        """Record a failed invoice processing"""
        self._failure_count += 1
        self._update_metrics()
        
    def record_processing_time(self, time_seconds: float):
        """Record the processing time for an invoice"""
        self._processing_times.append(time_seconds)
        self._update_metrics()
        
    def update_queue_size(self, size: int):
        """Update the current processing queue size"""
        self._queue_size = size
        self._update_metrics()
        
    def _update_metrics(self):
        """Update current metrics in Redis"""
        today = datetime.now().strftime("%Y-%m-%d")
        total = self._success_count + self._failure_count
        
        metrics = {
            "success_rate": self._success_count / total if total > 0 else 0,
            "processed_today": total,
            "processing_queue": self._queue_size,
            "avg_processing_time": sum(self._processing_times) / len(self._processing_times) if self._processing_times else 0
        }
        
        self.redis_client.hset(f"metrics:{today}", mapping=metrics)
        
    def get_current_metrics(self) -> Dict[str, float]:
        """Get the current day's metrics"""
        today = datetime.now().strftime("%Y-%m-%d")
        metrics = self.redis_client.hgetall(f"metrics:{today}")
        
        if not metrics:
            return {
                "success_rate": 0,
                "processed_today": 0,
                "processing_queue": 0,
                "avg_processing_time": 0
            }
            
        return {k.decode(): float(v) for k, v in metrics.items()}
        
    def get_historical_metrics(self, days: int = 7) -> List[Dict[str, float]]:
        """Get historical metrics for the specified number of days"""
        metrics = []
        today = datetime.now()
        
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            day_metrics = self.redis_client.hgetall(f"metrics:{date_str}")
            
            if day_metrics:
                metrics.append({
                    "date": date_str,
                    **{k.decode(): float(v) for k, v in day_metrics.items()}
                })
                
        return metrics
        
    def get_prometheus_metrics(self) -> Dict[str, Any]:
        """Get metrics in Prometheus format"""
        return {
            "invoice_processing_total": self._success_count + self._failure_count,
            "invoice_processing_success": self._success_count,
            "invoice_processing_failure": self._failure_count,
            "processing_time_histogram": {
                "count": len(self._processing_times),
                "sum": sum(self._processing_times),
                "avg": sum(self._processing_times) / len(self._processing_times) if self._processing_times else 0,
                "buckets": self._calculate_histogram_buckets()
            },
            "processing_queue_size": self._queue_size
        }
        
    def _calculate_histogram_buckets(self) -> Dict[str, int]:
        """Calculate histogram buckets for processing times"""
        buckets = {
            "le_0.1": 0,
            "le_0.5": 0,
            "le_1.0": 0,
            "le_2.0": 0,
            "le_5.0": 0,
            "le_inf": 0
        }
        
        for time in self._processing_times:
            if time <= 0.1:
                buckets["le_0.1"] += 1
            if time <= 0.5:
                buckets["le_0.5"] += 1
            if time <= 1.0:
                buckets["le_1.0"] += 1
            if time <= 2.0:
                buckets["le_2.0"] += 1
            if time <= 5.0:
                buckets["le_5.0"] += 1
            buckets["le_inf"] += 1
            
        return buckets 