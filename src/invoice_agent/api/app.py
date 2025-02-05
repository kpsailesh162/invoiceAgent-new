from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
import uuid
from pathlib import Path
import shutil
import logging
from typing import List
from datetime import datetime

from ..config.settings import config
from ..models import WorkflowStatus, InvoiceStatus
from ..database import Database
from ..workflow.service import WorkflowProcessorService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Invoice Processing API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for UI
static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Serve index.html at root
@app.get("/")
async def read_root():
    return FileResponse(str(static_dir / "index.html"))

# Initialize database connection
db = None

@app.on_event("startup")
async def startup_event():
    """Start the workflow processor service when the API starts"""
    global db
    try:
        db = Database(config.DB_CONFIG)
        await db.connect()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        logger.warning("Application will start without database connection")
    
    try:
        app.state.workflow_service = await WorkflowProcessorService.create_and_start()
        logger.info("Workflow processor service started")
    except Exception as e:
        logger.error(f"Failed to start workflow service: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop the workflow processor service when the API shuts down"""
    if hasattr(app.state, 'workflow_service'):
        await app.state.workflow_service.stop()

async def get_db():
    """Get database connection, attempting to reconnect if necessary"""
    global db
    if db is None:
        db = Database(config.DB_CONFIG)
    try:
        if not db.pool:
            await db.connect()
        return db
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=503, detail="Database service unavailable")

@app.post("/api/v1/invoices/upload")
async def upload_invoice(file: UploadFile = File(...)):
    """Handle invoice file upload"""
    try:
        # Generate unique workflow ID
        workflow_id = str(uuid.uuid4())
        
        # Save file to upload directory
        config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        file_path = Path(config.UPLOAD_DIR) / f"{workflow_id}_{file.filename}"
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create database entry
        try:
            database = await get_db()
            await database.create_invoice_entry({
                'workflow_id': workflow_id,
                'filename': file.filename,
                'file_path': str(file_path),
                'status': InvoiceStatus.PENDING,
                'upload_time': datetime.utcnow()
            })
        except HTTPException as e:
            if e.status_code == 503:  # Database unavailable
                logger.warning("Database unavailable, proceeding with file upload only")
        
        return JSONResponse({
            'workflow_id': workflow_id,
            'message': 'Invoice uploaded successfully'
        })
    
    except Exception as e:
        logger.error(f"Error uploading invoice: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/invoices/{workflow_id}/status")
async def get_invoice_status(workflow_id: str):
    """Get the status of a workflow"""
    try:
        database = await get_db()
        status = await database.get_workflow_status(workflow_id)
        if not status:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        return JSONResponse({
            'workflow_id': workflow_id,
            'status': status.value,
            'error_message': status.error_message if hasattr(status, 'error_message') else None
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/invoices")
async def list_invoices():
    """List all invoices and their statuses"""
    try:
        database = await get_db()
        invoices = await database.get_all_invoices()
        return JSONResponse({
            'invoices': [
                {
                    'workflow_id': inv.workflow_id,
                    'filename': inv.filename,
                    'status': inv.status.value,
                    'upload_time': inv.upload_time.isoformat(),
                    'error_message': inv.error_message if hasattr(inv, 'error_message') else None
                }
                for inv in invoices
            ]
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing invoices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 