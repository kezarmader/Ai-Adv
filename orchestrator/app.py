from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
import requests
import json
import time
import logging
from logging_config import (
    setup_logging, TimingContext, generate_request_id, request_id,
    log_request_details, log_response_details, log_external_api_call
)

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

def create_json_fix_prompt(original_context: str, error_message: str, failed_response: str) -> str:
    """Create a prompt asking the LLM to fix its JSON response"""
    return f"""CRITICAL ERROR CORRECTION NEEDED: Your previous response had JSON parsing errors.

ERROR: {error_message}

YOUR PREVIOUS RESPONSE:
{failed_response}

ORIGINAL REQUEST:
{original_context}

INSTRUCTIONS FOR CORRECTION:
1. You MUST output ONLY a valid JSON object - nothing else
2. Fix the JSON syntax errors from your previous response
3. Ensure all quotes are properly escaped
4. Remove any trailing commas
5. Ensure all brackets and braces are properly closed
6. Do NOT include any explanatory text, markdown formatting, or code blocks
7. Start directly with {{ and end with }}

The JSON must contain these exact keys:
- "product": string
- "audience": string or list of strings  
- "tone": string
- "description": string
- "features": list of strings
- "scene": string (detailed image generation prompt)

OUTPUT ONLY THE CORRECTED JSON NOW:"""

def parse_llm_json_response(response: str) -> dict:
    """Parse JSON response from LLM with minimal processing"""
    try:
        # First, try to parse the outer response structure
        response_obj = json.loads(response)
        
        # Extract the actual content
        if isinstance(response_obj, dict) and "response" in response_obj:
            json_content = response_obj["response"]
        else:
            json_content = response
            
        logger.debug("Extracted JSON content from LLM response", extra={
            "content_length": len(json_content),
            "content_preview": json_content[:200] + "..." if len(json_content) > 200 else json_content
        })
        
        # Try to parse the actual JSON content
        try:
            parsed_data = json.loads(json_content)
            
            # Validate required fields
            required_fields = ["product", "audience", "tone", "description", "features", "scene"]
            missing_fields = [field for field in required_fields if field not in parsed_data]
            
            if missing_fields:
                raise ValueError(f"Missing required fields in JSON response: {missing_fields}")
            
            logger.info("JSON response parsed and validated successfully", extra={
                "parsed_keys": list(parsed_data.keys()),
                "product": parsed_data.get('product'),
                "features_count": len(parsed_data.get('features', []))
            })
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON content", extra={
                "parse_error": str(e),
                "json_content": json_content,
                "error_position": getattr(e, 'pos', None)
            })
            raise ValueError(f"Invalid JSON format: {str(e)}")
            
    except json.JSONDecodeError as e:
        # Response itself is not valid JSON
        logger.error("Failed to parse LLM response structure", extra={
            "parse_error": str(e),
            "response_preview": response[:500] + "..." if len(response) > 500 else response
        })
        raise ValueError(f"LLM response is not valid JSON: {str(e)}")
    except Exception as e:
        logger.error("Unexpected error parsing LLM response", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "response_preview": response[:500] + "..." if len(response) > 500 else response
        })
        raise ValueError(f"Unexpected error parsing LLM response: {str(e)}")

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

            # LLM call to Ollama with retry logic for JSON errors
            max_retries = 3
            ad_text = None
            last_error = None
            last_response = None
            
            for attempt in range(max_retries):
                with TimingContext("llm_generation", logger, {"model": "llama3", "attempt": attempt + 1}) as llm_timer:
                    start_time = time.time()
                    
                    # Use original context for first attempt, error correction for retries
                    prompt_to_use = context if attempt == 0 else create_json_fix_prompt(context, last_error, last_response)
                    
                    llm_response = requests.post("http://llm-service:11434/api/generate", json={
                        "model": "llama3",
                        "prompt": prompt_to_use,
                        "stream": False
                    })
                    duration_ms = (time.time() - start_time) * 1000
                    
                    log_external_api_call(
                        logger, "llm-service", "/api/generate", "POST",
                        response_status=llm_response.status_code,
                        duration_ms=round(duration_ms, 2),
                        extra_data={"attempt": attempt + 1, "is_retry": attempt > 0}
                    )
                    
                    if llm_response.status_code != 200:
                        raise HTTPException(status_code=500, detail=f"LLM service error: {llm_response.status_code}")

                # Parse LLM response
                with TimingContext("llm_response_parsing", logger):
                    try:
                        raw_response = llm_response.text.strip()
                        logger.debug("Raw LLM response received", extra={
                            "attempt": attempt + 1,
                            "response_length": len(raw_response),
                            "response_preview": raw_response[:200] + "..." if len(raw_response) > 200 else raw_response,
                            "response_ends_with": raw_response[-50:] if len(raw_response) > 50 else raw_response
                        })
                        
                        ad_text = parse_llm_json_response(raw_response)
                        logger.info("LLM response parsed successfully", extra={
                            "attempt": attempt + 1,
                            "product_parsed": ad_text.get('product'),
                            "features_count": len(ad_text.get('features', [])),
                            "scene_length": len(ad_text.get('scene', ''))
                        })
                        break  # Success, exit retry loop
                        
                    except ValueError as e:
                        last_error = str(e)
                        last_response = llm_response.text.strip()
                        logger.warning("JSON parsing failed", extra={
                            "attempt": attempt + 1,
                            "error": last_error,
                            "will_retry": attempt < max_retries - 1,
                            "raw_response_length": len(last_response),
                            "raw_response_preview": last_response[:300] + "..." if len(last_response) > 300 else last_response
                        })
                        
                        if attempt == max_retries - 1:
                            # Final attempt failed
                            logger.error("All LLM retry attempts failed", extra={
                                "total_attempts": max_retries,
                                "final_error": last_error,
                                "final_response": last_response[:500] + "..." if len(last_response) > 500 else last_response
                            })
                            raise HTTPException(status_code=500, detail=f"LLM failed to generate valid JSON after {max_retries} attempts: {last_error}")
                    except Exception as e:
                        # Catch any other unexpected errors during parsing
                        last_error = str(e)
                        last_response = llm_response.text.strip()
                        logger.error("Unexpected error during LLM response parsing", extra={
                            "attempt": attempt + 1,
                            "error": last_error,
                            "error_type": type(e).__name__,
                            "raw_response_length": len(last_response),
                            "raw_response_preview": last_response[:300] + "..." if len(last_response) > 300 else last_response
                        })
                        
                        if attempt == max_retries - 1:
                            logger.error("All LLM retry attempts failed due to unexpected error", extra={
                                "total_attempts": max_retries,
                                "final_error": last_error,
                                "final_error_type": type(e).__name__
                            })
                            raise HTTPException(status_code=500, detail=f"LLM parsing failed with unexpected error after {max_retries} attempts: {last_error}")
                        # Continue to next retry attempt for unexpected errors too
            
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
            
            log_external_api_call(
                logger, "image-generator", f"/download/{filename}", "GET",
                response_status=image_response.status_code,
                duration_ms=round(duration_ms, 2)
            )
            
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
