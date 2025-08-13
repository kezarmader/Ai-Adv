from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class AdCampaignRequestModel(BaseModel):
    """HTTP request model for ad campaign generation"""
    product: str = Field(..., description="Product name")
    audience: str = Field(..., description="Target audience")
    tone: str = Field(..., description="Advertisement tone")
    ASIN: str = Field(..., description="Amazon product ID")
    brand_text: Optional[str] = Field(None, description="Brand text for image")
    cta_text: Optional[str] = Field(None, description="Call-to-action text")
    generate_video: Optional[bool] = Field(True, description="Whether to generate video")

class AdCampaignResponseModel(BaseModel):
    """HTTP response model for ad campaign"""
    ad_text: dict
    image_url: str
    video_url: Optional[str] = None
    video_info: Optional[Dict[str, Any]] = None
    post_status: dict
