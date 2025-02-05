from typing import Dict, Any, Optional
import traceback
import logging
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class ErrorHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def handle_exception(
        self,
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        error_id = self._generate_error_id()
        
        if isinstance(exc, HTTPException):
            return self._handle_http_exception(exc, error_id)
        
        # Log unexpected errors
        self.logger.error(
            f"Unhandled error {error_id}: {str(exc)}",
            exc_info=True,
            extra={
                'error_id': error_id,
                'path': request.url.path,
                'method': request.method,
                'traceback': traceback.format_exc()
            }
        )
        
        return JSONResponse(
            status_code=500,
            content=ErrorDetail(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred",
                details={'error_id': error_id}
            ).dict()
        ) 