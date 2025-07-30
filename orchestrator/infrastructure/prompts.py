"""
LLM Prompt Templates Configuration

This module contains all prompt templates used for LLM interactions.
Templates use Python string formatting for dynamic content injection.
"""

import os
from typing import Dict, Any

class PromptTemplates:
    """Collection of LLM prompt templates"""
    
    # Main ad generation prompt template
    AD_GENERATION_TEMPLATE = """IMPORTANT: You must output a single, valid UTF‑8 JSON object. Absolutely nothing else.

Context:
You are generating a realistic product ad for the following:
- Product: {product_name}
- Target Audience: {audience_demographics}
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
- Include leading/trailing newlines or explanation"""

    # Alternative prompt for different tones/styles
    CREATIVE_AD_TEMPLATE = """Generate a creative advertisement in JSON format for:
Product: {product_name}
Target: {audience_demographics}  
Style: {tone}
Amazon: https://www.amazon.com/dp/{asin}

Focus on emotional connection and storytelling. Return valid JSON with:
- product, audience, tone, description, features, scene

Keep description compelling and scene visually rich for image generation."""

    # Short/concise prompt version
    CONCISE_AD_TEMPLATE = """Create JSON ad for {product_name} targeting {audience_demographics} with {tone} tone.
Amazon: https://www.amazon.com/dp/{asin}
Required: product, audience, tone, description, features, scene"""

    # Prompt for specific industries
    TECH_PRODUCT_TEMPLATE = """Technical product advertisement for {product_name}:
Target: {audience_demographics}
Tone: {tone}
Link: https://www.amazon.com/dp/{asin}

Emphasize specifications, performance, and technical benefits.
JSON format with product, audience, tone, description, features, scene."""

class PromptConfig:
    """Configuration for prompt selection and customization"""
    
    # Default prompt template to use
    DEFAULT_TEMPLATE: str = os.getenv("LLM_PROMPT_TEMPLATE", "standard")
    
    # Template mapping
    TEMPLATES: Dict[str, str] = {
        "standard": PromptTemplates.AD_GENERATION_TEMPLATE,
        "creative": PromptTemplates.CREATIVE_AD_TEMPLATE,
        "concise": PromptTemplates.CONCISE_AD_TEMPLATE,
        "tech": PromptTemplates.TECH_PRODUCT_TEMPLATE
    }
    
    # Custom template from environment (for advanced users)
    CUSTOM_TEMPLATE: str = os.getenv("LLM_CUSTOM_PROMPT", "")
    
    @classmethod
    def get_template(cls, template_name: str = None) -> str:
        """Get prompt template by name"""
        if cls.CUSTOM_TEMPLATE:
            return cls.CUSTOM_TEMPLATE
            
        template_name = template_name or cls.DEFAULT_TEMPLATE
        return cls.TEMPLATES.get(template_name, cls.TEMPLATES["standard"])
    
    @classmethod
    def format_prompt(cls, template_name: str = None, **kwargs) -> str:
        """Format prompt template with provided variables"""
        template = cls.get_template(template_name)
        return template.format(**kwargs)
    
    @classmethod
    def list_available_templates(cls) -> Dict[str, str]:
        """List all available prompt templates"""
        return {
            name: template[:100] + "..." if len(template) > 100 else template
            for name, template in cls.TEMPLATES.items()
        }

# Global prompt config instance
prompt_config = PromptConfig()
