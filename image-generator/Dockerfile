FROM nvidia/cuda:12.3.2-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Install system dependencies
RUN apt update && apt install -y \
    python3 python3-pip python-is-python3 \
    git wget curl libgl1 libglib2.0-0 && \
    apt clean && rm -rf /var/lib/apt/lists/*

ENV TORCH_CUDA_ARCH_LIST="8.9;9.0"

# Upgrade pip and install nightly PyTorch with CUDA 12.1 (supports sm_90)
RUN pip install --upgrade pip && \
	pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# Install other requirements (excluding torch already installed)
COPY requirements.txt .
RUN grep -v 'torch' requirements.txt > temp_requirements.txt && \
    pip install -r temp_requirements.txt --no-cache-dir

ENV HF_HOME=/app/hf-cache
RUN mkdir -p $HF_HOME

# Create images directory with proper permissions
RUN mkdir -p /app/images && chmod 755 /app/images

COPY . .

# Optional debugging flags
ENV CUDA_LAUNCH_BLOCKING=1
ENV TORCH_USE_CUDA_DSA=1

EXPOSE 5001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5001"]

