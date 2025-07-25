# Image Generator API Documentation

## Overview
This API generates AI-powered advertising images with automatic cleanup after 10 minutes.

## Endpoints

### 1. Generate Image
**POST** `/generate`

Generates an AI image based on the provided prompt and branding information.

**Request Body:**
```json
{
  "product_name": "string",
  "features": ["string"],
  "brand_text": "string", 
  "cta_text": "string",
  "scene": "string"
}
```

**Response:**
```json
{
  "filename": "uuid.png",
  "download_url": "/download/uuid.png",
  "expires_in_minutes": 10
}
```

### 2. Download Image
**GET** `/download/{filename}`

Downloads the generated image. Images expire after 10 minutes.

**Response:** PNG image file as attachment

**Error Responses:**
- `404`: Image not found or has expired

### 3. Check Image Status
**GET** `/status/{filename}`

Checks if an image is still available and shows remaining time.

**Response:**
```json
{
  "status": "available|expired|not_found|unknown",
  "remaining_minutes": 8.5,
  "download_url": "/download/uuid.png"
}
```

### 4. Health Check
**GET** `/`

Simple health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "image-generator"
}
```

## Features

- **Automatic Cleanup**: Images are automatically deleted after 10 minutes
- **Download Support**: Images can be downloaded as attachments
- **Status Tracking**: Check remaining time before expiration
- **Error Handling**: Proper HTTP status codes for expired/missing images

## Usage Example

1. Generate an image:
```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "product_name": "Smart Phone",
    "features": ["5G", "AI Camera"],
    "brand_text": "TechCorp",
    "cta_text": "Buy Now!",
    "scene": "modern tech office setup"
  }'
```

2. Download the image:
```bash
curl -O "http://localhost:8000/download/uuid.png"
```

3. Check image status:
```bash
curl "http://localhost:8000/status/uuid.png"
```
