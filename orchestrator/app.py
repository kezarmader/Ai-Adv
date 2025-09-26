from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
import requests
import json
import time
import logging
from logging_config import (
    setup_logging, TimingContext, generate_request_id, request_id,
    log_request_details, log_response_details
)
from json_repair_engine import parse_llm_json_with_repair

# Setup structured logging
logger = setup_logging("orchestrator", "DEBUG")

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate and set request ID
        req_id = generate_request_id()
        request_id.set(req_id)
        
        # Log request details
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent")
        
        log_request_details(
            logger, 
            request.method, 
            str(request.url.path),
            client_ip,
            user_agent
        )
        
        # Start timing
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response details
        log_response_details(
            logger,
            response.status_code,
            duration_ms=round(duration_ms, 2)
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = req_id
        
        return response

app = FastAPI(title="AI Advertisement Generator - Orchestrator", version="1.0.0")
app.add_middleware(LoggingMiddleware)

def parse_llm_json_response(response: str) -> dict:
    """Parse JSON response from LLM using the comprehensive repair engine"""
    logger.debug("parse_llm_json_response called", extra={"response_length": len(response)})
    
    try:
        # Use the comprehensive JSON repair engine
        parsed_data = parse_llm_json_with_repair(response)
        
        logger.info("JSON response parsed and validated successfully", extra={
            "parsed_keys": list(parsed_data.keys()),
            "product": parsed_data.get('product'),
            "features_count": len(parsed_data.get('features', []))
        })
        
        return parsed_data
        
    except Exception as e:
        logger.error("Unexpected error in parse function", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "response_preview": response[:500] + "..." if len(response) > 500 else response
        })
        # This should never happen with the repair engine, but just in case
        raise ValueError(f"Unexpected error parsing LLM response: {str(e)}")

