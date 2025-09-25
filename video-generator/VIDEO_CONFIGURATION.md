# Video Generator Configuration Examples

This file shows various configuration options for the Video Generator service.

## Basic Video Generation

### Minimal Request
```json
{
  "image_url": "http://localhost:8000/download/image.png"
}
```
**Result**: 5-second zoom_pan video with smooth style at 30fps

### Complete Request
```json
{
  "image_url": "http://localhost:8000/download/image.png",
  "animation_type": "ken_burns",
  "duration": 8,
  "fps": 30,
  "style": "dramatic",
  "text_overlay": "Amazing Product Feature",
  "brand_text": "YourBrand",
  "cta_text": "Buy Now - Limited Time!"
}
```

## Animation Types

### 1. Zoom Pan (zoom_pan)
- **Description**: Smooth zoom and pan movements across the image
- **Best for**: Product showcases, lifestyle content
- **Duration**: 3-10 seconds recommended
- **Styles**: All styles work well

```json
{
  "animation_type": "zoom_pan",
  "style": "smooth",
  "duration": 5
}
```

### 2. Ken Burns Effect (ken_burns)
- **Description**: Classic documentary-style slow zoom with directional pan
- **Best for**: Storytelling, dramatic reveals
- **Duration**: 6-15 seconds recommended
- **Styles**: "dramatic" and "smooth" work best

```json
{
  "animation_type": "ken_burns",
  "style": "dramatic",
  "duration": 8
}
```

### 3. Parallax Effect (parallax)
- **Description**: Multi-layered movement with depth simulation
- **Best for**: Modern, dynamic content
- **Duration**: 4-8 seconds recommended
- **Styles**: "gentle" and "energetic" recommended

```json
{
  "animation_type": "parallax",
  "style": "gentle",
  "duration": 6
}
```

### 4. Fade Effects (fade_effects)
- **Description**: Fade in/out with subtle movements
- **Best for**: Elegant presentations, brand content
- **Duration**: 5-10 seconds recommended
- **Styles**: "smooth" and "gentle" work best

```json
{
  "animation_type": "fade_effects",
  "style": "gentle",
  "duration": 7
}
```

## Animation Styles

### smooth
- **Easing**: Cubic ease-in-out
- **Movement**: Gentle, flowing
- **Best for**: Professional content, products

### dramatic
- **Easing**: Quartic curves with emphasis
- **Movement**: Strong, impactful
- **Best for**: Action products, bold messaging

### gentle
- **Easing**: Sine wave curves
- **Movement**: Soft, subtle
- **Best for**: Luxury products, wellness

### energetic
- **Easing**: Bounce effects
- **Movement**: Dynamic, playful
- **Best for**: Sports, gaming, youth products

## Text Overlay Options

### Text Timing
- **Brand Text**: Visible throughout entire video
- **Main Text Overlay**: Appears after 20% of video duration
- **CTA Text**: Appears after 60% of video duration

### Text Styling
- **Brand Text**: Top-left, white text on black background
- **Main Text**: Center, white text on blue background
- **CTA Text**: Bottom, white text on orange background

### Example with All Text Types
```json
{
  "text_overlay": "Revolutionary Technology",
  "brand_text": "TechCorp",
  "cta_text": "Order Today - Free Shipping!"
}
```

## Technical Specifications

### Video Output
- **Format**: MP4 with H.264 codec
- **Resolution**: 1024x1024 pixels (square format)
- **Quality**: High quality encoding (quality=8)
- **Audio**: No audio track (silent videos)

### Frame Rate Options
- **15 fps**: Lower quality, smaller file size, faster processing
- **24 fps**: Cinematic feel, good balance
- **30 fps**: Smooth motion, recommended default
- **60 fps**: Ultra-smooth, larger files, slower processing

### Duration Limits
- **Minimum**: 1 second
- **Maximum**: 30 seconds
- **Recommended**: 3-10 seconds for web content

## Performance Considerations

### Fast Processing (< 10 seconds)
```json
{
  "animation_type": "zoom_pan",
  "duration": 3,
  "fps": 15,
  "style": "smooth"
}
```

### Balanced Quality/Speed (10-20 seconds)
```json
{
  "animation_type": "ken_burns",
  "duration": 5,
  "fps": 30,
  "style": "dramatic"
}
```

### High Quality (20+ seconds)
```json
{
  "animation_type": "parallax",
  "duration": 8,
  "fps": 60,
  "style": "energetic"
}
```

## Use Case Examples

### Product Showcase
```json
{
  "image_url": "http://localhost:8000/download/product.png",
  "animation_type": "zoom_pan",
  "duration": 5,
  "fps": 30,
  "style": "smooth",
  "brand_text": "Premium Brand",
  "text_overlay": "New Collection",
  "cta_text": "Shop Now"
}
```

### Social Media Post
```json
{
  "image_url": "http://localhost:8000/download/social.png",
  "animation_type": "fade_effects",
  "duration": 4,
  "fps": 30,
  "style": "energetic",
  "text_overlay": "Limited Time Offer!"
}
```

### Brand Story
```json
{
  "image_url": "http://localhost:8000/download/brand.png",
  "animation_type": "ken_burns",
  "duration": 10,
  "fps": 24,
  "style": "dramatic",
  "brand_text": "Our Story",
  "text_overlay": "Crafted with Passion"
}
```

### Quick Demo
```json
{
  "image_url": "http://localhost:8000/download/demo.png",
  "animation_type": "parallax",
  "duration": 3,
  "fps": 30,
  "style": "energetic",
  "text_overlay": "See It In Action"
}
```

## Error Handling

### Common Errors
1. **Image URL not accessible**: Ensure image is available and not expired
2. **Invalid animation type**: Use one of: zoom_pan, ken_burns, parallax, fade_effects
3. **Duration out of range**: Must be between 1-30 seconds
4. **FPS out of range**: Typically 15-60 fps

### Validation
- Image URL must be accessible via HTTP GET
- Duration must be positive integer
- FPS must be positive integer
- Animation type must be from allowed list
- Style must be from allowed list

## Integration Examples

### PowerShell
```powershell
$body = @{
    image_url = "http://localhost:8000/download/image.png"
    animation_type = "zoom_pan"
    duration = 5
    fps = 30
    style = "smooth"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:5003/generate" -Method Post -Body $body -ContentType "application/json"
```

### cURL
```bash
curl -X POST "http://localhost:5003/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "http://localhost:8000/download/image.png",
    "animation_type": "ken_burns",
    "duration": 6,
    "style": "dramatic"
  }'
```

### Python
```python
import requests

response = requests.post('http://localhost:5003/generate', json={
    'image_url': 'http://localhost:8000/download/image.png',
    'animation_type': 'parallax',
    'duration': 5,
    'fps': 30,
    'style': 'energetic',
    'brand_text': 'MyBrand'
})

video_data = response.json()
video_url = video_data['download_url']
```

## File Management

### Automatic Cleanup
- Videos are automatically deleted after 15 minutes
- Cleanup is logged for monitoring
- No manual cleanup required

### Download Window
- Videos must be downloaded within 15 minutes of generation
- Use the provided download URL immediately
- Check video status with GET /status/{filename}

### Storage Optimization
- Temporary files are cleaned during processing
- Only final MP4 files are retained
- Efficient encoding reduces file sizes