from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
import requests
import json
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any
import logging
from logging_config import (
    setup_logging, TimingContext, generate_request_id, request_id
)

# Setup structured logging
logger = setup_logging("asin-extractor", "INFO")

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate and set request ID
        req_id = generate_request_id()
        request_id.set(req_id)
        
        # Log request details
        client_ip = request.client.host if request.client else "unknown"
        logger.info("HTTP request received", extra={
            "method": request.method,
            "path": str(request.url.path),
            "client_ip": client_ip,
            "event": "http_request"
        })
        
        # Start timing
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response details
        logger.info("HTTP response sent", extra={
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "event": "http_response"
        })
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = req_id
        
        return response

app = FastAPI(title="AI Advertisement Generator - ASIN Extractor", version="1.0.0")
app.add_middleware(LoggingMiddleware)

logger.info("ASIN Extractor service starting up")

class ASINExtractor:
    """Extract product information from Amazon ASIN"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def extract_asin_from_url(self, url: str) -> Optional[str]:
        """Extract ASIN from Amazon URL"""
        try:
            # Pattern to match ASIN in URLs
            asin_patterns = [
                r'/dp/([A-Z0-9]{10})',
                r'/gp/product/([A-Z0-9]{10})',
                r'asin=([A-Z0-9]{10})',
                r'/([A-Z0-9]{10})(?:/|$)',
            ]
            
            for pattern in asin_patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            return None
        except Exception as e:
            logger.error("Error extracting ASIN from URL", extra={
                "url": url,
                "error": str(e)
            })
            return None
    
    def scrape_amazon_product_info(self, asin: str) -> Dict[str, Any]:
        """Scrape basic product information from Amazon"""
        url = f"https://www.amazon.com/dp/{asin}"
        
        try:
            with TimingContext("amazon_scraping", logger, {"asin": asin}):
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = {
                    "asin": asin,
                    "title": self._extract_title(soup),
                    "price": self._extract_price(soup),
                    "rating": self._extract_rating(soup),
                    "description": self._extract_description(soup),
                    "features": self._extract_features(soup),
                    "images": self._extract_images(soup),
                    "category": self._extract_category(soup),
                    "brand": self._extract_brand(soup),
                    "availability": self._extract_availability(soup)
                }
                
                logger.info("Product information extracted successfully", extra={
                    "asin": asin,
                    "title": product_info.get("title", "")[:50] + "..." if product_info.get("title") else "N/A",
                    "has_images": len(product_info.get("images", [])) > 0,
                    "features_count": len(product_info.get("features", []))
                })
                
                return product_info
                
        except requests.RequestException as e:
            logger.error("Network error during Amazon scraping", extra={
                "asin": asin,
                "error": str(e)
            })
            raise HTTPException(status_code=503, detail=f"Unable to fetch Amazon product data: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error during Amazon scraping", extra={
                "asin": asin,
                "error": str(e)
            })
            raise HTTPException(status_code=500, detail=f"Error processing Amazon product: {str(e)}")
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract product title"""
        selectors = [
            '#productTitle',
            '.product-title',
            '[data-automation-id="product-title"]',
            'h1.a-size-large'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text().strip()
        
        return "Unknown Product"
    
    def _extract_price(self, soup: BeautifulSoup) -> str:
        """Extract product price"""
        selectors = [
            '.a-price-whole',
            '.a-price.a-text-price.a-size-medium.apexPriceToPay',
            '.a-price-symbol + .a-price-whole',
            '[data-automation-id="product-price"]'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text().strip()
        
        return "Price not available"
    
    def _extract_rating(self, soup: BeautifulSoup) -> str:
        """Extract product rating"""
        selectors = [
            '.a-icon-alt',
            '[data-hook="average-star-rating"]',
            '.cr-widget-FocalReviews .a-icon-alt'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                if 'out of' in text or 'stars' in text:
                    return text
        
        return "No rating available"
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract product description"""
        selectors = [
            '#feature-bullets ul',
            '#productDescription',
            '.a-unordered-list.a-vertical.a-spacing-mini',
            '[data-automation-id="product-overview"]'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                # Get text from list items or paragraphs
                text_parts = []
                for item in element.find_all(['li', 'p'])[:5]:  # Limit to first 5 items
                    text = item.get_text().strip()
                    if text and len(text) > 10:  # Filter out short/empty items
                        text_parts.append(text)
                
                if text_parts:
                    return " ".join(text_parts)
        
        return "No description available"
    
    def _extract_features(self, soup: BeautifulSoup) -> list:
        """Extract product features"""
        features = []
        
        # Try different selectors for features
        selectors = [
            '#feature-bullets li',
            '.a-unordered-list.a-vertical li',
            '[data-automation-id="product-highlights"] li'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements[:10]:  # Limit to first 10 features
                text = element.get_text().strip()
                # Filter out unwanted text
                if (text and len(text) > 5 and 
                    not text.lower().startswith('make sure') and
                    not text.lower().startswith('asin') and
                    'customer reviews' not in text.lower()):
                    features.append(text)
            
            if features:
                break
        
        return features[:8]  # Return max 8 features
    
    def _extract_images(self, soup: BeautifulSoup) -> list:
        """Extract product images"""
        images = []
        
        # Try different selectors for images
        selectors = [
            '#landingImage',
            '.a-dynamic-image',
            '[data-automation-id="product-image"]',
            '#imgBlkFront'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for img in elements:
                src = img.get('src') or img.get('data-src')
                if src and 'amazon.com' in src and src not in images:
                    # Get higher resolution version if possible
                    if '._' in src:
                        high_res = re.sub(r'\._[^.]*\.', '._SL1500_.', src)
                        images.append(high_res)
                    else:
                        images.append(src)
        
        return images[:5]  # Return max 5 images
    
    def _extract_category(self, soup: BeautifulSoup) -> str:
        """Extract product category"""
        selectors = [
            '#wayfinding-breadcrumbs_feature_div a',
            '.a-breadcrumb a',
            '[data-automation-id="breadcrumb"] a'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements and len(elements) > 1:
                # Get the last meaningful category (skip "Home" etc.)
                for element in reversed(elements[1:]):
                    text = element.get_text().strip()
                    if text and len(text) > 2:
                        return text
        
        return "General"
    
    def _extract_brand(self, soup: BeautifulSoup) -> str:
        """Extract product brand"""
        selectors = [
            '#bylineInfo',
            '.a-link-normal[href*="/stores/"]',
            '[data-automation-id="product-brand"]',
            'tr:contains("Brand") td'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                if text:
                    # Clean up brand text
                    text = re.sub(r'Visit the .* Store', '', text)
                    text = re.sub(r'Brand:', '', text)
                    return text.strip()
        
        return "Unknown Brand"
    
    def _extract_availability(self, soup: BeautifulSoup) -> str:
        """Extract product availability"""
        selectors = [
            '#availability span',
            '[data-automation-id="availability-message"]',
            '.a-size-medium.a-color-success',
            '.a-size-medium.a-color-error'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                if text and ('stock' in text.lower() or 'available' in text.lower() or 'ships' in text.lower()):
                    return text
        
        return "Availability unknown"

# Initialize extractor
extractor = ASINExtractor()

@app.post("/extract-asin")
async def extract_product_info(req: Request):
    """Extract product information from ASIN or Amazon URL"""
    timer = None
    try:
        with TimingContext("asin_extraction", logger) as timer:
            body = await req.json()
            asin_input = body.get("asin") or body.get("ASIN")
            url_input = body.get("url")
            
            if not asin_input and not url_input:
                raise HTTPException(status_code=400, detail="Either 'asin' or 'url' is required")
            
            # Extract ASIN from URL if provided
            if url_input:
                asin_input = extractor.extract_asin_from_url(url_input)
                if not asin_input:
                    raise HTTPException(status_code=400, detail="Could not extract valid ASIN from URL")
            
            # Validate ASIN format
            if not re.match(r'^[A-Z0-9]{10}$', asin_input):
                raise HTTPException(status_code=400, detail="Invalid ASIN format (must be 10 alphanumeric characters)")
            
            logger.info("ASIN extraction request received", extra={
                "asin": asin_input,
                "from_url": bool(url_input)
            })
            
            # Extract product information
            product_info = extractor.scrape_amazon_product_info(asin_input)
            
            logger.info("ASIN extraction completed successfully", extra={
                "asin": asin_input,
                "total_duration_ms": round(timer.duration_ms, 2),
                "extracted_title": product_info.get("title", "")[:50] + "..." if product_info.get("title") else "N/A"
            })
            
            return {
                "status": "success",
                "asin": asin_input,
                "product_info": product_info,
                "extraction_time_ms": round(timer.duration_ms, 2)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error("Unexpected error in ASIN extraction", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(timer.duration_ms, 2) if timer else None,
            "traceback": traceback.format_exc()
        })
        raise HTTPException(status_code=500, detail=f"ASIN extraction failed: {str(e)}")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "asin-extractor",
        "features": [
            "Amazon ASIN extraction",
            "Product information scraping",
            "Image URL extraction",
            "Feature list extraction"
        ]
    }

logger.info("ASIN Extractor service ready")