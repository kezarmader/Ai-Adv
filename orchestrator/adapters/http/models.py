from pydantic import BaseModel, Field
from typing import List, Optional

class AdCampaignRequestModel(BaseModel):
    """HTTP request model for ad campaign generation"""
    product: str = Field(..., description="Product name")
    audience: str = Field(..., description="Target audience")
    tone: str = Field(..., description="Advertisement tone")
    ASIN: str = Field(..., description="Amazon product ID")
    brand_text: Optional[str] = Field(None, description="Brand text for image")
    cta_text: Optional[str] = Field(None, description="Call-to-action text")
    template: Optional[str] = Field(None, description="Prompt template to use: 'standard', 'creative', 'tech', 'concise', or custom prompt text")

class AdCampaignResponseModel(BaseModel):
    """HTTP response model for ad campaign"""
    ad_text: dict
    image_url: str
    post_status: dict
