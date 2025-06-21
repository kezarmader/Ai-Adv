from fastapi import FastAPI, Request
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

    context = f"""You are to output ONE thing and one thing only: a single, perfectly‑formed UTF‑8 JSON object.

                Context
                -------
                Create an ad for a product: {product}, targeted at {audience}, using a tone {tone}. Generate descriptive scene for an image generator as well so 
                that can be used to feed to an AI Model to generate a realistic image hook.

                reference: https://www.amazon.com/dp/{asin}

                Hard Rules (MUST follow every rule; failure on any rule makes the response invalid)
                1. Respond **only** with raw JSON — no prose, no markdown, no code‑block fences, no leading/trailing back‑ticks, and no surrounding quotes.
                2. All keys **must** be double‑quoted ASCII (\"...\").
                3. All string values **must** be double‑quoted UTF‑8 with no unescaped control characters.
                4. Absolutely **no** characters outside the UTF‑8 range.
                5. No trailing commas, missing commas, or dangling braces/brackets.
                6. Top‑level output must parse with both `json.load()` (file) and `json.loads()` (string) in Python without raising:
                   • TypeError: expected string or bytes‑like object
                   • ValueError / JSONDecodeError: expecting property name in double quotes
                   • ValueError / JSONDecodeError: expecting ',' delimiter
                   • ValueError / JSONDecodeError: extra data
                7. The structure MUST include at minimum these keys:
                   • "product"  – string
                   • "audience" – string or array of strings
                   • "tone"     – string
                   • "description" – string
                   • "features" – array of strings (or objects with name/value pairs)
                8. Do **not** escape the entire JSON or wrap it in additional quotes; emit it plainly.

                Example schema (for guidance only, DO NOT output this line):
                {{
                  "product": "...",
                  "audience": ["..."],
                  "tone": "...",
                  "description": "...",
                  "features": ["...", "...", "..."]
                }}

                Remember: if any character outside valid JSON appears, the whole response is invalid. Output just the JSON object, nothing more."""


    # LLM call to Ollama
    llm_response = requests.post("http://llm-service:11434/api/generate", json={
        "model": "llama3",
        "prompt": context,
        "stream": False
    })

    ad_text = parse_llm_escaped_json(llm_response.text.strip())
    
    print('ad_text', ad_text)

   # Image Generator
    image_response = requests.post("http://image-generator:5001/generate", json={
            "product_name": ad_text['product'],
            "features": ad_text['features'],
            "brand_text": brand_text,
            "cta_text": cta_text
        })
    
    print('image_response', image_response)

    image_url = image_response.json().get("url", "")

    if image_url == '' or image_url == None:
        raise('Error generating image_url', image_url)

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
