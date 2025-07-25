from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from diffusers import (
    StableDiffusionXLPipeline,
    StableDiffusionXLImg2ImgPipeline,
    EulerAncestralDiscreteScheduler
)
from PIL import Image, ImageDraw, ImageFont
import torch, uuid, os, time, threading
from transformers import CLIPTokenizer
from logging_config import (
    setup_logging, TimingContext, generate_request_id, request_id,
    log_gpu_usage, log_image_generation_metrics
)

# Setup structured logging
logger = setup_logging("image-generator", "INFO")

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate and set request ID
        req_id = generate_request_id()
        request_id.set(req_id)
        
        # Log request details
        client_ip = request.client.host if request.client else "unknown"
        logger.info("HTTP request received", extra={
            "method": request.method,
            "path": str(request.url.path),
            "client_ip": client_ip,
            "event": "http_request"
        })
        
        # Start timing
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response details
        logger.info("HTTP response sent", extra={
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "event": "http_response"
        })
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = req_id
        
        return response

app = FastAPI(title="AI Advertisement Generator - Image Generator", version="1.0.0")
app.add_middleware(LoggingMiddleware)

# Log service startup
logger.info("Image generator service starting up")
# Initialize CLIP tokenizer
with TimingContext("clip_tokenizer_init", logger):
    clip_tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-base-patch32")
    logger.info("CLIP tokenizer loaded successfully")

# Create images directory if it doesn't exist
IMAGES_DIR = "/tmp/images"
os.makedirs(IMAGES_DIR, exist_ok=True)
logger.info("Images directory created", extra={"directory": IMAGES_DIR})

# Mount static files for serving images
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# Dictionary to track image creation times for cleanup
image_timestamps = {}

# Load SDXL base model
logger.info("Loading SDXL base model...")
with TimingContext("sdxl_base_model_loading", logger):
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "playgroundai/playground-v2-1024px-aesthetic",
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True
    ).to("cuda")
    
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    logger.info("SDXL base model loaded successfully")
    log_gpu_usage(logger, "after_base_model_load")

# Load SDXL refiner
logger.info("Loading SDXL refiner model...")
with TimingContext("sdxl_refiner_model_loading", logger):
    refiner = StableDiffusionXLImg2ImgPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-refiner-1.0",
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True
    ).to("cuda")
    logger.info("SDXL refiner model loaded successfully")
    log_gpu_usage(logger, "after_refiner_model_load")

logger.info("Image generator service ready")


# Input model
class ImagePrompt(BaseModel):
    product_name: str
    features: list[str]
    brand_text: str
    cta_text: str
    scene: str


# Utility: add branding/CTA overlays
def add_overlay(image: Image.Image, brand: str, product: str, cta: str) -> Image.Image:
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    font_brand = ImageFont.truetype(font_path, 36)
    font_product = ImageFont.truetype(font_path, 28)
    font_cta = ImageFont.truetype(font_path, 24)

    # Top-left: brand and product
    draw.text((30, 20), brand, fill="blue", font=font_brand)
    draw.text((30, 70), product, fill="orange", font=font_product)

    # Bottom-left: CTA
    draw.text((30, image.height - 50), cta, fill="black", font=font_cta)
    draw.text((image.width - (image.width * 0.5), image.height - 50), "AI Generated", font=font_cta)

    return image

def trim_prompt(prompt: str, max_tokens: int = 77) -> str:
    tokens = clip_tokenizer(prompt, truncation=True, max_length=max_tokens, return_tensors="pt")
    decoded = clip_tokenizer.decode(tokens["input_ids"][0], skip_special_tokens=True)
    return decoded

def cleanup_image(image_path: str, filename: str):
    """Delete image file after 10 minutes"""
    time.sleep(600)  # 10 minutes = 600 seconds
    try:
        if os.path.exists(image_path):
            os.remove(image_path)
            logger.info("Image cleaned up successfully", extra={
                "filename": filename,
                "image_path": image_path
            })
        # Remove from tracking dictionary
        if filename in image_timestamps:
            del image_timestamps[filename]
    except Exception as e:
        logger.error("Error cleaning up image", extra={
            "filename": filename,
            "image_path": image_path,
            "error": str(e)
        })

def schedule_cleanup(image_path: str, filename: str):
    """Schedule image cleanup in a background thread"""
    cleanup_thread = threading.Thread(target=cleanup_image, args=(image_path, filename))
    cleanup_thread.daemon = True
    cleanup_thread.start()
    logger.info("Image cleanup scheduled", extra={
        "filename": filename,
        "cleanup_in_seconds": 600
    })

