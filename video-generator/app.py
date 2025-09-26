from fastapi import FastAPI, HTTPException, Request, File, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import torch
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import uuid
import os
import time
import threading
import json
import requests
from io import BytesIO
import imageio
from typing import Optional, List
import logging
from diffusers import StableDiffusionPipeline, DDIMScheduler, StableVideoDiffusionPipeline 
from transformers import CLIPVisionModel, CLIPImageProcessor
import torchvision.transforms as transforms
from logging_config import (
    setup_logging, TimingContext, generate_request_id, request_id,
    log_gpu_usage
)

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

app = FastAPI(title="AI Advertisement Generator - Video Generator", version="1.0.0")
app.add_middleware(LoggingMiddleware)

# Log service startup
logger.info("Video generator service starting up")

# Create directories
VIDEOS_DIR = "/app/videos"
TEMP_DIR = "/app/temp"
for directory in [VIDEOS_DIR, TEMP_DIR]:
    os.makedirs(directory, exist_ok=True)
    logger.info(f"Directory created: {directory}")

# Mount static files for serving videos
app.mount("/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")

# Dictionary to track video creation times for cleanup
video_timestamps = {}

# Video generation parameters
DEFAULT_FPS = 30
DEFAULT_DURATION = 5  # seconds
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024

class VideoRequest(BaseModel):
    image_url: Optional[str] = None
    animation_type: str = "zoom_pan"  # zoom_pan, fade_effects, parallax, ken_burns
    duration: int = 5  # seconds
    fps: int = 30
    audio_prompt: Optional[str] = None
    style: str = "smooth"  # smooth, dramatic, gentle, energetic
    text_overlay: Optional[str] = None
    brand_text: Optional[str] = None
    cta_text: Optional[str] = None

class AIVideoRequest(BaseModel):
    image_url: str
    prompt: str = "dramatic transformation with dynamic motion"
    duration_frames: int = 25  # SVD works with frames, not seconds

