"""
FastAPI Backend for Watermarking Service
Integrates invisible-text-watermark library with frontend
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import local packages
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from typing import Optional

# Import the watermarking library
try:
    from invisible_text_watermark import Watermarker
    print("✓ Successfully imported invisible_text_watermark")
except ImportError as e:
    print(f"✗ Failed to import invisible_text_watermark: {e}")
    print("Installing from local path...")
    sys.path.insert(0, str(Path(__file__).parent.parent / "invisible-text-watermark" / "src"))
    from invisible_text_watermark import Watermarker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Watermark Service API",
    description="API for embedding and detecting invisible text watermarks",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize watermarker with default config
watermarker = Watermarker(
    issuer_id=1,
    model_id=42,
    key_id=1
)

# Request/Response models
class WatermarkRequest(BaseModel):
    text: str
    issuer_id: Optional[int] = 1
    model_id: Optional[int] = 42
    key_id: Optional[int] = 1


class WatermarkResponse(BaseModel):
    watermarked_text: str
    success: bool


class DetectRequest(BaseModel):
    text: str


class DetectResponse(BaseModel):
    is_watermarked: bool
    payloads: Optional[list] = None
    confidence_score: float
    message: str


class StripRequest(BaseModel):
    text: str


class StripResponse(BaseModel):
    clean_text: str
    success: bool


# Routes
@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "watermark-api"}


@app.post("/api/watermark/embed", response_model=WatermarkResponse)
async def embed_watermark(request: WatermarkRequest):
    """
    Embed invisible watermark into text
    
    Args:
        text: The text to watermark
        issuer_id: Issuer ID (default: 1)
        model_id: Model ID (default: 42) 
        key_id: Key ID (default: 1)
    
    Returns:
        Watermarked text and success status
    """
    try:
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Create watermarker with specified config
        wm = Watermarker(
            issuer_id=request.issuer_id,
            model_id=request.model_id,
            key_id=request.key_id
        )
        
        watermarked = wm.apply(request.text)
        
        logger.info(f"Successfully watermarked text of length {len(request.text)}")
        
        return WatermarkResponse(
            watermarked_text=watermarked,
            success=True
        )
    except Exception as e:
        logger.error(f"Watermarking failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/watermark/detect", response_model=DetectResponse)
async def detect_watermark(request: DetectRequest):
    """
    Detect if text contains invisible watermark
    
    Args:
        text: The text to analyze
    
    Returns:
        Detection result with confidence score
    """
    try:
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        result = watermarker.detect(request.text)
        
        # Calculate confidence score based on detection
        confidence = 95.0 if result.watermarked else 5.0
        
        message = ""
        if result.watermarked:
            message = f"Watermark detected with {len(result.payloads)} payload(s)"
        else:
            message = "No watermark detected in the provided text"
        
        logger.info(f"Detection completed: watermarked={result.watermarked}")
        
        return DetectResponse(
            is_watermarked=result.watermarked,
            payloads=result.payloads if result.watermarked else None,
            confidence_score=confidence,
            message=message
        )
    except Exception as e:
        logger.error(f"Detection failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/watermark/strip", response_model=StripResponse)
async def strip_watermark(request: StripRequest):
    """
    Remove watermark from text
    
    Args:
        text: The watermarked text
    
    Returns:
        Clean text without watermark
    """
    try:
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        clean_text = Watermarker.strip(request.text)
        
        logger.info(f"Successfully stripped watermark from text of length {len(request.text)}")
        
        return StripResponse(
            clean_text=clean_text,
            success=True
        )
    except Exception as e:
        logger.error(f"Strip failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Status endpoint for monitoring
@app.get("/api/status")
async def status():
    """Get service status"""
    return {
        "status": "running",
        "service": "watermark-api",
        "version": "1.0.0",
        "watermark_config": {
            "issuer_id": watermarker.cfg.issuer_id,
            "model_id": watermarker.cfg.model_id,
            "key_id": watermarker.cfg.active_key_id
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
