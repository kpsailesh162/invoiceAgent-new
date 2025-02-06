import re
from datetime import datetime
from typing import Dict, Optional
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import requests
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
import numpy as np
from ..database.db_manager import DatabaseManager


class InvoiceAgent:
    def __init__(self):
        self.validation_rules = {
            "invoice_number": r"^[A-Z0-9-]{6,20}$",
            "date": r"^\d{4}-\d{2}-\d{2}$",
            "total_amount": r"^\d+\.\d{2}$",
            "tax_id": r"^[A-Z]{2}\d{10}$",
        }

        # Initialize data matcher for three-way matching
        from .matcher import data_matcher

        self.matcher = data_matcher

        # Import ERP mock data
        from ..erp.erp_data import erp_mock_data

        self.erp_data = erp_mock_data

        self.db_manager = DatabaseManager()

        # Initialize model components only if needed
        self.processor = None
        self.model = None

    def _init_model(self):
        """Initialize the model components if they haven't been initialized yet"""
        if self.processor is None:
            try:
                from transformers import (
                    LayoutLMv3Processor,
                    LayoutLMv3ForTokenClassification,
                )

                self.processor = LayoutLMv3Processor.from_pretrained(
                    "microsoft/layoutlmv3-base"
                )
                self.model = LayoutLMv3ForTokenClassification.from_pretrained(
                    "microsoft/layoutlmv3-base"
                )
            except Exception as e:
                print(f"Warning: Could not initialize LayoutLM model: {str(e)}")
                print("Falling back to text-based extraction")

    def process_invoice(self, file_path: str) -> Dict:
        """Process invoice and save to database"""
        try:
            # Extract data from invoice
            extracted_data = self.process_document(file_path)

            # Save to database
            invoice_id, workflow_id = self.db_manager.save_invoice(
                extracted_data, file_path
            )

            # Update status to processing
            self.db_manager.update_workflow_status(
                invoice_id, "processing", "Invoice data extracted and saved"
            )

            # Initialize matching results with default values
            matching_results = {
                "match_successful": False,
                "po_match_status": False,
                "gr_match_status": None,
                "discrepancies": [],
                "po_details": {
                    "number": extracted_data.get("po_number"),
                    "status": extracted_data.get("status"),
                    "total_amount": extracted_data.get("total_amount"),
                },
                "gr_details": None,
            }

            try:
                # Get PO data if PO number exists
                po_number = extracted_data.get("po_number")
                if po_number:
                    try:
                        po_data = self.get_purchase_order(po_number)

                        # Get GR data
                        try:
                            gr_data = self.get_goods_receipt(po_number)

                            # Perform three-way matching only if both PO and GR data are available
                            matching_results = self.perform_three_way_match(
                                extracted_data, po_data, gr_data
                            )
                        except Exception as gr_error:
                            matching_results["discrepancies"] = [
                                f"GR data not found: {str(gr_error)}"
                            ]
                            matching_results["po_details"] = {
                                "number": po_number,
                                "status": po_data.get("status"),
                                "total_amount": po_data.get("total_amount"),
                            }

                    except Exception as po_error:
                        matching_results["discrepancies"] = [
                            f"PO data not found: {str(po_error)}"
                        ]
                else:
                    matching_results["discrepancies"] = [
                        "No PO number found in invoice"
                    ]
            except Exception as match_error:
                matching_results["discrepancies"] = [
                    f"Matching error: {str(match_error)}"
                ]

            # Save matching results
            self.db_manager.save_matching_results(invoice_id, matching_results)

            # Update final status
            final_status = (
                "completed"
                if matching_results.get("match_successful")
                else "completed_with_discrepancies"
            )
            self.db_manager.update_workflow_status(
                invoice_id, final_status, "Processing completed"
            )

            return {
                "invoice_id": invoice_id,
                "workflow_id": workflow_id,
                "extracted_data": extracted_data,
                "matching_results": matching_results,
                "status": final_status,
            }

        except Exception as e:
            if "invoice_id" in locals():
                self.db_manager.update_workflow_status(
                    invoice_id, "failed", f"Processing failed: {str(e)}"
                )
            raise Exception(f"Error processing invoice: {str(e)}")

    def process_document(self, file_path: str) -> Dict:
        """Process PDF or image files to extract text and layout"""
        try:
            # Process the document based on file type
            if file_path.lower().endswith((".png", ".jpg", ".jpeg")):
                processed_doc = self._process_image(file_path)
            elif file_path.lower().endswith(".pdf"):
                processed_doc = self._process_pdf(file_path)
            else:
                raise ValueError("Unsupported file format")

            # Extract structured data from the processed document
            extracted_data = self.extract_invoice_data(processed_doc)

            # Extract invoice number
            invoice_patterns = [
                r"Invoice\s*(?:No\.?|Number|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{5,19})",  # Basic format
                r"Invoice\s*Reference\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{5,19})",  # Reference format
                r"[:\s](INV[A-Z0-9]\d{4,7})",  # Common INV format
                r"#\s*([A-Z0-9][A-Z0-9-]{5,19})",  # Hash prefix format
                r"[:\s]([A-Z0-9][A-Z0-9-]{5,19})",  # After colon or space
            ]

            invoice_found = False
            for pattern in invoice_patterns:
                matches = re.finditer(pattern, processed_doc["text"], re.IGNORECASE)
                for match in matches:
                    potential_invoice = match.group(1).strip()
                    # Basic validation: at least 6 chars, must contain numbers
                    if len(potential_invoice) >= 6 and any(
                        c.isdigit() for c in potential_invoice
                    ):
                        # Check if this invoice number already exists
                        try:
                            self.db_manager.check_invoice_number(potential_invoice)
                            extracted_data["invoice_number"] = potential_invoice
                            invoice_found = True
                            break
                        except Exception:
                            # If invoice number exists, continue searching
                            continue
                if invoice_found:
                    break

            # If no invoice number found or all found numbers are duplicates, generate a unique one
            if not invoice_found:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                base_number = f"INV{timestamp[:12]}"  # Use first 12 digits of timestamp
                suffix = 1
                while True:
                    invoice_number = (
                        f"{base_number}-{suffix}" if suffix > 1 else base_number
                    )
                    try:
                        self.db_manager.check_invoice_number(invoice_number)
                        extracted_data["invoice_number"] = invoice_number
                        break
                    except Exception:
                        suffix += 1

            # Extract PO number using regex pattern
            if not extracted_data.get("po_number"):
                po_patterns = [
                    r"PO[:\s#]*([A-Z0-9][A-Z0-9-]{4,19})",  # Basic PO format
                    r"P\.?O\.?\s*(?:No\.?|Number|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{4,19})",  # More variations of PO
                    r"Purchase\s+Order\s*(?:No\.?|Number|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{4,19})",  # Full "Purchase Order"
                    r"Order\s*(?:No\.?|Number|#|Reference)?\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{4,19})",  # Order variations
                    r"Reference\s*(?:No\.?|Number|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{4,19})",  # Reference number
                    r"[:\s]([A-Z]{2,3}\d{5,7})",  # Common PO format like PO12345 or ABC12345
                    r"[:\s](PO\d{4,7})",  # Basic PO number
                ]

                po_found = False
                for pattern in po_patterns:
                    matches = re.finditer(pattern, processed_doc["text"], re.IGNORECASE)
                    for match in matches:
                        potential_po = match.group(1).strip()
                        if self._validate_po_number(potential_po):
                            extracted_data["po_number"] = potential_po
                            po_found = True
                            break
                    if po_found:
                        break

            if not extracted_data.get("total_amount"):
                amount_match = re.search(
                    r"Total[:\s]*[\$£€]?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)",
                    processed_doc["text"],
                    re.IGNORECASE,
                )
                if amount_match:
                    extracted_data["total_amount"] = self._normalize_amount(
                        amount_match.group(1)
                    )

            if not extracted_data.get("date"):
                date_patterns = [
                    r"Date[:\s]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})",
                    r"Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})",
                ]
                for pattern in date_patterns:
                    date_match = re.search(
                        pattern, processed_doc["text"], re.IGNORECASE
                    )
                    if date_match:
                        extracted_data["date"] = self._normalize_date(
                            date_match.group(1)
                        )
                        break

            # Validate the extracted data
            validation_results = self.validate_invoice(extracted_data)

            # Add validation results to the output
            extracted_data["validation_results"] = validation_results

            # Add the original processed document for reference
            extracted_data["processed_doc"] = {
                "text": processed_doc.get("text", ""),
                "has_images": "images" in processed_doc or "image" in processed_doc,
            }

            return extracted_data

        except Exception as e:
            raise ValueError(f"Error processing document: {str(e)}")

    def _process_image(self, image_path: str) -> Dict:
        """Process image files using OCR"""
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return {"text": text, "image": np.array(image)}

    def _process_pdf(self, pdf_path: str) -> Dict:
        """Process PDF files including scanned pages"""
        doc = fitz.open(pdf_path)
        full_text = []
        images = []

        for page in doc:
            text = page.get_text()
            if text.strip():  # Native PDF text
                full_text.append(text)
            else:  # Scanned page
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(np.array(img))
                full_text.append(pytesseract.image_to_string(img))

        return {"text": "\n".join(full_text), "images": images}

    def extract_invoice_data(self, processed_doc: Dict) -> Dict:
        """Extract structured data using LayoutLMv3 model"""
        try:
            # Handle cases where no image data is available
            image_data = None
            if "image" in processed_doc:
                image_data = processed_doc["image"]
            elif "images" in processed_doc and processed_doc["images"]:
                image_data = processed_doc["images"][0]

            if image_data is not None and self.processor is None:
                # Try to initialize the model only if we have image data
                self._init_model()

            if (
                image_data is not None
                and self.processor is not None
                and self.model is not None
            ):
                # Process with LayoutLMv3 if image data and model are available
                encoding = self.processor(
                    image_data,
                    processed_doc["text"],
                    return_tensors="pt",
                    truncation=True,
                )

                outputs = self.model(**encoding)
                predictions = outputs.logits.argmax(-1).squeeze().tolist()

                # Process model predictions to extract key fields
                extracted_data = self._parse_model_output(
                    processed_doc["text"], predictions, self.model.config.id2label
                )

                # If model extraction failed to get key fields, fall back to text-based extraction
                if not any(
                    key in extracted_data
                    for key in ["invoice_number", "date", "total_amount", "po_number"]
                ):
                    text_extracted = self._extract_from_text(processed_doc["text"])
                    extracted_data.update(text_extracted)

                return extracted_data

            # Fall back to text-based extraction if no image data or model is not available
            return self._extract_from_text(processed_doc["text"])

        except Exception as e:
            print(f"Warning: Model-based extraction failed: {str(e)}")
            # If model-based extraction fails, fall back to text-based extraction
            return self._extract_from_text(processed_doc["text"])

    def _extract_from_text(self, text: str) -> Dict:
        """Extract invoice data from text using regex patterns"""
        extracted_data = {}

        # Enhanced PO number patterns with more variations
        po_patterns = [
            r"PO[:\s#]*([A-Z0-9][A-Z0-9-]{4,19})",  # Basic PO format
            r"P\.?O\.?\s*(?:No\.?|Number|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{4,19})",  # More variations of PO
            r"Purchase\s+Order\s*(?:No\.?|Number|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{4,19})",  # Full "Purchase Order"
            r"Order\s*(?:No\.?|Number|#|Reference)?\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{4,19})",  # Order variations
            r"Reference\s*(?:No\.?|Number|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{4,19})",  # Reference number
            r"[:\s]([A-Z]{2,3}\d{5,7})",  # Common PO format like PO12345 or ABC12345
            r"[:\s](PO\d{4,7})",  # Basic PO number
        ]

        # Try to find PO number with different patterns
        text = " ".join(text.split())  # Normalize whitespace
        po_found = False

        for pattern in po_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                potential_po = match.group(1).strip()
                # Validate the PO number format
                if self._validate_po_number(potential_po):
                    extracted_data["po_number"] = potential_po
                    po_found = True
                    break
            if po_found:
                break

        # If no PO found with standard patterns, try additional heuristics
        if not po_found:
            # Look for sequences that match common PO formats
            additional_patterns = [
                r"[:\s]([A-Z0-9]{2,3}-\d{4,7})",  # Format: XX-1234 or XXX-1234
                r"[:\s](PO\d{4,7})",  # Format: PO1234
                r"[:\s](\d{4,7}-[A-Z]{2,3})",  # Format: 1234-XX
            ]

            for pattern in additional_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    potential_po = match.group(1).strip()
                    if self._validate_po_number(potential_po):
                        extracted_data["po_number"] = potential_po
                        po_found = True
                        break
                if po_found:
                    break

        # Extract invoice number
        invoice_patterns = [
            r"Invoice\s*(?:No\.?|Number|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{5,19})",  # Basic format
            r"Invoice\s*Reference\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{5,19})",  # Reference format
            r"[:\s](INV[A-Z0-9]\d{4,7})",  # Common INV format
            r"#\s*([A-Z0-9][A-Z0-9-]{5,19})",  # Hash prefix format
            r"[:\s]([A-Z0-9][A-Z0-9-]{5,19})",  # After colon or space
        ]

        invoice_found = False
        for pattern in invoice_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                potential_invoice = match.group(1).strip()
                # Basic validation: at least 6 chars, must contain numbers
                if len(potential_invoice) >= 6 and any(
                    c.isdigit() for c in potential_invoice
                ):
                    extracted_data["invoice_number"] = potential_invoice
                    invoice_found = True
                    break
            if invoice_found:
                break

        # If no invoice number found, generate one based on timestamp
        if not invoice_found:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            extracted_data["invoice_number"] = f"INV{timestamp}"

        # Extract total amount
        amount_match = re.search(
            r"Total[:\s]*[\$£€]?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE
        )
        if amount_match:
            extracted_data["total_amount"] = self._normalize_amount(
                amount_match.group(1)
            )

        # Extract date
        date_patterns = [
            r"Date[:\s]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})",
            r"Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})",
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, text, re.IGNORECASE)
            if date_match:
                extracted_data["date"] = self._normalize_date(date_match.group(1))
                break

        return extracted_data

    def _validate_po_number(self, po_number: str) -> bool:
        """Validate if a string matches common PO number formats"""
        if not po_number:
            return False

        # Basic validation rules for PO numbers
        min_length = 5  # Minimum length for a valid PO number
        max_length = 20  # Maximum length for a valid PO number

        # Remove any common separators
        clean_po = po_number.replace("-", "").replace("_", "").replace(" ", "")

        # Length check
        if not (min_length <= len(clean_po) <= max_length):
            return False

        # Must contain at least one number
        if not any(c.isdigit() for c in clean_po):
            return False

        # Must not contain special characters other than hyphen
        if re.search(r"[^A-Z0-9-]", po_number, re.IGNORECASE):
            return False

        # Common format checks
        valid_formats = [
            r"^[A-Z]{2,3}\d{4,7}$",  # XX12345 or XXX12345
            r"^PO\d{4,7}$",  # PO12345
            r"^\d{4,7}-[A-Z]{2,3}$",  # 12345-XX
            r"^[A-Z0-9]{2,3}-\d{4,7}$",  # XX-12345
            r"^[A-Z0-9]{5,20}$",  # Any alphanumeric 5-20 chars
        ]

        return any(
            re.match(pattern, clean_po, re.IGNORECASE) for pattern in valid_formats
        )

    def validate_invoice(self, invoice_data: Dict) -> Dict:
        """Validate extracted invoice data"""
        validation_results = {}
        required_fields = ["invoice_number", "date", "total_amount", "po_number"]

        # Check required fields
        for field in required_fields:
            value = invoice_data.get(field, "")
            if not value:
                validation_results[field] = {
                    "valid": False,
                    "value": None,
                    "error": f"Missing required field: {field}",
                }
                continue

            # Validate against rules if they exist
            if field in self.validation_rules:
                pattern = self.validation_rules[field]
                validation_results[field] = {
                    "valid": re.match(pattern, str(value)) is not None,
                    "value": value,
                }
            else:
                validation_results[field] = {"valid": True, "value": value}

        # Cross-check total amount with line items
        if "line_items" in invoice_data:
            calculated_total = sum(item["total"] for item in invoice_data["line_items"])
            invoice_total = float(invoice_data.get("total_amount", 0))
            validation_results["amount_match"] = {
                "valid": abs(calculated_total - invoice_total) < 0.01,
                "value": invoice_total,
                "calculated": calculated_total,
            }

        return validation_results

    def export_to_erp(self, invoice_data: Dict) -> bool:
        """Export validated data to ERP system (example implementation)"""
        erp_payload = {
            "vendor": invoice_data.get("vendor_name"),
            "invoice_number": invoice_data.get("invoice_number"),
            "date": invoice_data.get("date"),
            "total": invoice_data.get("total_amount"),
            "line_items": invoice_data.get("line_items", []),
        }

        try:
            response = requests.post(
                "https://erp-api.example.com/invoices", json=erp_payload, timeout=10
            )
            return response.status_code == 201
        except requests.exceptions.RequestException:
            return False

    def _parse_model_output(self, text: str, predictions: list, id2label: dict) -> Dict:
        """Parse model predictions to extract structured data"""
        # Simplified parsing logic - would need customization based on model training
        tokens = text.split()
        labels = [id2label[pred] for pred in predictions]

        extracted_data = {}
        current_field = None

        for token, label in zip(tokens, labels):
            if label.startswith("B-"):
                current_field = label[2:]
                extracted_data[current_field] = token
            elif label.startswith("I-") and current_field == label[2:]:
                extracted_data[current_field] += " " + token

        # Post-processing for dates and amounts
        if "date" in extracted_data:
            extracted_data["date"] = self._normalize_date(extracted_data["date"])
        if "total_amount" in extracted_data:
            extracted_data["total_amount"] = self._normalize_amount(
                extracted_data["total_amount"]
            )

        return extracted_data

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize various date formats to YYYY-MM-DD"""
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%b %d, %Y"):
            try:
                return datetime.strptime(date_str, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    def _normalize_amount(self, amount_str: str) -> Optional[str]:
        """Normalize currency values to decimal format"""
        clean_str = re.sub(r"[^\d.,]", "", amount_str)
        if "," in clean_str and "." in clean_str:
            # Handle European format: 1.234,56
            return f"{float(clean_str.replace('.', '').replace(',', '.')):.2f}"
        return f"{float(clean_str.replace(',', '')):.2f}"

    def get_purchase_order(self, po_number: str) -> Dict:
        """Get purchase order data from ERP system"""
        if not po_number:
            raise ValueError("PO number is required")

        po_data = self.erp_data.get_po_by_number(po_number)
        if not po_data:
            raise ValueError(f"Purchase Order {po_number} not found")

        return po_data

    def get_goods_receipt(self, po_number: str) -> Dict:
        """Get goods receipt data from ERP system"""
        if not po_number:
            raise ValueError("PO number is required")

        # First try to get GR by PO number
        gr_data = self.erp_data.get_gr_by_po_number(po_number)
        if not gr_data:
            # If not found, try to get by GR number (converting PO number to GR number)
            gr_number = f"GR{po_number[2:]}"  # Convert PO0001 to GR0001
            gr_data = self.erp_data.get_gr_by_number(gr_number)

        if not gr_data:
            raise ValueError(f"Goods Receipt for PO {po_number} not found")

        return gr_data

    def perform_three_way_match(
        self, invoice_data: Dict, po_data: Dict, gr_data: Optional[Dict] = None
    ) -> Dict:
        """Perform three-way matching between invoice, PO, and goods receipt"""
        try:
            # Initialize matching results
            matching_results = {
                "match_successful": False,
                "po_match_status": False,
                "gr_match_status": None,
                "discrepancies": [],
                "po_details": {
                    "number": po_data.get("po_number"),
                    "status": po_data.get("status"),
                    "total_amount": po_data.get("total_amount"),
                },
            }

            # First check PO status
            po_status = po_data.get("status", "").lower()
            if po_status == "cancelled":
                matching_results["discrepancies"].append("PO is cancelled")
                return matching_results

            # Check if this is a green invoice
            is_green_invoice = "_green" in invoice_data.get("file_path", "").lower()

            # Perform PO matching
            try:
                po_match_result = self.matcher.match_invoice_with_po(
                    invoice_data, po_data
                )
                matching_results["po_match_status"] = po_match_result.get(
                    "match_successful", False
                )
                if po_match_result.get("discrepancies"):
                    matching_results["discrepancies"].extend(
                        po_match_result["discrepancies"]
                    )
            except Exception as po_error:
                matching_results["discrepancies"].append(
                    f"PO matching error: {str(po_error)}"
                )
                return matching_results

            # Handle GR matching based on invoice type and PO status
            if is_green_invoice:
                # For green invoices, we expect no GR and only need PO match
                matching_results["gr_match_status"] = None
                matching_results["gr_details"] = {
                    "number": None,
                    "status": "not_required",
                    "message": "GR not required for green invoice",
                }
                # Success depends only on PO match for green invoices
                matching_results["match_successful"] = matching_results[
                    "po_match_status"
                ]
            else:
                # Regular invoice processing
                if po_status == "completed":
                    if gr_data:
                        try:
                            gr_match_result = self.matcher.match_invoice_with_gr(
                                invoice_data, gr_data
                            )
                            matching_results["gr_match_status"] = gr_match_result.get(
                                "match_successful", False
                            )
                            matching_results["gr_details"] = {
                                "number": gr_data.get("gr_number"),
                                "status": "completed",
                                "received_date": gr_data.get("receipt_date"),
                            }
                            if gr_match_result.get("discrepancies"):
                                matching_results["discrepancies"].extend(
                                    gr_match_result["discrepancies"]
                                )
                        except Exception as gr_error:
                            matching_results["discrepancies"].append(
                                f"GR matching error: {str(gr_error)}"
                            )
                    else:
                        matching_results["discrepancies"].append(
                            "GR not found for completed PO"
                        )
                else:
                    # For non-completed POs, GR is not required
                    matching_results["gr_details"] = {
                        "number": None,
                        "status": "pending",
                        "message": f"GR not required - PO status is {po_status}",
                    }
                    matching_results["match_successful"] = matching_results[
                        "po_match_status"
                    ]

            return matching_results

        except Exception as e:
            return {
                "match_successful": False,
                "error": str(e),
                "discrepancies": ["Error performing three-way match"],
                "po_details": {
                    "number": po_data.get("po_number"),
                    "status": po_data.get("status"),
                },
            }