class AIVideoAnimationEngine:
    """AI-powered video animation engine using CLIP for motion understanding"""
    
    def __init__(self, device: str, clip_model, clip_processor):
        self.device = device
        self.clip_model = clip_model
        self.clip_processor = clip_processor
        self.temp_dir = TEMP_DIR
    
    def analyze_image_for_motion(self, image: Image.Image) -> dict:
        """Analyze image content to determine optimal motion patterns"""
        try:
            if not self.clip_model or not self.clip_processor:
                logger.warning("CLIP model not available, using fallback analysis")
                return self._fallback_image_analysis(image)
            
            # Process image with CLIP
            inputs = self.clip_processor(images=image, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                image_features = self.clip_model(**inputs).last_hidden_state
                
            # Analyze features to determine motion characteristics
            # This is a simplified version - in production, you'd train a model for this
            feature_variance = torch.var(image_features).item()
            
            # Determine motion based on image complexity
            if feature_variance > 0.5:
                motion_type = "parallax"  # Complex images work well with parallax
                intensity = min(0.8, feature_variance)
            elif feature_variance > 0.3:
                motion_type = "ken_burns"  # Medium complexity for ken burns
                intensity = 0.5
            else:
                motion_type = "zoom_pan"  # Simple images for zoom/pan
                intensity = 0.3
            
            return {
                "motion_type": motion_type,
                "intensity": intensity,
                "complexity": feature_variance
            }
            
        except Exception as e:
            logger.warning(f"AI motion analysis failed: {e}. Using fallback.")
            return self._fallback_image_analysis(image)
    
    def _fallback_image_analysis(self, image: Image.Image) -> dict:
        """Fallback image analysis without CLIP model"""
        import numpy as np
        
        # Convert to numpy array for analysis
        img_array = np.array(image)
        
        # Simple image complexity analysis based on pixel variance
        if len(img_array.shape) == 3:
            # Color image - analyze color variance
            color_variance = np.var(img_array, axis=(0, 1)).mean()
            edge_variance = np.var(np.diff(img_array, axis=0)) + np.var(np.diff(img_array, axis=1))
        else:
            # Grayscale
            color_variance = np.var(img_array)
            edge_variance = np.var(np.diff(img_array, axis=0)) + np.var(np.diff(img_array, axis=1))
        
        # Normalize and determine motion type
        complexity = min(1.0, (color_variance + edge_variance) / 10000)
        
        if complexity > 0.6:
            return {"motion_type": "parallax", "intensity": 0.7, "complexity": complexity}
        elif complexity > 0.3:
            return {"motion_type": "ken_burns", "intensity": 0.5, "complexity": complexity}
        else:
            return {"motion_type": "zoom_pan", "intensity": 0.4, "complexity": complexity}
    
    def create_ai_enhanced_animation(self, image: Image.Image, duration: int, fps: int, 
                                   style: str = "smooth", motion_analysis: dict = None) -> List[np.ndarray]:
        """Create AI-enhanced animation based on image content analysis"""
        
        try:
            if not motion_analysis:
                motion_analysis = self.analyze_image_for_motion(image)
            
            logger.info("Creating AI-enhanced animation", extra={
                "motion_type": motion_analysis.get("motion_type"),
                "intensity": motion_analysis.get("intensity"),
                "complexity": motion_analysis.get("complexity")
            })
            
            # Use the determined motion type with AI-enhanced parameters
            animation_type = motion_analysis.get("motion_type", "zoom_pan")
            intensity = motion_analysis.get("intensity", 0.3)
            
            # Enhance the basic animation engine with AI insights
            if animation_type == "parallax":
                return self._create_ai_parallax(image, duration, fps, style, intensity)
            elif animation_type == "ken_burns":
                return self._create_ai_ken_burns(image, duration, fps, style, intensity)
            else:
                return self._create_ai_zoom_pan(image, duration, fps, style, intensity)
                
        except Exception as e:
            logger.warning(f"AI analysis failed, falling back to enhanced zoom_pan: {e}")
            # Fallback to a sophisticated zoom_pan with multiple phases
            return self._create_ai_zoom_pan(image, duration, fps, style, 0.4)
    
    def _create_ai_zoom_pan(self, image: Image.Image, duration: int, fps: int, 
                           style: str, intensity: float) -> List[np.ndarray]:
        """AI-enhanced zoom and pan with content-aware movement"""
        frames = []
        total_frames = duration * fps
        img_array = np.array(image)
        height, width = img_array.shape[:2]
        
        # AI-determined parameters
        max_zoom = 1.0 + (0.5 * intensity)  # Zoom based on content complexity
        
        for i in range(total_frames):
            progress = i / total_frames
            eased_progress = self._apply_easing(progress, style)
            
            # AI-enhanced zoom curve
            zoom_factor = 1.0 + ((max_zoom - 1.0) * eased_progress)
            
            # Content-aware pan (simplified - in production, use optical flow)
            pan_x = int(width * 0.08 * intensity * np.sin(eased_progress * np.pi))
            pan_y = int(height * 0.05 * intensity * np.cos(eased_progress * np.pi))
            
            frame = self._transform_frame(img_array, zoom_factor, 0, pan_x, pan_y, width, height)
            frames.append(frame)
        
        return frames
    
    def _create_ai_ken_burns(self, image: Image.Image, duration: int, fps: int, 
                            style: str, intensity: float) -> List[np.ndarray]:
        """AI-enhanced Ken Burns effect with content-aware focal points"""
        frames = []
        total_frames = duration * fps
        img_array = np.array(image)
        height, width = img_array.shape[:2]
        
        # AI-determined focal points (simplified)
        start_zoom = 1.0
        end_zoom = 1.0 + (0.6 * intensity)
        
        # Content-aware movement direction
        end_x = int(width * 0.15 * intensity)
        end_y = int(height * 0.08 * intensity)
        
        for i in range(total_frames):
            progress = i / total_frames
            eased_progress = self._apply_easing(progress, style)
            
            current_zoom = start_zoom + (end_zoom - start_zoom) * eased_progress
            current_x = int(end_x * eased_progress)
            current_y = int(end_y * eased_progress)
            
            frame = self._transform_frame(img_array, current_zoom, 0, current_x, current_y, width, height)
            frames.append(frame)
        
        return frames
    
    def _create_ai_parallax(self, image: Image.Image, duration: int, fps: int, 
                           style: str, intensity: float) -> List[np.ndarray]:
        """AI-enhanced parallax with content-aware depth simulation"""
        frames = []
        total_frames = duration * fps
        img_array = np.array(image)
        height, width = img_array.shape[:2]
        
        for i in range(total_frames):
            progress = i / total_frames
            eased_progress = self._apply_easing(progress, style)
            
            # AI-enhanced parallax movement
            zoom = 1.0 + (0.2 * intensity * np.sin(eased_progress * 2 * np.pi))
            rotation = 3 * intensity * np.sin(eased_progress * np.pi)
            
            frame = self._transform_frame(img_array, zoom, rotation, 0, 0, width, height)
            frames.append(frame)
        
        return frames
    
    def _apply_easing(self, t: float, style: str) -> float:
        """Apply easing function based on style"""
        if style == "smooth":
            return self._ease_in_out_cubic(t)
        elif style == "dramatic":
            return self._ease_in_out_quart(t)
        elif style == "gentle":
            return self._ease_in_out_sine(t)
        else:  # energetic
            return self._ease_out_bounce(t)
    
    def _transform_frame(self, img_array: np.ndarray, zoom: float, rotation: float, 
                        pan_x: int, pan_y: int, target_width: int, target_height: int) -> np.ndarray:
        """Apply transformations to frame"""
        height, width = img_array.shape[:2]
        
        # Create transformation matrix
        center = (width // 2, height // 2)
        matrix = cv2.getRotationMatrix2D(center, rotation, zoom)
        
        # Add translation
        matrix[0, 2] += pan_x
        matrix[1, 2] += pan_y
        
        # Apply transformation
        transformed = cv2.warpAffine(img_array, matrix, (width, height), flags=cv2.INTER_LANCZOS4)
        
        # Resize to target if needed
        if (height, width) != (target_height, target_width):
            transformed = cv2.resize(transformed, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
        
        return transformed
    
    # Easing functions (same as in VideoAnimationEngine)
    def _ease_in_out_cubic(self, t: float) -> float:
        return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2
    
    def _ease_in_out_quart(self, t: float) -> float:
        return 8 * t * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 4) / 2
    
    def _ease_in_out_sine(self, t: float) -> float:
        return -(np.cos(np.pi * t) - 1) / 2
    
    def _ease_out_bounce(self, t: float) -> float:
        n1 = 7.5625
        d1 = 2.75
        
        if t < 1 / d1:
            return n1 * t * t
        elif t < 2 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        elif t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        else:
            t -= 2.625 / d1
            return n1 * t * t + 0.984375

class VideoAnimationEngine:
    """Engine for creating various video animations from static images"""
    
    def __init__(self):
        self.temp_dir = TEMP_DIR
        
    def create_zoom_pan_animation(self, image: Image.Image, duration: int, fps: int, style: str = "smooth") -> List[np.ndarray]:
        """Create zoom and pan animation"""
        frames = []
        total_frames = duration * fps
        
        # Convert PIL image to numpy array
        img_array = np.array(image)
        height, width = img_array.shape[:2]
        
        logger.info(f"Creating zoom-pan animation", extra={
            "total_frames": total_frames,
            "duration": duration,
            "fps": fps,
            "image_size": f"{width}x{height}"
        })
        
        for i in range(total_frames):
            progress = i / total_frames
            
            # Apply easing based on style
            if style == "smooth":
                eased_progress = self._ease_in_out_cubic(progress)
            elif style == "dramatic":
                eased_progress = self._ease_in_out_quart(progress)
            elif style == "gentle":
                eased_progress = self._ease_in_out_sine(progress)
            else:  # energetic
                eased_progress = self._ease_out_bounce(progress)
            
            # Calculate zoom factor (1.0 to 1.3)
            zoom_factor = 1.0 + (0.3 * eased_progress)
            
            # Calculate pan offset (slight movement)
            pan_x = int(width * 0.05 * np.sin(eased_progress * np.pi))
            pan_y = int(height * 0.03 * np.cos(eased_progress * np.pi))
            
            # Create zoomed and panned frame
            frame = self._zoom_and_pan_frame(img_array, zoom_factor, pan_x, pan_y, width, height)
            frames.append(frame)
            
        return frames
    
    def create_ken_burns_effect(self, image: Image.Image, duration: int, fps: int, style: str = "smooth") -> List[np.ndarray]:
        """Create Ken Burns effect (slow zoom with pan)"""
        frames = []
        total_frames = duration * fps
        
        img_array = np.array(image)
        height, width = img_array.shape[:2]
        
        logger.info(f"Creating Ken Burns effect", extra={
            "total_frames": total_frames,
            "duration": duration,
            "fps": fps
        })
        
        # Define start and end positions/zoom
        start_zoom = 1.0
        end_zoom = 1.4
        start_x, start_y = 0, 0
        end_x = int(width * 0.1)
        end_y = int(height * 0.05)
        
        for i in range(total_frames):
            progress = i / total_frames
            eased_progress = self._ease_in_out_cubic(progress)
            
            # Interpolate zoom and position
            current_zoom = start_zoom + (end_zoom - start_zoom) * eased_progress
            current_x = int(start_x + (end_x - start_x) * eased_progress)
            current_y = int(start_y + (end_y - start_y) * eased_progress)
            
            frame = self._zoom_and_pan_frame(img_array, current_zoom, current_x, current_y, width, height)
            frames.append(frame)
            
        return frames
    
    def create_parallax_effect(self, image: Image.Image, duration: int, fps: int, style: str = "smooth") -> List[np.ndarray]:
        """Create parallax effect with multiple movement layers"""
        frames = []
        total_frames = duration * fps
        
        # Convert to numpy and create multiple layers
        img_array = np.array(image)
        height, width = img_array.shape[:2]
        
        logger.info(f"Creating parallax effect", extra={
            "total_frames": total_frames,
            "duration": duration,
            "fps": fps
        })
        
        for i in range(total_frames):
            progress = i / total_frames
            eased_progress = self._ease_in_out_cubic(progress)
            
            # Multiple layer movements at different speeds
            base_movement = eased_progress * 0.1
            
            # Create multiple offset versions
            frame = img_array.copy()
            
            # Apply subtle transformations
            zoom = 1.0 + (0.15 * np.sin(eased_progress * 2 * np.pi))
            rotation = 2 * np.sin(eased_progress * np.pi)  # degrees
            
            frame = self._apply_transform(frame, zoom, rotation, width, height)
            frames.append(frame)
            
        return frames
    
    def create_fade_effects(self, image: Image.Image, duration: int, fps: int, style: str = "smooth") -> List[np.ndarray]:
        """Create fade in/out effects with subtle movements"""
        frames = []
        total_frames = duration * fps
        
        img_array = np.array(image)
        height, width = img_array.shape[:2]
        
        logger.info(f"Creating fade effects", extra={
            "total_frames": total_frames,
            "duration": duration,
            "fps": fps
        })
        
        fade_in_frames = total_frames // 4
        fade_out_frames = total_frames // 4
        stable_frames = total_frames - fade_in_frames - fade_out_frames
        
        frame_count = 0
        
        # Fade in
        for i in range(fade_in_frames):
            alpha = i / fade_in_frames
            frame = self._apply_fade(img_array, alpha)
            frames.append(frame)
            frame_count += 1
        
        # Stable with subtle movement
        for i in range(stable_frames):
            progress = i / stable_frames
            zoom = 1.0 + (0.1 * np.sin(progress * 2 * np.pi))
            frame = self._zoom_and_pan_frame(img_array, zoom, 0, 0, width, height)
            frames.append(frame)
            frame_count += 1
        
        # Fade out
        for i in range(fade_out_frames):
            alpha = 1.0 - (i / fade_out_frames)
            frame = self._apply_fade(img_array, alpha)
            frames.append(frame)
            frame_count += 1
        
        return frames
    
    def add_text_overlays(self, frames: List[np.ndarray], text_overlay: str = None, 
                         brand_text: str = None, cta_text: str = None) -> List[np.ndarray]:
        """Add text overlays to video frames"""
        if not any([text_overlay, brand_text, cta_text]):
            return frames
        
        logger.info("Adding text overlays to frames", extra={
            "frame_count": len(frames),
            "has_text_overlay": bool(text_overlay),
            "has_brand_text": bool(brand_text),
            "has_cta_text": bool(cta_text)
        })
        
        overlaid_frames = []
        
        for i, frame in enumerate(frames):
            # Convert numpy array to PIL Image
            pil_frame = Image.fromarray(frame)
            
            # Add overlays
            pil_frame = self._add_text_to_frame(pil_frame, text_overlay, brand_text, cta_text, i, len(frames))
            
            # Convert back to numpy array
            overlaid_frames.append(np.array(pil_frame))
        
        return overlaid_frames
    
    def _add_text_to_frame(self, frame: Image.Image, text_overlay: str = None, 
                          brand_text: str = None, cta_text: str = None, frame_num: int = 0, total_frames: int = 1) -> Image.Image:
        """Add text overlay to a single frame"""
        overlay = Image.new('RGBA', frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        try:
            font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
            font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            font_cta = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        except:
            font_brand = font_text = font_cta = ImageFont.load_default()
        
        # Calculate animation progress for text effects
        progress = frame_num / max(total_frames - 1, 1)
        
        # Brand text (top-left, always visible)
        if brand_text:
            self._draw_text_with_background(
                draw, (30, 30), brand_text, font_brand,
                text_color=(255, 255, 255, 255), bg_color=(0, 0, 0, 180)
            )
        
        # Main text overlay (center, fade in after 1 second)
        if text_overlay and frame_num > (total_frames * 0.2):
            text_alpha = min(255, int((frame_num - total_frames * 0.2) / (total_frames * 0.3) * 255))
            text_y = frame.height // 2 - 50
            self._draw_text_with_background(
                draw, (frame.width // 2 - 200, text_y), text_overlay, font_text,
                text_color=(255, 255, 255, text_alpha), bg_color=(0, 100, 200, min(180, text_alpha))
            )
        
        # CTA text (bottom, appear in last 2 seconds)
        if cta_text and frame_num > (total_frames * 0.6):
            cta_alpha = min(255, int((frame_num - total_frames * 0.6) / (total_frames * 0.4) * 255))
            cta_y = frame.height - 80
            self._draw_text_with_background(
                draw, (30, cta_y), cta_text, font_cta,
                text_color=(255, 255, 255, cta_alpha), bg_color=(255, 100, 0, min(200, cta_alpha))
            )
        
        # Composite overlay onto frame
        frame = frame.convert('RGBA')
        combined = Image.alpha_composite(frame, overlay)
        return combined.convert('RGB')
    
    def _draw_text_with_background(self, draw, position, text, font, text_color, bg_color, padding=8):
        """Draw text with background box"""
        x, y = position
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        bg_rect = [x - padding, y - padding, x + text_width + padding, y + text_height + padding]
        draw.rectangle(bg_rect, fill=bg_color)
        draw.text((x, y), text, font=font, fill=text_color)
    
    def _zoom_and_pan_frame(self, img_array: np.ndarray, zoom_factor: float, pan_x: int, pan_y: int, target_width: int, target_height: int) -> np.ndarray:
        """Apply zoom and pan to a frame"""
        height, width = img_array.shape[:2]
        
        # Calculate new dimensions
        new_width = int(width * zoom_factor)
        new_height = int(height * zoom_factor)
        
        # Resize image
        resized = cv2.resize(img_array, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
        
        # Calculate crop coordinates
        start_x = max(0, (new_width - target_width) // 2 + pan_x)
        start_y = max(0, (new_height - target_height) // 2 + pan_y)
        end_x = min(new_width, start_x + target_width)
        end_y = min(new_height, start_y + target_height)
        
        # Crop to target size
        cropped = resized[start_y:end_y, start_x:end_x]
        
        # Ensure exact target size
        if cropped.shape[:2] != (target_height, target_width):
            cropped = cv2.resize(cropped, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
        
        return cropped
    
    def _apply_transform(self, img_array: np.ndarray, zoom: float, rotation: float, target_width: int, target_height: int) -> np.ndarray:
        """Apply zoom and rotation transformation"""
        height, width = img_array.shape[:2]
        
        # Create transformation matrix
        center = (width // 2, height // 2)
        matrix = cv2.getRotationMatrix2D(center, rotation, zoom)
        
        # Apply transformation
        transformed = cv2.warpAffine(img_array, matrix, (width, height), flags=cv2.INTER_LANCZOS4)
        
        # Resize to target if needed
        if (height, width) != (target_height, target_width):
            transformed = cv2.resize(transformed, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
        
        return transformed
    
    def _apply_fade(self, img_array: np.ndarray, alpha: float) -> np.ndarray:
        """Apply fade effect to frame"""
        faded = img_array.astype(np.float32)
        faded = faded * alpha
        return np.clip(faded, 0, 255).astype(np.uint8)
    
    # Easing functions
    def _ease_in_out_cubic(self, t: float) -> float:
        return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2
    
    def _ease_in_out_quart(self, t: float) -> float:
        return 8 * t * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 4) / 2
    
    def _ease_in_out_sine(self, t: float) -> float:
        return -(np.cos(np.pi * t) - 1) / 2
    
    def _ease_out_bounce(self, t: float) -> float:
        n1 = 7.5625
        d1 = 2.75
        
        if t < 1 / d1:
            return n1 * t * t
        elif t < 2 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        elif t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        else:
            t -= 2.625 / d1
            return n1 * t * t + 0.984375

# AI-based video generation setup
logger.info("Initializing AI models for video generation...")

# Check GPU availability
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

if device == "cuda":
    log_gpu_usage(logger, "before_model_loading")

# Load CLIP for image understanding (lightweight, used for motion planning)
try:
    with TimingContext("clip_model_loading", logger):
        clip_processor = CLIPImageProcessor.from_pretrained("openai/clip-vit-base-patch32")
        clip_model = CLIPVisionModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
        logger.info("CLIP model loaded successfully")
except Exception as e:
    logger.warning(f"Could not load CLIP model: {e}. Using basic animation engine.")
    clip_processor = None
    clip_model = None

if device == "cuda":
    log_gpu_usage(logger, "after_clip_loading")

# Load Stable Video Diffusion for AI video generation
svd_pipeline = None
try:
    with TimingContext("svd_model_loading", logger):
        logger.info("Loading Stable Video Diffusion model...")
        svd_pipeline = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid-xt",
            torch_dtype=torch.float16,
            variant="fp16"
        ).to(device)
        logger.info("Stable Video Diffusion model loaded successfully")
        if device == "cuda":
            log_gpu_usage(logger, "after_svd_loading")
except Exception as e:
    logger.warning(f"Could not load SVD model: {e}. Falling back to basic animation.")
    svd_pipeline = None

# Initialize animation engines
animation_engine = VideoAnimationEngine()
ai_animation_engine = AIVideoAnimationEngine(device, clip_model, clip_processor) if clip_model else None

def download_image_from_url(image_url: str) -> Image.Image:
    """Download image from URL"""
    try:
        logger.info(f"Downloading image from URL", extra={"image_url": image_url})
        
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        image = Image.open(BytesIO(response.content)).convert('RGB')
        logger.info(f"Image downloaded successfully", extra={
            "image_size": image.size,
            "image_mode": image.mode
        })
        
        return image
        
    except Exception as e:
        logger.error(f"Error downloading image", extra={
            "image_url": image_url,
            "error": str(e)
        })
        raise HTTPException(status_code=400, detail=f"Error downloading image: {str(e)}")

def generate_ai_video_from_image(image: Image.Image, prompt: str = "", duration_frames: int = 25) -> str:
    """Generate AI video using Stable Video Diffusion"""
    
    if not svd_pipeline:
        raise HTTPException(status_code=503, detail="AI video generation not available - SVD model not loaded")
    
    try:
        with TimingContext("ai_video_generation", logger):
            logger.info("Starting AI video generation", extra={
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "duration_frames": duration_frames,
                "input_image_size": image.size
            })
            
            # Resize image for SVD (typically requires specific dimensions)
            target_size = (1024, 576)  # SVD's preferred aspect ratio
            image_resized = image.resize(target_size, Image.Resampling.LANCZOS)
            
            # Generate video frames using SVD
            with torch.no_grad():
                frames = svd_pipeline(
                    image=image_resized,
                    height=target_size[1],
                    width=target_size[0],
                    num_frames=duration_frames,
                    motion_bucket_id=127,  # Controls motion intensity (1-255)
                    fps=7,  # SVD works best at 7 FPS
                    noise_aug_strength=0.1,  # Slight noise for variation
                    decode_chunk_size=8,  # Memory optimization
                ).frames[0]
            
            # Convert frames to numpy arrays
            video_frames = []
            for frame in frames:
                # Convert PIL to numpy array
                frame_np = np.array(frame)
                video_frames.append(frame_np)
            
            # Save as MP4
            filename = f"{uuid.uuid4()}.mp4"
            video_path = os.path.join(VIDEOS_DIR, filename)
            
            # Use imageio to save with better quality
            with imageio.get_writer(
                video_path, 
                fps=15,  # Upsampled from 7 FPS for smoother playback
                codec='libx264',
                output_params=[
                    '-pix_fmt', 'yuv420p',
                    '-profile:v', 'high', 
                    '-level', '4.0',
                    '-crf', '18',  # High quality
                    '-preset', 'slow'  # Better compression
                ]
            ) as writer:
                # Interpolate frames for smoother playback
                for i, frame in enumerate(video_frames):
                    writer.append_data(frame)
                    # Add interpolated frame (simple duplication for now)
                    if i < len(video_frames) - 1:
                        writer.append_data(frame)
            
            file_size = os.path.getsize(video_path)
            logger.info("AI video generation completed", extra={
                "video_filename": filename,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / 1024 / 1024, 2),
                "frames_generated": len(video_frames),
                "output_fps": 15
            })
            
            # Schedule cleanup after 15 minutes
            video_timestamps[filename] = time.time()
            cleanup_thread = threading.Thread(target=cleanup_video, args=(video_path, filename))
            cleanup_thread.daemon = True
            cleanup_thread.start()
            
            return filename
            
    except Exception as e:
        logger.error("AI video generation failed", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise HTTPException(status_code=500, detail=f"AI video generation failed: {str(e)}")

def cleanup_video(video_path: str, filename: str):
    """Delete video file after 15 minutes"""
    time.sleep(900)  # 15 minutes = 900 seconds
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
        "cleanup_in_minutes": 15
    })

@app.post("/generate")
async def generate_video(data: VideoRequest):
    """Generate video from image with specified animation"""
    timer = None
    try:
        with TimingContext("video_generation_full", logger) as timer:
            logger.info("Video generation request received", extra={
                "animation_type": data.animation_type,
                "duration": data.duration,
                "fps": data.fps,
                "style": data.style,
                "has_image_url": bool(data.image_url),
                "has_text_overlay": bool(data.text_overlay),
                "has_brand_text": bool(data.brand_text),
                "has_cta_text": bool(data.cta_text)
            })
            
            if not data.image_url:
                raise HTTPException(status_code=400, detail="image_url is required")
            
            # Download image
            with TimingContext("image_download", logger):
                image = download_image_from_url(data.image_url)
                
                # Resize image to standard video dimensions if needed
                if image.size != (DEFAULT_WIDTH, DEFAULT_HEIGHT):
                    image = image.resize((DEFAULT_WIDTH, DEFAULT_HEIGHT), Image.Resampling.LANCZOS)
                    logger.info(f"Image resized to {DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
            
            # Generate animation frames
            with TimingContext("animation_generation", logger):
                logger.info(f"Generating {data.animation_type} animation")
                
                if data.animation_type == "zoom_pan":
                    frames = animation_engine.create_zoom_pan_animation(image, data.duration, data.fps, data.style)
                elif data.animation_type == "ken_burns":
                    frames = animation_engine.create_ken_burns_effect(image, data.duration, data.fps, data.style)
                elif data.animation_type == "parallax":
                    frames = animation_engine.create_parallax_effect(image, data.duration, data.fps, data.style)
                elif data.animation_type == "fade_effects":
                    frames = animation_engine.create_fade_effects(image, data.duration, data.fps, data.style)
                elif data.animation_type == "ai_enhanced":
                    frames = animation_engine.create_ai_enhanced_animation(image, data.duration, data.fps, data.style)
                else:
                    raise HTTPException(status_code=400, detail=f"Unknown animation type: {data.animation_type}")
                
                logger.info(f"Generated {len(frames)} frames")
            
            # Add text overlays if specified
            if any([data.text_overlay, data.brand_text, data.cta_text]):
                with TimingContext("text_overlay_addition", logger):
                    frames = animation_engine.add_text_overlays(
                        frames, data.text_overlay, data.brand_text, data.cta_text
                    )
            
            # Create video file
            with TimingContext("video_encoding", logger):
                filename = f"{uuid.uuid4()}.mp4"
                video_path = os.path.join(VIDEOS_DIR, filename)
                
                logger.info(f"Encoding video to {video_path}")
                
                # Use imageio to create MP4 with highly compatible encoding
                with imageio.get_writer(
                    video_path, 
                    fps=data.fps, 
                    codec='libx264',
                    output_params=[
                        '-pix_fmt', 'yuv420p',
                        '-profile:v', 'baseline', 
                        '-level', '3.0',
                        '-crf', '23', 
                        '-preset', 'medium',
                        '-movflags', '+faststart'
                    ]
                ) as writer:
                    for frame in frames:
                        writer.append_data(frame)
                
                # Verify file was created and get size
                if not os.path.exists(video_path):
                    raise FileNotFoundError(f"Video file was not created: {video_path}")
                
                file_size = os.path.getsize(video_path)
                logger.info("Video encoded successfully", extra={
                    "video_filename": filename,
                    "file_size_bytes": file_size,
                    "file_size_mb": round(file_size / 1024 / 1024, 2),
                    "frame_count": len(frames)
                })
            
            # Track creation time and schedule cleanup
            video_timestamps[filename] = time.time()
            schedule_cleanup(video_path, filename)
            
            logger.info("Video generation completed successfully", extra={
                "video_filename": filename,
                "total_duration_ms": round(timer.duration_ms, 2),
                "file_size_mb": round(file_size / 1024 / 1024, 2)
            })
            
            return {
                "filename": filename,
                "download_url": f"/download/{filename}",
                "expires_in_minutes": 15,
                "file_size_mb": round(file_size / 1024 / 1024, 2),
                "duration_seconds": data.duration,
                "fps": data.fps,
                "animation_type": data.animation_type
            }
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = {
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(timer.duration_ms, 2) if timer else None,
            "traceback": traceback.format_exc()
        }
        
        logger.error("Unexpected error during video generation", extra=error_details)
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")

@app.post("/generate-from-upload")
async def generate_video_from_upload(
    file: UploadFile = File(...),
    animation_type: str = "zoom_pan",
    duration: int = 5,
    fps: int = 30,
    style: str = "smooth",
    text_overlay: Optional[str] = None,
    brand_text: Optional[str] = None,
    cta_text: Optional[str] = None
):
    """Generate video from uploaded image file"""
    timer = None
    try:
        with TimingContext("video_generation_upload", logger) as timer:
            logger.info("Video generation from upload request received", extra={
                "filename": file.filename,
                "content_type": file.content_type,
                "animation_type": animation_type,
                "duration": duration,
                "fps": fps
            })
            
            # Validate file type
            if not file.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="File must be an image")
            
            # Read and process uploaded image
            with TimingContext("image_processing", logger):
                contents = await file.read()
                image = Image.open(BytesIO(contents)).convert('RGB')
                
                # Resize if needed
                if image.size != (DEFAULT_WIDTH, DEFAULT_HEIGHT):
                    image = image.resize((DEFAULT_WIDTH, DEFAULT_HEIGHT), Image.Resampling.LANCZOS)
                    logger.info(f"Image resized to {DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
            
            # Generate animation frames
            with TimingContext("animation_generation", logger):
                if animation_type == "zoom_pan":
                    frames = animation_engine.create_zoom_pan_animation(image, duration, fps, style)
                elif animation_type == "ken_burns":
                    frames = animation_engine.create_ken_burns_effect(image, duration, fps, style)
                elif animation_type == "parallax":
                    frames = animation_engine.create_parallax_effect(image, duration, fps, style)
                elif animation_type == "fade_effects":
                    frames = animation_engine.create_fade_effects(image, duration, fps, style)
                else:
                    raise HTTPException(status_code=400, detail=f"Unknown animation type: {animation_type}")
            
            # Add text overlays if specified
            if any([text_overlay, brand_text, cta_text]):
                with TimingContext("text_overlay_addition", logger):
                    frames = animation_engine.add_text_overlays(frames, text_overlay, brand_text, cta_text)
            
            # Create video file
            with TimingContext("video_encoding", logger):
                filename = f"{uuid.uuid4()}.mp4"
                video_path = os.path.join(VIDEOS_DIR, filename)
                
                with imageio.get_writer(
                    video_path, 
                    fps=fps, 
                    codec='libx264',
                    output_params=[
                        '-pix_fmt', 'yuv420p',
                        '-profile:v', 'baseline', 
                        '-level', '3.0',
                        '-crf', '23', 
                        '-preset', 'medium',
                        '-movflags', '+faststart'
                    ]
                ) as writer:
                    for frame in frames:
                        writer.append_data(frame)
                
                file_size = os.path.getsize(video_path)
            
            # Track and schedule cleanup
            video_timestamps[filename] = time.time()
            schedule_cleanup(video_path, filename)
            
            logger.info("Video generation from upload completed", extra={
                "video_filename": filename,
                "total_duration_ms": round(timer.duration_ms, 2),
                "file_size_mb": round(file_size / 1024 / 1024, 2)
            })
            
            return {
                "filename": filename,
                "download_url": f"/download/{filename}",
                "expires_in_minutes": 15,
                "file_size_mb": round(file_size / 1024 / 1024, 2)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error("Error in video generation from upload", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(timer.duration_ms, 2) if timer else None,
            "traceback": traceback.format_exc()
        })
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")

@app.post("/generate-ai-video")
async def generate_ai_video(request: AIVideoRequest):
    """Generate AI video using Stable Video Diffusion"""
    try:
        logger.info("AI video generation request received", extra={
            "image_url": request.image_url,
            "prompt": request.prompt[:100] + "..." if len(request.prompt) > 100 else request.prompt,
            "duration_frames": request.duration_frames
        })
        
        # Download image
        image = download_image_from_url(request.image_url)
        
        # Generate AI video
        filename = generate_ai_video_from_image(
            image=image, 
            prompt=request.prompt, 
            duration_frames=request.duration_frames
        )
        
        return {
            "filename": filename, 
            "status": "success", 
            "type": "ai_generated",
            "download_url": f"/download/{filename}",
            "expires_in_minutes": 15
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI video generation failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"AI video generation failed: {str(e)}")

@app.get("/download/{filename}")
def download_video(filename: str, request: Request):
    """Download endpoint for generated videos"""
    with TimingContext("video_download", logger, {"video_filename": filename}):
        client_ip = request.client.host if request.client else "unknown"
        logger.info("Video download request", extra={
            "video_filename": filename,
            "client_ip": client_ip
        })
        
        video_path = os.path.join(VIDEOS_DIR, filename)
        
        # Check if file exists
        if not os.path.exists(video_path):
            logger.warning("Video file not found", extra={
                "video_filename": filename,
                "video_path": video_path,
                "client_ip": client_ip
            })
            raise HTTPException(status_code=404, detail="Video not found or has expired")
        
        # Check if video has expired (more than 15 minutes old)
        if filename in video_timestamps:
            creation_time = video_timestamps[filename]
            elapsed_time = time.time() - creation_time
            if elapsed_time > 900:  # 15 minutes
                logger.info("Video has expired, cleaning up", extra={
                    "video_filename": filename,
                    "elapsed_minutes": round(elapsed_time / 60, 1),
                    "client_ip": client_ip
                })
                try:
                    os.remove(video_path)
                    del video_timestamps[filename]
                except Exception as e:
                    logger.error("Error removing expired video", extra={
                        "video_filename": filename,
                        "error": str(e)
                    })
                raise HTTPException(status_code=404, detail="Video has expired")
        
        # Get file size for logging
        try:
            file_size = os.path.getsize(video_path)
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
            path=video_path,
            filename=filename,
            media_type="video/mp4",
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600"
            }
        )

@app.get("/status/{filename}")
def check_video_status(filename: str):
    """Check if a video is still available"""
    video_path = os.path.join(VIDEOS_DIR, filename)
    
    if not os.path.exists(video_path):
        return {"status": "not_found", "message": "Video not found or has expired"}
    
    if filename in video_timestamps:
        creation_time = video_timestamps[filename]
        elapsed_time = time.time() - creation_time
        remaining_time = max(0, 900 - elapsed_time)  # 15 minutes = 900 seconds
        
        if remaining_time > 0:
            return {
                "status": "available",
                "remaining_minutes": round(remaining_time / 60, 1),
                "download_url": f"/download/{filename}",
                "file_size_mb": round(os.path.getsize(video_path) / 1024 / 1024, 2)
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
        "supported_animations": ["zoom_pan", "ken_burns", "parallax", "fade_effects"],
        "supported_styles": ["smooth", "dramatic", "gentle", "energetic"]
    }

logger.info("Video generator service ready")