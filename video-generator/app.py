from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import torch, uuid, os, time, threading, requests
from PIL import Image
import numpy as np
from logging_config import setup_logging, TimingContext, generate_request_id, request_id

# AI model imports - Required
from diffusers import StableVideoDiffusionPipeline
from diffusers.utils import export_to_video

# Setup structured logging
logger = setup_logging("video-generator", "INFO")

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

app = FastAPI(title="AI Advertisement Generator - Video Generator", version="2.0.0")
app.add_middleware(LoggingMiddleware)

# AI Model Configuration
MODEL_ID = "stabilityai/stable-video-diffusion-img2vid-xt"
pipeline = None

# Log service startup with detailed GPU information
cuda_available = torch.cuda.is_available()
gpu_count = torch.cuda.device_count() if cuda_available else 0

logger.info("Video generator service starting up", extra={
    "cuda_available": cuda_available,
    "gpu_count": gpu_count
})

# Additional debugging for RTX 5090
if cuda_available:
    for i in range(gpu_count):
        gpu_name = torch.cuda.get_device_name(i)
        gpu_capability = torch.cuda.get_device_capability(i)
        gpu_memory = torch.cuda.get_device_properties(i).total_memory // (1024**3)  # GB
        logger.info(f"GPU {i} detected", extra={
            "gpu_name": gpu_name,
            "compute_capability": f"sm_{gpu_capability[0]}{gpu_capability[1]}",
            "memory_gb": gpu_memory
        })
else:
    logger.warning("CUDA not available - RTX 5090 not detected", extra={
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda if hasattr(torch.version, 'cuda') else "unknown"
    })

# Create videos directory if it doesn't exist
VIDEOS_DIR = "/app/videos"
os.makedirs(VIDEOS_DIR, exist_ok=True)
logger.info("Videos directory created", extra={"directory": VIDEOS_DIR})

# Mount static files for serving videos
app.mount("/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")

# Dictionary to track video creation times for cleanup
video_timestamps = {}

