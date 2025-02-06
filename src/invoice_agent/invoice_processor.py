import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph

class InvoiceProcessor:
    def _generate_pdf_invoice(self, invoice_data, po_data):
        """Generate a PDF invoice"""
        is_green = False
        
        # Check if this is a green invoice (all validations pass)
        if po_data:
            # 1. Check vendor match
            vendor_match = (
                po_data["vendor_info"]["id"] == invoice_data["vendor_info"]["id"] and
                po_data["vendor_info"]["name"] == invoice_data["vendor_info"]["name"]
            )
            
            # 2. Check line items match
            items_match = True
            po_items = {item["description"]: item for item in po_data["items"]}
            for inv_item in invoice_data["items"]:
                if inv_item["description"] not in po_items:
                    items_match = False
                    break
                po_item = po_items[inv_item["description"]]
                if (po_item["quantity"] != inv_item["quantity"] or
                    abs(po_item["unit_price"] - inv_item["unit_price"]) > 0.01):
                    items_match = False
                    break
            
            # 3. Check total amount matches (within 1 cent tolerance)
            amount_match = abs(po_data["total_amount"] - invoice_data["total_amount"]) <= 0.01
            
            # 4. Check GR exists and quantities match
            gr_data = self.erp_data.get_gr_by_po_number(po_data["po_number"])
            gr_match = False
            if gr_data:
                gr_match = True
                gr_items = {item["description"]: item for item in gr_data["items"]}
                for inv_item in invoice_data["items"]:
                    if inv_item["description"] not in gr_items:
                        gr_match = False
                        break
                    gr_item = gr_items[inv_item["description"]]
                    if gr_item["received_quantity"] != inv_item["quantity"]:
                        gr_match = False
                        break
            
            is_green = vendor_match and items_match and amount_match and gr_match
        
        # Generate the invoice file
        invoice_number = invoice_data["invoice_number"]
        filename = f"{invoice_number}_green.pdf" if is_green else f"{invoice_number}.pdf"
        filepath = os.path.join(self.output_dir, "pdf", filename)
        
        # Create PDF
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        story = []
        
        # Add watermark for green invoices
        if is_green:
            story.append(Paragraph("GREEN INVOICE", self.styles["Heading1"]))
        
        # Rest of the PDF generation code...
        # ... existing code ...
        
        return filepath, is_green 