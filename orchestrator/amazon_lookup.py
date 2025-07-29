"""
Amazon Product Lookup Module
Fetches product details using ASIN for better ad generation
"""

import requests
import json
import logging
from typing import Dict, Optional
import time
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class AmazonProductLookup:
    """
    Amazon Product Information Lookup
    Uses web scraping to get product details from Amazon
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def get_product_info(self, asin: str) -> Optional[Dict]:
        """
        Get product information from Amazon using ASIN
        
        Args:
            asin: Amazon product ASIN
            
        Returns:
            Dictionary with product info or None if failed
        """
        if not asin or len(asin) != 10:
            logger.warning(f"Invalid ASIN format: {asin}")
            return None
            
        try:
            # Amazon product URL
            url = f"https://www.amazon.com/dp/{asin}"
            
            logger.info(f"Fetching product info for ASIN: {asin}")
            
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Amazon request failed: {response.status_code}")
                return None
                
            # Basic product info extraction
            product_info = self._extract_product_info(response.text, asin)
            
            logger.info(f"Successfully extracted product info for ASIN: {asin}", extra={
                "product_title": product_info.get("title", "Unknown")[:50],
                "features_count": len(product_info.get("features", [])),
                "has_description": bool(product_info.get("description"))
            })
            
            return product_info
            
        except requests.RequestException as e:
            logger.warning(f"Network error fetching ASIN {asin}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching ASIN {asin}: {str(e)}")
            return None
    
    def _extract_product_info(self, html_content: str, asin: str) -> Dict:
        """
        Extract product information from Amazon HTML
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract basic product information
        product_info = {
            "asin": asin,
            "title": "",
            "features": [],
            "description": "",
            "brand": "",
            "category": "",
            "specifications": {},
            "availability": True
        }
        
        # Title extraction
        title_selectors = [
            '#productTitle',
            '.product-title',
            'h1 span',
            '[data-automation-id="product-title"]',
            '.a-size-large.product-title-word-break'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                product_info["title"] = title_elem.get_text().strip()
                break
        
        # Features extraction (bullet points)
        feature_selectors = [
            '#feature-bullets ul li span.a-list-item',
            '#feature-bullets ul li .a-size-base',
            '.a-unordered-list .a-list-item',
            '[data-automation-id="feature-bullet"]',
            '#feature-bullets li',
            '.feature .a-list-item'
        ]
        
        for selector in feature_selectors:
            features = soup.select(selector)
            if features:
                extracted_features = []
                for f in features:
                    text = f.get_text().strip()
                    # Clean up feature text
                    text = re.sub(r'^[•\-\*]\s*', '', text)  # Remove bullet points
                    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
                    if text and len(text) > 10 and len(text) < 200 and text not in extracted_features:
                        extracted_features.append(text)
                
                product_info["features"] = extracted_features[:8]  # Top 8 features
                if extracted_features:
                    break
        
        # Brand extraction
        brand_selectors = [
            '#bylineInfo',
            '.a-link-normal[data-automation-id="byline"]',
            '[data-automation-id="brand-name"]',
            '#bylineInfo_feature_div .a-link-normal',
            '.po-brand .po-break-word'
        ]
        
        for selector in brand_selectors:
            brand_elem = soup.select_one(selector)
            if brand_elem:
                brand_text = brand_elem.get_text().strip()
                # Clean up brand text
                brand_text = re.sub(r'Visit the\s*', '', brand_text, flags=re.IGNORECASE)
                brand_text = re.sub(r'\s*Store\s*', '', brand_text, flags=re.IGNORECASE)
                brand_text = re.sub(r'Brand:\s*', '', brand_text, flags=re.IGNORECASE)
                product_info["brand"] = brand_text.strip()
                break
        
        # Description extraction
        description_selectors = [
            '#feature-bullets .a-expander-content',
            '[data-automation-id="productDescription"]',
            '#productDescription p',
            '.aplus-p1',
            '.product-description'
        ]
        
        for selector in description_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                desc_text = desc_elem.get_text().strip()
                if len(desc_text) > 50:  # Only meaningful descriptions
                    product_info["description"] = desc_text[:500]  # Limit length
                    break
        
        # Category extraction
        category_selectors = [
            '#wayfinding-breadcrumbs_feature_div a',
            '.a-breadcrumb a',
            '[data-automation-id="breadcrumb"] a'
        ]
        
        categories = []
        for selector in category_selectors:
            cat_elems = soup.select(selector)
            for elem in cat_elems:
                cat_text = elem.get_text().strip()
                if cat_text and cat_text.lower() not in ['home', 'amazon.com']:
                    categories.append(cat_text)
        
        if categories:
            product_info["category"] = " > ".join(categories[-3:])  # Last 3 categories
        
        # Specifications extraction (if available)
        spec_rows = soup.select('#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr')
        for row in spec_rows[:5]:  # Limit to top 5 specs
            cols = row.select('td')
            if len(cols) >= 2:
                key = cols[0].get_text().strip()
                value = cols[1].get_text().strip()
                if key and value and len(key) < 50 and len(value) < 100:
                    product_info["specifications"][key] = value
        
        return product_info

    def enhance_product_prompt(self, base_product: str, asin: str) -> str:
        """
        Enhance product description with ASIN lookup data
        
        Args:
            base_product: User-provided product name
            asin: Amazon ASIN
            
        Returns:
            Enhanced product description for LLM prompt
        """
        product_info = self.get_product_info(asin)
        
        if not product_info or not product_info.get("title"):
            logger.info(f"Using fallback product info for ASIN: {asin}")
            return base_product
        
        # Create enhanced description
        enhanced_parts = []
        
        # Use Amazon title as primary product name
        enhanced_parts.append(f"Product: {product_info['title']}")
        
        if product_info.get("brand"):
            enhanced_parts.append(f"Brand: {product_info['brand']}")
        
        if product_info.get("category"):
            enhanced_parts.append(f"Category: {product_info['category']}")
        
        if product_info.get("features"):
            # Include top 3-5 most relevant features
            features_text = " | ".join(product_info["features"][:5])
            enhanced_parts.append(f"Key Features: {features_text}")
        
        if product_info.get("description"):
            # Include a snippet of the description
            desc_snippet = product_info["description"][:200] + "..." if len(product_info["description"]) > 200 else product_info["description"]
            enhanced_parts.append(f"Description: {desc_snippet}")
        
        if product_info.get("specifications"):
            # Include key specifications
            specs = []
            for key, value in list(product_info["specifications"].items())[:3]:
                specs.append(f"{key}: {value}")
            if specs:
                enhanced_parts.append(f"Specifications: {' | '.join(specs)}")
        
        enhanced_description = "\n".join(enhanced_parts)
        
        logger.info("Enhanced product description created", extra={
            "original_product": base_product,
            "enhanced_length": len(enhanced_description),
            "asin": asin,
            "amazon_title": product_info.get("title", "")[:50]
        })
        
        return enhanced_description

# Global instance
amazon_lookup = AmazonProductLookup()

async def get_enhanced_product_info(product: str, asin: str) -> str:
    """
    Async wrapper for product enhancement
    """
    if not asin:
        return product
        
    try:
        return amazon_lookup.enhance_product_prompt(product, asin)
    except Exception as e:
        logger.warning(f"Failed to enhance product with ASIN {asin}: {str(e)}")
        return product
