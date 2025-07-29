"""
Google Trends Integration Module
Fetches trending topics and creates spiced-up stories for image generation
Uses multiple data sources with fallback mechanisms for reliability
"""
import requests
import random
import logging
from typing import List, Dict, Optional
from datetime import datetime
import re
import json
import time
from bs4 import BeautifulSoup
import asyncio
import aiohttp
from trends_config import config

logger = logging.getLogger(__name__)

class SecureTrendsProcessor:
    """
    Secure trends processor with multiple data sources and authentication handling
    """
    
    def __init__(self):
        self.happy_modifiers = [
            "vibrant", "colorful", "joyful", "exciting", "magical", "whimsical", 
            "fantastic", "amazing", "spectacular", "delightful", "cheerful", "bright"
        ]
        
        self.story_templates = [
            "A {modifier} scene featuring {topic} with sparkling effects and rainbow colors",
            "An enchanting {topic} adventure in a {modifier} wonderland setting",
            "A festive celebration of {topic} with {modifier} decorations everywhere",
            "A {modifier} carnival atmosphere celebrating {topic} with confetti and lights",
            "An uplifting {topic} scene in a {modifier} fairy tale environment"
        ]
        
        # Comprehensive content safety filter - topics to avoid
        self.avoid_keywords = [
            # Violence & Crime
            "war", "violence", "shooting", "murder", "kill", "death", "died", "dead", "suicide",
            "bomb", "explosion", "attack", "terrorism", "terrorist", "assault", "abuse", "rape",
            "kidnap", "torture", "weapon", "gun", "knife", "blood", "stabbing", "beaten",
            
            # Politics & Controversy  
            "politics", "election", "trump", "biden", "republican", "democrat", "vote", "campaign",
            "protest", "scandal", "controversy", "impeach", "coup", "fraud", "corruption",
            
            # Disasters & Tragedies
            "tragedy", "disaster", "crash", "accident", "fire", "flood", "hurricane", "earthquake",
            "pandemic", "covid", "virus", "disease", "illness", "hospital", "emergency",
            
            # Sensitive Topics
            "sexual", "porn", "nude", "naked", "sex", "inappropriate", "offensive", "racist",
            "discrimination", "hate", "extremist", "radical", "banned", "illegal", "drugs",
            
            # News & Current Events (often negative)
            "breaking", "urgent", "alert", "warning", "crisis", "investigation", "arrest",
            "charged", "guilty", "sentence", "prison", "jail", "court", "lawsuit", "trial",
            
            # Additional Safety Terms
            "child", "minor", "kid", "baby", "infant", "teen", "student", "school", "young",
            "victim", "injured", "hurt", "pain", "suffering", "sad", "depression", "anxiety"
        ]
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = config.min_request_interval
        self.cached_trends = None
        self.cache_expiry = 0
        self.cache_duration = config.cache_duration
        
    async def fetch_trends_multi_source(self) -> List[str]:
        """
        Fetch trends from multiple sources with fallback mechanisms
        """
        # Check cache first
        if self._is_cache_valid():
            logger.info("Using cached trends data")
            return self.cached_trends
        
        # Try multiple sources in order of preference
        sources = [
            self._fetch_from_pytrends,
            self._fetch_from_rss_feed,
            self._fetch_from_reddit_trending,
            self._fetch_from_twitter_trends_alternative,
            self._get_curated_trending_topics
        ]
        
        for i, source_func in enumerate(sources, 1):
            try:
                logger.info(f"Attempting source {i}: {source_func.__name__}")
                trends = await source_func()
                
                if trends and len(trends) > 0:
                    # Filter and validate trends with aggressive safety checks
                    filtered_trends = self._filter_and_validate_trends(trends)
                    
                    # FINAL SAFETY CHECK with 3-attempt mechanism
                    final_safe_trends = []
                    safety_attempts = 0
                    max_safety_attempts = 3
                    
                    for trend in filtered_trends:
                        if self._is_sensitive_topic(trend):
                            safety_attempts += 1
                            logger.warning(f"Safety attempt {safety_attempts}: Skipping harmful content, trying next trend: {trend}")
                            
                            # If we've tried 3 harmful trends, stop and use what we have
                            if safety_attempts >= max_safety_attempts:
                                logger.warning(f"Reached {max_safety_attempts} harmful trends, stopping safety checks for this source")
                                break
                            continue
                        final_safe_trends.append(trend)
                    
                    # If we have any safe trends, use them
                    if final_safe_trends and len(final_safe_trends) >= 1:
                        logger.info(f"Source {i} provided {len(final_safe_trends)} SAFE trends after {safety_attempts} safety skips")
                        self._update_cache(final_safe_trends)
                        return final_safe_trends
                    else:
                        if safety_attempts >= max_safety_attempts:
                            logger.error(f"Source {i} failed: too many harmful trends ({safety_attempts} attempts), trying next source")
                        else:
                            logger.warning(f"Source {i} had insufficient safe content, trying next source")
                        continue
                        
            except Exception as e:
                logger.warning(f"Source {source_func.__name__} failed: {str(e)}")
                continue
        
        # All sources failed, use fallback
        logger.warning("All trend sources failed, using SAFE fallback topics")
        fallback_trends = self._get_fallback_trends()
        self._update_cache(fallback_trends)
        return fallback_trends
    
    async def _fetch_from_pytrends(self) -> List[str]:
        """
        Fetch trends using pytrends library (unofficial Google Trends API)
        """
        try:
            from pytrends.request import TrendReq
            
            # Create pytrends request object with proper headers and delays
            pytrends = TrendReq(
                hl='en-US', 
                tz=360,
                timeout=(10, 25),
                retries=2,
                backoff_factor=0.1
            )
            
            # Get trending searches
            trending_searches = pytrends.trending_searches(pn='united_states')
            
            if trending_searches is not None and not trending_searches.empty:
                trends = trending_searches[0].head(10).tolist()  # Get top 10
                logger.info(f"PyTrends returned {len(trends)} trends")
                return trends
            else:
                logger.warning("PyTrends returned empty results")
                return []
                
        except Exception as e:
            logger.error(f"PyTrends failed: {str(e)}")
            raise
    
    async def _fetch_from_rss_feed(self) -> List[str]:
        """
        Fetch from Google Trends RSS with proper authentication handling
        """
        try:
            # Use multiple RSS endpoints
            rss_urls = [
                "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US",
                "https://trends.google.com/trends/hottrends/atom/feed?pn=p1"
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=config.request_timeout),
                headers=config.get_headers('google_trends')
            ) as session:
                
                for url in rss_urls:
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                content = await response.read()
                                
                                # Parse RSS XML
                                soup = BeautifulSoup(content, 'xml')
                                items = soup.find_all('item')
                                
                                trends = []
                                for item in items[:10]:
                                    title = item.find('title')
                                    if title and title.text:
                                        trends.append(title.text.strip())
                                
                                if trends:
                                    logger.info(f"RSS feed returned {len(trends)} trends")
                                    return trends
                                    
                    except Exception as e:
                        logger.warning(f"RSS URL {url} failed: {str(e)}")
                        continue
            
            return []
            
        except Exception as e:
            logger.error(f"RSS feed fetch failed: {str(e)}")
            raise
    
    async def _fetch_from_reddit_trending(self) -> List[str]:
        """
        Fetch trending topics from Reddit as alternative source
        """
        try:
            headers = {
                'User-Agent': 'TrendBot/1.0 (by /u/anonymous)'
            }
            
            # Get trending from multiple subreddits
            subreddits = ['all', 'popular', 'trending']
            trends = []
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers=headers
            ) as session:
                
                for subreddit in subreddits:
                    try:
                        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=10"
                        async with session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                for post in data.get('data', {}).get('children', []):
                                    title = post.get('data', {}).get('title', '')
                                    if title and len(title) < 100:  # Reasonable length
                                        trends.append(title)
                                
                                if len(trends) >= 5:
                                    break
                                    
                    except Exception as e:
                        logger.warning(f"Reddit subreddit {subreddit} failed: {str(e)}")
                        continue
            
            if trends:
                logger.info(f"Reddit returned {len(trends)} trending topics")
                return trends[:10]  # Limit to top 10
            
            return []
            
        except Exception as e:
            logger.error(f"Reddit trending fetch failed: {str(e)}")
            raise
    
    async def _fetch_from_twitter_trends_alternative(self) -> List[str]:
        """
        Fetch trending topics from Twitter-like sources (alternative APIs)
        """
        try:
            # Use trend tracking websites that aggregate social media trends
            trend_apis = [
                "https://api.trendsmap.com/v2/map/trends",  # Example - would need API key
                # Add other trend aggregator APIs here
            ]
            
            # For now, return empty to move to next source
            # In production, implement with proper API keys
            logger.info("Twitter alternative APIs not configured, skipping")
            return []
            
        except Exception as e:
            logger.error(f"Twitter alternative fetch failed: {str(e)}")
            raise
    
    async def _get_curated_trending_topics(self) -> List[str]:
        """
        Get curated trending topics based on current date/season
        """
        try:
            # Get current date info
            now = datetime.now()
            month = now.month
            day = now.day
            
            # Seasonal and date-based trending topics
            seasonal_trends = {
                1: ["New Year resolutions", "Winter sports", "Cozy home decor", "Fitness goals", "Detox recipes"],
                2: ["Valentine's Day gifts", "Winter fashion", "Indoor activities", "Heart-healthy recipes", "Love quotes"],
                3: ["Spring cleaning", "Garden planning", "Easter decorations", "Spring fashion", "Outdoor activities"],
                4: ["Earth Day activities", "Spring flowers", "Outdoor fitness", "Fresh recipes", "Travel planning"],
                5: ["Mother's Day gifts", "Graduation parties", "Summer planning", "Outdoor weddings", "BBQ recipes"],
                6: ["Father's Day gifts", "Summer vacations", "Beach activities", "Outdoor sports", "Pool parties"],
                7: ["Summer festivals", "Independence Day", "Beach fashion", "Outdoor concerts", "Summer recipes"],
                8: ["Back to school", "Summer activities", "Vacation photos", "School supplies", "Family time"],
                9: ["Fall fashion", "Autumn decorations", "School activities", "Harvest festivals", "Comfort food"],
                10: ["Halloween costumes", "Autumn leaves", "Pumpkin recipes", "Fall activities", "Cozy sweaters"],
                11: ["Thanksgiving recipes", "Holiday planning", "Black Friday deals", "Gratitude activities", "Family gatherings"],
                12: ["Christmas gifts", "Holiday decorations", "Winter activities", "Holiday recipes", "Year-end reflection"]
            }
            
            # Get trends for current month
            monthly_trends = seasonal_trends.get(month, seasonal_trends[7])  # Default to July
            
            # Add some evergreen positive trends
            evergreen_trends = [
                "Healthy lifestyle tips",
                "Creative art projects", 
                "Home improvement ideas",
                "Pet care tips",
                "Cooking techniques",
                "Travel destinations",
                "Fitness routines",
                "Photography tips",
                "Music discoveries",
                "Book recommendations"
            ]
            
            # Combine and randomize
            all_trends = monthly_trends + evergreen_trends
            selected_trends = random.sample(all_trends, min(10, len(all_trends)))
            
            logger.info(f"Generated {len(selected_trends)} curated trending topics for month {month}")
            return selected_trends
            
        except Exception as e:
            logger.error(f"Curated topics generation failed: {str(e)}")
            raise
    
    def _filter_and_validate_trends(self, trends: List[str]) -> List[str]:
        """
        Filter out sensitive topics and validate trend quality with aggressive safety filtering
        """
        filtered_trends = []
        
        for trend in trends:
            if not trend or len(trend.strip()) < 3:
                continue
                
            trend_clean = trend.strip()
            
            # Aggressive sensitivity check
            if self._is_sensitive_topic(trend_clean):
                logger.debug(f"Filtered out sensitive topic: {trend_clean}")
                continue
            
            # Check for reasonable length
            if len(trend_clean) > 150:
                logger.debug(f"Filtered out overly long topic: {trend_clean[:50]}...")
                continue
            
            # Check for special characters that might cause issues
            if re.search(r'[<>{}[\]\\|`~]', trend_clean):
                logger.debug(f"Filtered out topic with special characters: {trend_clean}")
                continue
            
            # Additional safety check: reject anything that looks like news
            if self._looks_like_news(trend_clean):
                logger.debug(f"Filtered out news-like topic: {trend_clean}")
                continue
                
            filtered_trends.append(trend_clean)
            
            # Limit to reasonable number
            if len(filtered_trends) >= 15:
                break
        
        # If we filtered out too many trends, add safe fallback topics
        if len(filtered_trends) < 3:
            logger.warning(f"Only {len(filtered_trends)} safe trends found, adding fallback topics")
            safe_fallbacks = self._get_safe_fallback_trends()
            filtered_trends.extend(safe_fallbacks[:5])
        
        return filtered_trends[:10]  # Return top 10 filtered trends
    
    def _looks_like_news(self, topic: str) -> bool:
        """Check if topic looks like a news headline (often negative)"""
        news_patterns = [
            r'^\w+ (says|reports|confirms|denies|announces)',
            r'- [A-Z][a-z]+, [A-Z][A-Z]',  # Location pattern
            r'(investigation|incident|reports|breaking|urgent)',
            r'(arrested|charged|guilty|sentenced)',
            r'\d+ (killed|injured|dead|hurt)'
        ]
        
        for pattern in news_patterns:
            if re.search(pattern, topic, re.IGNORECASE):
                return True
        return False
    
    def _get_safe_fallback_trends(self) -> List[str]:
        """Get guaranteed safe trending topics for advertising"""
        return [
            "Summer outdoor activities",
            "Healthy cooking recipes", 
            "Home garden tips",
            "Pet care advice",
            "Travel destinations",
            "Art and creativity",
            "Music and entertainment",
            "Sports and fitness",
            "Technology gadgets",
            "Fashion trends"
        ]
    
    def _is_cache_valid(self) -> bool:
        """Check if cached trends are still valid"""
        return (
            self.cached_trends is not None and 
            time.time() < self.cache_expiry and 
            len(self.cached_trends) > 0
        )
    
    def _update_cache(self, trends: List[str]):
        """Update trends cache"""
        self.cached_trends = trends
        self.cache_expiry = time.time() + self.cache_duration
        self.last_request_time = time.time()
        logger.info(f"Updated trends cache with {len(trends)} items, expires in {self.cache_duration//60} minutes")
    
    def _respect_rate_limit(self):
        """Ensure we don't make requests too frequently"""
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.info(f"Rate limiting: sleeping for {sleep_time:.1f} seconds")
            time.sleep(sleep_time)
    
    def _is_sensitive_topic(self, topic: str) -> bool:
        """Check if topic contains sensitive keywords with comprehensive filtering"""
        topic_lower = topic.lower()
        
        # Check against avoid keywords
        if any(keyword in topic_lower for keyword in self.avoid_keywords):
            logger.warning(f"Filtered out sensitive topic: {topic}")
            return True
        
        # Additional patterns to catch
        sensitive_patterns = [
            r'\b(kill|murder|death|died|dead)\b',
            r'\b(rape|sexual|abuse)\b', 
            r'\b(trump|biden|president)\b',
            r'\b(shooting|bomb|attack)\b',
            r'\b(child|kid|minor|teen)\b',
            r'\b(crash|accident|tragedy)\b'
        ]
        
        for pattern in sensitive_patterns:
            if re.search(pattern, topic_lower):
                logger.warning(f"Filtered out topic matching pattern '{pattern}': {topic}")
                return True
        
        # Check for news-like formatting (often negative)
        if re.search(r'^[A-Z][a-z]+ (says|reports|confirms|denies)', topic):
            logger.warning(f"Filtered out news-style topic: {topic}")
            return True
            
        # Check for location + negative event pattern
        if re.search(r'- [A-Z][a-z]+, [A-Z][A-Z]', topic) and any(word in topic_lower for word in ['reports', 'investigation', 'incident']):
            logger.warning(f"Filtered out location-based news topic: {topic}")
            return True
            
        return False
    
    def _get_fallback_trends(self) -> List[str]:
        """Fallback trending topics when all sources fail - guaranteed safe content"""
        safe_topics = [
            "Summer vacation destinations",
            "Ice cream flavors and recipes",
            "Pet adoption and care", 
            "Music festivals and concerts",
            "Art exhibitions and galleries",
            "Food trucks and street food",
            "Beach activities and water sports",
            "Garden parties and outdoor dining",
            "Street art and murals",
            "Local farmers markets",
            "Home workout routines",
            "Healthy cooking and nutrition",
            "DIY crafts and hobbies",
            "Photography tips and techniques",
            "Book recommendations and reviews",
            "Coffee shop culture",
            "Hiking trails and nature",
            "Board games and puzzles",
            "Sustainable living tips",
            "Mindfulness and meditation"
        ]
        selected = random.sample(safe_topics, min(10, len(safe_topics)))
        logger.info(f"Using {len(selected)} safe fallback trends")
        return selected
    
    def extract_hook_keywords(self, trend: str) -> List[str]:
        """Extract key hook words from trending topic for visual emphasis - returns safe keywords only"""
        import re
        
        # If trend contains any harmful content, return safe default keywords
        if self._is_sensitive_topic(trend):
            logger.warning(f"Trend contains sensitive content, using safe default keywords instead of extracting: {trend}")
            return ['trending', 'popular', 'viral']
        
        # Clean the trend
        clean_trend = self._clean_trend_title(trend)
        
        # Another safety check on cleaned trend
        if self._is_sensitive_topic(clean_trend):
            logger.warning(f"Cleaned trend contains sensitive content, using safe default keywords: {clean_trend}")
            return ['trending', 'popular', 'viral']
        
        # Split into words and filter
        words = re.findall(r'\b\w+\b', clean_trend.lower())
        
        # Filter out common words AND potentially harmful words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
            # Add safety words to stop list
            'trump', 'biden', 'president', 'rape', 'kill', 'murder', 'death', 'died', 'dead', 'child', 'kid'
        }
        
        # Keep meaningful words (length > 2, not in stop words, not harmful)
        keywords = []
        for word in words:
            if len(word) > 2 and word not in stop_words:
                # Double-check each word for safety
                if not any(harmful in word for harmful in self.avoid_keywords):
                    keywords.append(word)
                else:
                    logger.debug(f"Skipping potentially harmful keyword: {word}")
        
        # If no safe keywords found, return generic safe ones
        if not keywords:
            logger.info("No safe keywords extracted, using default safe keywords")
            return ['trending', 'viral', 'popular']
        
        # Return top 3 most impactful keywords
        return keywords[:3]
    
    def create_spiced_story(self, trends: List[str]) -> Dict[str, str]:
        """Create a spiced-up story from trending topics - try up to 3 safe trends before falling back"""
        try:
            attempts = 0
            max_attempts = 3
            
            # Try each trend until we find a safe one or reach max attempts
            for attempt_trend in trends:
                attempts += 1
                
                # Check if this trend is safe BEFORE processing
                if self._is_sensitive_topic(attempt_trend):
                    logger.info(f"Attempt {attempts}: Skipping sensitive trend, trying next: {attempt_trend}")
                    
                    # If we've tried 3 sensitive trends, break and use fallback
                    if attempts >= max_attempts:
                        logger.warning(f"Failed to find safe trend after {max_attempts} attempts, using fallback")
                        break
                    continue  # Skip to next trend
                
                # This trend is safe, use it
                selected_trend = attempt_trend
                
                # Clean up the trend title
                clean_trend = self._clean_trend_title(selected_trend)
                
                # Double-check cleaned trend is still safe
                if self._is_sensitive_topic(clean_trend):
                    logger.info(f"Attempt {attempts}: Skipping trend after cleaning, trying next: {clean_trend}")
                    
                    # If we've tried 3 trends (including cleaned ones), break and use fallback
                    if attempts >= max_attempts:
                        logger.warning(f"Failed to find safe cleaned trend after {max_attempts} attempts, using fallback")
                        break
                    continue  # Skip to next trend
                
                # We found a safe trend! Create the story
                # Select random modifiers and template
                modifier = random.choice(self.happy_modifiers)
                template = random.choice(self.story_templates)
                
                # Create the spiced story
                spiced_story = template.format(
                    topic=clean_trend,
                    modifier=modifier
                )
                
                # Add extra spice elements
                spice_elements = [
                    "with golden hour lighting",
                    "surrounded by floating balloons",
                    "with gentle sparkles in the air",
                    "in a dreamy pastel color palette",
                    "with soft bokeh effects",
                    "featuring happy people laughing",
                    "with beautiful flowers blooming",
                    "under a clear blue sky",
                    "with warm sunset colors",
                    "featuring vibrant energy",
                    "with magical atmosphere",
                    "in a picture-perfect setting"
                ]
                
                extra_spice = random.choice(spice_elements)
                final_story = f"{spiced_story} {extra_spice}"
                
                logger.info(f"Successfully created spiced story from SAFE trend on attempt {attempts}", extra={
                    "original_trend": selected_trend,
                    "clean_trend": clean_trend,
                    "spiced_story": final_story,
                    "attempts_made": attempts,
                    "safety_verified": True
                })
                
                return {
                    "original_trend": selected_trend,
                    "clean_trend": clean_trend,
                    "spiced_story": final_story,
                    "modifier_used": modifier
                }
            
            # If we get here, all attempts failed or we reached max attempts
            logger.error(f"All {max_attempts} trend attempts were sensitive or failed safety checks, using fallback story")
            return self._get_fallback_story()
            
        except Exception as e:
            logger.error(f"Failed to create spiced story: {str(e)}")
            return self._get_fallback_story()
    
    def _clean_trend_title(self, trend: str) -> str:
        """Clean up trend title for better story integration"""
        # Remove special characters and extra spaces
        clean = re.sub(r'[^\w\s-]', '', trend)
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        # Lowercase for better integration
        return clean.lower()
    
    def _get_fallback_story(self) -> Dict[str, str]:
        """Fallback story when trend processing fails"""
        fallback = {
            "original_trend": "Summer celebration",
            "clean_trend": "summer celebration", 
            "spiced_story": "A vibrant summer celebration with colorful decorations and joyful people dancing under golden hour lighting",
            "modifier_used": "vibrant"
        }
        logger.info("Using fallback story", extra=fallback)
        return fallback

