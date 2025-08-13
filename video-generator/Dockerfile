# Use latest NVIDIA CUDA runtime that supports RTX 5090 Blackwell architecture
# Using CUDA 13.0.0 as it's the latest available with RTX 5090 support
FROM nvidia/cuda:13.0.0-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# RTX 5090 Blackwell architecture requires CUDA 12.8+ (confirmed by PyTorch maintainers)
# See: https://github.com/pytorch/pytorch/issues/151448 and #159207
ENV TORCH_CUDA_ARCH_LIST="8.9;9.0;12.0"

# Install system dependencies for AI models
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python-is-python3 \
    ffmpeg \
    git \
    wget \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && apt clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch with CUDA 13.0+ support for RTX 5090 Blackwell architecture
# Using cu128 wheels as they're compatible with CUDA 13.0 and support sm_120
# Official fix per PyTorch maintainer @malfet: CUDA-12.1 do not support 5090, use 12.8+
RUN pip install --upgrade pip && \
    pip install torch==2.7.1+cu128 torchvision==0.22.1+cu128 torchaudio==0.17.1+cu128 \
    --index-url https://download.pytorch.org/whl/cu128

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

# Remove debugging flags - RTX 5090 issue is resolved with proper CUDA 12.8+ version
# These were causing performance issues and are no longer needed

# Expose port
EXPOSE 5003

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5003/ || exit 1

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5003"]