@app.post("/generate")
def generate_ad(data: ImagePrompt):
    """Generate advertisement image with text overlays"""
    timer = None
    try:
        with TimingContext("image_generation_full", logger) as timer:
            logger.info("Image generation request received", extra={
                "product_name": data.product_name,
                "features_count": len(data.features),
                "scene_length": len(data.scene),
                "brand_text": data.brand_text[:50] + "..." if len(data.brand_text) > 50 else data.brand_text,
                "cta_text": data.cta_text[:50] + "..." if len(data.cta_text) > 50 else data.cta_text
            })
            
            log_gpu_usage(logger, "before_generation")
            # 1. Build the prompt
            with TimingContext("prompt_building", logger):
                prompt = (f"{data.scene}")
                prompt = trim_prompt(prompt)
                logger.info("Prompt prepared", extra={
                    "original_scene_length": len(data.scene),
                    "trimmed_prompt_length": len(prompt),
                    "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt
                })

            # 2. Generate base image with retries
            with TimingContext("base_image_generation", logger) as base_timer:
                base_image = None
                for attempt in range(3):
                    try:
                        logger.info(f"Base image generation attempt {attempt + 1}", extra={
                            "attempt": attempt + 1,
                            "max_attempts": 3
                        })
                        
                        log_image_generation_metrics(
                            logger, 1024, 1024, 40, 7.5, "playground-v2-1024px-aesthetic"
                        )
                        
                        base_image = pipe(prompt, guidance_scale=7.5, num_inference_steps=40).images[0]
                        logger.info("Base image generated successfully", extra={
                            "attempt": attempt + 1,
                            "duration_ms": round(base_timer.duration_ms, 2)
                        })
                        break
                    except Exception as e:
                        logger.warning(f"Base image generation attempt {attempt + 1} failed", extra={
                            "attempt": attempt + 1,
                            "error": str(e),
                            "duration_ms": round(base_timer.duration_ms, 2) if base_timer else None
                        })
                        if attempt == 2:
                            logger.error("All base image generation attempts failed")
                            raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")
                        time.sleep(1)
                        
                if base_image is None:
                    raise HTTPException(status_code=500, detail="Failed to generate base image")

            log_gpu_usage(logger, "after_base_generation")

            # 3. Refine image
            with TimingContext("image_refinement", logger):
                logger.info("Starting image refinement")
                final_image = refiner(
                    prompt=prompt,
                    image=base_image,
                    strength=0.3,
                    guidance_scale=7.5,
                    num_inference_steps=20
                ).images[0]
                logger.info("Image refinement completed")

            log_gpu_usage(logger, "after_refinement")

            # 4. Add brand/CTA overlay
            with TimingContext("overlay_addition", logger):
                logger.info("Adding brand and CTA overlays")
                branded_image = add_overlay(final_image, data.brand_text, data.product_name, data.cta_text)

            # 5. Save and return download URL
            with TimingContext("image_saving", logger):
                filename = f"{uuid.uuid4()}.png"
                file_path = os.path.join(IMAGES_DIR, filename)
                branded_image.save(file_path)
                
                # Get file size for logging
                file_size = os.path.getsize(file_path)
                
                logger.info("Image saved successfully", extra={
                    "filename": filename,
                    "file_path": file_path,
                    "file_size_bytes": file_size,
                    "file_size_mb": round(file_size / 1024 / 1024, 2)
                })
                
                # Track creation time and schedule cleanup
                image_timestamps[filename] = time.time()
                schedule_cleanup(file_path, filename)

            logger.info("Image generation completed successfully", extra={
                "filename": filename,
                "total_duration_ms": round(timer.duration_ms, 2),
                "file_size_mb": round(file_size / 1024 / 1024, 2)
            })

            return {
                "filename": filename,
                "download_url": f"/download/{filename}",
                "expires_in_minutes": 10
            }
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error("Unexpected error during image generation", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(timer.duration_ms, 2) if timer else None
        })
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

@app.get("/download/{filename}")
def download_image(filename: str, request: Request):
    """Download endpoint for generated images"""
    with TimingContext("image_download", logger, {"filename": filename}):
        client_ip = request.client.host if request.client else "unknown"
        logger.info("Image download request", extra={
            "filename": filename,
            "client_ip": client_ip
        })
        
        file_path = os.path.join(IMAGES_DIR, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.warning("Image file not found", extra={
                "filename": filename,
                "file_path": file_path,
                "client_ip": client_ip
            })
            raise HTTPException(status_code=404, detail="Image not found or has expired")
        
        # Check if image has expired (more than 10 minutes old)
        if filename in image_timestamps:
            creation_time = image_timestamps[filename]
            elapsed_time = time.time() - creation_time
            if elapsed_time > 600:  # 10 minutes
                logger.info("Image has expired, cleaning up", extra={
                    "filename": filename,
                    "elapsed_minutes": round(elapsed_time / 60, 1),
                    "client_ip": client_ip
                })
                # Clean up expired image
                try:
                    os.remove(file_path)
                    del image_timestamps[filename]
                except Exception as e:
                    logger.error("Error removing expired image", extra={
                        "filename": filename,
                        "error": str(e)
                    })
                raise HTTPException(status_code=404, detail="Image has expired")
        
        # Get file size for logging
        try:
            file_size = os.path.getsize(file_path)
            logger.info("Image download successful", extra={
                "filename": filename,
                "client_ip": client_ip,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / 1024 / 1024, 2)
            })
        except Exception as e:
            logger.error("Error getting file size", extra={
                "filename": filename,
                "error": str(e)
            })
            file_size = 0
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(file_size)
            }
        )

@app.get("/status/{filename}")
def check_image_status(filename: str):
    """Check if an image is still available"""
    file_path = os.path.join(IMAGES_DIR, filename)
    
    if not os.path.exists(file_path):
        return {"status": "not_found", "message": "Image not found or has expired"}
    
    if filename in image_timestamps:
        creation_time = image_timestamps[filename]
        elapsed_time = time.time() - creation_time
        remaining_time = max(0, 600 - elapsed_time)  # 10 minutes = 600 seconds
        
        if remaining_time > 0:
            return {
                "status": "available",
                "remaining_minutes": round(remaining_time / 60, 1),
                "download_url": f"/download/{filename}"
            }
        else:
            return {"status": "expired", "message": "Image has expired"}
    
    return {"status": "unknown", "message": "Image status unknown"}

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "image-generator"}

