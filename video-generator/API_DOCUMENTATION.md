# Video Generator Service

This service generates animated videos from static images using various animation techniques.

## Features

- **Multiple Animation Types**:
  - `zoom_pan`: Smooth zoom and pan effects
  - `ken_burns`: Classic Ken Burns documentary-style effect
  - `parallax`: Multi-layer parallax movement
  - `fade_effects`: Fade in/out with subtle movements

- **Customization Options**:
  - Animation duration (1-30 seconds)
  - Frame rate (15-60 fps)
  - Animation style (smooth, dramatic, gentle, energetic)
  - Text overlays (brand text, main text, CTA)

- **Input Methods**:
  - URL-based image input
  - Direct file upload

## API Endpoints

### POST /generate
Generate video from image URL.

**Request Body:**
```json
{
  "image_url": "http://example.com/image.jpg",
  "animation_type": "zoom_pan",
  "duration": 5,
  "fps": 30,
  "style": "smooth",
  "text_overlay": "Amazing Product",
  "brand_text": "YourBrand",
  "cta_text": "Buy Now!"
}
```

### POST /generate-from-upload
Generate video from uploaded image file.

**Form Data:**
- `file`: Image file
- `animation_type`: Animation type
- `duration`: Duration in seconds
- `fps`: Frames per second
- `style`: Animation style
- `text_overlay`: Main text overlay
- `brand_text`: Brand text
- `cta_text`: Call-to-action text

### GET /download/{filename}
Download generated video file.

### GET /status/{filename}
Check video availability and status.

## Animation Types

1. **zoom_pan**: Creates smooth zoom and pan movements across the image
2. **ken_burns**: Implements the classic Ken Burns effect with slow zoom and pan
3. **parallax**: Creates multi-layered movement effects
4. **fade_effects**: Adds fade in/out effects with subtle movements

## Animation Styles

- **smooth**: Gentle easing curves
- **dramatic**: Strong, impactful movements
- **gentle**: Soft, subtle animations
- **energetic**: Dynamic, bouncy effects

## Technical Details

- **Output Format**: MP4 with H.264 codec
- **Resolution**: 1024x1024 pixels
- **Quality**: High quality encoding
- **File Cleanup**: Videos expire after 15 minutes
- **Dependencies**: OpenCV, Pillow, ImageIO, NumPy

## Usage Examples

### Basic video generation:
```bash
curl -X POST "http://localhost:5003/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "http://image-generator:5001/download/image.png",
    "animation_type": "zoom_pan",
    "duration": 5,
    "fps": 30
  }'
```

### With text overlays:
```bash
curl -X POST "http://localhost:5003/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "http://image-generator:5001/download/image.png",
    "animation_type": "ken_burns",
    "duration": 8,
    "fps": 30,
    "style": "dramatic",
    "brand_text": "YourBrand",
    "text_overlay": "Revolutionary Product",
    "cta_text": "Order Today!"
  }'
```

## Integration

This service integrates with the existing AI Advertisement Generator ecosystem:

1. **Image Generator**: Receives generated images from the image generator service
2. **Orchestrator**: Can be called by the orchestrator for complete ad campaigns
3. **File Management**: Automatic cleanup and expiration handling
4. **Logging**: Comprehensive structured logging for monitoring and debugging