def initialize_ai_pipeline():
    """Initialize the Stable Video Diffusion pipeline"""
    global pipeline
    
    try:
        logger.info("Initializing Stable Video Diffusion pipeline...")
        
        # Check if CUDA is available - FAIL FAST if not
        if not torch.cuda.is_available():
            logger.error("CUDA is not available - GPU is required for video generation")
            logger.error("Please ensure NVIDIA Container Toolkit is properly configured")
            return False
        
        device = "cuda"
        logger.info(f"Using device: {device}")
        
        # Log GPU information
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory // (1024**3)
        logger.info(f"GPU detected: {gpu_name}, Memory: {gpu_memory}GB")
        
        # Load the pipeline
        pipeline = StableVideoDiffusionPipeline.from_pretrained(
            MODEL_ID, 
            torch_dtype=torch.float16,
            variant="fp16"
        )
        
        pipeline = pipeline.to(device)
        # Enable aggressive memory optimizations for shared GPU environment
        pipeline.enable_model_cpu_offload()
        # Enable VAE slicing if available (not all pipelines support this)
        if hasattr(pipeline, 'enable_vae_slicing'):
            pipeline.enable_vae_slicing()
        # Enable attention slicing for memory efficiency
        if hasattr(pipeline, 'enable_attention_slicing'):
            pipeline.enable_attention_slicing()
        # Set low VRAM mode
        if hasattr(pipeline, 'enable_sequential_cpu_offload'):
            pipeline.enable_sequential_cpu_offload()
            
        # Clear any cached memory
        torch.cuda.empty_cache()
        
        # Log memory usage
        memory_allocated = torch.cuda.memory_allocated(0) / (1024**3)
        memory_reserved = torch.cuda.memory_reserved(0) / (1024**3)
        logger.info(f"GPU Memory - Allocated: {memory_allocated:.2f}GB, Reserved: {memory_reserved:.2f}GB")
        
        logger.info("Stable Video Diffusion pipeline initialized successfully on GPU!")
        return True
        
    except Exception as e:
        logger.error("Failed to initialize AI pipeline", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        return False

# Initialize AI pipeline on startup
@app.on_event("startup")
async def startup_event():
    """Initialize AI pipeline when the service starts"""
    global pipeline
    try:
        logger.info("Starting AI pipeline initialization...")
        ai_initialized = initialize_ai_pipeline()
        logger.info("AI pipeline initialization result", extra={"success": ai_initialized})
        if not ai_initialized:
            logger.error("AI pipeline failed to initialize - service will return 503 for video requests")
    except Exception as e:
        logger.error("Error during AI initialization", extra={"error": str(e)})

# Input model
class VideoPrompt(BaseModel):
    image_filename: str
    scene: str
    duration_seconds: int = 5
    fps: int = 7  # Optimal for SVD
    num_frames: int = 25  # SVD default
    motion_bucket_id: int = 127  # Motion intensity
    noise_aug_strength: float = 0.02  # Noise augmentation

def download_image_from_generator(image_filename: str) -> Image.Image:
    """Download image from image-generator service"""
    try:
        logger.info("Downloading image from image-generator", extra={
            "image_filename": image_filename
        })
        
        response = requests.get(f"http://image-generator:5001/download/{image_filename}")
        
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail=f"Image not found: {image_filename}")
        
        # Convert to PIL Image
        from io import BytesIO
        image = Image.open(BytesIO(response.content)).convert('RGB')
        
        # Resize to optimal dimensions for SVD (1024x576)
        image = image.resize((1024, 576), Image.Resampling.LANCZOS)
        
        logger.info("Image downloaded and processed successfully", extra={
            "image_filename": image_filename,
            "image_size": image.size
        })
        
        return image
        
    except Exception as e:
        logger.error("Failed to download image", extra={
            "image_filename": image_filename,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=f"Failed to download image: {str(e)}")

def create_video_with_ai(image: Image.Image, scene: str, data: VideoPrompt) -> str:
    """Create video using Stable Video Diffusion"""
    global pipeline
    
    if pipeline is None:
        raise RuntimeError("AI pipeline not initialized")
    
    try:
        # Generate unique filename
        video_filename = f"{uuid.uuid4()}.mp4"
        video_path = os.path.join(VIDEOS_DIR, video_filename)
        
        logger.info("Creating video with AI", extra={
            "video_filename": video_filename,
            "image_size": image.size,
            "num_frames": data.num_frames,
            "fps": data.fps,
            "motion_bucket_id": data.motion_bucket_id
        })
        
        # Generate video frames using SVD
        generator = torch.manual_seed(42)  # For reproducible results
        
        # Clear GPU cache before generation
        torch.cuda.empty_cache()
        
        with TimingContext("ai_video_generation", logger):
            frames = pipeline(
                image,
                decode_chunk_size=4,  # Reduced for memory efficiency
                generator=generator,
                motion_bucket_id=data.motion_bucket_id,
                noise_aug_strength=data.noise_aug_strength,
                num_frames=data.num_frames,
            ).frames[0]
        
        # Clear GPU cache after generation
        torch.cuda.empty_cache()
        
        # Export frames to video
        with TimingContext("video_export", logger):
            export_to_video(frames, video_path, fps=data.fps)
        
        # Verify video was created
        if not os.path.exists(video_path):
            raise RuntimeError("Video file was not created")
        
        file_size = os.path.getsize(video_path)
        logger.info("AI video created successfully", extra={
            "video_filename": video_filename,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / 1024 / 1024, 2),
            "method": "ai_svd"
        })
        
        return video_filename
        
    except Exception as e:
        logger.error("AI video creation failed", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise RuntimeError(f"AI video creation failed: {str(e)}")

def cleanup_video(video_path: str, filename: str):
    """Delete video file after 10 minutes"""
    time.sleep(600)  # 10 minutes = 600 seconds
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
            logger.info("Video cleaned up successfully", extra={
                "video_filename": filename,
                "video_path": video_path
            })
        # Remove from tracking dictionary
        if filename in video_timestamps:
            del video_timestamps[filename]
    except Exception as e:
        logger.error("Error cleaning up video", extra={
            "video_filename": filename,
            "video_path": video_path,
            "error": str(e)
        })

def schedule_cleanup(video_path: str, filename: str):
    """Schedule video cleanup in a background thread"""
    cleanup_thread = threading.Thread(target=cleanup_video, args=(video_path, filename))
    cleanup_thread.daemon = True
    cleanup_thread.start()
    logger.info("Video cleanup scheduled", extra={
        "video_filename": filename,
        "cleanup_in_seconds": 600
    })

@app.post("/generate")
def generate_video(data: VideoPrompt):
    """Generate video from image using AI Stable Video Diffusion"""
    timer = None
    method_used = "unknown"
    
    try:
        with TimingContext("video_generation_full", logger) as timer:
            logger.info("Video generation request received", extra={
                "image_filename": data.image_filename,
                "scene_length": len(data.scene),
                "duration_seconds": data.duration_seconds,
                "fps": data.fps,
                "num_frames": data.num_frames,
                "ai_available": pipeline is not None,
                "scene_preview": data.scene[:100] + "..." if len(data.scene) > 100 else data.scene
            })
            
            # Step 1: Download image from image-generator service
            with TimingContext("image_download", logger):
                image = download_image_from_generator(data.image_filename)
            
            # Step 2: Create video with AI
            if pipeline is None:
                raise HTTPException(
                    status_code=503, 
                    detail="AI pipeline not initialized. Service unavailable."
                )
            
            video_filename = create_video_with_ai(image, data.scene, data)
            method_used = "ai_svd"
            
            # Step 3: Schedule cleanup and track
            video_path = os.path.join(VIDEOS_DIR, video_filename)
            video_timestamps[video_filename] = time.time()
            schedule_cleanup(video_path, video_filename)
            
            file_size = os.path.getsize(video_path)
            
            logger.info("Video generation completed successfully", extra={
                "video_filename": video_filename,
                "total_duration_ms": round(timer.duration_ms, 2),
                "file_size_mb": round(file_size / 1024 / 1024, 2),
                "method_used": method_used
            })

            return {
                "filename": video_filename,
                "download_url": f"/download/{video_filename}",
                "expires_in_minutes": 10,
                "duration_seconds": data.duration_seconds,
                "fps": data.fps,
                "file_size_mb": round(file_size / 1024 / 1024, 2),
                "method_used": method_used,
                "ai_generated": method_used.startswith("ai_")
            }
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        error_details = {
            "error": str(e),
            "error_type": type(e).__name__,
            "method_attempted": method_used,
            "duration_ms": round(timer.duration_ms, 2) if timer else None
        }
        
        # Add traceback for debugging
        import traceback
        error_details["traceback"] = traceback.format_exc()
        
        logger.error("Unexpected error during video generation", extra=error_details)
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")

@app.get("/download/{filename}")
def download_video(filename: str, request: Request):
    """Download endpoint for generated videos"""
    with TimingContext("video_download", logger, {"video_filename": filename}):
        client_ip = request.client.host if request.client else "unknown"
        logger.info("Video download request", extra={
            "video_filename": filename,
            "client_ip": client_ip
        })
        
        file_path = os.path.join(VIDEOS_DIR, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.warning("Video file not found", extra={
                "video_filename": filename,
                "file_path": file_path,
                "client_ip": client_ip
            })
            raise HTTPException(status_code=404, detail="Video not found or has expired")
        
        # Check if video has expired (more than 10 minutes old)
        if filename in video_timestamps:
            creation_time = video_timestamps[filename]
            elapsed_time = time.time() - creation_time
            if elapsed_time > 600:  # 10 minutes
                logger.info("Video has expired, cleaning up", extra={
                    "video_filename": filename,
                    "elapsed_minutes": round(elapsed_time / 60, 1),
                    "client_ip": client_ip
                })
                # Clean up expired video
                try:
                    os.remove(file_path)
                    del video_timestamps[filename]
                except Exception as e:
                    logger.error("Error removing expired video", extra={
                        "video_filename": filename,
                        "error": str(e)
                    })
                raise HTTPException(status_code=404, detail="Video has expired")
        
        # Get file size for logging
        try:
            file_size = os.path.getsize(file_path)
            logger.info("Video download successful", extra={
                "video_filename": filename,
                "client_ip": client_ip,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / 1024 / 1024, 2)
            })
        except Exception as e:
            logger.error("Error getting file size", extra={
                "video_filename": filename,
                "error": str(e)
            })
            file_size = 0
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(file_size)
            }
        )

