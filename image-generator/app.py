from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
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
logger = setup_logging("image-generator", "INFO" )

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
IMAGES_DIR = "/app/images"
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
    trending_boost: bool = False      # Flag for trending mode
    trending_topic: str = ""          # Full trending topic
    trending_keywords: list[str] = [] # Key words from trend for visual emphasis
    hook_mode: bool = False           # Flag for hook-focused generation


# Utility: add branding/CTA overlays with enhanced readability
def add_overlay(image: Image.Image, brand: str, product: str, cta: str) -> Image.Image:
    # Create a new image for overlay with alpha channel
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    font_brand = ImageFont.truetype(font_path, 42)
    font_product = ImageFont.truetype(font_path, 32)
    font_cta = ImageFont.truetype(font_path, 28)
    font_ai = ImageFont.truetype(font_path, 20)

    # Helper function to draw text with background box
    def draw_text_with_background(draw, position, text, font, text_color, bg_color, padding=8):
        x, y = position
        # Get text dimensions
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Draw background rectangle with alpha
        bg_rect = [
            x - padding, 
            y - padding, 
            x + text_width + padding, 
            y + text_height + padding
        ]
        draw.rectangle(bg_rect, fill=bg_color)
        
        # Draw text
        draw.text((x, y), text, font=font, fill=text_color)

    # Top-left: brand with dark semi-transparent background
    draw_text_with_background(
        draw, (30, 30), brand, font_brand, 
        text_color=(255, 255, 255, 255), bg_color=(0, 0, 0, 180)  # White text, black bg
    )
    
    # Below brand: product with blue semi-transparent background
    draw_text_with_background(
        draw, (30, 90), product, font_product,
        text_color=(255, 255, 255, 255), bg_color=(0, 100, 200, 180)  # White text, blue bg
    )

    # Bottom-left: CTA with orange background for strong visibility
    cta_y = image.height - 80
    draw_text_with_background(
        draw, (30, cta_y), cta, font_cta,
        text_color=(255, 255, 255, 255), bg_color=(255, 100, 0, 200)  # White text, orange bg
    )
    
    # Bottom-right: "AI Generated" with subtle gray background
    ai_text = "AI Generated"
    ai_bbox = draw.textbbox((0, 0), ai_text, font=font_ai)
    ai_width = ai_bbox[2] - ai_bbox[0]
    ai_x = image.width - ai_width - 30
    ai_y = image.height - 50
    
    draw_text_with_background(
        draw, (ai_x, ai_y), ai_text, font_ai,
        text_color=(255, 255, 255, 255), bg_color=(100, 100, 100, 150)  # White text, gray bg
    )

    # Composite the overlay onto the original image
    image = image.convert('RGBA')
    combined = Image.alpha_composite(image, overlay)
    return combined.convert('RGB')

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
                "image_filename": filename,
                "image_path": image_path
            })
        # Remove from tracking dictionary
        if filename in image_timestamps:
            del image_timestamps[filename]
    except Exception as e:
        logger.error("Error cleaning up image", extra={
            "image_filename": filename,
            "image_path": image_path,
            "error": str(e)
        })

