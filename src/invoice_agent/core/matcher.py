from typing import Dict, List, Tuple
import logging
from pathlib import Path
from ..erp.erp_data import erp_mock_data
from ..mock.invoice_generator import MATCHING_FIELDS

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('matching.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DataMatcher:
    def __init__(self):
        self.matching_fields = MATCHING_FIELDS
    
    def match_invoice_with_erp(self, extracted_data: Dict) -> Dict:
        """Match extracted invoice data with ERP data"""
        logger.info(f"Starting matching process for invoice {extracted_data.get('invoice_number', 'UNKNOWN')}")
        
        matching_results = {
            "match_status": "unknown",
            "po_match": False,
            "receipt_match": False,
            "amount_match": False,
            "discrepancies": [],
            "confidence_scores": {}
        }
        
        # Step 1: Validate required fields
        missing_fields = self._check_required_fields(extracted_data)
        if missing_fields:
            matching_results["match_status"] = "validation_failed"
            matching_results["discrepancies"].extend(
                [f"Missing required field: {field}" for field in missing_fields]
            )
            logger.warning(f"Missing required fields: {missing_fields}")
            return matching_results
        
        # Step 2: Match with Purchase Order
        po_number = extracted_data.get("po_number")
        po_data = erp_mock_data.get_po_by_number(po_number)
        
        if not po_data:
            matching_results["match_status"] = "match_failed"
            matching_results["discrepancies"].append(f"PO number {po_number} not found in ERP system")
            logger.warning(f"PO not found: {po_number}")
            return matching_results
        
        # Step 3: Perform detailed matching
        po_discrepancies = self._match_with_po(extracted_data, po_data)
        matching_results["discrepancies"].extend(po_discrepancies)
        
        # Step 4: Match with Goods Receipt if PO is completed
        if po_data["status"] == "completed":
            gr_number = f"GR{po_number[2:]}"
            gr_data = erp_mock_data.get_gr_by_number(gr_number)
            
            if gr_data:
                gr_discrepancies = self._match_with_gr(extracted_data, gr_data)
                matching_results["discrepancies"].extend(gr_discrepancies)
                matching_results["receipt_match"] = not bool(gr_discrepancies)
        
        # Step 5: Calculate match status
        matching_results["po_match"] = not bool(po_discrepancies)
        matching_results["amount_match"] = self._check_amount_match(extracted_data, po_data)
        
        if not matching_results["discrepancies"]:
            matching_results["match_status"] = "full_match"
        elif len(matching_results["discrepancies"]) <= 2:
            matching_results["match_status"] = "partial_match"
        else:
            matching_results["match_status"] = "match_failed"
        
        # Log matching results
        logger.info(f"Matching completed for invoice {extracted_data.get('invoice_number')}. "
                   f"Status: {matching_results['match_status']}")
        if matching_results["discrepancies"]:
            logger.warning(f"Discrepancies found: {matching_results['discrepancies']}")
        
        return matching_results
    
    def _check_required_fields(self, data: Dict) -> List[str]:
        """Check if all required fields are present"""
        missing_fields = []
        for field in self.matching_fields["required"]:
            if "." in field:
                parent, child = field.split(".")
                if parent not in data or child not in data[parent]:
                    missing_fields.append(field)
            elif field not in data:
                missing_fields.append(field)
        return missing_fields
    
    def _match_with_po(self, invoice_data: Dict, po_data: Dict) -> List[str]:
        """Match invoice data with purchase order data"""
        discrepancies = []
        
        # Match vendor
        vendor = erp_mock_data.get_vendor_by_id(po_data["vendor_id"])
        if vendor["tax_id"] != invoice_data["vendor_info"]["tax_id"]:
            discrepancies.append("Vendor tax ID mismatch")
        
        # Match line items
        invoice_items = {item["id"]: item for item in invoice_data["items"]}
        po_items = {item["id"]: item for item in po_data["items"]}
        
        for item_id, invoice_item in invoice_items.items():
            if item_id not in po_items:
                discrepancies.append(f"Item {item_id} not found in PO")
                continue
            
            po_item = po_items[item_id]
            if invoice_item["quantity"] != po_item["quantity"]:
                discrepancies.append(
                    f"Quantity mismatch for item {item_id}: "
                    f"Invoice: {invoice_item['quantity']}, PO: {po_item['quantity']}"
                )
            
            if abs(invoice_item["unit_price"] - po_item["unit_price"]) > 0.01:
                discrepancies.append(
                    f"Unit price mismatch for item {item_id}: "
                    f"Invoice: {invoice_item['unit_price']}, PO: {po_item['unit_price']}"
                )
        
        # Check for missing items
        for item_id in po_items:
            if item_id not in invoice_items:
                discrepancies.append(f"PO item {item_id} missing from invoice")
        
        return discrepancies
    
    def _match_with_gr(self, invoice_data: Dict, gr_data: Dict) -> List[str]:
        """Match invoice data with goods receipt data"""
        discrepancies = []
        
        invoice_items = {item["id"]: item for item in invoice_data["items"]}
        gr_items = {item["id"]: item for item in gr_data["items"]}
        
        for item_id, invoice_item in invoice_items.items():
            if item_id not in gr_items:
                discrepancies.append(f"Item {item_id} not found in goods receipt")
                continue
            
            gr_item = gr_items[item_id]
            if invoice_item["quantity"] > gr_item["received_quantity"]:
                discrepancies.append(
                    f"Invoice quantity exceeds received quantity for item {item_id}: "
                    f"Invoice: {invoice_item['quantity']}, Received: {gr_item['received_quantity']}"
                )
        
        return discrepancies
    
    def _check_amount_match(self, invoice_data: Dict, po_data: Dict) -> bool:
        """Check if invoice amounts match PO amounts"""
        return (
            abs(invoice_data["subtotal"] - po_data["subtotal"]) < 0.01 and
            abs(invoice_data["tax_amount"] - po_data["tax_amount"]) < 0.01 and
            abs(invoice_data["total_amount"] - po_data["total_amount"]) < 0.01
        )

# Initialize matcher
data_matcher = DataMatcher() 