@app.post("/run")
async def run_ad_campaign(req: Request):
    """Generate a complete advertisement with copy, image, and optionally video using ASIN"""
    timer = None
    try:
        with TimingContext("ad_campaign_generation", logger) as timer:
            # Parse request body
            with TimingContext("request_parsing", logger):
                body = await req.json()
                asin = body.get("ASIN") or body.get("asin")
                audience = body.get("audience", "general consumers")
                tone = body.get("tone", "friendly and engaging")
                # Video parameters
                generate_video = body.get("generate_video", False)
                video_animation = body.get("video_animation", "ai_enhanced")  # New AI-enhanced option
                video_duration = body.get("video_duration", 5)
                video_style = body.get("video_style", "smooth")
                use_product_image = body.get("use_product_image", True)  # Use Amazon product image
                
                if not asin:
                    raise HTTPException(status_code=400, detail="ASIN is required")
                
                logger.info("ASIN-based ad generation request received", extra={
                    "asin": asin,
                    "audience": audience,
                    "tone": tone,
                    "generate_video": generate_video,
                    "video_animation": video_animation if generate_video else None,
                    "use_product_image": use_product_image
                })

            # Step 1: Extract product details from Amazon ASIN
            with TimingContext("asin_extraction", logger):
                logger.info("Extracting product information from ASIN")
                
                asin_response = requests.post("http://asin-extractor:5004/extract-asin", json={
                    "asin": asin
                })
                
                if asin_response.status_code != 200:
                    logger.error("ASIN extraction failed", extra={
                        "status_code": asin_response.status_code,
                        "response": asin_response.text[:200]
                    })
                    raise HTTPException(status_code=500, detail=f"ASIN extraction failed: {asin_response.status_code}")
                
                asin_data = asin_response.json()
                product_info = asin_data["product_info"]
                
                logger.info("Product information extracted successfully", extra={
                    "product_title": product_info.get("title", "")[:50] + "..." if product_info.get("title") else "N/A",
                    "brand": product_info.get("brand", "N/A"),
                    "image_count": len(product_info.get("images", [])),
                    "feature_count": len(product_info.get("features", []))
                })

            # Step 2: Enhanced LLM prompt with product information
            product_title = product_info.get("title", "Unknown Product")
            product_brand = product_info.get("brand", "Unknown Brand")
            product_features = product_info.get("features", [])
            product_description = product_info.get("description", "")
            product_category = product_info.get("category", "General")
            product_images = product_info.get("images", [])

            # Step 3: Generate enhanced LLM prompt with extracted product information
            with TimingContext("llm_prompt_generation", logger):
                features_text = "; ".join(product_features[:5]) if product_features else "No specific features listed"
                
                context = f"""IMPORTANT: You must output a single, valid UTF‑8 JSON object. Absolutely nothing else.

                Context:
                You are generating a realistic product advertisement using REAL Amazon product information:
                
                PRODUCT INFORMATION FROM AMAZON:
                - Product Title: {product_title}
                - Brand: {product_brand}
                - Category: {product_category}
                - Key Features: {features_text}
                - Product Description: {product_description[:200]}...
                - ASIN: {asin}
                
                TARGET AUDIENCE: {audience}
                DESIRED TONE: {tone}
                
                Your tasks:
                1. Create compelling ad copy using the specified tone and audience
                2. Generate TWO different scene descriptions:
                   - "generated_scene": Creative scene for AI image generation (studio/lifestyle setting)
                   - "video_scene": Scene description optimized for video animation
                3. Suggest appropriate brand text and CTA based on the product
                4. Refine the product features for marketing appeal

                STRICT RULES (Failure on any rule makes the output invalid):
                1. Output **only** a raw JSON object — no markdown, no comments, no backticks, no prose.
                2. All keys must be **double-quoted** ASCII.
                3. All string values must be **double-quoted** UTF‑8, with no control characters.
                4. **No** characters outside the UTF‑8 range.
                5. **No** trailing commas, missing commas, or malformed brackets/braces.
                6. The output must be valid for both `json.loads()` and `json.load()` in Python — no exceptions, no escapes.
                7. You MUST return these exact keys:
                   - `"product"`: refined product name for marketing
                   - `"brand"`: brand name
                   - `"audience"`: string or list of strings
                   - `"tone"`: string
                   - `"description"`: compelling ad copy (100-200 words)
                   - `"features"`: list of marketing-friendly feature descriptions
                   - `"generated_scene"`: detailed prompt for AI image generation
                   - `"video_scene"`: scene description optimized for video animation
                   - `"suggested_brand_text"`: suggested brand text for overlays
                   - `"suggested_cta"`: suggested call-to-action text

                Output Example (for format only — do not copy exact content):
                {{
                  "product": "Pro Wireless Gaming Mouse",
                  "brand": "TechBrand",
                  "audience": ["gamers", "professionals"],
                  "tone": "exciting",
                  "description": "Experience precision like never before with our advanced gaming mouse...",
                  "features": ["Ultra-fast response", "Ergonomic design", "RGB lighting"],
                  "generated_scene": "Professional gaming setup with RGB lighting, modern desk, focused gamer in action",
                  "video_scene": "Close-up product shots with smooth camera movements highlighting design details",
                  "suggested_brand_text": "TechBrand Pro",
                  "suggested_cta": "Level Up Today!"
                }}

                DO NOT:
                - Wrap the JSON in quotes
                - Add ```json blocks
                - Escape the entire response
                - Include leading/trailing newlines or explanation
               """

            # LLM call to Ollama - comprehensive repair engine handles all JSON parsing issues
            with TimingContext("llm_generation", logger, {"model": "llama3"}) as llm_timer:
                start_time = time.time()
                
                logger.debug("Making LLM request")
                
                llm_response = requests.post("http://llm-service:11434/api/generate", json={
                    "model": "llama3",
                    "prompt": context,
                    "stream": False
                })
                duration_ms = (time.time() - start_time) * 1000
                
                logger.debug("LLM response received", extra={
                    "status_code": llm_response.status_code,
                    "response_headers": dict(llm_response.headers),
                    "duration_ms": round(duration_ms, 2)
                })
                
                if llm_response.status_code != 200:
                    logger.error("LLM service error", extra={"status_code": llm_response.status_code})
                    raise HTTPException(status_code=500, detail=f"LLM service error: {llm_response.status_code}")

            # Parse LLM response using comprehensive repair engine
            with TimingContext("llm_response_parsing", logger):
                raw_response = llm_response.text.strip()
                logger.debug("Raw LLM response received", extra={
                    "response_length": len(raw_response),
                    "response_preview": raw_response[:300] + "..." if len(raw_response) > 300 else raw_response,
                    "response_ends_with": raw_response[-50:] if len(raw_response) > 50 else raw_response
                })
                
                # The repair engine guarantees successful parsing with valid JSON
                ad_text = parse_llm_json_response(raw_response)
                logger.info("LLM response parsed successfully", extra={
                    "product_parsed": ad_text.get('product'),
                    "features_count": len(ad_text.get('features', [])),
                    "scene_length": len(ad_text.get('scene', ''))
                })
            
            if ad_text is None:
                raise HTTPException(status_code=500, detail="Failed to parse LLM response after all retry attempts")

            # Prepare image generation prompt
            image_prompt = {
                "product_name": ad_text['product'],
                "features": ad_text['features'],
                "brand_text": ad_text.get('suggested_brand_text', ad_text.get('product', '')),
                "cta_text": ad_text.get('suggested_cta', 'Shop Now'),
                "scene": ad_text['scene']
            }
            
            logger.info("Image generation prompt prepared", extra={
                "prompt_size": len(json.dumps(image_prompt))
            })

            # Image Generator call
            with TimingContext("image_generation", logger) as img_timer:
                start_time = time.time()
                image_response = requests.post("http://image-generator:5001/generate", json=image_prompt)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.info("Image generation request completed", extra={
                    "service": "image-generator",
                    "endpoint": "/generate",
                    "status_code": image_response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "prompt_size": len(json.dumps(image_prompt))
                })
                
                if image_response.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"Image generation error: {image_response.status_code}")

            # Process image response
            with TimingContext("image_response_processing", logger):
                response_data = image_response.json()
                filename = response_data.get("filename", "")
                
                if filename == '' or filename == None:
                    raise ValueError(f'Error generating filename: {filename}')
                
                # Get the host from the request to construct the proper external URL
                host = req.headers.get("host", "localhost:8000")
                # Construct URL that points to orchestrator's download endpoint
                image_url = f"http://{host}/download/{filename}"
                
                logger.info("Image URL constructed", extra={
                    "image_filename": filename,
                    "image_url": image_url
                })

            # Optional video generation - ALWAYS use AI video generation
            video_url = None
            if generate_video:
                with TimingContext("video_generation", logger):
                    start_time = time.time()
                    
                    if use_product_image and product_images:
                        # Use Amazon product image for AI video generation
                        selected_image = product_images[0]  # Use first product image
                        image_source = selected_image
                        prompt_context = f"Dramatic product showcase for {ad_text.get('product', 'this product')}. {ad_text.get('video_scene', 'Dynamic camera movements highlighting product features with professional lighting and cinematic effects.')}"
                        logger.info("Using AI video generation with Amazon product image", extra={
                            "product_image_url": selected_image
                        })
                    else:
                        # Use generated image for AI video generation (NOT traditional animation)
                        image_source = f"http://image-generator:5001/download/{filename}"
                        prompt_context = f"Dramatic transformation and showcase for {ad_text.get('product', 'this product')}. {ad_text.get('video_scene', 'Cinematic camera movements with dynamic lighting, professional product presentation with smooth transitions and dramatic effects.')}"
                        logger.info("Using AI video generation with generated image", extra={
                            "generated_image_filename": filename
                        })
                    
                    # ALWAYS use AI video generation endpoint - no fallback to traditional animation
                    video_prompt = {
                        "image_url": image_source,
                        "prompt": prompt_context,
                        "duration_frames": 30  # ~2 seconds at 15fps output, ~4 seconds with interpolation
                    }
                    endpoint = "/generate-ai-video"
                    
                    logger.info("Sending AI video generation request", extra={
                        "prompt": prompt_context[:100] + "..." if len(prompt_context) > 100 else prompt_context,
                        "duration_frames": video_prompt["duration_frames"]
                    })
                    
                    video_response = requests.post(f"http://video-generator:5003{endpoint}", json=video_prompt)
                    duration_ms = (time.time() - start_time) * 1000
                    
                    logger.info("Video generation request completed", extra={
                        "service": "video-generator",
                        "endpoint": endpoint,
                        "status_code": video_response.status_code,
                        "duration_ms": round(duration_ms, 2),
                        "video_type": "ai_generated" if endpoint == "/generate-ai-video" else "animated",
                        "animation_type": video_animation if endpoint == "/generate" else "stable_video_diffusion"
                    })
                    
                    if video_response.status_code == 200:
                        video_data = video_response.json()
                        video_filename = video_data.get("filename", "")
                        if video_filename:
                            host = req.headers.get("host", "localhost:8000")
                            video_url = f"http://{host}/download-video/{video_filename}"
                            logger.info("Video URL constructed", extra={
                                "video_filename": video_filename,
                                "video_url": video_url
                            })

            # Poster service call
            with TimingContext("post_service", logger):
                start_time = time.time()
                post_data = {
                    "text": ad_text,
                    "image_url": image_url
                }
                if video_url:
                    post_data["video_url"] = video_url
                    
                post_response = requests.post("http://poster-service:5002/post", json=post_data)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.info("Poster service request completed", extra={
                    "service": "poster-service",
                    "endpoint": "/post",
                    "status_code": post_response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "has_video": bool(video_url)
                })

            # Prepare final response
            final_response = {
                "ad_text": ad_text,
                "image_url": image_url,
                "post_status": post_response.json() if post_response.status_code == 200 else {"status": "error", "message": "Post service unavailable"}
            }
            
            if video_url:
                final_response["video_url"] = video_url
            
            logger.info("Ad campaign generation completed successfully", extra={
                "total_duration_ms": round(timer.duration_ms, 2),
                "image_filename": filename,
                "post_status": final_response["post_status"].get("status", "unknown")
            })
            
            return final_response
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        logger.error("Validation error in ad generation", extra={
            "error": str(e),
            "duration_ms": round(timer.duration_ms, 2) if timer else None
        })
        raise HTTPException(status_code=400, detail=str(e))
    except requests.RequestException as e:
        logger.error("External service error", extra={
            "error": str(e),
            "duration_ms": round(timer.duration_ms, 2) if timer else None
        })
        raise HTTPException(status_code=503, detail=f"External service error: {str(e)}")
    except Exception as e:
        import traceback
        logger.error("Unexpected error in ad generation", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(timer.duration_ms, 2) if timer else None,
            "traceback": traceback.format_exc() if logger.isEnabledFor(logging.DEBUG) else None
        })
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/download/{filename}")
async def download_image(filename: str, request: Request):
    """Proxy endpoint to download images from image-generator service"""
    with TimingContext("image_download", logger, {"image_filename": filename}) as timer:
        try:
            client_ip = request.client.host if request.client else "unknown"
            logger.info("Image download request", extra={
                "image_filename": filename,
                "client_ip": client_ip
            })
            
            # Make request to image-generator service
            start_time = time.time()
            image_response = requests.get(f"http://image-generator:5001/download/{filename}")
            duration_ms = (time.time() - start_time) * 1000
            
            logger.debug("Image download request completed", extra={
                "service": "image-generator",
                "endpoint": f"/download/{filename}",
                "status_code": image_response.status_code,
                "duration_ms": round(duration_ms, 2)
            })
            
            if image_response.status_code == 404:
                logger.warning("Image not found", extra={
                    "image_filename": filename,
                    "client_ip": client_ip
                })
                raise HTTPException(status_code=404, detail="Image not found or has expired")
            elif image_response.status_code != 200:
                logger.error("Error fetching image from generator", extra={
                    "image_filename": filename,
                    "status_code": image_response.status_code
                })
                raise HTTPException(status_code=image_response.status_code, detail="Error fetching image")
            
            # Log successful download
            image_size = len(image_response.content)
            logger.info("Image download successful", extra={
                "image_filename": filename,
                "client_ip": client_ip,
                "image_size_bytes": image_size,
                "download_duration_ms": round(timer.duration_ms, 2)
            })
            
            # Return the image content with proper headers
            return Response(
                content=image_response.content,
                media_type="image/png",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Type": "image/png",
                    "Content-Length": str(image_size)
                }
            )
            
        except HTTPException:
            raise
        except requests.RequestException as e:
            logger.error("Request error during image download", extra={
                "image_filename": filename,
                "error": str(e),
                "duration_ms": round(timer.duration_ms, 2) if timer else None
            })
            raise HTTPException(status_code=500, detail=f"Error fetching image: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error during image download", extra={
                "image_filename": filename,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(timer.duration_ms, 2) if timer else None
            })
            raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/download-video/{filename}")
