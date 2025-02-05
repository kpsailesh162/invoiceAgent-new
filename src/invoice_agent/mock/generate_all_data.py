from pathlib import Path
import logging
import shutil
import random
from datetime import datetime
import pandas as pd
from ..erp.erp_data import erp_mock_data
from .invoice_generator import InvoiceGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TestDataGenerator:
    def __init__(self):
        # Create base directory for generated invoices
        self.base_dir = Path("src/invoice_agent/data/generated_invoices")
        self.create_directories()
    
    def create_directories(self):
        """Create all necessary directories"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create format-specific subdirectories
        (self.base_dir / "pdf").mkdir(exist_ok=True)
        (self.base_dir / "csv").mkdir(exist_ok=True)
        (self.base_dir / "xlsx").mkdir(exist_ok=True)
    
    def generate_all_data(self):
        """Generate all test data"""
        logger.info("Starting comprehensive data generation")
        
        try:
            # Step 1: Generate Master ERP Data
            logger.info("Generating master ERP data...")
            self._generate_master_erp_data()
            
            # Step 2: Generate Production-like Invoices
            logger.info("Generating production-like invoices...")
            self._generate_production_invoices()
            
            logger.info("Data generation completed successfully")
            
        except Exception as e:
            logger.error(f"Error during data generation: {str(e)}")
            raise
    
    def _generate_master_erp_data(self):
        """Generate master ERP data - this is handled by erp_mock_data initialization"""
        # The ERPMockData class automatically generates and saves the data
        # We just need to verify it was created
        mock_data_dir = Path("src/invoice_agent/erp/mock_data")
        expected_files = ["vendors.json", "purchase_orders.json", "goods_receipts.json"]
        
        for file_name in expected_files:
            file_path = mock_data_dir / file_name
            if not file_path.exists():
                raise FileNotFoundError(f"ERP mock data file not generated: {file_path}")
            logger.info(f"Verified ERP mock data file: {file_name}")
    
    def _generate_production_invoices(self):
        """Generate production-like invoices"""
        # Create an instance of InvoiceGenerator
        invoice_generator = InvoiceGenerator()
        
        # Generate a mix of invoices for production testing
        for po in erp_mock_data.purchase_orders:
            if po["status"] == "completed":
                # Generate both normal and slightly erroneous invoices
                invoice_data = invoice_generator.generate_invoice_data(po, introduce_errors=False)
                self._save_production_invoice(invoice_data, "normal")
                
                if random.random() < 0.3:  # 30% chance of error
                    error_invoice = invoice_generator.generate_invoice_data(po, introduce_errors=True)
                    self._save_production_invoice(error_invoice, "with_errors")
    
    def _save_production_invoice(self, invoice_data: dict, variant: str):
        """Save production-like invoice"""
        # Create an instance of InvoiceGenerator
        invoice_generator = InvoiceGenerator()
        
        # Save in all formats
        invoice_generator.generate_csv_invoice(
            invoice_data,
            self.base_dir / "csv" / f"invoice_{invoice_data['invoice_number']}_{variant}.csv"
        )
        invoice_generator.generate_pdf_invoice(
            invoice_data,
            self.base_dir / "pdf" / f"invoice_{invoice_data['invoice_number']}_{variant}.pdf"
        )
    
    def _generate_partial_match(self, po: dict, error_type: str) -> dict:
        """Generate invoice with partial match errors"""
        invoice_generator = InvoiceGenerator()
        invoice_data = invoice_generator.generate_invoice_data(po, introduce_errors=False)
        
        if error_type == "wrong_amount":
            invoice_data["total_amount"] += round(invoice_data["total_amount"] * 0.01, 2)
        elif error_type == "wrong_tax":
            invoice_data["tax_amount"] = round(invoice_data["subtotal"] * 0.11, 2)
            invoice_data["total_amount"] = invoice_data["subtotal"] + invoice_data["tax_amount"]
        
        return invoice_data
    
    def _generate_mismatch(self, po: dict, error_type: str) -> dict:
        """Generate invoice with significant mismatches"""
        invoice_generator = InvoiceGenerator()
        invoice_data = invoice_generator.generate_invoice_data(po, introduce_errors=False)
        
        if error_type == "wrong_po":
            invoice_data["po_number"] = f"PO{str(int(po['po_number'][2:]) + 1000).zfill(4)}"
        elif error_type == "missing_field":
            invoice_data.pop("tax_amount")
            invoice_data.pop("payment_terms")
        elif error_type == "duplicate_items":
            duplicate_item = invoice_data["items"][0].copy()
            duplicate_item["quantity"] += 1
            invoice_data["items"].append(duplicate_item)
            invoice_data["subtotal"] += duplicate_item["total"]
            invoice_data["tax_amount"] = round(invoice_data["subtotal"] * 0.1, 2)
            invoice_data["total_amount"] = invoice_data["subtotal"] + invoice_data["tax_amount"]
        
        return invoice_data
    
    def _generate_edge_cases(self) -> dict:
        """Generate edge cases for testing"""
        invoice_generator = InvoiceGenerator()
        edge_cases = {}
        
        # Zero amount invoice
        po = erp_mock_data.purchase_orders[0]
        zero_amount = invoice_generator.generate_invoice_data(po, introduce_errors=False)
        for item in zero_amount["items"]:
            item["quantity"] = 0
            item["total"] = 0
        zero_amount["subtotal"] = 0
        zero_amount["tax_amount"] = 0
        zero_amount["total_amount"] = 0
        edge_cases["zero_amount"] = zero_amount
        
        # Maximum values
        po = erp_mock_data.purchase_orders[1]
        max_values = invoice_generator.generate_invoice_data(po, introduce_errors=False)
        max_values["items"] = [max_values["items"][0]]
        max_values["items"][0]["quantity"] = 9999
        max_values["items"][0]["unit_price"] = 9999.99
        max_values["items"][0]["total"] = max_values["items"][0]["quantity"] * max_values["items"][0]["unit_price"]
        max_values["subtotal"] = max_values["items"][0]["total"]
        max_values["tax_amount"] = round(max_values["subtotal"] * 0.1, 2)
        max_values["total_amount"] = max_values["subtotal"] + max_values["tax_amount"]
        edge_cases["max_values"] = max_values
        
        # Special characters
        po = erp_mock_data.purchase_orders[2]
        special_chars = invoice_generator.generate_invoice_data(po, introduce_errors=False)
        special_chars["invoice_number"] = "INV#2023/特殊文字"
        special_chars["vendor_info"]["name"] = "Company Name & Söhne (€)"
        edge_cases["special_chars"] = special_chars
        
        return edge_cases
    
    def _update_summary_stats(self, summary: dict, invoice_data: dict):
        """Update summary statistics"""
        # Update vendor distribution
        vendor_name = invoice_data["vendor_info"]["name"]
        summary["vendor_distribution"][vendor_name] = summary["vendor_distribution"].get(vendor_name, 0) + 1
        
        # Update amount ranges
        amount = invoice_data["total_amount"]
        if amount <= 1000:
            summary["amount_ranges"]["0-1000"] += 1
        elif amount <= 5000:
            summary["amount_ranges"]["1001-5000"] += 1
        elif amount <= 10000:
            summary["amount_ranges"]["5001-10000"] += 1
        else:
            summary["amount_ranges"]["10001+"] += 1
    
    def _generate_summary_report(self, summary: dict):
        """Generate summary report of test data"""
        report = pd.DataFrame([
            ["Total Invoices", summary["total_invoices"]],
            ["Perfect Matches", summary["scenarios"].get("perfect_match", 0)],
            ["Partial Matches", summary["scenarios"].get("partial_match", 0)],
            ["Mismatches", summary["scenarios"].get("mismatch", 0)],
            ["Edge Cases", summary["scenarios"].get("edge_case", 0)],
            ["", ""],
            ["Error Cases:", ""],
            *[[f"  - {k}", v] for k, v in summary["error_cases"].items()],
            ["", ""],
            ["Amount Ranges:", ""],
            *[[f"  - {k}", v] for k, v in summary["amount_ranges"].items()],
            ["", ""],
            ["Vendor Distribution:", ""],
            *[[f"  - {k}", v] for k, v in summary["vendor_distribution"].items()]
        ], columns=["Metric", "Value"])
        
        report.to_csv(self.base_dir / "test_data_summary.csv", index=False)
        logger.info(f"Summary report generated: {self.base_dir / 'test_data_summary.csv'}")

def generate_all_test_data():
    """Main function to generate all test data"""
    generator = TestDataGenerator()
    generator.generate_all_data()

if __name__ == "__main__":
    generate_all_test_data() 