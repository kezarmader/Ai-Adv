import os
import logging
import uuid
import time
import gc
import requests
from contextlib import contextmanager
from typing import Optional
from io import BytesIO

import torch
import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import video generation libraries
try:
    from diffusers import StableVideoDiffusionPipeline
    SVD_AVAILABLE = True
except ImportError:
    SVD_AVAILABLE = False
    StableVideoDiffusionPipeline = None

from logging_config import setup_logging, TimingContext, log_gpu_usage

# Configure logging
logger = setup_logging("video-generator", "INFO")

# Initialize FastAPI app
app = FastAPI(title="AI Video Generator Service", version="2.0.0")

# Directory setup
VIDEOS_DIR = os.path.join(os.path.dirname(__file__), "videos")
TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")

# Create directories if they don't exist
for directory in [VIDEOS_DIR, TEMP_DIR]:
    os.makedirs(directory, exist_ok=True)

# Mount static files for serving videos (downloadable MP4s)
app.mount("/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")

# GPU configuration
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

if device == "cuda":
    # Configure CUDA memory allocation to reduce fragmentation
    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
    torch.cuda.set_per_process_memory_fraction(0.9)
    torch.cuda.empty_cache()
    log_gpu_usage(logger, "startup")

# Request/Response Models
class VideoGenerationRequest(BaseModel):
    image_url: str
    prompt: str
    duration_seconds: Optional[int] = 8
    
class VideoGenerationResponse(BaseModel):
    video_filename: str
    video_url: str
    duration_seconds: int
    status: str

