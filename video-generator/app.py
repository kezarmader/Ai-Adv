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
from diffusers import StableDiffusionPipeline, DDIMScheduler
from transformers import CLIPVisionModel, CLIPImageProcessor

# Try to import SVD - will be checked after logger is set up
try:
    from diffusers import StableVideoDiffusionPipeline
    SVD_AVAILABLE = True
except ImportError:
    StableVideoDiffusionPipeline = None
    SVD_AVAILABLE = False
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

class ProductMetadata(BaseModel):
    """Factual product data from ASIN service"""
    product_title: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    product_type: Optional[str] = None
    features: Optional[List[str]] = None
    use_case: Optional[str] = None
    target_audience: Optional[str] = None
    keywords: Optional[List[str]] = None

class VideoRequest(BaseModel):
    image_url: Optional[str] = None
    animation_type: str = "zoom_pan"  # zoom_pan, fade_effects, parallax, ken_burns
    duration: int = 8  # PREMIUM: Longer duration for mobile Reels (8-15 seconds optimal)
    fps: int = 30
    audio_prompt: Optional[str] = None
    style: str = "smooth"  # smooth, dramatic, gentle, energetic
    text_overlay: Optional[str] = None
    brand_text: Optional[str] = None
    cta_text: Optional[str] = None
    use_model: bool = False  # Whether to create a model scene first (disabled for better quality)
    product_metadata: Optional[ProductMetadata] = None  # Factual product data from ASIN service

class AIVideoRequest(BaseModel):
    image_url: str
    prompt: str = "dramatic transformation with dynamic motion"
    duration_frames: int = 60  # PREMIUM: Longer videos for high-quality mobile Reels
    product_metadata: Optional[ProductMetadata] = None  # Factual product data from ASIN service

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

# Check GPU availability and configure CUDA memory management
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

if device == "cuda":
    # MEMORY FIX: Configure CUDA memory allocation to reduce fragmentation
    import os
    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
    
    # MEMORY FIX: Set memory fraction to prevent OOM
    torch.cuda.set_per_process_memory_fraction(0.9)  # Use 90% of available GPU memory
    torch.cuda.empty_cache()
    
    log_gpu_usage(logger, "before_model_loading")

# Load CLIP for image understanding (lightweight, used for motion planning)
try:
    with TimingContext("clip_model_loading", logger):
        clip_processor = CLIPImageProcessor.from_pretrained("openai/clip-vit-base-patch32")
        clip_model = CLIPVisionModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
        logger.info("CLIP model loaded successfully")
except Exception as e:
    logger.warning(f"Could not load CLIP model: {e}. Image analysis features will be limited.")
    clip_processor = None
    clip_model = None

# Load image generation model for creating model scenes
try:
    with TimingContext("image_generation_model_loading", logger):
        logger.info("Loading image generation model for product modeling...")
        from diffusers import StableDiffusionXLPipeline
        
        # Use a lighter SDXL model for product modeling
        image_pipeline = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True
        ).to(device)
        
        # Enable memory efficient attention
        image_pipeline.enable_model_cpu_offload()
        image_pipeline.enable_vae_slicing()
        
        logger.info("Image generation model loaded successfully")
except Exception as e:
    logger.warning(f"Could not load image generation model: {e}. Product modeling features will be limited.")
    image_pipeline = None

if device == "cuda":
    log_gpu_usage(logger, "after_clip_loading")

def _enhance_for_svd(image: Image.Image) -> Image.Image:
    """PREMIUM ENHANCEMENT: Maximum quality enhancement for mobile Reels"""
    # PREMIUM: Strong contrast for mobile screen visibility
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.35)  # Higher contrast for mobile screens
    
    # PREMIUM: Maximum sharpness for crystal clear product details
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.6)  # Very high sharpness for mobile clarity
    
    # PREMIUM: Vibrant colors that pop on mobile screens
    enhancer = ImageEnhance.Color(image)
    image = enhancer.enhance(1.25)  # Strong color enhancement for mobile impact
    
    # PREMIUM: Optimized brightness for mobile viewing
    enhancer = ImageEnhance.Brightness(image)
    image = enhancer.enhance(1.08)  # Brighter for mobile screens
    
    # PREMIUM: Apply slight unsharp mask effect for even more detail
    image = image.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=2))
    
    return image

