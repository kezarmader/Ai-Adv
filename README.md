# AI Advertisement Generator

A microservices-based AI application that generates product advertisements using Large Language Models (LLM) and Stable Diffusion image generation. The system automatically creates ad copy and corresponding visuals for products based on user input, with secure temporary image storage and download capabilities.

## 📋 Table of Contents

- [🏗️ Architecture](#️-architecture)
- [⚠️ Privacy & Data Disclaimer](#️-privacy--data-disclaimer)
- [🌐 Live Demo](#-live-demo)
- [🛠️ Prerequisites](#️-prerequisites)
- [🚀 Quick Start](#-quick-start)
- [📝 Usage](#-usage)
- [🔧 Configuration](#-configuration)
- [📊 Monitoring & Logs](#-monitoring--logs)
- [🐛 Troubleshooting](#-troubleshooting)
- [🔄 Development](#-development)
- [📄 License](#-license)

## 🏗️ Architecture

The application consists of 6 microservices with **ASIN-based workflow**:

- **Orchestrator** (Port 8000): Main API that coordinates the entire ad generation workflow and provides download proxies
- **ASIN Extractor** (Port 5004): **NEW** - Extracts Amazon product information from ASIN codes
- **LLM Service** (Port 11434): Ollama service running Llama3 for enhanced text generation with product context
- **Image Generator** (Port 5001): Stable Diffusion XL service for creating AI-enhanced product images
- **Video Generator** (Port 5003): AI-powered video generation with content-aware animation from static images
- **Poster Service** (Port 5002): Mock service for posting/publishing generated ads

### 🔄 ASIN-Based Workflow (5 Steps)
1. **ASIN Input**: Orchestrator receives Amazon ASIN code
2. **Product Extraction**: ASIN Extractor scrapes Amazon product details, features, and images
3. **LLM Enhancement**: Llama3 refines product descriptions with enhanced marketing copy
4. **AI Image Generation**: Stable Diffusion creates professional product images
5. **AI Video Creation**: Advanced video generator creates dynamic animations from static images

## ⚠️ Privacy & Data Disclaimer

**IMPORTANT**: This application processes user inputs to generate advertisements. Please be aware:

- **Do NOT upload or provide any personally identifiable information (PII)** such as names, addresses, phone numbers, email addresses, or any sensitive personal data
- **We do not monitor or filter user inputs** - it is your responsibility to ensure appropriate content
- **Generated images are temporarily stored** and automatically deleted after 10 minutes
- **Use this service responsibly** and in compliance with applicable privacy laws and regulations
- **This is intended for product marketing content only** - avoid any content that could be harmful, inappropriate, or violate terms of service

By using this service, you acknowledge that you understand these limitations and agree to use the service responsibly.

### 🔒 Additional Security Features
- **Request tracking**: Each request has a unique ID for debugging (no personal data stored)
- **Automatic cleanup**: Generated images are deleted after 10 minutes
- **No data persistence**: No user inputs are permanently stored
- **Local processing**: All AI processing happens locally (no data sent to external services)
- **Network isolation**: Services communicate only within Docker network

## 🌐 Live Demo

**Try the service online**: [http://madhouse53.duckdns.org/](http://madhouse53.duckdns.org/)

**⚠️ Availability Notice**: 
- This demo service is subject to server availability
- The server may be offline during maintenance or when not in use
- For guaranteed access, you can rent the machine from [vast.ai](https://vast.ai) using **Machine ID: 37958**

If the demo is unavailable, you can deploy the service locally using the instructions below.

## 🛠️ Prerequisites

### Hardware Requirements
- **NVIDIA GPU** with CUDA support (required for both LLM and image generation)
- **16GB+ VRAM recommended** (both services share GPU memory)
- **16GB+ System RAM**

### Software Requirements
- Docker Desktop with Docker Compose
- NVIDIA Container Toolkit (for GPU support in Docker)
- Windows 10/11 with WSL2 (if on Windows)

## 🚀 Quick Start

### 1. Clone the Repository
```powershell
git clone https://github.com/kezarmader/Ai-Adv.git
cd Ai-Adv
```

### 2. Setup NVIDIA Docker Support
Ensure you have NVIDIA Container Toolkit installed. Verify with:
```powershell
docker run --rm --gpus all nvidia/cuda:11.0.3-base-ubuntu20.04 nvidia-smi
```

### 3. Start All Services
```powershell
docker-compose up --build
```

This command will:
- Build all custom Docker images
- Pull the Ollama image and Llama3 model (first run may take 10-15 minutes)
- Start all services with GPU support
- Set up internal networking between services

### 4. Verify Services are Running
Check that all services are healthy:
```powershell
# Check service status
docker-compose ps

# View logs
docker-compose logs orchestrator
docker-compose logs image-generator
```

You should see:
- ✅ Orchestrator: `http://localhost:8000`
- ✅ ASIN Extractor: `http://localhost:5004` (**NEW**)
- ✅ LLM Service: `http://localhost:11434`
- ✅ Image Generator: `http://localhost:5001`
- ✅ Video Generator: `http://localhost:5003`
- ✅ Poster Service: `http://localhost:5002`

## 📝 Usage

### Generate ASIN-Based Advertisement

Send a POST request to the orchestrator with Amazon ASIN for automatic product analysis:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `asin` | string | Yes | Amazon ASIN code (e.g., "B08N5WRWNW") |
| `generate_video` | boolean | No | Set to `true` to also generate AI-enhanced animated video |
| `video_animation` | string | No | Animation type: `zoom_pan`, `ken_burns`, `parallax`, `fade_effects`, `ai_enhanced` |
| `video_duration` | integer | No | Video duration in seconds (1-30, default: 5) |
| `video_style` | string | No | Animation style: `smooth`, `dramatic`, `gentle`, `energetic`, `dynamic` |

**🎯 ASIN-Based Workflow Benefits:**
- **Automatic Product Analysis**: Extracts title, brand, features, and images from Amazon
- **AI-Enhanced Descriptions**: LLM creates compelling marketing copy from product data
- **Content-Aware Generation**: Images and videos tailored to actual product characteristics
- **Single GPU Optimization**: All AI models share RTX 5090 GPU efficiently

**Example using curl (ASIN-based with image only):**
```powershell
# Basic ASIN-based advertisement generation
curl -X POST "http://localhost:8000/run" `
  -H "Content-Type: application/json" `
  -d '{
    "asin": "B08N5WRWNW"
  }'
```

**Example with AI-enhanced video generation:**
```powershell
# Full ASIN workflow with AI-powered video
curl -X POST "http://localhost:8000/run" `
  -H "Content-Type: application/json" `
  -d '{
    "asin": "B08N5WRWNW",
    "generate_video": true,
    "video_animation": "ai_enhanced",
    "video_duration": 8,
    "video_style": "dynamic"
  }'
```

**Example using PowerShell:**
```powershell
# Simple ASIN-based generation
$body = @{
    asin = "B08N5WRWNW"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/run" -Method Post -Body $body -ContentType "application/json"

# With AI-enhanced video
$bodyWithVideo = @{
    asin = "B08N5WRWNW"
    generate_video = $true
    video_animation = "ai_enhanced"
    video_duration = 10
    video_style = "dynamic"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/run" -Method Post -Body $bodyWithVideo -ContentType "application/json"
```

### Expected Response
The API will return a JSON object containing:
- **ad_text**: Complete generated advertisement with product details, features, and scene description
- **image_url**: Download URL for the generated product image (valid for 10 minutes)
- **video_url**: Download URL for the generated video (if requested, valid for 15 minutes)
- **post_status**: Status from the mock posting service

Example ASIN-based response (with AI-enhanced video):
```json
{
  "ad_text": {
    "product": "Echo Dot (5th Gen, 2022 release) | Smart speaker with bigger vibrant sound",
    "enhanced_description": "Transform your space with Amazon's most advanced Echo Dot featuring premium sound technology...",
    "features": ["Improved bass and clearer vocals", "Built-in Eero wifi", "Temperature sensor", "Alexa voice control"],
    "scene": "A modern living room showcasing the Echo Dot with dynamic lighting and sound visualization",
    "video_scene": "Dynamic zoom sequence highlighting the speaker's premium design with subtle particle effects and audio wave animations",
    "suggested_brand_text": "Amazon Echo",
    "suggested_cta": "Voice Control Everything!"
  },
  "image_url": "http://localhost:8000/download/a1b2c3d4-e5f6-7890-abcd-ef1234567890.png",
  "video_url": "http://localhost:8000/download-video/b2c3d4e5-f6g7-8901-bcde-fg2345678901.mp4",
  "post_status": {"status": "success", "message": "ASIN-based advertisement posted successfully"}
}
```

### Download Generated Content
Images and videos are temporarily stored and can be downloaded using the provided URLs:
```powershell
# Download the generated image
Invoke-WebRequest -Uri "http://localhost:8000/download/[filename].png" -OutFile "advertisement.png"

# Download the generated video (if created)
Invoke-WebRequest -Uri "http://localhost:8000/download-video/[filename].mp4" -OutFile "advertisement.mp4"
```

**Note**: 
- Generated images are automatically deleted after **10 minutes**
- Generated videos are automatically deleted after **15 minutes**
- Files are removed for security and storage management

### Generate Video from Existing Image
You can also create videos from existing images using the dedicated video endpoint:

```powershell
$body = @{
    image_url = "http://localhost:8000/download/existing-image.png"
    animation_type = "zoom_pan"
    duration = 5
    fps = 30
    style = "smooth"
    text_overlay = "Amazing Product"
    brand_text = "YourBrand"
    cta_text = "Buy Now!"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/generate-video" -Method Post -Body $body -ContentType "application/json"
```

### Performance Expectations
Typical response times (varies by hardware):
- **First request**: 60-120 seconds (model loading)
- **Subsequent requests**: 15-30 seconds
- **LLM generation**: 5-15 seconds  
- **Image generation**: 8-20 seconds
- **Image download**: <1 second

Response times depend on GPU performance and available VRAM.

## 🔧 Configuration

### GPU Memory Management
Edit `docker-compose.yml` to adjust GPU memory allocation:

```yaml
environment:
  # Limit Ollama GPU memory
  OLLAMA_MAX_GPU_MEMORY: "8GiB"
  # Optimize PyTorch memory for image generation
  PYTORCH_CUDA_ALLOC_CONF: max_split_size_mb:128
```

### Model Customization
To use a different LLM model, modify the Ollama service entrypoint in `docker-compose.yml`:
```yaml
entrypoint: ["/bin/sh", "-c", "ollama serve & sleep 3 && ollama pull mistral && wait"]
```

## 🛑 Stopping the Application

```powershell
# Stop all services
docker-compose down

# Stop and remove volumes (clears downloaded models)
docker-compose down -v
```

## 📊 Monitoring & Logs

### Structured Logging
All services now include comprehensive structured JSON logging with:
- **Request tracing** with unique IDs across services
- **Performance timing** for each operation 
- **Resource monitoring** (GPU memory, file sizes)
- **Error tracking** with detailed context
- **Security-conscious logging** (no PII in logs)

### View Real-time Logs
```powershell
# All services with structured output
docker-compose logs -f

# Specific service with filtering
docker-compose logs -f orchestrator
docker-compose logs -f image-generator

# Error monitoring
docker-compose logs -f | Select-String '"level":"ERROR"'

# Performance analysis (requests >10 seconds)
docker-compose logs | Select-String '"duration_ms":[0-9]{5,}'
```

### Log Management
For production deployments, consider log rotation:
```yaml
# Add to docker-compose.yml
services:
  orchestrator:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Performance Metrics
- **Ad Generation Pipeline**: Complete timing from request to response
- **Image Generation**: Base generation, refinement, and overlay timing
- **GPU Usage**: Memory allocation tracking for optimization
- **File Operations**: Image sizes and cleanup events

### Request Tracing
Each request gets a unique ID that follows the complete workflow:
```
Orchestrator → LLM Service → Image Generator → Poster Service
```

For detailed logging documentation, see **[LOGGING.md](LOGGING.md)**

### Check Service Health
```powershell
# Quick health check script
.\health_check.ps1

# Detailed health check with log analysis
.\health_check.ps1 -Detailed

# Continuous monitoring (updates every 30 seconds)
.\health_check.ps1 -Monitor

# API health checks (manual)
Invoke-RestMethod -Uri "http://localhost:8000/docs"  # FastAPI docs
Invoke-RestMethod -Uri "http://localhost:11434/api/tags"  # Ollama models
```

## 🐛 Troubleshooting

### Common Issues

1. **GPU Not Detected**
   ```
   Error: NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver
   ```
   - Ensure NVIDIA drivers are installed
   - Verify NVIDIA Container Toolkit is properly configured

2. **Out of Memory Errors**
   ```
   CUDA out of memory
   ```
   - Reduce GPU memory allocation in docker-compose.yml
   - Close other GPU-intensive applications

3. **Model Download Fails**
   ```
   Error pulling model
   ```
   - Check internet connection
   - Restart the llm-service: `docker-compose restart llm-service`

4. **Service Won't Start**
   ```
   Port already in use
   ```
   - Check for conflicting services: `netstat -ano | findstr :8000`
   - Modify port mappings in docker-compose.yml

5. **Image Download Fails**
   ```
   Image not found or has expired
   ```
   - Images are automatically deleted after 10 minutes
   - Regenerate the advertisement to get a new download link
   - Check if the filename in the URL is correct

6. **High Response Times**
   ```
   Requests taking longer than expected
   ```
   - Check individual operation timing: `docker-compose logs orchestrator | Select-String "duration_ms"`
   - Monitor GPU memory usage: `docker-compose logs image-generator | Select-String "memory_allocated_mb"`
   - Consider scaling or optimizing resource allocation

7. **Service Errors in Logs**
   ```
   Multiple ERROR level messages
   ```
   - View recent errors: `docker-compose logs | Select-String '"level":"ERROR"' | Select-Object -Last 10`
   - Check service health: `Invoke-RestMethod -Uri "http://localhost:8000/docs"`
   - Review resource usage and restart services if needed

8. **Permission Errors (Windows)**
   ```
   Access denied or file in use errors
   ```
   - Run PowerShell as Administrator
   - Ensure Docker Desktop is running with proper permissions
   - Check Windows Defender or antivirus interference

9. **Network Connectivity Issues**
   ```
   Services can't communicate
   ```
   - Verify Docker network: `docker network ls`
   - Check firewall settings
   - Restart Docker Desktop if needed

### Debug Mode
Enable verbose logging by adding to service environment:
```yaml
environment:
  - DEBUG=1
  - LOG_LEVEL=debug
```

## 🔄 Development

### Local Development
For development without Docker:

1. **Setup Python Environment** (each service):
   ```powershell
   cd orchestrator
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Run Services Individually**:
   ```powershell
   # Orchestrator
   cd orchestrator
   uvicorn app:app --host 0.0.0.0 --port 8000

   # Image Generator (requires CUDA)
   cd image-generator
   uvicorn app:app --host 0.0.0.0 --port 5001
   ```

### API Documentation
Once running, visit:
- Orchestrator API docs: http://localhost:8000/docs
- Image Generator API docs: http://localhost:5001/docs
- Poster Service API docs: http://localhost:5002/docs

#### Key Endpoints
- **POST /run**: Generate complete advertisement (copy + image + optional video)
- **POST /generate-video**: **NEW** - Generate video from existing image URL
- **GET /download/{filename}**: Download generated images (expires in 10 minutes)
- **GET /download-video/{filename}**: **NEW** - Download generated videos (expires in 15 minutes)

## � Quick Reference

### Essential Commands
```powershell
# Start services
docker-compose up --build

# Check status
.\health_check.ps1

# View logs
docker-compose logs -f

# Stop services  
docker-compose down

# Clean restart
docker-compose down -v && docker-compose up --build
```

### Service URLs
- **Main API**: http://localhost:8000 (see /docs for API documentation)
- **ASIN Extractor**: http://localhost:5004 (see /docs for product extraction)
- **LLM Service**: http://localhost:11434 (Ollama)
- **Image Generator**: http://localhost:5001 (see /docs)
- **Video Generator**: http://localhost:5003 (see /docs)
- **Poster Service**: http://localhost:5002 (see /docs)

### Important Files
- `docker-compose.yml` - Service configuration
- `LOGGING.md` - Detailed logging documentation  
- `health_check.ps1` - Health monitoring script
- `CODE_REVIEW_SUMMARY.md` - Development notes

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### MIT License Summary
- ✅ **Commercial use** - You can use this software commercially
- ✅ **Modification** - You can modify the source code
- ✅ **Distribution** - You can distribute the software
- ✅ **Private use** - You can use this software privately
- ⚠️ **Liability** - The software is provided "as is" without warranty
- ⚠️ **Attribution** - You must include the original license and copyright notice

### Third-Party Components
This project uses several open-source components:
- **FastAPI** (MIT License)
- **Stable Diffusion XL** (CreativeML Open RAIL++-M License)
- **Ollama** (MIT License)
- **Docker** (Apache 2.0 License)
- **PyTorch** (BSD License)

Please review the individual licenses of these components for their specific terms and conditions.

## 🤝 Contributing

We welcome contributions to the AI Advertisement Generator! Here's how you can help:

### 🚀 Ways to Contribute

- **🐛 Bug Reports** - Found a bug? Please open an issue with detailed reproduction steps
- **💡 Feature Requests** - Have an idea? Share it in the issues section
- **📝 Documentation** - Help improve documentation and examples
- **🔧 Code Contributions** - Submit pull requests for bug fixes or new features
- **🧪 Testing** - Help test the application on different hardware configurations
- **🎨 UI/UX** - Improve the API documentation or add web interfaces

### 📋 Development Setup

1. **Fork the repository**
2. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Set up development environment**:
   ```powershell
   # Clone your fork
   git clone https://github.com/your-username/Ai-Adv.git
   cd Ai-Adv
   
   # Install dependencies
   pip install -r orchestrator/requirements.txt
   pip install -r image-generator/requirements.txt
   pip install -r poster-service/requirements.txt
   ```

### 🔧 Coding Standards

- **Python**: Follow PEP 8 style guidelines
- **Logging**: Use structured logging (see `logging_config.py`)
- **Error Handling**: Include proper exception handling with context
- **Documentation**: Add docstrings to functions and classes
- **Testing**: Include tests for new features

### 📝 Pull Request Process

1. **Update documentation** if you're changing functionality
2. **Add tests** for new features or bug fixes
3. **Run the health check**: `.\health_check.ps1` before submitting
4. **Update CHANGELOG.md** with your changes
5. **Submit a pull request** with:
   - Clear description of changes
   - Screenshots/logs if applicable
   - Reference to related issues

### 🐛 Reporting Issues

When reporting bugs, please include:
- **Environment details** (OS, Docker version, GPU model)
- **Error logs** (use `docker-compose logs` output)
- **Steps to reproduce** the issue
- **Expected vs actual behavior**

**Example issue template:**
```markdown
**Bug Description**: Brief description of the issue

**Environment**:
- OS: Windows 11
- Docker Desktop: v4.x.x
- GPU: RTX 4090
- VRAM: 24GB

**Steps to Reproduce**:
1. Start services with `docker-compose up`
2. Send request to /run endpoint
3. Error occurs during image generation

**Error Logs**:
```
[Paste relevant logs here]
```

**Expected Behavior**: What should have happened
**Actual Behavior**: What actually happened
```

### 🏷️ Issue Labels

- `bug` - Something isn't working
- `enhancement` - New feature or request
- `documentation` - Improvements to documentation
- `good first issue` - Good for newcomers
- `help wanted` - Extra attention is needed
- `performance` - Performance improvements
- `security` - Security-related issues

### 🌟 Recognition

Contributors will be recognized in:
- GitHub contributors list
- CHANGELOG.md for significant contributions
- Special thanks in release notes

### 📞 Getting Help

- **General questions**: Open a discussion in GitHub Discussions
- **Bug reports**: Create an issue with the bug template
- **Feature requests**: Create an issue with the feature template
- **Security issues**: Email the maintainers directly

For detailed contribution guidelines, see **[CONTRIBUTING.md](CONTRIBUTING.md)**

### 🔒 Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold this code.

**In summary**: Be respectful, inclusive, and constructive in all interactions.

---

Thank you for contributing to the AI Advertisement Generator! 🎉

---

**Note**: First startup may take 10-15 minutes due to model downloads (Llama3 ~4GB, Stable Diffusion models ~6GB).