def schedule_cleanup(image_path: str, filename: str):
    """Schedule image cleanup in a background thread"""
    cleanup_thread = threading.Thread(target=cleanup_image, args=(image_path, filename))
    cleanup_thread.daemon = True
    cleanup_thread.start()
    logger.info("Image cleanup scheduled", extra={
        "image_filename": filename,
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
                "cta_text": data.cta_text[:50] + "..." if len(data.cta_text) > 50 else data.cta_text,
                "trending_boost": data.trending_boost,
                "trending_topic": data.trending_topic[:50] + "..." if len(data.trending_topic) > 50 else data.trending_topic,
                "hook_mode": data.hook_mode,
                "trending_keywords": data.trending_keywords[:3] if data.trending_keywords else []
            })
            
            log_gpu_usage(logger, "before_generation")
            # 1. Build the HOOK-FOCUSED prompt
            with TimingContext("prompt_building", logger):
                # Base prompt for better text readability
                base_prompt = (f"{data.scene}, clean composition, balanced lighting, "
                         f"clear areas for text overlay, high contrast, professional advertising style, "
                         f"uncluttered layout, space for branding elements")
                
                # Add trending keyword hooks for visual emphasis
                if data.hook_mode and data.trending_keywords:
                    import random  # Import here for hook functionality
                    keyword_hooks = ", ".join([f"prominent {keyword} elements" for keyword in data.trending_keywords[:3]])
                    visual_hooks = [
                        "attention-grabbing focal points", "viral content style", "social media impact",
                        "trending visual language", "hook-focused composition", "scroll-stopping design"
                    ]
                    hook_enhancement = f", {keyword_hooks}, " + ", ".join(random.sample(visual_hooks, 2))
                    base_prompt = f"{base_prompt}{hook_enhancement}"
                    
                    logger.info("Applied HOOK-FOCUSED enhancement", extra={
                        "trending_keywords": data.trending_keywords,
                        "keyword_hooks": keyword_hooks,
                        "hook_mode": True
                    })
                
                # Add trending boost effects if enabled
                if data.trending_boost:
                    trending_effects = [
                        "vibrant colors", "dynamic composition", "eye-catching effects",
                        "social media worthy", "trending aesthetic", "modern style",
                        "engaging visual elements", "shareable content style",
                        "contemporary design", "viral marketing appeal"
                    ]
                    import random
                    selected_effects = random.sample(trending_effects, 3)
                    trending_enhancement = ", ".join(selected_effects)
                    prompt = f"{base_prompt}, {trending_enhancement}, extra visual impact"
                    
                    logger.info("Applied trending boost", extra={
                        "trending_effects": selected_effects,
                        "trending_topic": data.trending_topic
                    })
                else:
                    prompt = base_prompt
                    
                prompt = trim_prompt(prompt)
                logger.info("Prompt prepared", extra={
                    "original_scene_length": len(data.scene),
                    "trimmed_prompt_length": len(prompt),
                    "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                    "trending_mode": data.trending_boost
                })

            # 2. Generate base image with retries
            with TimingContext("base_image_generation", logger) as base_timer:
                base_image = None
                
                # Enhanced parameters for trending mode
                if data.trending_boost:
                    guidance_scale = 8.0  # Higher guidance for more vibrant images
                    num_steps = 45        # More steps for better quality
                    logger.info("Using trending boost parameters", extra={
                        "guidance_scale": guidance_scale,
                        "num_inference_steps": num_steps
                    })
                else:
                    guidance_scale = 7.5  # Standard parameters
                    num_steps = 40
                
                for attempt in range(3):
                    try:
                        logger.info(f"Base image generation attempt {attempt + 1}", extra={
                            "attempt": attempt + 1,
                            "max_attempts": 3,
                            "trending_mode": data.trending_boost
                        })
                        
                        log_image_generation_metrics(
                            logger, 1024, 1024, num_steps, guidance_scale, "playground-v2-1024px-aesthetic"
                        )
                        
                        base_image = pipe(prompt, guidance_scale=guidance_scale, num_inference_steps=num_steps).images[0]
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
                
                # Enhanced refinement for trending mode
                if data.trending_boost:
                    refine_strength = 0.4    # Higher strength for more dramatic effect
                    refine_guidance = 8.0    # Higher guidance for trending appeal
                    refine_steps = 25        # More steps for trending mode
                    logger.info("Using trending refinement parameters", extra={
                        "strength": refine_strength,
                        "guidance_scale": refine_guidance,
                        "num_inference_steps": refine_steps
                    })
                else:
                    refine_strength = 0.3    # Standard parameters
                    refine_guidance = 7.5
                    refine_steps = 20
                
                final_image = refiner(
                    prompt=prompt,
                    image=base_image,
                    strength=refine_strength,
                    guidance_scale=refine_guidance,
                    num_inference_steps=refine_steps
                ).images[0]
                logger.info("Image refinement completed", extra={
                    "trending_mode": data.trending_boost
                })

            log_gpu_usage(logger, "after_refinement")

            # 4. Add brand/CTA overlay
            with TimingContext("overlay_addition", logger):
                logger.info("Adding brand and CTA overlays")
                branded_image = add_overlay(final_image, data.brand_text, data.product_name, data.cta_text)

            # 5. Save and return download URL
            with TimingContext("image_saving", logger):
                filename = f"{uuid.uuid4()}.png"
                file_path = os.path.join(IMAGES_DIR, filename)
                file_size = 0  # Initialize file_size
                
                try:
                    # Check directory exists and is writable
                    if not os.path.exists(IMAGES_DIR):
                        os.makedirs(IMAGES_DIR, exist_ok=True)
                        logger.info("Created images directory", extra={"directory": IMAGES_DIR})
                    
                    # Check directory permissions
                    if not os.access(IMAGES_DIR, os.W_OK):
                        raise PermissionError(f"No write permission for directory: {IMAGES_DIR}")
                    
                    # Save the image
                    logger.info("Attempting to save image", extra={
                        "file_path": file_path,
                        "branded_image_mode": branded_image.mode if hasattr(branded_image, 'mode') else "unknown",
                        "branded_image_size": branded_image.size if hasattr(branded_image, 'size') else "unknown"
                    })
                    branded_image.save(file_path)
                    
                    # Verify file was created
                    if not os.path.exists(file_path):
                        raise FileNotFoundError(f"Image file was not created: {file_path}")
                    
                    # Get file size for logging
                    file_size = os.path.getsize(file_path)
                    
                    logger.info("Image saved successfully", extra={
                        "image_filename": filename,
                        "file_path": file_path,
                        "file_size_bytes": file_size,
                        "file_size_mb": round(file_size / 1024 / 1024, 2)
                    })
                    
                    # Track creation time and schedule cleanup
                    image_timestamps[filename] = time.time()
                    schedule_cleanup(file_path, filename)
                    
                except Exception as save_error:
                    # Get detailed directory information
                    dir_exists = os.path.exists(IMAGES_DIR)
                    dir_writable = os.access(IMAGES_DIR, os.W_OK) if dir_exists else False
                    dir_readable = os.access(IMAGES_DIR, os.R_OK) if dir_exists else False
                    
                    logger.error("Image saving failed - detailed diagnostics", extra={
                        "image_filename": filename,
                        "file_path": file_path,
                        "images_dir": IMAGES_DIR,
                        "images_dir_exists": dir_exists,
                        "images_dir_writable": dir_writable,
                        "images_dir_readable": dir_readable,
                        "error_message": str(save_error),
                        "error_type": type(save_error).__name__,
                        "working_directory": os.getcwd(),
                        "disk_space_available": "checking..."
                    })
                    
                    # Additional diagnostic logging
                    logger.error(f"CRITICAL: Image save error details - {type(save_error).__name__}: {str(save_error)}")
                    logger.error(f"CRITICAL: Directory {IMAGES_DIR} exists: {dir_exists}, writable: {dir_writable}")
                    
                    raise save_error

            logger.info("Image generation completed successfully", extra={
                "image_filename": filename,
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
        error_details = {
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(timer.duration_ms, 2) if timer else None
        }
        
        # Add traceback for debugging
        import traceback
        error_details["traceback"] = traceback.format_exc()
        
        logger.error("Unexpected error during image generation", extra=error_details)
        logger.error(f"CRITICAL: Full error traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

@app.get("/download/{filename}")
def download_image(filename: str, request: Request):
    """Download endpoint for generated images"""
    with TimingContext("image_download", logger, {"image_filename": filename}):
        client_ip = request.client.host if request.client else "unknown"
        logger.info("Image download request", extra={
            "image_filename": filename,
            "client_ip": client_ip
        })
        
        file_path = os.path.join(IMAGES_DIR, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.warning("Image file not found", extra={
                "image_filename": filename,
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
                    "image_filename": filename,
                    "elapsed_minutes": round(elapsed_time / 60, 1),
                    "client_ip": client_ip
                })
                # Clean up expired image
                try:
                    os.remove(file_path)
                    del image_timestamps[filename]
                except Exception as e:
                    logger.error("Error removing expired image", extra={
                        "image_filename": filename,
                        "error": str(e)
                    })
                raise HTTPException(status_code=404, detail="Image has expired")
        
        # Get file size for logging
        try:
            file_size = os.path.getsize(file_path)
            logger.info("Image download successful", extra={
                "image_filename": filename,
                "client_ip": client_ip,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / 1024 / 1024, 2)
            })
        except Exception as e:
            logger.error("Error getting file size", extra={
                "image_filename": filename,
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

