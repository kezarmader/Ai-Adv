import requests
import logging
import json
from core.domain.entities import AdText
from core.ports.outbound import ImageGenerationPort

logger = logging.getLogger(__name__)

class ImageAdapter(ImageGenerationPort):
    """Adapter for image generation service"""
    
    def __init__(self, image_service_url: str = "http://image-generator:5001"):
        self.image_service_url = image_service_url
    
    async def generate_image(self, ad_text: AdText, brand_text: str = None, cta_text: str = None) -> str:
        """Generate image and return filename"""
        
        image_prompt = {
            "product_name": ad_text.product,
            "features": ad_text.features,
            "brand_text": brand_text,
            "cta_text": cta_text,
            "scene": ad_text.scene
        }
        
        logger.info("Sending image generation request", extra={
            "prompt_size": len(json.dumps(image_prompt))
        })
        
        response = requests.post(
            f"{self.image_service_url}/generate", 
            json=image_prompt
        )
        
        logger.info("Image generation request completed", extra={
            "status_code": response.status_code
        })
        
        if response.status_code != 200:
            raise requests.RequestException(f"Image generation error: {response.status_code}")
        
        response_data = response.json()
        filename = response_data.get("filename", "")
        
        if not filename:
            raise ValueError(f'Error generating filename: {filename}')
        
        logger.info("Image generated successfully", extra={"filename": filename})
        return filename
    
    async def download_image(self, filename: str) -> bytes:
        """Download image content"""
        
        logger.info("Downloading image", extra={"filename": filename})
        
        response = requests.get(f"{self.image_service_url}/download/{filename}")
        
        logger.debug("Image download request completed", extra={
            "status_code": response.status_code
        })
        
        if response.status_code == 404:
            logger.warning("Image not found", extra={"filename": filename})
            raise FileNotFoundError("Image not found or has expired")
        elif response.status_code != 200:
            logger.error("Error fetching image", extra={
                "filename": filename,
                "status_code": response.status_code
            })
            raise requests.RequestException(f"Error fetching image: {response.status_code}")
        
        image_size = len(response.content)
        logger.info("Image downloaded successfully", extra={
            "filename": filename,
            "size_bytes": image_size
        })
        
        return response.content
