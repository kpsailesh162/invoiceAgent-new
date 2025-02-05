from contextlib import contextmanager
from typing import Optional, List, Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base, ProcessedInvoice, ProcessedLineItem, InvoiceTemplate
from ..config.settings import config

class DatabaseManager:
    def __init__(self):
        """Initialize database connection"""
        self.engine = create_engine(config.database_url)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    def get_template_by_vendor(self, vendor_name: str) -> Optional[InvoiceTemplate]:
        """Get template by vendor name"""
        with self.session_scope() as session:
            return session.query(InvoiceTemplate).filter(
                InvoiceTemplate.vendor_name == vendor_name
            ).first()

    def get_template_by_name(self, template_name: str) -> Optional[InvoiceTemplate]:
        """Get template by name"""
        with self.session_scope() as session:
            return session.query(InvoiceTemplate).filter(
                InvoiceTemplate.name == template_name
            ).first()

    def save_template(self, template_data: dict) -> InvoiceTemplate:
        """Save template to database"""
        with self.session_scope() as session:
            template = InvoiceTemplate(
                name=template_data['name'],
                vendor_name=template_data['vendor_name'],
                field_mappings=template_data['field_mappings'],
                validation_rules=template_data.get('validation_rules', {})
            )
            session.add(template)
            session.commit()
            return template

    def update_template(self, template_id: int, template_data: dict) -> Optional[InvoiceTemplate]:
        """Update existing template"""
        with self.session_scope() as session:
            template = session.query(InvoiceTemplate).filter(
                InvoiceTemplate.id == template_id
            ).first()
            if template:
                template.name = template_data.get('name', template.name)
                template.vendor_name = template_data.get('vendor_name', template.vendor_name)
                template.field_mappings = template_data.get('field_mappings', template.field_mappings)
                template.validation_rules = template_data.get('validation_rules', template.validation_rules)
                session.commit()
            return template

    def delete_template(self, template_id: int) -> bool:
        """Delete template by ID"""
        with self.session_scope() as session:
            template = session.query(InvoiceTemplate).filter(
                InvoiceTemplate.id == template_id
            ).first()
            if template:
                session.delete(template)
                session.commit()
                return True
            return False

    def list_templates(self) -> List[InvoiceTemplate]:
        """List all templates"""
        with self.session_scope() as session:
            return session.query(InvoiceTemplate).all()

    def save_processed_invoice(self, invoice_data: dict) -> ProcessedInvoice:
        """Save processed invoice to database"""
        with self.session_scope() as session:
            invoice = ProcessedInvoice(
                invoice_number=invoice_data['invoice_number'],
                date=invoice_data['date'],
                vendor_name=invoice_data['vendor_name'],
                total_amount=invoice_data['total_amount'],
                status=invoice_data['status'],
                connector_type=invoice_data['connector_type'],
                raw_data=invoice_data['raw_data']
            )
            session.add(invoice)
            
            # Add line items if present
            if 'line_items' in invoice_data:
                for item_data in invoice_data['line_items']:
                    line_item = ProcessedLineItem(
                        description=item_data['description'],
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        total=item_data['total']
                    )
                    invoice.line_items.append(line_item)
            
            session.commit()
            return invoice

    def get_processed_invoice(self, invoice_id: int) -> Optional[ProcessedInvoice]:
        """Get processed invoice by ID"""
        with self.session_scope() as session:
            return session.query(ProcessedInvoice).filter(
                ProcessedInvoice.id == invoice_id
            ).first()

    def list_processed_invoices(self) -> List[ProcessedInvoice]:
        """List all processed invoices"""
        with self.session_scope() as session:
            return session.query(ProcessedInvoice).all()

    def update_invoice_status(self, invoice_id: int, status: str) -> bool:
        """Update invoice status"""
        with self.session_scope() as session:
            invoice = session.query(ProcessedInvoice).filter(
                ProcessedInvoice.id == invoice_id
            ).first()
            if invoice:
                invoice.status = status
                session.commit()
                return True
            return False 