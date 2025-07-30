import requests
import logging
from typing import Dict, Any
from core.domain.entities import AdText, Product, Audience
from core.ports.outbound import LLMPort
from json_repair_engine import parse_llm_json_with_repair
from infrastructure.prompts import prompt_config

logger = logging.getLogger(__name__)

class LLMAdapter(LLMPort):
    """Adapter for LLM service integration"""
    
    def __init__(self, llm_url: str = "http://llm-service:11434", model: str = "llama3", prompt_template: str = "standard"):
        self.llm_url = llm_url
        self.model = model
        self.prompt_template = prompt_template
    
    async def generate_ad_text(self, product: Product, audience: Audience, template: str = None) -> AdText:
        """Generate advertisement text using LLM"""
        
        prompt = self._build_prompt(product, audience, template)
        
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
    
    def _build_prompt(self, product: Product, audience: Audience, template: str = None) -> str:
        """Build the LLM prompt for ad generation using configured template"""
        
        # Use runtime template if provided, otherwise fall back to default
        template_to_use = template or self.prompt_template
        
        # Check if it's a predefined template name or custom prompt text
        available_templates = prompt_config.list_available_templates()
        if template_to_use in available_templates:
            # Use predefined template
            return prompt_config.format_prompt(
                template_name=template_to_use,
                product_name=product.name,
                audience_demographics=audience.demographics,
                tone=audience.tone,
                asin=product.asin
            )
        elif template_to_use:
            # Use as custom prompt template
            return template_to_use.format(
                product_name=product.name,
                audience_demographics=audience.demographics,
                tone=audience.tone,
                asin=product.asin
            )
        else:
            # Fallback to default configured template
            return prompt_config.format_prompt(
                template_name=self.prompt_template,
                product_name=product.name,
                audience_demographics=audience.demographics,
                tone=audience.tone,
                asin=product.asin
            )
