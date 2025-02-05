from typing import Dict, List, Tuple, Optional
import logging
from difflib import SequenceMatcher
import re
from datetime import datetime
from ..config.settings import enterprise_config
from ..utils.audit_logger import audit_logger
from ..erp.erp_data import erp_mock_data

class AdvancedMatcher:
    def __init__(self):
        self.config = enterprise_config.matching
        self.logger = logging.getLogger(__name__)
    
    def fuzzy_match_text(self, text1: str, text2: str) -> Tuple[bool, float]:
        """Perform fuzzy text matching"""
        if not text1 or not text2:
            return False, 0.0
        
        # Normalize texts
        text1 = self._normalize_text(text1)
        text2 = self._normalize_text(text2)
        
        # Calculate similarity ratio
        ratio = SequenceMatcher(None, text1, text2).ratio()
        
        # Check if match meets threshold
        is_match = ratio >= self.config.CONFIDENCE_THRESHOLD
        
        return is_match, ratio
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters and extra spaces
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def compare_amounts(
        self,
        amount1: float,
        amount2: float,
        tolerance: Optional[float] = None
    ) -> Tuple[bool, float]:
        """Compare monetary amounts with tolerance"""
        if tolerance is None:
            tolerance = self.config.AMOUNT_TOLERANCE
        
        if amount1 == 0 and amount2 == 0:
            return True, 1.0
        
        # Calculate difference percentage
        max_amount = max(abs(amount1), abs(amount2))
        difference = abs(amount1 - amount2)
        difference_ratio = difference / max_amount
        
        # Check if within tolerance
        is_match = difference_ratio <= tolerance
        confidence = 1.0 - (difference_ratio / tolerance if tolerance > 0 else 1.0)
        
        return is_match, max(0.0, min(1.0, confidence))
    
    def match_line_items(
        self,
        invoice_items: List[Dict],
        po_items: List[Dict]
    ) -> Tuple[bool, List[str], Dict[str, float]]:
        """Advanced line item matching with detailed analysis"""
        discrepancies = []
        confidence_scores = {}
        
        # Create lookup dictionaries
        invoice_items_dict = {item["id"]: item for item in invoice_items}
        po_items_dict = {item["id"]: item for item in po_items}
        
        # Track matched items
        matched_items = set()
        total_confidence = 0.0
        
        for item_id, invoice_item in invoice_items_dict.items():
            if item_id not in po_items_dict:
                # Try fuzzy matching if exact ID not found
                best_match_id = self._find_best_matching_item(invoice_item, po_items)
                if best_match_id:
                    po_item = po_items_dict[best_match_id]
                    matched_items.add(best_match_id)
                else:
                    discrepancies.append(f"Item {item_id} not found in PO")
                    confidence_scores[f"item_{item_id}"] = 0.0
                    continue
            else:
                po_item = po_items_dict[item_id]
                matched_items.add(item_id)
            
            # Compare quantities
            quantity_match, quantity_confidence = self._compare_quantities(
                invoice_item["quantity"],
                po_item["quantity"]
            )
            
            if not quantity_match:
                discrepancies.append(
                    f"Quantity mismatch for item {item_id}: "
                    f"Invoice: {invoice_item['quantity']}, PO: {po_item['quantity']}"
                )
            
            # Compare prices
            price_match, price_confidence = self.compare_amounts(
                invoice_item["unit_price"],
                po_item["unit_price"],
                self.config.PRICE_TOLERANCE_PERCENTAGE
            )
            
            if not price_match:
                discrepancies.append(
                    f"Unit price mismatch for item {item_id}: "
                    f"Invoice: {invoice_item['unit_price']}, PO: {po_item['unit_price']}"
                )
            
            # Calculate overall confidence for item
            item_confidence = (quantity_confidence + price_confidence) / 2
            confidence_scores[f"item_{item_id}"] = item_confidence
            total_confidence += item_confidence
        
        # Check for missing PO items
        for item_id in po_items_dict:
            if item_id not in matched_items:
                discrepancies.append(f"PO item {item_id} missing from invoice")
        
        # Calculate overall match status
        total_items = max(len(invoice_items), len(po_items))
        average_confidence = total_confidence / total_items if total_items > 0 else 0.0
        
        is_match = (
            len(discrepancies) <= self.config.PARTIAL_MATCH_MAX_DISCREPANCIES and
            average_confidence >= self.config.CONFIDENCE_THRESHOLD
        )
        
        return is_match, discrepancies, confidence_scores
    
    def _compare_quantities(
        self,
        invoice_qty: int,
        po_qty: int
    ) -> Tuple[bool, float]:
        """Compare quantities with tolerance"""
        difference = abs(invoice_qty - po_qty)
        
        if difference <= self.config.LINE_ITEM_QUANTITY_TOLERANCE:
            confidence = 1.0 - (difference / (po_qty if po_qty > 0 else 1))
            return True, max(0.0, min(1.0, confidence))
        
        return False, 0.0
    
    def _find_best_matching_item(
        self,
        invoice_item: Dict,
        po_items: List[Dict]
    ) -> Optional[str]:
        """Find best matching item using fuzzy matching"""
        best_match = None
        best_ratio = 0.0
        
        for po_item in po_items:
            # Compare item names
            _, name_ratio = self.fuzzy_match_text(
                invoice_item["name"],
                po_item["name"]
            )
            
            # Compare prices
            _, price_ratio = self.compare_amounts(
                invoice_item["unit_price"],
                po_item["unit_price"],
                self.config.PRICE_TOLERANCE_PERCENTAGE
            )
            
            # Calculate combined ratio
            combined_ratio = (name_ratio + price_ratio) / 2
            
            if combined_ratio > best_ratio and combined_ratio >= self.config.CONFIDENCE_THRESHOLD:
                best_ratio = combined_ratio
                best_match = po_item["id"]
        
        return best_match
    
    def validate_dates(
        self,
        invoice_date: str,
        po_date: str,
        gr_date: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """Validate date relationships"""
        discrepancies = []
        
        try:
            invoice_dt = datetime.strptime(invoice_date, enterprise_config.validation.DATE_FORMAT)
            po_dt = datetime.strptime(po_date, enterprise_config.validation.DATE_FORMAT)
            
            if invoice_dt < po_dt:
                discrepancies.append(
                    f"Invoice date ({invoice_date}) is before PO date ({po_date})"
                )
            
            if gr_date:
                gr_dt = datetime.strptime(gr_date, enterprise_config.validation.DATE_FORMAT)
                if invoice_dt < gr_dt:
                    discrepancies.append(
                        f"Invoice date ({invoice_date}) is before goods receipt date ({gr_date})"
                    )
        
        except ValueError as e:
            discrepancies.append(f"Date format error: {str(e)}")
        
        return len(discrepancies) == 0, discrepancies
    
    def analyze_matching_results(
        self,
        extracted_data: Dict,
        matching_results: Dict
    ) -> Dict:
        """Analyze matching results and provide insights"""
        analysis = {
            "confidence_level": "high",
            "risk_factors": [],
            "recommendations": [],
            "automated_processing": True
        }
        
        # Check confidence scores
        low_confidence_items = [
            item for item, score in matching_results["confidence_scores"].items()
            if score < self.config.HIGH_CONFIDENCE_THRESHOLD
        ]
        
        if low_confidence_items:
            analysis["confidence_level"] = "medium"
            analysis["risk_factors"].append(
                f"Low confidence matches: {', '.join(low_confidence_items)}"
            )
            analysis["recommendations"].append(
                "Manual review recommended for low confidence matches"
            )
            analysis["automated_processing"] = False
        
        # Check discrepancies
        if matching_results["discrepancies"]:
            if len(matching_results["discrepancies"]) > self.config.PARTIAL_MATCH_MAX_DISCREPANCIES:
                analysis["confidence_level"] = "low"
                analysis["automated_processing"] = False
            
            analysis["risk_factors"].extend(matching_results["discrepancies"])
            analysis["recommendations"].append(
                "Review and reconcile identified discrepancies"
            )
        
        # Log analysis results
        audit_logger.log_event(
            "matching_analysis",
            {
                "invoice_number": extracted_data.get("invoice_number"),
                "analysis_results": analysis
            }
        )
        
        return analysis

# Initialize advanced matcher
advanced_matcher = AdvancedMatcher() 