from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
import requests
import json
import time
from logging_config import (
    setup_logging, TimingContext, generate_request_id, request_id,
    log_request_details, log_response_details, log_external_api_call
)

# Setup structured logging
logger = setup_logging("orchestrator", "INFO")

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

            # LLM call to Ollama
            with TimingContext("llm_generation", logger, {"model": "llama3"}) as llm_timer:
                start_time = time.time()
                llm_response = requests.post("http://llm-service:11434/api/generate", json={
                    "model": "llama3",
                    "prompt": context,
                    "stream": False
                })
                duration_ms = (time.time() - start_time) * 1000
                
                log_external_api_call(
                    logger, "llm-service", "/api/generate", "POST",
                    response_status=llm_response.status_code,
                    duration_ms=round(duration_ms, 2)
                )
                
                if llm_response.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"LLM service error: {llm_response.status_code}")

            # Parse LLM response
            with TimingContext("llm_response_parsing", logger):
                ad_text = parse_llm_escaped_json(llm_response.text.strip())
                logger.info("LLM response parsed successfully", extra={
                    "product_parsed": ad_text.get('product'),
                    "features_count": len(ad_text.get('features', [])),
                    "scene_length": len(ad_text.get('scene', ''))
                })

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
                
                log_external_api_call(
                    logger, "image-generator", "/generate", "POST",
                    request_data=image_prompt,
                    response_status=image_response.status_code,
                    duration_ms=round(duration_ms, 2)
                )
                
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
                    "filename": filename,
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
                
                log_external_api_call(
                    logger, "poster-service", "/post", "POST",
                    response_status=post_response.status_code,
                    duration_ms=round(duration_ms, 2)
                )

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
        logger.error("Unexpected error in ad generation", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(timer.duration_ms, 2) if timer else None
        })
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/download/{filename}")
async def download_image(filename: str, request: Request):
    """Proxy endpoint to download images from image-generator service"""
    with TimingContext("image_download", logger, {"filename": filename}) as timer:
        try:
            client_ip = request.client.host if request.client else "unknown"
            logger.info("Image download request", extra={
                "filename": filename,
                "client_ip": client_ip
            })
            
            # Make request to image-generator service
            start_time = time.time()
            image_response = requests.get(f"http://image-generator:5001/download/{filename}")
            duration_ms = (time.time() - start_time) * 1000
            
            log_external_api_call(
                logger, "image-generator", f"/download/{filename}", "GET",
                response_status=image_response.status_code,
                duration_ms=round(duration_ms, 2)
            )
            
            if image_response.status_code == 404:
                logger.warning("Image not found", extra={
                    "filename": filename,
                    "client_ip": client_ip
                })
                raise HTTPException(status_code=404, detail="Image not found or has expired")
            elif image_response.status_code != 200:
                logger.error("Error fetching image from generator", extra={
                    "filename": filename,
                    "status_code": image_response.status_code
                })
                raise HTTPException(status_code=image_response.status_code, detail="Error fetching image")
            
            # Log successful download
            image_size = len(image_response.content)
            logger.info("Image download successful", extra={
                "filename": filename,
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
                "filename": filename,
                "error": str(e),
                "duration_ms": round(timer.duration_ms, 2) if timer else None
            })
            raise HTTPException(status_code=500, detail=f"Error fetching image: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error during image download", extra={
                "filename": filename,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(timer.duration_ms, 2) if timer else None
            })
            raise HTTPException(status_code=500, detail="Internal server error")

import json

