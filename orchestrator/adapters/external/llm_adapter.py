import requests
import logging
from typing import Dict, Any
from core.domain.entities import AdText, Product, Audience
from core.ports.outbound import LLMPort
from json_repair_engine import parse_llm_json_with_repair

logger = logging.getLogger(__name__)

class LLMAdapter(LLMPort):
    """Adapter for LLM service integration"""
    
    def __init__(self, llm_url: str = "http://llm-service:11434", model: str = "llama3"):
        self.llm_url = llm_url
        self.model = model
    
    async def generate_ad_text(self, product: Product, audience: Audience) -> AdText:
        """Generate advertisement text using LLM"""
        
        prompt = self._build_prompt(product, audience)
        
        logger.debug("Making LLM request", extra={"model": self.model})
        
        response = requests.post(f"{self.llm_url}/api/generate", json={
            "model": self.model,
            "prompt": prompt,
            "stream": False
        })
        
        if response.status_code != 200:
            logger.error("LLM service error", extra={"status_code": response.status_code})
            raise requests.RequestException(f"LLM service error: {response.status_code}")
        
        # Parse response using repair engine
        raw_response = response.text.strip()
        logger.debug("Raw LLM response received", extra={
            "response_length": len(raw_response),
            "response_preview": raw_response[:300] + "..." if len(raw_response) > 300 else raw_response
        })
        
        parsed_data = parse_llm_json_with_repair(raw_response)
        
        # Convert to domain entity
        ad_text = AdText(
            product=parsed_data.get('product', product.name),
            audience=parsed_data.get('audience', audience.demographics),
            tone=parsed_data.get('tone', audience.tone),
            description=parsed_data.get('description', ''),
            features=parsed_data.get('features', []),
            scene=parsed_data.get('scene', '')
        )
        
        logger.info("LLM response parsed successfully", extra={
            "product_parsed": ad_text.product,
            "features_count": len(ad_text.features),
            "scene_length": len(ad_text.scene)
        })
        
        return ad_text
    
    def _build_prompt(self, product: Product, audience: Audience) -> str:
        """Build the LLM prompt for ad generation"""
        return f"""IMPORTANT: You must output a single, valid UTF‑8 JSON object. Absolutely nothing else.

            Context:
            You are generating a realistic product ad for the following:
            - Product: {product.name}
            - Target Audience: {audience.demographics}
            - Tone: {audience.tone}
            - Reference Link: https://www.amazon.com/dp/{product.asin}

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
