import requests
import logging
from typing import Dict, Any
from core.domain.entities import AdText
from core.ports.outbound import PostingPort

logger = logging.getLogger(__name__)

class PostingAdapter(PostingPort):
    """Adapter for posting service"""
    
    def __init__(self, post_service_url: str = "http://poster-service:5002"):
        self.post_service_url = post_service_url
    
    async def post_advertisement(self, ad_text: AdText, image_url: str) -> Dict[str, Any]:
        """Post advertisement and return status"""
        
        post_data = {
            "text": ad_text.to_dict(),
            "image_url": image_url
        }
        
        logger.info("Posting advertisement", extra={
            "image_url": image_url
        })
        
        response = requests.post(
            f"{self.post_service_url}/post", 
            json=post_data
        )
        
        logger.info("Post request completed", extra={
            "status_code": response.status_code
        })
        
        if response.status_code == 200:
            result = response.json()
            logger.info("Advertisement posted successfully", extra={
                "status": result.get("status", "unknown")
            })
            return result
        else:
            logger.warning("Post service unavailable", extra={
                "status_code": response.status_code
            })
            return {"status": "error", "message": "Post service unavailable"}
