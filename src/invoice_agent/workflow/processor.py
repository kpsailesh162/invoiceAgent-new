from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import logging
import json
from enum import Enum
from ..core.data_model import Invoice, LineItem
from pathlib import Path
from ..models import WorkflowResult
from ..config.settings import config

class InvoiceStatus(Enum):
    NEW = "new"
    PROCESSING = "processing"
    MATCHED = "matched"
    EXCEPTION = "exception"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PAID = "paid"
    REJECTED = "rejected"

class EnhancedInvoiceWorkflowProcessor:
    def __init__(
        self,
        source_manager,
        document_processor,
        erp_connector,
        notification_manager,
        audit_logger,
        metrics,
        config: Dict[str, Any],
        processor_history
    ):
        self.source_manager = source_manager
        self.document_processor = document_processor
        self.erp_connector = erp_connector
        self.notification_manager = notification_manager
        self.audit_logger = audit_logger
        self.metrics = metrics
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.redis = None
        self.processor_history = processor_history

    async def _cache_invoice(self, invoice: Invoice):
        """Cache invoice data in Redis"""
        if not self.redis:
            return
        
        # Convert invoice to dict for caching
        invoice_data = {
            'invoice_number': invoice.invoice_number,
            'vendor_name': invoice.vendor_name,
            'vendor_id': invoice.vendor_id,
            'po_number': invoice.po_number,
            'total_amount': str(invoice.total_amount),
            'currency': invoice.currency,
            'status': invoice.status,
            'line_items': [
                {
                    'sku': item.sku,
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit_price': str(item.unit_price),
                    'total': str(item.total)
                }
                for item in invoice.line_items
            ]
        }
        
        await self.redis.set(
            f"invoice:{invoice.invoice_number}",
            json.dumps(invoice_data)
        )

    async def process_new_invoices(self):
        """Process all new invoices"""
        try:
            invoices = await self.source_manager.fetch_all_invoices()
            if not invoices:
                await self.metrics.update_queue_size(0)
                return

            await self.metrics.update_queue_size(len(invoices))
            await asyncio.gather(*(self._process_single_invoice_with_retry(invoice) for invoice in invoices))
        except Exception as e:
            self.logger.error(f"Failed to process invoices: {str(e)}")
            raise

    async def _process_single_invoice_with_retry(self, invoice: Invoice):
        """Process single invoice with retry logic"""
        max_retries = self.config.get('max_retries', 3)
        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                await self._process_single_invoice(invoice)
                return
            except (asyncio.TimeoutError, Exception) as e:
                last_error = e
                retry_count += 1
                if retry_count == max_retries:
                    self.logger.error(
                        f"Max retries exceeded for invoice {invoice.invoice_number}: {str(e)}"
                    )
                    invoice.status = InvoiceStatus.EXCEPTION.value
                    if isinstance(e, asyncio.TimeoutError):
                        await self.metrics.record_error("timeout_error")
                        await self.audit_logger.log_event(
                            'invoice_exception',
                            invoice,
                            metadata={'exception_type': ['TIMEOUT'], 'description': [str(e)]}
                        )
                    else:
                        await self.metrics.record_error("max_retries_exceeded")
                        await self.audit_logger.log_event(
                            'invoice_exception',
                            invoice,
                            metadata={'exception_type': ['MAX_RETRIES'], 'description': [str(e)]}
                        )
                    await self.metrics.record_invoice_processed('exception')
                    await self.notification_manager.send_notification(
                        'invoice_exception',
                        {
                            'invoice_number': invoice.invoice_number,
                            'vendor_name': invoice.vendor_name,
                            'amount': str(invoice.total_amount),
                            'currency': invoice.currency,
                            'error': str(e)
                        }
                    )
                    await self._cache_invoice(invoice)
                    raise last_error
                await asyncio.sleep(1)  # Wait before retry

    async def _process_single_invoice(self, invoice: Invoice):
        """Process a single invoice"""
        try:
            # Update status
            invoice.status = InvoiceStatus.PROCESSING.value
            await self.audit_logger.log_event(
                'invoice_status_change',
                invoice,
                metadata={'status': invoice.status}
            )
            start_time = datetime.now()

            # Process document
            try:
                processed_data = await self.document_processor.process_document(invoice.file_path)
                if not isinstance(processed_data, dict):
                    raise ValueError("Invalid document processing result")
                invoice.update(processed_data)
            except Exception as e:
                invoice.status = InvoiceStatus.EXCEPTION.value
                await self.metrics.record_error("processing_error")
                await self.audit_logger.log_event(
                    'invoice_exception',
                    invoice,
                    metadata={'exception_type': ['PROCESSING_ERROR'], 'description': [str(e)]}
                )
                await self.metrics.record_invoice_processed('exception')
                await self.notification_manager.send_notification(
                    'invoice_exception',
                    {
                        'invoice_number': invoice.invoice_number,
                        'vendor_name': invoice.vendor_name,
                        'amount': str(invoice.total_amount),
                        'currency': invoice.currency,
                        'error': str(e)
                    }
                )
                await self._cache_invoice(invoice)
                raise

            # Check for duplicate invoice
            if await self._is_duplicate_invoice(invoice):
                invoice.status = InvoiceStatus.EXCEPTION.value
                await self.metrics.record_error("duplicate_invoice")
                await self.audit_logger.log_event(
                    'invoice_exception',
                    invoice,
                    metadata={'exception_type': ['DUPLICATE'], 'description': ['Duplicate invoice detected']}
                )
                await self.metrics.record_invoice_processed('exception')
                await self.notification_manager.send_notification(
                    'invoice_exception',
                    {
                        'invoice_number': invoice.invoice_number,
                        'vendor_name': invoice.vendor_name,
                        'amount': str(invoice.total_amount),
                        'currency': invoice.currency,
                        'error': 'Duplicate invoice detected'
                    }
                )
                await self._cache_invoice(invoice)
                return

            # Handle currency conversion if needed
            if invoice.currency != self.config.get('default_currency', 'USD'):
                try:
                    exchange_rate = await self.erp_connector.get_exchange_rate(
                        invoice.currency,
                        self.config.get('default_currency', 'USD')
                    )
                    if not exchange_rate:
                        invoice.status = InvoiceStatus.EXCEPTION.value
                        await self.metrics.record_error("exchange_rate_error")
                        await self.audit_logger.log_event(
                            'invoice_exception',
                            invoice,
                            metadata={'exception_type': ['EXCHANGE_RATE'], 'description': ['Failed to get exchange rate']}
                        )
                        await self.metrics.record_invoice_processed('exception')
                        await self.notification_manager.send_notification(
                            'invoice_exception',
                            {
                                'invoice_number': invoice.invoice_number,
                                'vendor_name': invoice.vendor_name,
                                'amount': str(invoice.total_amount),
                                'currency': invoice.currency,
                                'error': 'Failed to get exchange rate'
                            }
                        )
                        await self._cache_invoice(invoice)
                        return
                except asyncio.TimeoutError as e:
                    invoice.status = InvoiceStatus.EXCEPTION.value
                    await self.metrics.record_error("timeout_error")
                    await self.audit_logger.log_event(
                        'invoice_exception',
                        invoice,
                        metadata={'exception_type': ['TIMEOUT'], 'description': ['Exchange rate service timeout']}
                    )
                    await self.metrics.record_invoice_processed('exception')
                    await self.notification_manager.send_notification(
                        'invoice_exception',
                        {
                            'invoice_number': invoice.invoice_number,
                            'vendor_name': invoice.vendor_name,
                            'amount': str(invoice.total_amount),
                            'currency': invoice.currency,
                            'error': 'Exchange rate service timeout'
                        }
                    )
                    await self._cache_invoice(invoice)
                    raise

            # Perform three-way match
            try:
                match_result = await self._perform_three_way_match(invoice)
            except asyncio.TimeoutError as e:
                invoice.status = InvoiceStatus.EXCEPTION.value
                await self.metrics.record_error("timeout_error")
                await self.audit_logger.log_event(
                    'invoice_exception',
                    invoice,
                    metadata={'exception_type': ['TIMEOUT'], 'description': [str(e)]}
                )
                await self.metrics.record_invoice_processed('exception')
                await self.notification_manager.send_notification(
                    'invoice_exception',
                    {
                        'invoice_number': invoice.invoice_number,
                        'vendor_name': invoice.vendor_name,
                        'amount': str(invoice.total_amount),
                        'currency': invoice.currency,
                        'error': str(e)
                    }
                )
                await self._cache_invoice(invoice)
                raise

            # Record confidence score
            await self.metrics.record_confidence_score(match_result['confidence_score'])

            if match_result['matched']:
                await self._handle_matched_invoice(invoice)
            else:
                await self._handle_invoice_exception(invoice, match_result)

            # Record metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            await self.metrics.observe_processing_time(start_time)
            await self.metrics.observe_amount(float(invoice.total_amount))
            
            # Add history entry
            await self.processor_history.add_history_entry(
                invoice_number=invoice.invoice_number,
                status=invoice.status,
                confidence_score=match_result['confidence_score'],
                match_details=match_result['match_details'],
                processing_time=processing_time
            )
            
            # Cache invoice data
            await self._cache_invoice(invoice)

        except asyncio.TimeoutError as e:
            invoice.status = InvoiceStatus.EXCEPTION.value
            await self.metrics.record_error("timeout_error")
            await self.audit_logger.log_event(
                'invoice_exception',
                invoice,
                metadata={'exception_type': ['TIMEOUT'], 'description': [str(e)]}
            )
            await self.metrics.record_invoice_processed('exception')
            await self.notification_manager.send_notification(
                'invoice_exception',
                {
                    'invoice_number': invoice.invoice_number,
                    'vendor_name': invoice.vendor_name,
                    'amount': str(invoice.total_amount),
                    'currency': invoice.currency,
                    'error': str(e)
                }
            )
            await self._cache_invoice(invoice)
            raise
        except Exception as e:
            invoice.status = InvoiceStatus.EXCEPTION.value
            self.logger.error(
                f"Failed to process invoice {invoice.invoice_number}: {str(e)}"
            )
            await self.metrics.record_error("processing_error")
            await self.audit_logger.log_event(
                'invoice_exception',
                invoice,
                metadata={'exception_type': ['PROCESSING_ERROR'], 'description': [str(e)]}
            )
            await self.metrics.record_invoice_processed('exception')
            await self.notification_manager.send_notification(
                'invoice_exception',
                {
                    'invoice_number': invoice.invoice_number,
                    'vendor_name': invoice.vendor_name,
                    'amount': str(invoice.total_amount),
                    'currency': invoice.currency,
                    'error': str(e)
                }
            )
            await self._cache_invoice(invoice)
            raise

    async def _perform_three_way_match(self, invoice: Invoice) -> Dict[str, Any]:
        """Perform three-way match between invoice, PO, and goods receipt"""
        match_details = {
            "matched_fields": [],
            "mismatched_fields": [],
            "missing_fields": [],
            "confidence_scores": {}
        }
        
        # Check required fields
        required_fields = self.config.validation.REQUIRED_FIELDS
        for field in required_fields:
            if not self._check_field_exists(invoice, field):
                match_details["missing_fields"].append(field)
        
        # Get PO data
        po_data = await self.erp_connector.get_purchase_order(invoice.po_number)
        if not po_data:
            match_details["missing_fields"].append("po_number")
            return {
                'matched': False,
                'errors': ['PO not found or invalid'],
                'match_details': match_details,
                'confidence_score': 0.0
            }

        # Validate PO match
        po_match_result = self._validate_po_match(invoice, po_data)
        match_details.update(po_match_result["match_details"])
        match_details["confidence_scores"]["po_match"] = po_match_result["confidence_score"]

        # Get goods receipt
        gr_data = await self.erp_connector.get_goods_receipt(invoice.po_number)
        if not gr_data:
            match_details["missing_fields"].append("goods_receipt")
            return {
                'matched': False,
                'errors': ['Goods receipt not found or invalid'],
                'match_details': match_details,
                'confidence_score': po_match_result["confidence_score"] * 0.5
            }

        # Validate goods receipt match
        gr_match_result = self._validate_gr_match(invoice, gr_data)
        match_details.update(gr_match_result["match_details"])
        match_details["confidence_scores"]["gr_match"] = gr_match_result["confidence_score"]

        # Validate amounts
        amount_match_result = self._validate_amount_match(invoice, po_data, gr_data)
        match_details.update(amount_match_result["match_details"])
        match_details["confidence_scores"]["amount_match"] = amount_match_result["confidence_score"]

        # Calculate overall confidence score
        confidence_score = (
            match_details["confidence_scores"]["po_match"] * 0.4 +
            match_details["confidence_scores"]["gr_match"] * 0.3 +
            match_details["confidence_scores"]["amount_match"] * 0.3
        )

        is_matched = (
            len(match_details["mismatched_fields"]) == 0 and
            len(match_details["missing_fields"]) == 0 and
            confidence_score >= self.config.get("min_confidence_score", 0.8)
        )

        return {
            'matched': is_matched,
            'errors': [],
            'match_details': match_details,
            'confidence_score': confidence_score
        }

    def _validate_po_match(self, invoice: Invoice, po_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate invoice matches PO"""
        match_details = {
            "matched_fields": [],
            "mismatched_fields": [],
            "missing_fields": []
        }
        field_scores = {}

        # Check vendor match
        if 'vendor_id' not in po_data:
            match_details["missing_fields"].append("vendor_id")
            field_scores["vendor_match"] = 0.0
        elif invoice.vendor_id == po_data['vendor_id']:
            match_details["matched_fields"].append("vendor_id")
            field_scores["vendor_match"] = 1.0
        else:
            match_details["mismatched_fields"].append("vendor_id")
            field_scores["vendor_match"] = 0.0

        # Check line items
        if 'line_items' not in po_data:
            match_details["missing_fields"].append("line_items")
            field_scores["line_items_match"] = 0.0
        else:
            line_items_result = self._compare_line_items(invoice.line_items, po_data['line_items'])
            match_details.update(line_items_result["match_details"])
            field_scores["line_items_match"] = line_items_result["confidence_score"]

        # Calculate overall PO match confidence score
        confidence_score = (
            field_scores.get("vendor_match", 0.0) * 0.4 +
            field_scores.get("line_items_match", 0.0) * 0.6
        )

        return {
            "match_details": match_details,
            "confidence_score": confidence_score
        }

    def _validate_gr_match(self, invoice: Invoice, gr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate invoice matches goods receipt"""
        match_details = {
            "matched_fields": [],
            "mismatched_fields": [],
            "missing_fields": []
        }

        if 'line_items' not in gr_data:
            match_details["missing_fields"].append("line_items")
            return {
                "match_details": match_details,
                "confidence_score": 0.0
            }

        total_items = len(invoice.line_items)
        matched_items = 0

        for item in invoice.line_items:
            if self._compare_quantities(item, gr_data['line_items']):
                matched_items += 1
                match_details["matched_fields"].append(f"quantity_{item.sku}")
            else:
                match_details["mismatched_fields"].append(f"quantity_{item.sku}")

        confidence_score = matched_items / total_items if total_items > 0 else 0.0

        return {
            "match_details": match_details,
            "confidence_score": confidence_score
        }

    def _validate_amount_match(
        self,
        invoice: Invoice,
        po_data: Dict[str, Any],
        gr_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate amounts match within tolerance"""
        match_details = {
            "matched_fields": [],
            "mismatched_fields": [],
            "missing_fields": []
        }

        if 'total_amount' not in po_data:
            match_details["missing_fields"].append("total_amount")
            return {
                "match_details": match_details,
                "confidence_score": 0.0
            }

        tolerance = self.config.get('amount_tolerance', 0.01)
        po_amount = float(po_data['total_amount'])
        invoice_amount = float(invoice.total_amount)

        difference = abs(po_amount - invoice_amount)
        max_difference = po_amount * tolerance

        if difference <= max_difference:
            match_details["matched_fields"].append("total_amount")
            confidence_score = 1.0 - (difference / max_difference)
        else:
            match_details["mismatched_fields"].append("total_amount")
            confidence_score = 0.0

        return {
            "match_details": match_details,
            "confidence_score": confidence_score
        }

    def _compare_line_items(
        self,
        invoice_items: List[LineItem],
        po_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare invoice line items with PO items"""
        match_details = {
            "matched_fields": [],
            "mismatched_fields": [],
            "missing_fields": []
        }

        if len(invoice_items) != len(po_items):
            match_details["mismatched_fields"].append("line_items_count")
            return {
                "match_details": match_details,
                "confidence_score": 0.0
            }

        total_matches = 0
        total_fields = len(invoice_items) * 3  # SKU, quantity, and price for each item

        for inv_item in invoice_items:
            matching_po_item = next(
                (item for item in po_items if item.get('sku') == inv_item.sku),
                None
            )

            if not matching_po_item:
                match_details["missing_fields"].append(f"line_item_{inv_item.sku}")
                continue

            # Check quantity
            if 'quantity' not in matching_po_item:
                match_details["missing_fields"].append(f"quantity_{inv_item.sku}")
            elif inv_item.quantity == matching_po_item['quantity']:
                match_details["matched_fields"].append(f"quantity_{inv_item.sku}")
                total_matches += 1
            else:
                match_details["mismatched_fields"].append(f"quantity_{inv_item.sku}")

            # Check unit price
            if 'unit_price' not in matching_po_item:
                match_details["missing_fields"].append(f"unit_price_{inv_item.sku}")
            else:
                tolerance = self.config.get('price_tolerance', 0.01)
                price_diff = abs(float(inv_item.unit_price) - float(matching_po_item['unit_price']))
                if price_diff <= float(matching_po_item['unit_price']) * tolerance:
                    match_details["matched_fields"].append(f"unit_price_{inv_item.sku}")
                    total_matches += 1
                else:
                    match_details["mismatched_fields"].append(f"unit_price_{inv_item.sku}")

            # SKU matched
            total_matches += 1

        confidence_score = total_matches / total_fields if total_fields > 0 else 0.0

        return {
            "match_details": match_details,
            "confidence_score": confidence_score
        }

    def _check_field_exists(self, invoice: Invoice, field: str) -> bool:
        """Check if a field exists and has a non-None value"""
        try:
            if "." in field:
                obj_name, field_name = field.split(".")
                obj = getattr(invoice, obj_name)
                return hasattr(obj, field_name) and getattr(obj, field_name) is not None
            return hasattr(invoice, field) and getattr(invoice, field) is not None
        except Exception:
            return False

    async def _handle_matched_invoice(self, invoice: Invoice):
        """Handle a matched invoice"""
        try:
            # Convert invoice to dict
            invoice_data = {
                'invoice_number': invoice.invoice_number,
                'vendor_id': invoice.vendor_id,
                'vendor_name': invoice.vendor_name,
                'po_number': invoice.po_number,
                'total_amount': str(invoice.total_amount),
                'currency': invoice.currency,
                'line_items': [
                    {
                        'sku': item.sku,
                        'description': item.description,
                        'quantity': item.quantity,
                        'unit_price': str(item.unit_price),
                        'total': str(item.total)
                    }
                    for item in invoice.line_items
                ]
            }
            
            # Schedule payment
            payment_date = await self.erp_connector.schedule_payment(invoice_data)
            if payment_date:
                invoice.status = InvoiceStatus.SCHEDULED.value
                await self.audit_logger.log_event(
                    'invoice_status_change',
                    invoice,
                    metadata={'status': invoice.status}
                )
                await self.metrics.record_invoice_processed('matched')
                await self.notification_manager.send_notification(
                    'invoice_matched',
                    {
                        'invoice_number': invoice.invoice_number,
                        'vendor_name': invoice.vendor_name,
                        'amount': str(invoice.total_amount),
                        'currency': invoice.currency,
                        'payment_date': payment_date.isoformat()
                    }
                )
            else:
                await self._handle_invoice_exception(invoice, {'errors': ['Failed to schedule payment']})
        except Exception as e:
            await self._handle_invoice_exception(invoice, {'errors': [str(e)]})

    async def _handle_invoice_exception(self, invoice: Invoice, match_result: dict):
        """Handle an invoice exception"""
        invoice.status = InvoiceStatus.EXCEPTION.value
        await self.audit_logger.log_event(
            'invoice_exception',
            invoice,
            metadata={'exception_type': ['PO_MISMATCH'], 'description': ['Purchase order details do not match']}
        )
        await self.metrics.record_error("processing_error")
        await self.metrics.record_invoice_processed('exception')
        await self.notification_manager.send_notification(
            'invoice_exception',
            {
                'invoice_number': invoice.invoice_number,
                'vendor_name': invoice.vendor_name,
                'amount': str(invoice.total_amount),
                'currency': invoice.currency,
                'errors': match_result.get('errors', [])
            }
        )

    async def _is_duplicate_invoice(self, invoice: Invoice) -> bool:
        """Check if invoice is a duplicate"""
        # In a real implementation, this would check against a database
        # For now, we'll just return False
        return False

    def _create_exception_details(
        self,
        invoice: Invoice,
        match_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create detailed exception information"""
        return {
            'invoice_number': invoice.invoice_number,
            'vendor_id': invoice.vendor_id,
            'po_number': invoice.po_number,
            'exception_type': match_result.get('errors', []),
            'timestamp': datetime.now().isoformat(),
            'amount': str(invoice.total_amount),
            'currency': invoice.currency
        }

    def _should_contact_vendor(self, exception_details: Dict[str, Any]) -> bool:
        """Determine if vendor should be contacted"""
        critical_errors = [
            'Amount mismatch',
            'PO not found',
            'Invalid quantities'
        ]
        return any(
            error in critical_errors
            for error in exception_details['exception_type']
        )

    async def _send_vendor_communication(
        self,
        invoice: Invoice,
        exception_details: Dict[str, Any]
    ):
        """Send communication to vendor"""
        if not invoice.vendor_email:
            return

        await self.notification_manager.send_notification(
            'vendor_communication',
            {
                'invoice_number': invoice.invoice_number,
                'vendor_name': invoice.vendor_name,
                'exception_details': exception_details,
                'action_required': True
            },
            [invoice.vendor_email]
        )

    def _compare_quantities(
        self,
        invoice_item: LineItem,
        gr_items: List[Dict[str, Any]]
    ) -> bool:
        """Compare invoice quantities with goods receipt"""
        received_quantity = sum(
            item.get('quantity', 0)
            for item in gr_items
            if item.get('sku') == invoice_item.sku
        )
        return invoice_item.quantity <= received_quantity

    async def process_invoice(self, invoice: Invoice) -> WorkflowResult:
        """Process an invoice and return the result"""
        try:
            # Load JSON sidecar file
            sidecar_path = Path(invoice.file_path + '.json')
            if not sidecar_path.exists():
                return WorkflowResult(
                    success=False,
                    error_message=f"JSON sidecar file not found: {sidecar_path}"
                )
            
            # Read JSON data
            with sidecar_path.open() as f:
                invoice_data = json.load(f)
            
            # Validate required fields
            missing_fields = []
            for field in self.config.validation.REQUIRED_FIELDS:
                if not self._get_nested_value(invoice_data, field):
                    missing_fields.append(field)
            
            if missing_fields:
                return WorkflowResult(
                    success=False,
                    error_message=f"Missing required fields: {', '.join(missing_fields)}"
                )
            
            # Process the invoice (in a real system, this would do more)
            # For now, we'll just return success if all required fields are present
            return WorkflowResult(
                success=True,
                data={
                    'invoice_number': invoice_data['invoice_number'],
                    'total_amount': invoice_data['total_amount'],
                    'vendor': invoice_data['vendor_info']['name']
                }
            )
        
        except Exception as e:
            logger.error(f"Error processing invoice {invoice.workflow_id}: {str(e)}")
            return WorkflowResult(
                success=False,
                error_message=str(e)
            )
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Optional[Any]:
        """Get a value from a nested dictionary using dot notation"""
        keys = key_path.split('.')
        value = data
        
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        
        return value

async def main():
    """Main entry point for the workflow processor service"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('workflow.log'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    # Initialize dependencies
    from invoice_agent.config.settings import enterprise_config
    from invoice_agent.document.processor import DocumentProcessor
    from invoice_agent.erp.connector import MockERPConnector
    from invoice_agent.notification.manager import NotificationManager
    from invoice_agent.utils.audit_logger import audit_logger
    from invoice_agent.metrics.collector import MetricsCollector
    from invoice_agent.source.manager import SourceManager
    from invoice_agent.history.processor_history import processor_history
    
    # Initialize processor
    processor = EnhancedInvoiceWorkflowProcessor(
        source_manager=SourceManager(),
        document_processor=DocumentProcessor(),
        erp_connector=MockERPConnector(),
        notification_manager=NotificationManager(),
        audit_logger=audit_logger,
        metrics=MetricsCollector(),
        config=enterprise_config,
        processor_history=processor_history
    )
    
    logger.info("Starting workflow processor service...")
    
    try:
        # Run the processor
        await processor.process_new_invoices()
        logger.info("Workflow processor service completed successfully")
    except Exception as e:
        logger.error(f"Workflow processor service failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 