async def download_video(filename: str, request: Request):
    """Proxy endpoint to download videos from video-generator service"""
    with TimingContext("video_download", logger, {"video_filename": filename}) as timer:
        try:
            client_ip = request.client.host if request.client else "unknown"
            logger.info("Video download request", extra={
                "video_filename": filename,
                "client_ip": client_ip
            })
            
            # Make request to video-generator service
            start_time = time.time()
            video_response = requests.get(f"http://video-generator:5003/download/{filename}")
            duration_ms = (time.time() - start_time) * 1000
            
            logger.debug("Video download request completed", extra={
                "service": "video-generator",
                "endpoint": f"/download/{filename}",
                "status_code": video_response.status_code,
                "duration_ms": round(duration_ms, 2)
            })
            
            if video_response.status_code == 404:
                logger.warning("Video not found", extra={
                    "video_filename": filename,
                    "client_ip": client_ip
                })
                raise HTTPException(status_code=404, detail="Video not found or has expired")
            elif video_response.status_code != 200:
                logger.error("Error fetching video from generator", extra={
                    "video_filename": filename,
                    "status_code": video_response.status_code
                })
                raise HTTPException(status_code=video_response.status_code, detail="Error fetching video")
            
            # Log successful download
            video_size = len(video_response.content)
            logger.info("Video download successful", extra={
                "video_filename": filename,
                "client_ip": client_ip,
                "video_size_bytes": video_size,
                "download_duration_ms": round(timer.duration_ms, 2)
            })
            
            # Return the video content with streaming-friendly headers
            return Response(
                content=video_response.content,
                media_type="video/mp4",
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(video_size),
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "public, max-age=3600"
                }
            )
            
        except HTTPException:
            raise
        except requests.RequestException as e:
            logger.error("Request error during video download", extra={
                "video_filename": filename,
                "error": str(e),
                "duration_ms": round(timer.duration_ms, 2) if timer else None
            })
            raise HTTPException(status_code=500, detail=f"Error fetching video: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error during video download", extra={
                "video_filename": filename,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(timer.duration_ms, 2) if timer else None
            })
            raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/generate-video")
