from fastapi import FastAPI, Request
from infrastructure.middleware import LoggingMiddleware
from infrastructure.dependencies import setup_dependencies
from infrastructure.config import config
from logging_config import setup_logging

# Setup logging
logger = setup_logging(config.SERVICE_NAME, config.LOG_LEVEL)

# Initialize FastAPI app
app = FastAPI(title=config.APP_TITLE, version=config.APP_VERSION)

# Add middleware
app.add_middleware(LoggingMiddleware)

# Setup dependencies
controller = setup_dependencies()

# Routes
@app.post("/run")
async def run_ad_campaign(request: Request):
    """Generate a complete advertisement with copy and image"""
    return await controller.generate_campaign(request)

@app.get("/download/{filename}")
async def download_image(filename: str, request: Request):
    """Proxy endpoint to download images from image-generator service"""
    return await controller.download_image(filename, request)

@app.get("/download-video/{filename}")
async def download_video(filename: str, request: Request):
    """Proxy endpoint to download videos from video-generator service"""
    return await controller.download_video(filename, request)
