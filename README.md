# AI Advertisement Generator

A microservices-based AI application that generates product advertisements using Large Language Models (LLM) and Stable Diffusion image generation. The system automatically creates ad copy and corresponding visuals for products based on user input.

## 🏗️ Architecture

The application consists of 4 microservices:

- **Orchestrator** (Port 8000): Main API that coordinates the entire ad generation workflow
- **LLM Service** (Port 11434): Ollama service running Llama3 for text generation
- **Image Generator** (Port 5001): Stable Diffusion XL service for creating product images
- **Poster Service** (Port 5002): Mock service for posting/publishing generated ads

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
git clone <repository-url>
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
- ✅ LLM Service: `http://localhost:11434`
- ✅ Image Generator: `http://localhost:5001`
- ✅ Poster Service: `http://localhost:5002`

## 📝 Usage

### Generate an Advertisement

Send a POST request to the orchestrator:

```powershell
# Using curl (if available)
curl -X POST "http://localhost:8000/run" `
  -H "Content-Type: application/json" `
  -d '{
    "product": "Wireless Bluetooth Headphones",
    "audience": "fitness enthusiasts",
    "tone": "energetic and motivating",
    "ASIN": "B08N5WRWNW",
    "brand_text": "SoundFit Pro",
    "cta_text": "Get Yours Today!"
  }'
```

Or using PowerShell with Invoke-RestMethod:
```powershell
$body = @{
    product = "Wireless Bluetooth Headphones"
    audience = "fitness enthusiasts"
    tone = "energetic and motivating"
    ASIN = "B08N5WRWNW"
    brand_text = "SoundFit Pro"
    cta_text = "Get Yours Today!"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/run" -Method Post -Body $body -ContentType "application/json"
```

### Expected Response
The API will return a JSON object containing:
- Generated ad copy
- Image URL/path for the generated product image
- Posting status from the poster service

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

### View Real-time Logs
```powershell
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f orchestrator
docker-compose logs -f image-generator
```

### Check Service Health
```powershell
# API health checks
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

## 📄 License

[Add your license information here]

## 🤝 Contributing

[Add contribution guidelines here]

---

**Note**: First startup may take 10-15 minutes due to model downloads (Llama3 ~4GB, Stable Diffusion models ~6GB).