async def generate_video_only(req: Request):
    """Generate video from existing image URL"""
    timer = None
    try:
        with TimingContext("video_only_generation", logger) as timer:
            # Parse request body
            with TimingContext("request_parsing", logger):
                body = await req.json()
                image_url = body.get("image_url")
                animation_type = body.get("animation_type", "zoom_pan")
                duration = body.get("duration", 5)
                fps = body.get("fps", 30)
                style = body.get("style", "smooth")
                text_overlay = body.get("text_overlay")
                brand_text = body.get("brand_text")
                cta_text = body.get("cta_text")
                
                if not image_url:
                    raise HTTPException(status_code=400, detail="image_url is required")
                
                logger.info("Video generation request received", extra={
                    "image_url": image_url,
                    "animation_type": animation_type,
                    "duration": duration,
                    "fps": fps,
                    "style": style
                })

            # Video generation call
            with TimingContext("video_generation", logger):
                start_time = time.time()
                video_prompt = {
                    "image_url": image_url,
                    "animation_type": animation_type,
                    "duration": duration,
                    "fps": fps,
                    "style": style,
                    "text_overlay": text_overlay,
                    "brand_text": brand_text,
                    "cta_text": cta_text
                }
                
                video_response = requests.post("http://video-generator:5003/generate", json=video_prompt)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.info("Video generation request completed", extra={
                    "service": "video-generator",
                    "endpoint": "/generate",
                    "status_code": video_response.status_code,
                    "duration_ms": round(duration_ms, 2)
                })
                
                if video_response.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"Video generation error: {video_response.status_code}")

            # Process video response
            with TimingContext("video_response_processing", logger):
                response_data = video_response.json()
                filename = response_data.get("filename", "")
                
                if not filename:
                    raise ValueError("Error generating video filename")
                
                # Get the host from the request to construct the proper external URL
                host = req.headers.get("host", "localhost:8000")
                video_url = f"http://{host}/download-video/{filename}"
                
                logger.info("Video URL constructed", extra={
                    "video_filename": filename,
                    "video_url": video_url
                })

            # Prepare final response
            final_response = {
                "video_url": video_url,
                "filename": filename,
                "file_size_mb": response_data.get("file_size_mb"),
                "duration_seconds": response_data.get("duration_seconds"),
                "fps": response_data.get("fps"),
                "animation_type": response_data.get("animation_type"),
                "expires_in_minutes": response_data.get("expires_in_minutes", 15)
            }
            
            logger.info("Video generation completed successfully", extra={
                "total_duration_ms": round(timer.duration_ms, 2),
                "video_filename": filename
            })
            
            return final_response
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error("Validation error in video generation", extra={
            "error": str(e),
            "duration_ms": round(timer.duration_ms, 2) if timer else None
        })
        raise HTTPException(status_code=400, detail=str(e))
    except requests.RequestException as e:
        logger.error("External service error", extra={
            "error": str(e),
            "duration_ms": round(timer.duration_ms, 2) if timer else None
        })
        raise HTTPException(status_code=503, detail=f"External service error: {str(e)}")
    except Exception as e:
        import traceback
        logger.error("Unexpected error in video generation", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(timer.duration_ms, 2) if timer else None,
            "traceback": traceback.format_exc() if logger.isEnabledFor(logging.DEBUG) else None
        })
        raise HTTPException(status_code=500, detail="Internal server error")