def _resize_with_smart_crop(image: Image.Image, target_size: tuple) -> Image.Image:
    """Resize image to target size using intelligent cropping to preserve important content"""
    target_width, target_height = target_size
    original_width, original_height = image.size
    
    target_aspect = target_width / target_height
    original_aspect = original_width / original_height
    
    if abs(target_aspect - original_aspect) < 0.1:
        # Aspect ratios are close, just resize
        return image.resize(target_size, Image.Resampling.LANCZOS)
    
    # Calculate crop dimensions to match target aspect ratio
    if original_aspect > target_aspect:
        # Original is wider, crop width (keep height)
        new_width = int(original_height * target_aspect)
        new_height = original_height
        # Center crop horizontally
        left = (original_width - new_width) // 2
        top = 0
    else:
        # Original is taller, crop height (keep width)
        new_width = original_width
        new_height = int(original_width / target_aspect)
        # Crop from top to preserve subject (products usually centered-top)
        left = 0
        top = max(0, (original_height - new_height) // 4)  # Slight bias toward top
    
    # Crop the image
    cropped = image.crop((left, top, left + new_width, top + new_height))
    
    # Resize to exact target size
    return cropped.resize(target_size, Image.Resampling.LANCZOS)

# Load Stable Video Diffusion with nightly PyTorch - MEMORY OPTIMIZED
svd_pipeline = None
if not SVD_AVAILABLE:
    logger.warning("StableVideoDiffusionPipeline not available - check diffusers version")
else:
    try:
        with TimingContext("svd_model_loading", logger):
            logger.info("Loading Stable Video Diffusion model with MEMORY OPTIMIZATION...", extra={
                "pytorch_version": "nightly",
                "cuda_version": "12.8", 
                "diffusers_available": SVD_AVAILABLE,
                "memory_optimization": "enabled"
            })
            
            # MEMORY FIX: Free up GPU memory before loading SVD
            if device == "cuda":
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            # MEMORY FIX: Load SVD with maximum memory efficiency
            svd_pipeline = StableVideoDiffusionPipeline.from_pretrained(
                "stabilityai/stable-video-diffusion-img2vid-xt",
                torch_dtype=torch.float16,
                variant="fp16",
                low_cpu_mem_usage=True  # MEMORY FIX: Reduce CPU memory usage
            )
            
            # MEMORY FIX: Enable all memory optimizations BEFORE moving to GPU
            svd_pipeline.enable_model_cpu_offload()  # Keep models on CPU until needed
            svd_pipeline.enable_vae_slicing()        # Process VAE in slices
            svd_pipeline.enable_vae_tiling()         # Process VAE in tiles
            
            # MEMORY FIX: Move to GPU with sequential loading
            if device == "cuda":
                svd_pipeline = svd_pipeline.to(device)
                torch.cuda.empty_cache()  # Clean up after GPU transfer
                
            logger.info("Stable Video Diffusion model loaded with MEMORY OPTIMIZATION", extra={
                "memory_optimizations": ["cpu_offload", "vae_slicing", "vae_tiling", "low_cpu_mem_usage"]
            })
            if device == "cuda":
                log_gpu_usage(logger, "after_svd_loading_optimized")
    except Exception as e:
        logger.error(f"Failed to load SVD model: {e}. Check GPU compatibility and model availability.")
        svd_pipeline = None

# Animation engines not needed - using pure AI generation

# Startup validation
def validate_service_requirements():
    """Validate that service can run with required GPU and AI models"""
    issues = []
    
    if device == "cpu":
        issues.append("Service requires GPU but CPU detected")
        logger.warning("Service requires GPU but CPU detected")
    
    if not torch.cuda.is_available():
        issues.append("CUDA not available - GPU required for AI video generation")
        logger.warning("CUDA not available - GPU required for AI video generation")
    
    if not SVD_AVAILABLE:
        issues.append("StableVideoDiffusionPipeline not available - diffusers version too old")
        logger.warning("StableVideoDiffusionPipeline not available - diffusers version too old")
    
    if not svd_pipeline:
        issues.append("Stable Video Diffusion model not loaded")
        logger.warning("Stable Video Diffusion model not loaded")
    
    if not image_pipeline:
        logger.info("Image generation model not loaded - model scenes will be disabled")
    
    if not issues:
        logger.info("Service validation passed", extra={
            "device": device,
            "gpu_available": True,
            "svd_loaded": True,
            "mode": "gpu_ai_only"
        })
        return True
    else:
        logger.warning("Service validation found issues", extra={
            "issues": issues,
            "service_degraded": True
        })
        return False

# Validate service requirements on startup
service_ready = validate_service_requirements()

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

def extract_product_info_from_metadata(metadata: ProductMetadata) -> dict:
    """Extract factual product information from ASIN service metadata"""
    
    if not metadata:
        # Fallback minimal info when no metadata provided
        return {
            "type": "product",
            "use_case": "general product showcase", 
            "context": "professional presentation",
            "brand": "premium brand",
            "category": "lifestyle product",
            "target_audience": "consumers"
        }
    
    # Use factual data from ASIN service
    product_info = {
        "type": metadata.product_type or "product",
        "use_case": metadata.use_case or "product demonstration",
        "context": f"{metadata.category or 'lifestyle'} focused presentation",
        "brand": metadata.brand or "premium brand",
        "category": metadata.category or "consumer product",
        "target_audience": metadata.target_audience or "consumers",
        "title": metadata.product_title or "product",
        "features": metadata.features or [],
        "keywords": metadata.keywords or []
    }
    
    return product_info

def create_model_scene(product_image: Image.Image, product_type: str) -> Image.Image:
    """Create a lifestyle scene with a model using/demonstrating the product"""
    
    if not image_pipeline:
        logger.warning("Image generation model not available, returning original product image")
        return product_image
    
    try:
        with TimingContext("model_scene_generation", logger):
            logger.info("Creating model scene", extra={
                "product_type": product_type,
                "original_size": product_image.size
            })
            
            # Define prompts based on product type
            model_prompts = {
                "skincare": "professional model applying skincare product, clean modern bathroom, soft natural lighting, commercial photography style, elegant hands, serene expression",
                "cosmetics": "beautiful model using makeup product, professional makeup studio, perfect lighting, glamorous style, confident expression, commercial beauty photography",
                "bottle": "athletic person using water bottle or supplement, gym or outdoor setting, active lifestyle, professional fitness photography, dynamic pose",
                "tech": "person using tech gadget, modern minimalist setting, professional product photography, focused expression, clean aesthetic",
                "accessory": "stylish person wearing or using accessory, fashion photography style, professional lighting, modern urban background"
            }
            
            base_prompt = model_prompts.get(product_type, model_prompts["accessory"])
            full_prompt = f"{base_prompt}, high quality, commercial advertisement style, 8k resolution, professional photography"
            
            negative_prompt = "low quality, blurry, distorted, amateur, poor lighting, cluttered background, unprofessional"
            
            # Generate the model scene
            with torch.no_grad():
                generated_images = image_pipeline(
                    prompt=full_prompt,
                    negative_prompt=negative_prompt,
                    num_inference_steps=25,  # Balanced quality/speed
                    guidance_scale=7.5,
                    width=768,
                    height=768,
                    num_images_per_prompt=1
                ).images
            
            model_scene = generated_images[0]
            
            # Composite the original product into the scene
            # This is a simple overlay - in production, you'd use more sophisticated blending
            scene_with_product = composite_product_into_scene(model_scene, product_image, product_type)
            
            logger.info("Model scene created successfully", extra={
                "generated_size": model_scene.size,
                "final_size": scene_with_product.size
            })
            
            return scene_with_product
            
    except Exception as e:
        logger.error("Failed to create model scene", extra={
            "error": str(e),
            "product_type": product_type
        })
        # Fallback to original product image
        return product_image

def composite_product_into_scene(scene: Image.Image, product: Image.Image, product_type: str) -> Image.Image:
    """Composite the product image into the generated model scene"""
    try:
        # Create a copy of the scene
        composite = scene.copy()
        
        # Resize product to appropriate size for compositing
        scene_width, scene_height = scene.size
        
        # Size the product based on type
        size_ratios = {
            "skincare": 0.15,    # Small, held in hands
            "cosmetics": 0.12,   # Small makeup item
            "bottle": 0.2,       # Medium bottle
            "tech": 0.25,        # Larger tech device
            "accessory": 0.18    # Medium accessory
        }
        
        ratio = size_ratios.get(product_type, 0.15)
        product_size = int(min(scene_width, scene_height) * ratio)
        
        # Maintain aspect ratio when resizing
        product_aspect = product.size[0] / product.size[1]
        if product_aspect > 1:
            # Wider than tall
            new_width = product_size
            new_height = int(product_size / product_aspect)
        else:
            # Taller than wide
            new_height = product_size
            new_width = int(product_size * product_aspect)
        
        product_resized = product.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Position based on product type
        positions = {
            "skincare": (int(scene_width * 0.7), int(scene_height * 0.6)),  # Lower right, in hands area
            "cosmetics": (int(scene_width * 0.65), int(scene_height * 0.5)), # Center-right
            "bottle": (int(scene_width * 0.75), int(scene_height * 0.4)),    # Upper right
            "tech": (int(scene_width * 0.6), int(scene_height * 0.6)),       # Center-right
            "accessory": (int(scene_width * 0.5), int(scene_height * 0.7))   # Center-bottom
        }
        
        pos_x, pos_y = positions.get(product_type, (int(scene_width * 0.7), int(scene_height * 0.6)))
        
        # Ensure the product fits within scene bounds
        pos_x = min(pos_x, scene_width - new_width)
        pos_y = min(pos_y, scene_height - new_height)
        
        # Create a mask for smoother blending
        mask = Image.new('L', product_resized.size, 255)
        
        # Apply slight transparency to blend better
        if product_resized.mode != 'RGBA':
            product_resized = product_resized.convert('RGBA')
        
        # Reduce opacity slightly for natural integration
        alpha_data = list(product_resized.getdata())
        alpha_data = [(r, g, b, int(a * 0.95)) for r, g, b, a in alpha_data]
        product_resized.putdata(alpha_data)
        
        # Paste the product onto the scene
        composite.paste(product_resized, (pos_x, pos_y), product_resized)
        
        return composite
        
    except Exception as e:
        logger.error("Failed to composite product into scene", extra={"error": str(e)})
        # Return the scene without product overlay
        return scene

def generate_factual_use_case_prompt(product_info: dict, style: str) -> str:
    """Generate intelligent prompts based on FACTUAL product data from ASIN service"""
    
    # Extract factual data
    product_type = product_info.get("type", "product")
    use_case = product_info.get("use_case", "product demonstration")
    context = product_info.get("context", "professional presentation")
    brand = product_info.get("brand", "premium brand")
    category = product_info.get("category", "consumer product")
    target_audience = product_info.get("target_audience", "consumers")
    title = product_info.get("title", "product")
    features = product_info.get("features", [])
    keywords = product_info.get("keywords", [])
    
    # Build factual prompt components
    main_components = []
    
    # Primary product showcase
    if brand and brand != "premium brand":
        main_components.append(f"Professional {brand} {product_type} showcase")
    else:
        main_components.append(f"Professional {product_type} demonstration")
    
    # Add specific use case from ASIN data
    if use_case and use_case != "product demonstration":
        main_components.append(f"highlighting {use_case}")
    
    # Add category context
    if category and category != "consumer product":
        main_components.append(f"in {category} market context")
    
    # Add key features if available
    if features:
        key_features = ", ".join(features[:3])  # Use top 3 features
        main_components.append(f"emphasizing {key_features}")
    
    # Add target audience context
    if target_audience and target_audience != "consumers":
        main_components.append(f"designed for {target_audience}")
    
    # Combine main components
    main_prompt = " ".join(main_components)
    
    # PREMIUM: Mobile Reels-optimized style enhancements
    style_enhancements = {
        "smooth": "with smooth, flowing camera movements optimized for mobile viewing and social media engagement",
        "dramatic": "with dramatic lighting, bold shadows, and cinematic appeal perfect for viral mobile content", 
        "energetic": "with dynamic motion, vibrant energy, and high-impact presentation designed for mobile screens",
        "gentle": "with soft, calming movements and peaceful atmosphere ideal for wellness and lifestyle content",
        "product show": "with professional studio lighting, precise product focus, and premium commercial quality for mobile advertising"
    }
    
    style_enhancement = style_enhancements.get(style, style_enhancements["smooth"])
    
    # Add keywords for better context if available
    keyword_context = ""
    if keywords:
        relevant_keywords = ", ".join(keywords[:3])  # Use top 3 keywords
        keyword_context = f", featuring {relevant_keywords}"
    
    # PREMIUM: Mobile Reels quality specifications
    quality_spec = "ultra-high definition mobile-optimized quality, perfect for Instagram Reels and TikTok, crystal clear product visibility with enhanced mobile contrast and sharpness"
    
    # Combine everything factually
    final_prompt = f"{main_prompt} {style_enhancement}{keyword_context}, {quality_spec}, premium studio lighting, professional mobile cinematography, vertical format optimization, social media ready"
    
    return final_prompt

def generate_ai_video_from_image(image: Image.Image, prompt: str = "", duration_frames: int = 40, style: str = "smooth", product_metadata: ProductMetadata = None) -> str:
    """Generate AI video using Stable Video Diffusion - GPU ONLY"""
    
    # Strict requirements - no fallbacks
    if not SVD_AVAILABLE:
        raise HTTPException(status_code=503, detail="StableVideoDiffusionPipeline not available - upgrade diffusers to >=0.24.0")
    
    if not svd_pipeline:
        raise HTTPException(status_code=503, detail="AI video generation not available - SVD model not loaded")
    
    if device == "cpu":
        raise HTTPException(status_code=503, detail="GPU required for AI video generation - CPU not allowed")
    
    try:
        with TimingContext("ai_video_generation", logger):
            logger.info("Starting AI video generation", extra={
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "duration_frames": duration_frames,
                "input_image_size": image.size
            })
            
            # Smart resize for SVD while preserving aspect ratio
            original_width, original_height = image.size
            original_aspect = original_width / original_height
            
            # PREMIUM QUALITY: Prioritize vertical format for mobile/Reels
            # Force vertical orientation for maximum mobile compatibility and quality
            if original_aspect > 1.5:  # Very wide - crop to vertical for mobile
                target_size = (576, 1024)  # 9:16 - Premium mobile vertical
            elif original_aspect > 1.0:  # Landscape - convert to square or vertical
                target_size = (768, 768)   # 1:1 - Instagram square format
            else:  # Portrait or square - optimize for vertical
                target_size = (576, 1024)  # 9:16 - Premium mobile vertical (best for Reels)
            
            # Extract factual product information from ASIN service metadata
            product_info = extract_product_info_from_metadata(product_metadata)
            
            # Generate intelligent prompt if none provided
            if not prompt or prompt == "dramatic transformation with dynamic motion":
                prompt = generate_factual_use_case_prompt(product_info, style)
                logger.info("Generated factual use case prompt from ASIN data", extra={
                    "product_type": product_info.get("type"),
                    "use_case": product_info.get("use_case"),
                    "brand": product_info.get("brand"),
                    "category": product_info.get("category"),
                    "has_metadata": bool(product_metadata),
                    "generated_prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt
                })
            
            # Resize with smart cropping to preserve content quality
            image_resized = _resize_with_smart_crop(image, target_size)
            
            # Enhance image quality for better SVD results
            image_resized = _enhance_for_svd(image_resized)
            
            logger.info("Image resized and enhanced for SVD", extra={
                "original_size": image.size,
                "original_aspect": f"{original_aspect:.3f}",
                "target_size": target_size,
                "target_aspect": f"{target_size[0]/target_size[1]:.3f}",
                "product_info": product_info
            })
            
            # PREMIUM MOTION: Optimized for engaging mobile Reels
            style_motion_map = {
                "smooth": 45,        # Smooth, engaging motion for mobile viewing
                "gentle": 35,        # Gentle but noticeable motion for Reels
                "dramatic": 75,      # Bold dramatic motion for viral potential
                "energetic": 85,     # High-energy motion for active products
                "product show": 40   # Professional but engaging motion for product focus
            }
            
            motion_intensity = style_motion_map.get(style, 40)  # Default engaging for mobile
            
            # MEMORY-OPTIMIZED SVD GENERATION: Balance quality and memory usage
            # Clear GPU cache before generation
            if device == "cuda":
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            with torch.no_grad():
                frames = svd_pipeline(
                    image=image_resized,
                    height=target_size[1],
                    width=target_size[0],
                    num_frames=duration_frames,
                    motion_bucket_id=motion_intensity,  # Engaging motion for mobile
                    fps=7,  # SVD's optimal generation FPS
                    noise_aug_strength=0.02,  # MEMORY FIX: Slightly higher noise for less memory
                    decode_chunk_size=2,  # MEMORY FIX: Larger chunks to reduce memory fragmentation
                    num_videos_per_prompt=1,  # Generate single high-quality video
                    generator=torch.Generator().manual_seed(42)  # Consistent quality
                ).frames[0]
            
            # MEMORY FIX: Clear cache after generation
            if device == "cuda":
                torch.cuda.empty_cache()
            
            # Convert frames to numpy arrays
            video_frames = []
            for frame in frames:
                # Convert PIL to numpy array
                frame_np = np.array(frame)
                video_frames.append(frame_np)
            
            # Save as MP4
            filename = f"{uuid.uuid4()}.mp4"
            video_path = os.path.join(VIDEOS_DIR, filename)
            
            # PREMIUM ENCODING: Maximum quality for mobile Reels - time and memory intensive
            with imageio.get_writer(
                video_path, 
                fps=30,  # High FPS for ultra-smooth mobile playback
                codec='libx264',
                output_params=[
                    '-pix_fmt', 'yuv420p',
                    '-profile:v', 'high', 
                    '-level', '5.1',  # Higher level for better quality
                    '-crf', '8',   # PREMIUM: Near-lossless quality (8-12 is visually lossless)
                    '-preset', 'veryslow',  # PREMIUM: Maximum compression efficiency (takes more time)
                    '-tune', 'stillimage',  # Optimize for product content
                    '-movflags', '+faststart',  # Mobile/web optimization
                    '-bf', '3',  # More B-frames for better compression
                    '-g', '30',  # Keyframe every second at 30fps
                    '-maxrate', '25M',  # PREMIUM: Very high bitrate for mobile quality
                    '-bufsize', '50M',  # Large buffer for consistent premium quality
                    '-refs', '6',  # More reference frames for better quality
                    '-me_method', 'umh',  # Better motion estimation
                    '-subq', '10',  # Maximum subpixel motion estimation
                    '-trellis', '2',  # Maximum trellis quantization
                    '-aq-mode', '3',  # Advanced adaptive quantization
                    '-psy-rd', '1.0:0.15'  # Psychovisual optimizations for mobile screens
                ]
            ) as writer:
                # Write original frames without interpolation to avoid artifacts
                for frame in video_frames:
                    writer.append_data(frame)
            
            file_size = os.path.getsize(video_path)
            logger.info("PREMIUM mobile Reels video generation completed", extra={
                "video_filename": filename,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / 1024 / 1024, 2),
                "frames_generated": len(video_frames),
                "output_fps": 30,  # Premium 30fps
                "motion_intensity": motion_intensity,
                "style": style,
                "product_type": product_info.get("type", "unknown"),
                "use_case": product_info.get("use_case", "unknown"),
                "brand": product_info.get("brand", "unknown"),
                "category": product_info.get("category", "unknown"),
                "target_format": "mobile_reels_vertical",
                "quality_mode": "premium_maximum",
                "encoding_preset": "veryslow_premium",
                "intelligent_prompting": True,
                "mobile_optimized": True
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
    """Generate video from image - REDIRECTS to AI generation when available"""
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
            
            # ENFORCE GPU-BASED AI GENERATION ONLY
            if not svd_pipeline:
                raise HTTPException(
                    status_code=503, 
                    detail="AI video generation not available - Stable Video Diffusion model not loaded"
                )
            
            if device == "cpu":
                raise HTTPException(
                    status_code=503, 
                    detail="GPU required for AI video generation - CPU fallback not allowed"
                )
            
            # Use AI generation exclusively
            logger.info("Using AI video generation", extra={
                "device": device,
                "svd_available": True,
                "original_animation": data.animation_type
            })
            
            # Download image for AI generation
            image = download_image_from_url(data.image_url)
            
            # Focus on product-centered video generation with intelligent use case detection
            logger.info("Creating intelligent product-focused video", extra={
                "style": data.style,
                "product_centered": True,
                "intelligent_prompting": True
            })
            
            # Let the AI generate an intelligent prompt based on product analysis
            # The generate_ai_video_from_image function will analyze the product and create the prompt
            prompt = ""  # Empty prompt will trigger intelligent generation
            
            # MEMORY-OPTIMIZED: Balanced duration for quality and memory efficiency
            duration_frames = max(25, min(60, data.duration * 8))  # MEMORY FIX: ~8 frames per second for memory efficiency
            
            filename = generate_ai_video_from_image(
                image=image,
                prompt=prompt,
                duration_frames=duration_frames,
                style=data.style,
                product_metadata=data.product_metadata
            )
            
            return {
                "filename": filename,
                "download_url": f"/download/{filename}",
                "expires_in_minutes": 15,
                "file_size_mb": round(os.path.getsize(os.path.join(VIDEOS_DIR, filename)) / 1024 / 1024, 2),
                "type": "ai_generated"
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
    prompt: str = "professional product showcase with dynamic motion",
    duration_frames: int = 25
):
    """Generate AI video from uploaded image file using Stable Video Diffusion"""
    try:
        logger.info("AI video generation from upload request received", extra={
            "filename": file.filename,
            "content_type": file.content_type,
            "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
            "duration_frames": duration_frames
        })
        
        # Enforce GPU-only AI generation
        if not svd_pipeline:
            raise HTTPException(
                status_code=503, 
                detail="AI video generation not available - Stable Video Diffusion model not loaded"
            )
        
        if device == "cpu":
            raise HTTPException(
                status_code=503, 
                detail="GPU required for AI video generation - CPU fallback not allowed"
            )
        
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read and process uploaded image
        contents = await file.read()
        image = Image.open(BytesIO(contents)).convert('RGB')
        
        # Generate AI video
        filename = generate_ai_video_from_image(
            image=image,
            prompt=prompt,
            duration_frames=duration_frames
        )
        
        return {
            "filename": filename,
            "download_url": f"/download/{filename}",
            "expires_in_minutes": 15,
            "file_size_mb": round(os.path.getsize(os.path.join(VIDEOS_DIR, filename)) / 1024 / 1024, 2),
            "type": "ai_generated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI video generation from upload failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"AI video generation failed: {str(e)}")

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
            duration_frames=request.duration_frames,
            product_metadata=request.product_metadata
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
    """Health check endpoint - GPU-only AI video generation service"""
    gpu_available = torch.cuda.is_available()
    gpu_device_count = torch.cuda.device_count() if gpu_available else 0
    current_device = str(device)
    svd_loaded = bool(svd_pipeline)
    service_ready = svd_loaded and gpu_available and device != "cpu"
    
    status = {
        "status": "ready" if service_ready else "degraded", 
        "service": "ai-video-generator",
        "mode": "gpu_ai_only",
        "timestamp": time.time(),
        "gpu_available": gpu_available,
        "gpu_device_count": gpu_device_count,
        "current_device": current_device,
        "svd_model_loaded": svd_loaded,
        "image_model_loaded": bool(image_pipeline),
        "model_scenes_available": bool(image_pipeline),
        "service_ready": service_ready,
        "requirements": {
            "gpu_required": True,
            "svd_model_required": True,
            "image_model_optional": True,
            "cpu_fallback": False
        }
    }
    
    if gpu_available:
        try:
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            gpu_name = torch.cuda.get_device_name(0)
            status["gpu_memory_gb"] = round(gpu_memory, 2)
            status["gpu_name"] = gpu_name
            
            if torch.cuda.is_available():
                allocated_memory = torch.cuda.memory_allocated(0) / 1024**3
                cached_memory = torch.cuda.memory_reserved(0) / 1024**3
                status["gpu_memory_allocated_gb"] = round(allocated_memory, 2)
                status["gpu_memory_cached_gb"] = round(cached_memory, 2)
        except Exception:
            pass
    
    if not service_ready:
        status["issues"] = []
        if not gpu_available:
            status["issues"].append("GPU not available")
        if device == "cpu":
            status["issues"].append("Service running on CPU - GPU required")
        if not svd_loaded:
            status["issues"].append("Stable Video Diffusion model not loaded")
    
    return status

logger.info("Video generator service ready")