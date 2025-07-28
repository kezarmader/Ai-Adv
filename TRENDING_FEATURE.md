# 🔥 Secure Google Trends Integration Feature

This document explains the new secure Google Trends integration feature that creates spiced-up advertisements based on current trending topics with multiple data sources and robust security.

## 🆕 New Endpoints

### 1. Get Current Trends
```bash
GET /trends
```
Fetches current trends from multiple secure sources with caching and rate limiting.

### 2. Generate Trending Advertisement  
```bash
POST /run/trending
```
Generates an advertisement incorporating current trends for maximum engagement.

### 3. Debug Trends System
```bash
GET /trends/debug
```
Returns debug information about the trends fetching system.

## 🛡️ Security Features

### Multi-Source Data Fetching
The system uses multiple data sources with fallback mechanisms:

1. **PyTrends Library** - Unofficial Google Trends API
2. **Google Trends RSS** - Direct RSS feed access with authentication
3. **Reddit Trending** - Alternative social media trends
4. **Curated Topics** - Season-based and evergreen trending topics
5. **Fallback Topics** - Safe, positive topics when all sources fail

### Content Filtering
- **Sensitive Topic Detection**: Automatically filters political, violent, or negative content
- **Length Validation**: Ensures trends are reasonable length
- **Character Filtering**: Removes potentially problematic special characters
- **Quality Validation**: Checks trend quality before use

### Rate Limiting & Caching
- **Request Throttling**: Minimum 60-second intervals between external requests
- **Smart Caching**: 15-minute cache to reduce API calls
- **Graceful Degradation**: Falls back to cached or curated content
- **API Respect**: Follows proper rate limiting for external services

## 🔧 Configuration

### Environment Variables (Optional)
```bash
# Google Trends API (if you have official access)
GOOGLE_TRENDS_API_KEY=your_api_key_here

# Twitter API v2 (for Twitter trends)
TWITTER_BEARER_TOKEN=your_bearer_token_here

# Reddit API (for Reddit trending topics)
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here

# Rate limiting settings
TRENDS_MIN_REQUEST_INTERVAL=60    # seconds between requests
TRENDS_CACHE_DURATION=900         # cache duration (15 minutes)
TRENDS_MAX_RETRIES=3              # max retries per source
```

### Automatic Fallbacks
The system works without any API keys by using:
- Curated seasonal topics
- Evergreen positive trends
- Smart fallback mechanisms

**Request Body:**
```json
{
  "product": "Beach Umbrella",
  "audience": "vacation travelers",
  "tone": "excited",
  "ASIN": "B08ABC123",
  "brand_text": "SunShade Pro",
  "cta_text": "Get Summer Ready!"
}
```

**Response:**
```json
{
  "ad_text": {
    "product": "Beach Umbrella Pro",
    "audience": ["vacation travelers", "beach enthusiasts"],
    "tone": "super excited", 
    "description": "This amazing beach umbrella is perfect for the current trend of summer vacation destinations...",
    "features": ["UV Protection", "Wind-resistant", "Instagram-worthy Design"],
    "scene": "A vibrant beach scene with colorful umbrellas and joyful people enjoying summer vacation destinations under golden hour lighting with gentle sparkles in the air",
    "trending_topic": "Summer vacation destinations"
  },
  "image_url": "http://localhost:8000/download/uuid.png",
  "post_status": {"status": "success", "message": "Posted successfully"},
  "trending_data": {
    "original_trend": "Summer vacation destinations",
    "spiced_story": "A vibrant summer vacation destinations adventure...",
    "trending_topic_used": "Summer vacation destinations"
  }
}
```

## 🎯 How It Works

1. **Trend Fetching**: The system fetches top 5 trending topics from Google Trends RSS feed
2. **Content Filtering**: Automatically filters out sensitive/political topics
3. **Story Spicing**: Creates engaging, positive stories using trending topics
4. **LLM Enhancement**: The LLM incorporates trending context into ad copy
5. **Image Boosting**: The image generator applies trending visual effects

## ✨ Key Features

- **Automatic Trend Detection**: Fetches real-time Google Trends
- **Smart Filtering**: Avoids political, sensitive, or negative topics
- **Spiced Storytelling**: Transforms trends into engaging visual stories
- **Enhanced Visuals**: Trending mode uses enhanced image generation parameters
- **Fallback System**: Uses predefined happy topics if Google Trends unavailable

## 🎨 Trending Mode Enhancements

When `trending_boost: true` is set, the image generator applies:
- **Higher guidance scale** (8.0 vs 7.5) for more vibrant images
- **More inference steps** (45 vs 40) for better quality
- **Enhanced refinement** (0.4 strength vs 0.3) for dramatic effect
- **Trending effects**: Dynamic composition, vibrant colors, social media appeal

## 📊 Usage Examples

### PowerShell Examples

```powershell
# Check current trends
Invoke-RestMethod -Uri "http://localhost:8000/trends" -Method GET

# Generate trending ad
$body = @{
    product = "Fitness Tracker"
    audience = "health enthusiasts"
    tone = "motivational"
    brand_text = "FitLife"
    cta_text = "Start Your Journey!"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/run/trending" -Method POST -Body $body -ContentType "application/json"
```

### cURL Examples

```bash
# Check current trends
curl -X GET "http://localhost:8000/trends"

# Generate trending ad
curl -X POST "http://localhost:8000/run/trending" \
  -H "Content-Type: application/json" \
  -d '{
    "product": "Smart Home Device",
    "audience": "tech enthusiasts", 
    "tone": "exciting",
    "brand_text": "TechHome",
    "cta_text": "Upgrade Now!"
  }'
```

## 🔧 Configuration

The trending feature includes several configuration options:

### Trend Modifiers
- vibrant, colorful, joyful, exciting, magical, whimsical
- fantastic, amazing, spectacular, delightful, cheerful, bright

### Story Templates
- "A {modifier} scene featuring {topic} with sparkling effects"
- "An enchanting {topic} adventure in a {modifier} wonderland" 
- "A festive celebration of {topic} with {modifier} decorations"

### Visual Effects (Trending Mode)
- Dynamic composition, eye-catching effects, social media worthy
- Trending aesthetic, modern style, engaging visual elements
- Contemporary design, viral marketing appeal

## 🛡️ Safety Features

- **Content Filtering**: Automatically excludes sensitive topics
- **Fallback System**: Uses safe topics if trends unavailable
- **Positive Focus**: Only uses happy, fun, engaging trends
- **Error Handling**: Graceful degradation if Google Trends fails

## 📈 Benefits

1. **Higher Engagement**: Ads incorporate current popular topics
2. **Viral Potential**: Uses trending themes for social media appeal
3. **Relevance**: Always current with what people are talking about  
4. **Visual Impact**: Enhanced image generation for trending content
5. **Automatic Updates**: No manual trend research needed

## 🚀 Getting Started

1. Start the services: `docker-compose up --build`
2. Test trends endpoint: `http://localhost:8000/trends`
3. Generate trending ad: `http://localhost:8000/run/trending`
4. Use the test script: `python test_trending_feature.py`

## 🔍 Monitoring

Check logs for trending activity:
```bash
# View trending-specific logs
docker-compose logs orchestrator | Select-String "trending"

# Monitor trends fetching
docker-compose logs orchestrator | Select-String "Trending story generated"
```

The trending feature is designed to make your advertisements more engaging by automatically incorporating current popular topics while maintaining brand safety and visual appeal.