# Global instance with secure processor
trends_processor = SecureTrendsProcessor()

async def get_trending_spiced_story() -> Dict[str, str]:
    """
    Main function to get a spiced story from current trends
    Uses secure multi-source trend fetching with caching and rate limiting
    Implements 3-attempt mechanism for safety verification
    """
    try:
        # Respect rate limiting
        trends_processor._respect_rate_limit()
        
        max_story_attempts = 3
        story_attempt = 0
        
        while story_attempt < max_story_attempts:
            story_attempt += 1
            
            # Fetch current trends from multiple sources
            trends = await trends_processor.fetch_trends_multi_source()
            
            if not trends:
                logger.warning(f"Story attempt {story_attempt}: No trends fetched from any source")
                if story_attempt >= max_story_attempts:
                    logger.error("Failed to fetch trends after 3 attempts, using fallback")
                    return trends_processor._get_fallback_story()
                continue
            
            # Create spiced story with hook keywords (will skip sensitive trends automatically)
            story_data = trends_processor.create_spiced_story(trends)
            
            # Verify the resulting story is safe
            if 'original_trend' in story_data:
                if not trends_processor._is_sensitive_topic(story_data['original_trend']):
                    # Story is safe, add hook keywords
                    story_data['hook_keywords'] = trends_processor.extract_hook_keywords(story_data['original_trend'])
                    
                    logger.info(f"Successfully generated safe trending story on attempt {story_attempt}", extra={
                        "trend_count": len(trends),
                        "story_length": len(story_data.get("spiced_story", "")),
                        "hook_keywords": story_data.get('hook_keywords', []),
                        "cache_used": trends_processor._is_cache_valid(),
                        "attempts_made": story_attempt,
                        "safety_verified": True
                    })
                    
                    return story_data
                else:
                    logger.warning(f"Story attempt {story_attempt}: Generated story contains sensitive content, retrying")
                    if story_attempt >= max_story_attempts:
                        logger.error("All story generation attempts contained sensitive content, using fallback")
                        break
                    continue
            else:
                logger.warning(f"Story attempt {story_attempt}: Story data missing original_trend, retrying")
                if story_attempt >= max_story_attempts:
                    logger.error("All story generation attempts had malformed data, using fallback")
                    break
                continue
        
        # If we get here, all attempts failed
        logger.error("Failed to generate safe trending story after 3 attempts, using fallback")
        return trends_processor._get_fallback_story()
        
    except Exception as e:
        logger.error(f"Error in get_trending_spiced_story: {str(e)}")
        return trends_processor._get_fallback_story()

async def get_trends_debug_info() -> Dict[str, any]:
    """
    Get debugging information about trends fetching
    """
    try:
        cache_valid = trends_processor._is_cache_valid()
        cached_count = len(trends_processor.cached_trends) if trends_processor.cached_trends else 0
        
        return {
            "cache_valid": cache_valid,
            "cached_trends_count": cached_count,
            "cache_expiry": trends_processor.cache_expiry,
            "last_request_time": trends_processor.last_request_time,
            "min_request_interval": trends_processor.min_request_interval,
            "current_time": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting debug info: {str(e)}")
        return {"error": str(e)}
