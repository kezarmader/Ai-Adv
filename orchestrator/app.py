from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
import requests
import json

app = FastAPI()

@app.post("/run")
async def run_ad_campaign(req: Request):
    body = await req.json()
    product = body.get("product")
    audience = body.get("audience")
    tone = body.get("tone")
    asin = body.get("ASIN")
    brand_text = body.get("brand_text")
    cta_text = body.get("cta_text")

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
    llm_response = requests.post("http://llm-service:11434/api/generate", json={
        "model": "llama3",
        "prompt": context,
        "stream": False
    })

    ad_text = parse_llm_escaped_json(llm_response.text.strip())
    
    print('ad_text', ad_text)

    image_prompt = {
             "product_name": ad_text['product'],
            "features": ad_text['features'],
            "brand_text": brand_text,
            "cta_text": cta_text,
            "scene": ad_text['scene']
            }
    print('image_prompt', image_prompt)

   # Image Generator
    image_response = requests.post("http://image-generator:5001/generate", json=image_prompt)
    
    print('image_response', image_response)
    print('image_response.json()', image_response.json())

    response_data = image_response.json()
    filename = response_data.get("filename", "")
    
    if filename == '' or filename == None:
        raise ValueError(f'Error generating filename: {filename}')
    
    # Get the host from the request to construct the proper external URL
    host = req.headers.get("host", "localhost:8000")
    # Construct URL that points to orchestrator's download endpoint
    image_url = f"http://{host}/download/{filename}"

    print('constructed image_url:', image_url)

    # Post
    post_response = requests.post("http://poster-service:5002/post", json={
        "text": ad_text,
        "image_url": image_url
    })

    return {
        "ad_text": ad_text,
        "image_url": image_url,
        "post_status": post_response.json()
    }

@app.get("/download/{filename}")
async def download_image(filename: str):
    """Proxy endpoint to download images from image-generator service"""
    try:
        # Make request to image-generator service
        image_response = requests.get(f"http://image-generator:5001/download/{filename}")
        
        if image_response.status_code == 404:
            raise HTTPException(status_code=404, detail="Image not found or has expired")
        elif image_response.status_code != 200:
            raise HTTPException(status_code=image_response.status_code, detail="Error fetching image")
        
        # Return the image content with proper headers
        return Response(
            content=image_response.content,
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "image/png"
            }
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching image: {str(e)}")

import json

def parse_llm_escaped_json(response):
    response_obj = json.loads(response)
    print('response obj', response_obj)

    # Step 1: Get the raw string containing escaped JSON
    raw_json_str = response_obj.get("response")
    # clean_json = extract_json_from_llm_response(raw_json_str)
    clean_json = raw_json_str

    if not clean_json:
        raise ValueError("Missing 'response' key in LLM output")

    print('clean_json', clean_json)
    # Step 2: Unescape the string and convert it into a valid JSON object
    try:
        unescaped = json.loads(clean_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to decode JSON from response: {e}")

    print('parsed', unescaped)
    return unescaped

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