@app.get("/status/{filename}")
def check_video_status(filename: str):
    """Check if a video is still available"""
    file_path = os.path.join(VIDEOS_DIR, filename)
    
    if not os.path.exists(file_path):
        return {"status": "not_found", "message": "Video not found or has expired"}
    
    if filename in video_timestamps:
        creation_time = video_timestamps[filename]
        elapsed_time = time.time() - creation_time
        remaining_time = max(0, 600 - elapsed_time)  # 10 minutes = 600 seconds
        
        if remaining_time > 0:
            file_size = os.path.getsize(file_path)
            return {
                "status": "available",
                "remaining_minutes": round(remaining_time / 60, 1),
                "download_url": f"/download/{filename}",
                "file_size_mb": round(file_size / 1024 / 1024, 2)
            }
        else:
            return {"status": "expired", "message": "Video has expired"}
    
    return {"status": "unknown", "message": "Video status unknown"}

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "video-generator",
        "version": "2.0.0",
        "ai_pipeline_loaded": pipeline is not None,
        "cuda_available": torch.cuda.is_available(),
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
    }

@app.get("/models/info")
def get_model_info():
    """Get information about loaded AI models"""
    gpu_memory_total = torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else 0
    gpu_memory_allocated = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
    gpu_memory_cached = torch.cuda.memory_reserved() if torch.cuda.is_available() else 0
    
    return {
        "pipeline_loaded": pipeline is not None,
        "model_id": MODEL_ID if pipeline is not None else None,
        "device": "cuda" if torch.cuda.is_available() and pipeline is not None else "cpu",
        "cuda_available": torch.cuda.is_available(),
        "gpu_memory_total_gb": round(gpu_memory_total / 1024**3, 2),
        "gpu_memory_allocated_gb": round(gpu_memory_allocated / 1024**3, 2),
        "gpu_memory_cached_gb": round(gpu_memory_cached / 1024**3, 2),
        "gpu_memory_free_gb": round((gpu_memory_total - gpu_memory_cached) / 1024**3, 2),
        "gpu_utilization_percent": round((gpu_memory_cached / gpu_memory_total * 100), 1) if gpu_memory_total > 0 else 0
    }
