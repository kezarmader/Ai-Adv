"""
Configuration for Secure Trends Integration
Handles authentication, API keys, and security settings
"""
import os
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class TrendsConfig:
    """Configuration class for trends integration"""
    
    # Rate limiting settings
    min_request_interval: int = 60  # seconds between requests
    cache_duration: int = 900  # 15 minutes cache
    max_retries: int = 3
    request_timeout: int = 15
    
    # Content filtering
    max_trend_length: int = 150
    max_trends_per_source: int = 10
    avoid_keywords: list = None
    
    # API Keys (set via environment variables)
    google_trends_api_key: Optional[str] = None
    twitter_bearer_token: Optional[str] = None
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    
    # Fallback settings
    enable_seasonal_fallback: bool = True
    enable_curated_fallback: bool = True
    
    def __post_init__(self):
        """Initialize configuration from environment variables"""
        if self.avoid_keywords is None:
            self.avoid_keywords = [
                "war", "politics", "election", "death", "tragedy", "disaster", 
                "crime", "violence", "protest", "scandal", "controversy", "shooting",
                "terrorism", "bomb", "attack", "murder", "suicide", "crash", "accident",
                "covid", "pandemic", "lockdown", "recession", "inflation", "unemployment"
            ]
        
        # Load API keys from environment
        self.google_trends_api_key = os.getenv('GOOGLE_TRENDS_API_KEY')
        self.twitter_bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        self.reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    
    def get_headers(self, service: str) -> Dict[str, str]:
        """Get appropriate headers for different services"""
        base_headers = {
            'User-Agent': 'AI-Advertisement-Generator/1.0 (Trends Integration)',
            'Accept': 'application/json, application/xml, text/xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0'
        }
        
        if service == 'google_trends':
            base_headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            })
            if self.google_trends_api_key:
                base_headers['Authorization'] = f'Bearer {self.google_trends_api_key}'
        
        elif service == 'twitter':
            base_headers['User-Agent'] = 'TrendBot/1.0'
            if self.twitter_bearer_token:
                base_headers['Authorization'] = f'Bearer {self.twitter_bearer_token}'
        
        elif service == 'reddit':
            base_headers['User-Agent'] = 'TrendBot/1.0 (by /u/anonymous)'
            # Reddit uses OAuth2, would need separate auth flow
        
        return base_headers
    
    def is_api_configured(self, service: str) -> bool:
        """Check if API credentials are configured for a service"""
        if service == 'google_trends':
            return self.google_trends_api_key is not None
        elif service == 'twitter':
            return self.twitter_bearer_token is not None
        elif service == 'reddit':
            return self.reddit_client_id is not None and self.reddit_client_secret is not None
        return False

# Global configuration instance
config = TrendsConfig()

# Environment variable documentation
ENV_VARS_DOCUMENTATION = """
# Secure Trends Integration Environment Variables

## Required for enhanced functionality (optional, has fallbacks):

# Google Trends API (if you have official access)
GOOGLE_TRENDS_API_KEY=your_google_trends_api_key_here

# Twitter API v2 (for Twitter trends)
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here

# Reddit API (for Reddit trending topics)
REDDIT_CLIENT_ID=your_reddit_client_id_here
REDDIT_CLIENT_SECRET=your_reddit_client_secret_here

## Configuration (optional, uses defaults):

# Rate limiting
TRENDS_MIN_REQUEST_INTERVAL=60  # seconds between requests
TRENDS_CACHE_DURATION=900       # cache duration in seconds (15 minutes)
TRENDS_MAX_RETRIES=3            # max retries per source
TRENDS_REQUEST_TIMEOUT=15       # request timeout in seconds

# Content filtering
TRENDS_MAX_LENGTH=150           # maximum trend title length
TRENDS_MAX_PER_SOURCE=10        # maximum trends per source

## Usage:
# 1. Copy this to a .env file in your project root
# 2. Replace the placeholder values with actual API keys
# 3. The system will work without API keys using fallback methods
# 4. API keys are recommended for production use for better reliability

## Security Notes:
# - Never commit .env files to version control
# - Use secure methods to deploy environment variables in production
# - API keys should have minimal required permissions
# - Monitor API usage to stay within rate limits
"""

def save_env_template():
    """Save environment variable template to .env.example"""
    try:
        with open('.env.example', 'w') as f:
            f.write(ENV_VARS_DOCUMENTATION)
        print("✅ Created .env.example with API configuration template")
    except Exception as e:
        print(f"❌ Failed to create .env.example: {e}")

if __name__ == "__main__":
    # Create example environment file
    save_env_template()
    
    # Show current configuration
    print("📊 Current Trends Configuration:")
    print(f"   Rate limiting: {config.min_request_interval}s between requests")
    print(f"   Cache duration: {config.cache_duration//60} minutes")
    print(f"   Google Trends API: {'✅ Configured' if config.is_api_configured('google_trends') else '❌ Not configured'}")
    print(f"   Twitter API: {'✅ Configured' if config.is_api_configured('twitter') else '❌ Not configured'}")
    print(f"   Reddit API: {'✅ Configured' if config.is_api_configured('reddit') else '❌ Not configured'}")
    print(f"   Fallback enabled: {'✅' if config.enable_seasonal_fallback else '❌'}")
