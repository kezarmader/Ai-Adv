# Use CUDA 12.3.2 runtime (same as working image-generator)
FROM nvidia/cuda:12.3.2-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# RTX 5090 Blackwell architecture sm_120 support (same as image-generator)
ENV TORCH_CUDA_ARCH_LIST="8.9;9.0"

# Install system dependencies
RUN apt update && apt install -y \
    python3 python3-pip python-is-python3 \
    git wget curl libgl1 libglib2.0-0 && \
    apt clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch nightly with CUDA 12.8 support for RTX 5090 sm_120
RUN pip install --upgrade pip && \
    pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# Copy requirements and install other dependencies (excluding torch)
COPY requirements.txt .
RUN grep -v 'torch' requirements.txt > temp_requirements.txt && \
    pip install -r temp_requirements.txt --no-cache-dir

# Setup HuggingFace cache for AI models (match docker-compose volume)
ENV HF_HOME=/app/.cache/huggingface
RUN mkdir -p $HF_HOME

# Create videos directory with proper permissions
RUN mkdir -p /app/videos && chmod 755 /app/videos

# Copy application code
COPY . .

# Optional debugging flags (same as working image-generator)
ENV CUDA_LAUNCH_BLOCKING=1
ENV TORCH_USE_CUDA_DSA=1

# Expose port
EXPOSE 5003

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5003/ || exit 1

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5003"]