class DynamicModelManager:
    """Manages dynamic loading/unloading of GPU models for memory efficiency"""
    
    def __init__(self):
        self.svd_pipeline = None
        self.svd_loaded = False
        self.device = device
        
    def unload_svd_pipeline(self):
        """Unload SVD pipeline from GPU to free memory"""
        if self.svd_pipeline is not None:
            logger.info("Unloading SVD pipeline from GPU memory")
            self.svd_pipeline.to("cpu")
            del self.svd_pipeline
            self.svd_pipeline = None
            self.svd_loaded = False
            
            if self.device == "cuda":
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                gc.collect()
                log_gpu_usage(logger, "after_svd_unload")
                
            logger.info("SVD pipeline unloaded successfully")
    
    def load_svd_pipeline(self):
        """Load SVD pipeline to GPU when needed"""
        if self.svd_pipeline is None and SVD_AVAILABLE:
            logger.info("Loading SVD pipeline to GPU memory")
            
            # Aggressive memory cleanup before loading
            if self.device == "cuda":
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                gc.collect()
                log_gpu_usage(logger, "before_svd_load")
            
            try:
                # Load SVD 1.1 - Superior model with your authorized token
                self.svd_pipeline = StableVideoDiffusionPipeline.from_pretrained(
                    "stabilityai/stable-video-diffusion-img2vid-xt-1-1",
                    torch_dtype=torch.float16,
                    variant="fp16",
                    use_safetensors=True,
                    device_map="auto",
                    token=os.getenv("HF_TOKEN")
                )
                
                # Enable memory efficient attention
                self.svd_pipeline.enable_model_cpu_offload()
                self.svd_pipeline.enable_vae_slicing()
                
                if hasattr(self.svd_pipeline, 'enable_vae_tiling'):
                    self.svd_pipeline.enable_vae_tiling()
                
                if self.device == "cuda":
                    log_gpu_usage(logger, "after_svd_load")
                
                self.svd_loaded = True
                logger.info("SVD pipeline loaded successfully")
                
            except Exception as e:
                logger.error(f"Failed to load SVD pipeline: {e}")
                self.svd_pipeline = None
                self.svd_loaded = False
                raise
    
    def get_svd_pipeline(self):
        """Get SVD pipeline, loading it if necessary"""
        if not self.svd_loaded:
            self.load_svd_pipeline()
        return self.svd_pipeline
    
    def request_llm_offload(self):
        """Request that the LLM service offload its models to free GPU memory"""
        try:
            response = requests.post("http://llm-service:11434/api/offload", timeout=30)
            if response.status_code == 200:
                logger.info("LLM models offloaded successfully")
                return True
            else:
                logger.warning(f"LLM offload request failed: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"Could not request LLM offload: {e}")
            return False

# Initialize model manager
model_manager = DynamicModelManager()

def download_image_from_url(image_url: str) -> Image.Image:
    """Download image from URL"""
    try:
        logger.info(f"Downloading image from URL: {image_url}")
        
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        image = Image.open(BytesIO(response.content)).convert('RGB')
        logger.info(f"Image downloaded successfully, size: {image.size}")
        
        return image
        
    except Exception as e:
        logger.error(f"Error downloading image: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error downloading image: {str(e)}")

def generate_video_from_image(image: Image.Image, prompt: str, duration_seconds: int = 8) -> str:
    """Generate video using Stable Video Diffusion - core functionality"""
    
    if not SVD_AVAILABLE:
        raise HTTPException(status_code=503, detail="StableVideoDiffusionPipeline not available")
    
    if device == "cpu":
        raise HTTPException(status_code=503, detail="GPU required for AI video generation")
    
    # Request LLM offload to free GPU memory
    logger.info("Requesting LLM model offload for video generation")
    model_manager.request_llm_offload()
    time.sleep(2)  # Wait for offload
    
    # Aggressive memory cleanup
    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        gc.collect()
    
    try:
        with TimingContext("video_generation", logger):
            logger.info("Starting video generation", extra={
                "prompt": prompt,
                "duration_seconds": duration_seconds,
                "image_size": image.size
            })
            
            # Get SVD pipeline (loads if needed)
            svd_pipeline = model_manager.get_svd_pipeline()
            
            # Resize image to SVD requirements (1024x576 for optimal performance)
            target_size = (1024, 576)
            image_resized = image.resize(target_size, Image.Resampling.LANCZOS)
            
            # Calculate frames for duration
            fps = 6  # SVD default FPS
            num_frames = min(duration_seconds * fps, 25)  # SVD max frames
            
            logger.info(f"Generating {num_frames} frames at {fps} FPS")
            
            # Generate video frames using SVD
            with torch.no_grad():
                frames = svd_pipeline(
                    image=image_resized,
                    decode_chunk_size=2,  # Memory optimization
                    num_frames=num_frames,
                    motion_bucket_id=127,  # Standard motion
                    fps=fps,
                    noise_aug_strength=0.02,  # Minimal noise
                    num_inference_steps=20,  # Balanced quality/speed
                    generator=torch.manual_seed(42)  # Reproducible results
                ).frames[0]
            
            # Save video as MP4
            video_filename = f"video_{uuid.uuid4().hex}.mp4"
            video_path = os.path.join(VIDEOS_DIR, video_filename)
            
            # Convert frames to video using imageio
            import imageio
            
            # Convert PIL images to numpy arrays
            frame_arrays = []
            for frame in frames:
                frame_arrays.append(np.array(frame))
            
            # Write MP4 video
            with imageio.get_writer(video_path, fps=fps, codec='libx264', quality=8) as writer:
                for frame_array in frame_arrays:
                    writer.append_data(frame_array)
            
            logger.info("Video generation completed", extra={
                "video_filename": video_filename,
                "frames_generated": len(frames),
                "file_size_mb": os.path.getsize(video_path) / (1024 * 1024)
            })
            
            return video_filename
            
    except Exception as e:
        logger.error(f"Video generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")
    
    finally:
        # Memory cleanup after generation
        if device == "cuda":
            torch.cuda.empty_cache()
            gc.collect()

@app.post("/generate-video", response_model=VideoGenerationResponse)
async def generate_video(request: VideoGenerationRequest):
    """Generate video from image URL and prompt"""
    
    logger.info("Video generation request received", extra={
        "image_url": request.image_url,
        "prompt": request.prompt,
        "duration_seconds": request.duration_seconds
    })
    
    try:
        # Download image
        image = download_image_from_url(request.image_url)
        
        # Generate video
        video_filename = generate_video_from_image(
            image=image,
            prompt=request.prompt,
            duration_seconds=request.duration_seconds
        )
        
        # Construct video URL for download
        video_url = f"/videos/{video_filename}"
        
        response = VideoGenerationResponse(
            video_filename=video_filename,
            video_url=video_url,
            duration_seconds=request.duration_seconds,
            status="success"
        )
        
        logger.info("Video generation request completed successfully", extra={
            "video_filename": video_filename,
            "video_url": video_url
        })
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in video generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/model-status")
async def get_model_status():
    """Get current model loading status"""
    return JSONResponse({
        "svd_loaded": model_manager.svd_loaded,
        "svd_available": SVD_AVAILABLE,
        "device": device,
        "cuda_available": torch.cuda.is_available()
    })

@app.post("/offload-svd")
async def offload_svd():
    """Manually offload SVD pipeline to free GPU memory"""
    try:
        model_manager.unload_svd_pipeline()
        return JSONResponse({"status": "success", "message": "SVD pipeline offloaded"})
    except Exception as e:
        logger.error(f"Failed to offload SVD pipeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to offload SVD: {str(e)}")

@app.post("/load-svd")
async def load_svd():
    """Manually load SVD pipeline"""
    try:
        model_manager.load_svd_pipeline()
        return JSONResponse({"status": "success", "message": "SVD pipeline loaded"})
    except Exception as e:
        logger.error(f"Failed to load SVD pipeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load SVD: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "video-generator",
        "version": "2.0.0",
        "gpu_available": torch.cuda.is_available(),
        "svd_available": SVD_AVAILABLE
    })

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Video Generator Service v2.0.0")
    uvicorn.run(app, host="0.0.0.0", port=5002)