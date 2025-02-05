from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import json
from prometheus_client import start_http_server
from ..config.app_config import get_settings, AppSettings
from ..monitoring.metrics import MetricsCollector
from ..middleware.rate_limit import RateLimiter
from ..errors.handler import ErrorHandler
from ..cache.manager import CacheManager
from ..queue.worker import TaskQueue
from ..integrations.manager import SourceManager
from fastapi import BackgroundTasks
import logging

def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.API_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize components
    metrics = MetricsCollector()
    rate_limiter = RateLimiter(
        requests_per_minute=settings.API_RATE_LIMIT,
        burst_size=10
    )
    error_handler = ErrorHandler()
    cache_manager = CacheManager()
    task_queue = TaskQueue(
        max_workers=settings.MAX_WORKERS
    )
    
    # Start metrics server
    if settings.ENABLE_METRICS:
        start_http_server(settings.METRICS_PORT)
    
    # Initialize source manager
    source_manager = SourceManager(settings.dict())
    
    @app.on_event("startup")
    async def startup():
        # Start background tasks
        await task_queue.start()
    
    @app.on_event("shutdown")
    async def shutdown():
        # Cleanup
        await task_queue.stop()
    
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        await rate_limiter.check_rate_limit(request)
        return await call_next(request)
    
    # Add error handlers
    app.exception_handler(Exception)(error_handler.handle_exception)
    
    return app

app = create_app()

class LineItemSchema(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    total: Decimal
    tax_rate: Optional[Decimal]
    tax_amount: Optional[Decimal]
    product_code: Optional[str]

class InvoiceSchema(BaseModel):
    invoice_number: str
    date: datetime
    vendor_name: str
    total_amount: Decimal
    currency: str
    line_items: List[LineItemSchema]

@app.post("/api/v1/invoices/process")
async def process_invoice(invoice: InvoiceSchema):
    try:
        # Convert Pydantic model to Invoice class instance
        from ..core.data_model import Invoice, LineItem
        invoice_obj = Invoice(
            invoice_number=invoice.invoice_number,
            date=invoice.date,
            vendor_name=invoice.vendor_name,
            total_amount=invoice.total_amount,
            currency=invoice.currency,
            line_items=[
                LineItem(**item.dict())
                for item in invoice.line_items
            ]
        )
        
        # Process invoice
        from ..agent import InvoiceAgent
        agent = InvoiceAgent("config.yaml")
        result = agent.process_invoice(invoice_obj)
        
        if not result['success']:
            raise HTTPException(
                status_code=400,
                detail=result['errors']
            )
        
        return {"message": "Invoice processed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/api/v1/invoices/upload")
async def upload_invoice(file: UploadFile = File(...)):
    try:
        # Process uploaded file (PDF/Image)
        from ..ml.ocr import extract_invoice_data
        invoice_data = await extract_invoice_data(file)
        return invoice_data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/api/v1/sources/fetch")
async def fetch_from_sources(
    since: datetime = None,
    background_tasks: BackgroundTasks = None
):
    """Fetch invoices from all configured sources"""
    try:
        # Default to last 24 hours if no date provided
        since = since or datetime.utcnow() - timedelta(days=1)
        
        # Fetch invoices in background
        background_tasks.add_task(
            process_source_invoices,
            since
        )
        
        return {
            "message": "Invoice fetch started",
            "since": since
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch invoices: {str(e)}"
        )

async def process_source_invoices(since: datetime):
    """Process invoices from all sources"""
    try:
        invoices = await source_manager.fetch_all_invoices(since)
        
        # Process each invoice
        for invoice in invoices:
            await task_queue.enqueue(
                agent.process_invoice,
                invoice
            )
    except Exception as e:
        logger.error(f"Failed to process source invoices: {str(e)}") 