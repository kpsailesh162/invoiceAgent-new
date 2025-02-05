from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from decimal import Decimal

Base = declarative_base()

class ProcessedInvoice(Base):
    __tablename__ = 'processed_invoices'
    
    id = Column(Integer, primary_key=True)
    invoice_number = Column(String(50), unique=True)
    date = Column(DateTime, nullable=False)
    vendor_name = Column(String(255))
    total_amount = Column(Numeric(precision=10, scale=2))
    status = Column(String(50))  # 'processed', 'failed', 'pending'
    processed_at = Column(DateTime, default=datetime.utcnow)
    connector_type = Column(String(50))
    raw_data = Column(JSON)  # Store original invoice data
    line_items = relationship("ProcessedLineItem", back_populates="invoice")

class ProcessedLineItem(Base):
    __tablename__ = 'processed_line_items'
    
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey('processed_invoices.id'))
    description = Column(String(255))
    quantity = Column(Numeric(precision=10, scale=2))
    unit_price = Column(Numeric(precision=10, scale=2))
    total = Column(Numeric(precision=10, scale=2))
    invoice = relationship("ProcessedInvoice", back_populates="line_items")

class InvoiceTemplate(Base):
    """Invoice template model"""
    __tablename__ = 'invoice_template'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    vendor_name = Column(String(255))
    field_mappings = Column(JSON)  # Store field mappings
    validation_rules = Column(JSON)  # Store validation rules
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow) 