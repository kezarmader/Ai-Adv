from fastapi import FastAPI, Request
from infrastructure.middleware import LoggingMiddleware
from infrastructure.dependencies import setup_dependencies
from infrastructure.config import config
from infrastructure.prompts import prompt_config
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

@app.get("/admin/prompts")
async def list_prompt_templates():
    """List available LLM prompt templates (admin endpoint)"""
    return {
        "current_template": config.LLM_PROMPT_TEMPLATE,
        "available_templates": prompt_config.list_available_templates(),
        "custom_template_configured": bool(config.LLM_CUSTOM_PROMPT)
    }
