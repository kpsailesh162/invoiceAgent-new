import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pathlib import Path

class ProcessorHistory:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.history_file = Path("data/processing_history.json")
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize history file if it doesn't exist
        if not self.history_file.exists():
            self._save_history([])
    
    def _load_history(self) -> List[Dict[str, Any]]:
        """Load processing history from file"""
        try:
            return json.loads(self.history_file.read_text())
        except Exception as e:
            self.logger.error(f"Error loading history: {str(e)}")
            return []
    
    def _save_history(self, history: List[Dict[str, Any]]):
        """Save processing history to file"""
        try:
            self.history_file.write_text(json.dumps(history, indent=2))
        except Exception as e:
            self.logger.error(f"Error saving history: {str(e)}")
    
    async def add_history_entry(
        self,
        invoice_number: str,
        status: str,
        confidence_score: float,
        match_details: Dict[str, Any],
        processing_time: float
    ):
        """Add a new history entry"""
        history = self._load_history()
        
        entry = {
            "invoice_number": invoice_number,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "confidence_score": confidence_score,
            "match_details": match_details,
            "processing_time": processing_time
        }
        
        history.append(entry)
        self._save_history(history)
    
    async def get_invoice_history(self, invoice_number: str) -> List[Dict[str, Any]]:
        """Get processing history for a specific invoice"""
        history = self._load_history()
        return [entry for entry in history if entry["invoice_number"] == invoice_number]
    
    async def get_all_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all processing history with optional filters"""
        history = self._load_history()
        
        filtered_history = history
        
        if start_date:
            filtered_history = [
                entry for entry in filtered_history
                if datetime.fromisoformat(entry["timestamp"]) >= start_date
            ]
        
        if end_date:
            filtered_history = [
                entry for entry in filtered_history
                if datetime.fromisoformat(entry["timestamp"]) <= end_date
            ]
        
        if status:
            filtered_history = [
                entry for entry in filtered_history
                if entry["status"] == status
            ]
        
        return filtered_history

# Initialize global processor history
processor_history = ProcessorHistory() 