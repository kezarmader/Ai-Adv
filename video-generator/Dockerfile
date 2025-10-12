FROM nvidia/cuda:12.3.2-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Install system dependencies
RUN apt update && apt install -y \
    python3 python3-pip python-is-python3 \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libfontconfig1 \
    fonts-dejavu-core \
    git wget curl && \
    apt clean && rm -rf /var/lib/apt/lists/*

# Critical: Set CUDA architecture list to include RTX 5090 (sm_120) 
ENV TORCH_CUDA_ARCH_LIST="8.9;9.0;12.0"

# Copy requirements and install Python dependencies
COPY video-generator/requirements.txt .

# Upgrade pip and install nightly PyTorch with CUDA 12.8 (RTX 5090 support)
RUN pip install --upgrade pip && \
    pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# Install other requirements (excluding torch already installed)
RUN grep -v 'torch' requirements.txt > temp_requirements.txt && \
    pip install -r temp_requirements.txt --no-cache-dir

# Copy shared GPU memory manager
COPY shared/gpu_memory_manager.py .

# Copy application code
COPY video-generator/ .

# Create directories for videos and temp files
RUN mkdir -p /app/videos /app/temp && chmod 755 /app/videos /app/temp

# MEMORY OPTIMIZATION: Configure CUDA memory management for RTX 5090
ENV PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
ENV CUDA_MEMORY_FRACTION=0.8
ENV TORCH_CUDA_MEMORY_FRACTION=0.8

# Optional debugging flags for RTX 5090 troubleshooting
ENV CUDA_LAUNCH_BLOCKING=1
ENV TORCH_USE_CUDA_DSA=1

# Expose port
EXPOSE 5003

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5003"]