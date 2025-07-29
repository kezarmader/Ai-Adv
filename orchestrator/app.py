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
from trends_integration import get_trending_spiced_story, get_trends_debug_info

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

@app.post("/run/trending")
async def run_trending_ad_campaign(req: Request):
    """Generate a spiced-up advertisement based on current Google Trends with STRICT CONTENT SAFETY"""
    timer = None
    try:
        with TimingContext("trending_ad_campaign_generation", logger) as timer:
            # Parse request body
            with TimingContext("request_parsing", logger):
                body = await req.json()
                product = body.get("product", "")
                audience = body.get("audience", "general audience")
                tone = body.get("tone", "excited")
                asin = body.get("ASIN", "")
                brand_text = body.get("brand_text", "")
                cta_text = body.get("cta_text", "")
                
                logger.info("Trending ad generation request received", extra={
                    "product": product,
                    "audience": audience,
                    "tone": tone,
                    "asin": asin,
                    "has_brand_text": bool(brand_text),
                    "has_cta_text": bool(cta_text)
                })

            # Get trending spiced story with hook keywords
            with TimingContext("trending_story_generation", logger):
                story_data = await get_trending_spiced_story()
                trending_scene = story_data["spiced_story"]
                original_trend = story_data["original_trend"]
                hook_keywords = story_data.get("hook_keywords", [])
                
                # EMERGENCY CONTENT SAFETY CHECK
                harmful_keywords = [
                    "trump", "biden", "rape", "kill", "murder", "death", "died", "dead", "child", "kid", 
                    "minor", "teen", "sexual", "violence", "shooting", "bomb", "attack", "terrorism",
                    "tragedy", "disaster", "crash", "accident", "politics", "election", "war", "crime"
                ]
                
                # Check original trend for harmful content
                trend_lower = original_trend.lower()
                if any(harmful in trend_lower for harmful in harmful_keywords):
                    logger.error(f"EMERGENCY SAFETY OVERRIDE: Harmful trend detected: {original_trend}")
                    # Replace with safe content immediately
                    original_trend = "Summer outdoor activities and healthy lifestyle"
                    trending_scene = "A vibrant summer scene featuring outdoor activities with sparkling effects and rainbow colors"
                    hook_keywords = ["summer", "outdoor", "healthy"]
                
                # Check trending scene for harmful content
                scene_lower = trending_scene.lower()
                if any(harmful in scene_lower for harmful in harmful_keywords):
                    logger.error(f"EMERGENCY SAFETY OVERRIDE: Harmful scene detected: {trending_scene}")
                    trending_scene = "A vibrant summer scene featuring outdoor activities with sparkling effects and rainbow colors"
                
                # Check hook keywords for harmful content
                safe_keywords = []
                for keyword in hook_keywords:
                    if not any(harmful in keyword.lower() for harmful in harmful_keywords):
                        safe_keywords.append(keyword)
                    else:
                        logger.error(f"EMERGENCY SAFETY OVERRIDE: Harmful keyword removed: {keyword}")
                
                # If no safe keywords, use defaults
                if not safe_keywords:
                    safe_keywords = ["trending", "popular", "viral"]
                
                hook_keywords = safe_keywords
                
                logger.info("Trending story with hooks generated (SAFETY CHECKED)", extra={
                    "original_trend": original_trend,
                    "scene_length": len(trending_scene),
                    "hook_keywords": hook_keywords,
                    "safety_checked": True
                })

            # Generate enhanced LLM prompt with trending context
            trending_context = f"""IMPORTANT: You must output a single, valid UTF‑8 JSON object. Absolutely nothing else.

                Context:
                You are generating a VIRAL-WORTHY product ad that uses TRENDING KEYWORDS as the main hook.
                
                🔥 TRENDING HOOK: "{original_trend}"
                🎬 Trending Scene Inspiration: {trending_scene}
                
                Product Details:
                - Product: {product if product else "trendy lifestyle product"}
                - Target Audience: {audience}
                - Tone: {tone} (make it ULTRA engaging and trend-focused)
                - Reference Link: {"https://www.amazon.com/dp/" + asin if asin else "modern product showcase"}

                🎯 HOOK STRATEGY - Use "{original_trend}" as your PRIMARY ATTENTION GRABBER:
                1. Start your description with a reference to this trending topic
                2. Connect the product directly to why this trend matters to your audience
                3. Create urgency: "Join the {original_trend} movement with..."
                4. Use the trend as the main selling angle, not just background

                SPECIAL INSTRUCTIONS FOR VIRAL APPEAL:
                1. HEADLINE APPROACH: Lead with the trending topic as a hook
                2. FOMO CREATION: Make people feel they'll miss out if they don't connect to this trend
                3. SOCIAL PROOF: Imply everyone is talking about this trend
                4. SCENE INTEGRATION: The visual scene should PROMINENTLY feature trend elements
                5. TRENDING LANGUAGE: Use current viral phrases and social media language

                The goal is to:
                1. Make the trending topic the STAR of the ad, with the product as the perfect solution
                2. Create a scene that visually represents both the trend AND the product powerfully
                3. Generate maximum engagement by tapping into what's already popular

                STRICT RULES (Failure on any rule makes the output invalid):
                1. Output **only** a raw JSON object — no markdown, no comments, no backticks, no prose.
                2. All keys must be **double-quoted** ASCII.
                3. All string values must be **double-quoted** UTF‑8, with no control characters.
                4. **No** characters outside the UTF‑8 range.
                5. **No** trailing commas, missing commas, or malformed brackets/braces.
                6. The output must be valid for both `json.loads()` and `json.load()` in Python — no exceptions, no escapes.
                7. You MUST return at least these keys:
                   - `"product"`: string
                   - `"audience"`: string or list of strings
                   - `"tone"`: string
                   - `"description"`: string (incorporate trending elements)
                   - `"features"`: list of strings (make them sound trendy)
                   - `"scene"`: a SUPER detailed, spiced-up scene combining product with trending elements
                   - `"trending_topic"`: the original trending topic used

                Output Example (for format only — do not copy):
                {{
                  "product": "Trending Product Name",
                  "audience": ["trend followers", "social media users"],
                  "tone": "super excited",
                  "description": "This amazing product is perfect for the current trend of...",
                  "features": ["Trending Feature 1", "Viral-worthy Feature 2", "Instagram-ready Feature 3"],
                  "scene": "An incredibly vibrant scene featuring the product in a trending context with amazing lighting and exciting elements",
                  "trending_topic": "{original_trend}"
                }}

                DO NOT:
                - Wrap the JSON in quotes
                - Add ```json blocks
                - Escape the entire response
                - Include leading/trailing newlines or explanation
               """

            # LLM call to Ollama with trending context
            with TimingContext("llm_generation", logger, {"model": "llama3", "type": "trending"}) as llm_timer:
                start_time = time.time()
                
                logger.debug("Making trending LLM request")
                
                llm_response = requests.post("http://llm-service:11434/api/generate", json={
                    "model": "llama3",
                    "prompt": trending_context,
                    "stream": False
                })
                duration_ms = (time.time() - start_time) * 1000
                
                logger.debug("Trending LLM response received", extra={
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
                logger.debug("Raw trending LLM response received", extra={
                    "response_length": len(raw_response),
                    "response_preview": raw_response[:300] + "..." if len(raw_response) > 300 else raw_response,
                    "response_ends_with": raw_response[-50:] if len(raw_response) > 50 else raw_response
                })
                
                # The repair engine guarantees successful parsing with valid JSON
                ad_text = parse_llm_json_response(raw_response)
                logger.info("Trending LLM response parsed successfully", extra={
                    "product_parsed": ad_text.get('product'),
                    "features_count": len(ad_text.get('features', [])),
                    "scene_length": len(ad_text.get('scene', '')),
                    "trending_topic": ad_text.get('trending_topic')
                })
            
            if ad_text is None:
                raise HTTPException(status_code=500, detail="Failed to parse LLM response after all retry attempts")

            # Prepare HOOK-FOCUSED image generation prompt with trending elements
            effective_keywords = hook_keywords if hook_keywords else original_trend.split()[:3]
            
            image_prompt = {
                "product_name": ad_text['product'],
                "features": ad_text['features'],
                "brand_text": brand_text,
                "cta_text": f"🔥 {original_trend} 🔥 {cta_text}",  # Add trending hook to CTA
                "scene": ad_text['scene'],
                "trending_boost": True,  # Flag for image generator to apply extra effects
                "trending_topic": ad_text.get('trending_topic', original_trend),
                "trending_keywords": effective_keywords,  # Key words for visual emphasis
                "hook_mode": True  # Special flag for hook-focused generation
            }
            
            logger.info("HOOK-FOCUSED trending image generation prompt prepared", extra={
                "prompt_size": len(json.dumps(image_prompt)),
                "trending_topic": image_prompt.get("trending_topic"),
                "trending_keywords": effective_keywords,
                "hook_cta": image_prompt["cta_text"],
                "hook_source": "extracted" if hook_keywords else "split_trend"
            })

            # Image Generator call with trending boost
            with TimingContext("image_generation", logger, {"type": "trending"}) as img_timer:
                start_time = time.time()
                image_response = requests.post("http://image-generator:5001/generate", json=image_prompt)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.info("Trending image generation request completed", extra={
                    "service": "image-generator",
                    "endpoint": "/generate",
                    "status_code": image_response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "prompt_size": len(json.dumps(image_prompt)),
                    "trending_mode": True
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
                
                logger.info("Trending image URL constructed", extra={
                    "image_filename": filename,
                    "image_url": image_url
                })

            # Poster service call with trending flag
            with TimingContext("post_service", logger, {"type": "trending"}):
                start_time = time.time()
                post_response = requests.post("http://poster-service:5002/post", json={
                    "text": ad_text,
                    "image_url": image_url,
                    "trending": True,
                    "trending_topic": ad_text.get('trending_topic', original_trend)
                })
                duration_ms = (time.time() - start_time) * 1000
                
                logger.info("Trending poster service request completed", extra={
                    "service": "poster-service",
                    "endpoint": "/post",
                    "status_code": post_response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "trending_mode": True
                })

            # Prepare final response with trending metadata
            final_response = {
                "ad_text": ad_text,
                "image_url": image_url,
                "post_status": post_response.json() if post_response.status_code == 200 else {"status": "error", "message": "Post service unavailable"},
                "trending_data": {
                    "original_trend": original_trend,
                    "spiced_story": trending_scene,
                    "trending_topic_used": ad_text.get('trending_topic', original_trend)
                }
            }
            
            logger.info("Trending ad campaign generation completed successfully", extra={
                "total_duration_ms": round(timer.duration_ms, 2),
                "image_filename": filename,
                "post_status": final_response["post_status"].get("status", "unknown"),
                "trending_topic": original_trend
            })
            
            return final_response
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        logger.error("Validation error in trending ad generation", extra={
            "error": str(e),
            "duration_ms": round(timer.duration_ms, 2) if timer else None
        })
        raise HTTPException(status_code=400, detail=str(e))
    except requests.RequestException as e:
        logger.error("External service error in trending generation", extra={
            "error": str(e),
            "duration_ms": round(timer.duration_ms, 2) if timer else None
        })
        raise HTTPException(status_code=503, detail=f"External service error: {str(e)}")
    except Exception as e:
        import traceback
        logger.error("Unexpected error in trending ad generation", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(timer.duration_ms, 2) if timer else None,
            "traceback": traceback.format_exc() if logger.isEnabledFor(logging.DEBUG) else None
        })
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/trends")
async def get_current_trends():
    """Get current Google Trends without generating ads"""
    try:
        with TimingContext("trends_fetch", logger):
            story_data = await get_trending_spiced_story()
            
            logger.info("Trends fetched successfully", extra={
                "trending_topic": story_data.get("original_trend"),
                "story_length": len(story_data.get("spiced_story", ""))
            })
            
            return {
                "status": "success",
                "trending_data": story_data,
                "timestamp": time.time()
            }
            
    except Exception as e:
        logger.error("Error fetching trends", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise HTTPException(status_code=500, detail=f"Failed to fetch trends: {str(e)}")

@app.get("/trends/debug")
async def get_trends_debug():
    """Get debug information about trends fetching system"""
    try:
        debug_info = await get_trends_debug_info()
        
        logger.info("Trends debug info requested")
        
        return {
            "status": "success",
            "debug_info": debug_info,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error("Error getting trends debug info", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise HTTPException(status_code=500, detail=f"Failed to get debug info: {str(e)}")

@app.post("/run")
async def run_ad_campaign(req: Request):
    """Generate a complete advertisement with copy and image"""
    timer = None
    try:
        with TimingContext("ad_campaign_generation", logger) as timer:
            # Parse request body
            with TimingContext("request_parsing", logger):
                body = await req.json()
                product = body.get("product")
                audience = body.get("audience")
                tone = body.get("tone")
                asin = body.get("ASIN")
                brand_text = body.get("brand_text")
                cta_text = body.get("cta_text")
                
                logger.info("Ad generation request received", extra={
                    "product": product,
                    "audience": audience,
                    "tone": tone,
                    "asin": asin,
                    "has_brand_text": bool(brand_text),
                    "has_cta_text": bool(cta_text)
                })

            # Generate LLM prompt
            context = f"""IMPORTANT: You must output a single, valid UTF‑8 JSON object. Absolutely nothing else.

                Context:
                You are generating a realistic product ad for the following:
                - Product: {product}
                - Target Audience: {audience}
                - Tone: {tone}
                - Reference Link: https://www.amazon.com/dp/{asin}

                The goal is to:
                1. Write an ad description using the specified tone and audience.
                2. Provide a detailed scene prompt for use in image generation (include setting, objects, people if relevant).

                STRICT RULES (Failure on any rule makes the output invalid):
                1. Output **only** a raw JSON object — no markdown, no comments, no backticks, no prose.
                2. All keys must be **double-quoted** ASCII.
                3. All string values must be **double-quoted** UTF‑8, with no control characters.
                4. **No** characters outside the UTF‑8 range.
                5. **No** trailing commas, missing commas, or malformed brackets/braces.
                6. The output must be valid for both `json.loads()` and `json.load()` in Python — no exceptions, no escapes.
                7. You MUST return at least these keys:
                   - `"product"`: string
                   - `"audience"`: string or list of strings
                   - `"tone"`: string
                   - `"description"`: string
                   - `"features"`: list of strings
                   - `"scene"`: a richly detailed text prompt for image generation

                Output Example (for format only — do not copy):
                {{
                  "product": "Example Product",
                  "audience": ["photographers", "tech lovers"],
                  "tone": "excited",
                  "description": "This camera changes how you capture light and motion...",
                  "features": ["Ultra HD", "Stabilized Zoom", "Wireless sync"],
                  "scene": "A photographer holding the camera on a mountain at sunrise, dramatic golden light, backpack gear, wind in hair, 4K realism"
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
                "brand_text": brand_text,
                "cta_text": cta_text,
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

            # Poster service call
            with TimingContext("post_service", logger):
                start_time = time.time()
                post_response = requests.post("http://poster-service:5002/post", json={
                    "text": ad_text,
                    "image_url": image_url
                })
                duration_ms = (time.time() - start_time) * 1000
                
                logger.info("Poster service request completed", extra={
                    "service": "poster-service",
                    "endpoint": "/post",
                    "status_code": post_response.status_code,
                    "duration_ms": round(duration_ms, 2)
                })

            # Prepare final response
            final_response = {
                "ad_text": ad_text,
                "image_url": image_url,
                "post_status": post_response.json() if post_response.status_code == 200 else {"status": "error", "message": "Post service unavailable"}
            }
            
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