def parse_llm_escaped_json(response):
    """Parse JSON response from LLM with error handling and logging"""
    try:
        response_obj = json.loads(response)
        logger.debug("LLM response object parsed", extra={
            "response_keys": list(response_obj.keys()) if isinstance(response_obj, dict) else None
        })

        # Step 1: Get the raw string containing escaped JSON
        raw_json_str = response_obj.get("response")
        clean_json = raw_json_str

        if not clean_json:
            logger.error("Missing 'response' key in LLM output", extra={
                "available_keys": list(response_obj.keys()) if isinstance(response_obj, dict) else None,
                "full_response": response[:500] + "..." if len(response) > 500 else response
            })
            raise ValueError("Missing 'response' key in LLM output")

        logger.debug("Raw JSON extracted from LLM response", extra={
            "json_length": len(clean_json),
            "json_preview": clean_json[:300] + "..." if len(clean_json) > 300 else clean_json
        })
        
        # Step 2: Try to clean up common JSON issues before parsing
        try:
            # First attempt: direct parsing
            unescaped = json.loads(clean_json)
            logger.info("LLM JSON response parsed successfully", extra={
                "parsed_keys": list(unescaped.keys()) if isinstance(unescaped, dict) else None,
                "product": unescaped.get('product') if isinstance(unescaped, dict) else None
            })
            return unescaped
            
        except json.JSONDecodeError as e:
            logger.warning("Initial JSON parse failed, attempting repair", extra={
                "parse_error": str(e),
                "error_line": e.lineno if hasattr(e, 'lineno') else None,
                "error_column": e.colno if hasattr(e, 'colno') else None,
                "error_position": e.pos if hasattr(e, 'pos') else None
            })
            
            # Try common fixes
            repaired_json = clean_json
            
            # Fix 1: Remove trailing commas
            import re
            repaired_json = re.sub(r',(\s*[}\]])', r'\1', repaired_json)
            
            # Fix 2: Remove control characters except newlines and tabs
            repaired_json = ''.join(char for char in repaired_json if ord(char) >= 32 or char in '\n\t')
            
            # Fix 3: Try to fix common quote issues
            repaired_json = repaired_json.replace('"', '"').replace('"', '"')
            repaired_json = repaired_json.replace("'", '"')
            
            logger.info("Attempting to parse repaired JSON", extra={
                "original_length": len(clean_json),
                "repaired_length": len(repaired_json),
                "repaired_preview": repaired_json[:300] + "..." if len(repaired_json) > 300 else repaired_json
            })
            
            try:
                unescaped = json.loads(repaired_json)
                logger.info("LLM JSON response parsed successfully after repair", extra={
                    "parsed_keys": list(unescaped.keys()) if isinstance(unescaped, dict) else None,
                    "product": unescaped.get('product') if isinstance(unescaped, dict) else None
                })
                return unescaped
                
            except json.JSONDecodeError as repair_error:
                logger.error("Failed to decode JSON even after repair attempts", extra={
                    "original_error": str(e),
                    "repair_error": str(repair_error),
                    "raw_json_full": clean_json,
                    "repaired_json_full": repaired_json,
                    "json_lines": clean_json.split('\n')[:10]  # First 10 lines for debugging
                })
                raise ValueError(f"Failed to decode JSON from response: {e}")
            
    except json.JSONDecodeError as e:
        logger.error("Failed to parse initial LLM response", extra={
            "json_decode_error": str(e),
            "response_preview": response[:500] + "..." if len(response) > 500 else response,
            "response_full": response  # Full response for debugging
        })
        raise ValueError(f"Failed to parse LLM response: {e}")
    except Exception as e:
        logger.error("Unexpected error parsing LLM response", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "response_preview": response[:500] + "..." if len(response) > 500 else response
        })
        raise ValueError(f"Unexpected error parsing LLM response: {e}")

import re

def extract_json_from_llm_response(inner_str: str) -> dict:
    print('inner str', inner_str)
    # ---------- STEP 2 ─ unescape inner JSON --------
    try:
        # Un‑escape \" and \n etc.
        inner_str = json.loads(inner_str)
    except json.JSONDecodeError:
        # It might already be raw JSON; keep going
        pass

    # ---------- STEP 3 ─ strip trailing commas ------
    inner_str = re.sub(r",\s*(\}|\])", r"\1", inner_str, flags=re.MULTILINE)
    inner_str = re.sub(r'[“”‘’]', '"', inner_str)

    # ---------- STEP 4 ─ final parse ----------------
    try:
        inner_json = json.loads(inner_str)
        return inner_json
    except json.JSONDecodeError as e:
        raise ValueError(f"Cleaned JSON still invalid: {e}")
