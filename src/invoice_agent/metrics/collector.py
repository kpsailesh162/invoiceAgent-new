import logging
from typing import Dict, Any, List
import asyncio
from datetime import datetime, timedelta
import json
from pathlib import Path

class MetricsCollector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics_file = Path("data/metrics.json")
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize metrics file if it doesn't exist
        if not self.metrics_file.exists():
            self._save_metrics({
                "queue_size": 0,
                "processed_count": 0,
                "error_count": 0,
                "processing_times": [],
                "amounts": [],
                "confidence_scores": [],
                "status_counts": {},
                "hourly_metrics": {},
                "daily_metrics": {}
            })
    
    def _load_metrics(self) -> Dict[str, Any]:
        """Load metrics from file"""
        try:
            return json.loads(self.metrics_file.read_text())
        except Exception as e:
            self.logger.error(f"Error loading metrics: {str(e)}")
            return {}
    
    def _save_metrics(self, metrics: Dict[str, Any]):
        """Save metrics to file"""
        try:
            self.metrics_file.write_text(json.dumps(metrics, indent=2))
        except Exception as e:
            self.logger.error(f"Error saving metrics: {str(e)}")
    
    async def update_queue_size(self, size: int):
        """Update queue size metric"""
        metrics = self._load_metrics()
        metrics["queue_size"] = size
        self._save_metrics(metrics)
        self.logger.debug(f"Queue size updated: {size}")
    
    async def record_invoice_processed(self, status: str):
        """Record a processed invoice"""
        metrics = self._load_metrics()
        metrics["processed_count"] += 1
        
        # Update status counts
        if status not in metrics["status_counts"]:
            metrics["status_counts"][status] = 0
        metrics["status_counts"][status] += 1
        
        # Update hourly metrics
        hour_key = datetime.now().strftime("%Y-%m-%d-%H")
        if hour_key not in metrics["hourly_metrics"]:
            metrics["hourly_metrics"][hour_key] = {"processed": 0, "errors": 0}
        metrics["hourly_metrics"][hour_key]["processed"] += 1
        
        # Update daily metrics
        day_key = datetime.now().strftime("%Y-%m-%d")
        if day_key not in metrics["daily_metrics"]:
            metrics["daily_metrics"][day_key] = {"processed": 0, "errors": 0}
        metrics["daily_metrics"][day_key]["processed"] += 1
        
        self._save_metrics(metrics)
        self.logger.debug(f"Invoice processed: {status}")
    
    async def record_error(self, error_type: str):
        """Record an error"""
        metrics = self._load_metrics()
        metrics["error_count"] += 1
        
        # Update hourly metrics
        hour_key = datetime.now().strftime("%Y-%m-%d-%H")
        if hour_key not in metrics["hourly_metrics"]:
            metrics["hourly_metrics"][hour_key] = {"processed": 0, "errors": 0}
        metrics["hourly_metrics"][hour_key]["errors"] += 1
        
        # Update daily metrics
        day_key = datetime.now().strftime("%Y-%m-%d")
        if day_key not in metrics["daily_metrics"]:
            metrics["daily_metrics"][day_key] = {"processed": 0, "errors": 0}
        metrics["daily_metrics"][day_key]["errors"] += 1
        
        self._save_metrics(metrics)
        self.logger.debug(f"Error recorded: {error_type}")
    
    async def observe_processing_time(self, start_time: datetime):
        """Record processing time"""
        processing_time = (datetime.now() - start_time).total_seconds()
        metrics = self._load_metrics()
        metrics["processing_times"].append(processing_time)
        self._save_metrics(metrics)
        self.logger.debug(f"Processing time recorded: {processing_time}s")
    
    async def observe_amount(self, amount: float):
        """Record invoice amount"""
        metrics = self._load_metrics()
        metrics["amounts"].append(amount)
        self._save_metrics(metrics)
        self.logger.debug(f"Amount recorded: {amount}")
    
    async def record_confidence_score(self, score: float):
        """Record confidence score"""
        metrics = self._load_metrics()
        metrics["confidence_scores"].append(score)
        self._save_metrics(metrics)
        self.logger.debug(f"Confidence score recorded: {score}")
    
    async def get_summary_metrics(self) -> Dict[str, Any]:
        """Get summary metrics"""
        metrics = self._load_metrics()
        
        # Calculate averages
        avg_processing_time = sum(metrics["processing_times"]) / len(metrics["processing_times"]) if metrics["processing_times"] else 0
        avg_amount = sum(metrics["amounts"]) / len(metrics["amounts"]) if metrics["amounts"] else 0
        avg_confidence = sum(metrics["confidence_scores"]) / len(metrics["confidence_scores"]) if metrics["confidence_scores"] else 0
        
        return {
            "total_processed": metrics["processed_count"],
            "total_errors": metrics["error_count"],
            "current_queue_size": metrics["queue_size"],
            "avg_processing_time": avg_processing_time,
            "avg_amount": avg_amount,
            "avg_confidence_score": avg_confidence,
            "status_distribution": metrics["status_counts"]
        }
    
    async def get_time_series_metrics(self, period: str = "hourly") -> Dict[str, Any]:
        """Get time series metrics"""
        metrics = self._load_metrics()
        
        if period == "hourly":
            return metrics["hourly_metrics"]
        else:
            return metrics["daily_metrics"] 