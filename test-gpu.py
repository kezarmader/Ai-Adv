#!/usr/bin/env python3
"""
GPU Test Script for RTX 5090
Tests CUDA availability and PyTorch GPU access
"""

import torch
import sys

def test_cuda():
    print("=== GPU Test Report ===")
    print(f"PyTorch Version: {torch.__version__}")
    
    # Test CUDA availability
    cuda_available = torch.cuda.is_available()
    print(f"CUDA Available: {cuda_available}")
    
    if cuda_available:
        print(f"CUDA Version: {torch.version.cuda}")
        gpu_count = torch.cuda.device_count()
        print(f"GPU Count: {gpu_count}")
        
        for i in range(gpu_count):
            gpu_name = torch.cuda.get_device_name(i)
            gpu_capability = torch.cuda.get_device_capability(i)
            gpu_memory = torch.cuda.get_device_properties(i).total_memory // (1024**3)
            
            print(f"GPU {i}:")
            print(f"  Name: {gpu_name}")
            print(f"  Compute Capability: sm_{gpu_capability[0]}{gpu_capability[1]}")
            print(f"  Memory: {gpu_memory}GB")
            
            # Test tensor creation
            try:
                test_tensor = torch.randn(1000, 1000, device=f'cuda:{i}')
                print(f"  Tensor Creation: SUCCESS")
                
                # Test computation
                result = torch.matmul(test_tensor, test_tensor)
                print(f"  Matrix Multiplication: SUCCESS")
                
            except Exception as e:
                print(f"  GPU Test FAILED: {e}")
                
        return True
    else:
        print("No CUDA GPUs detected")
        print("Possible issues:")
        print("- NVIDIA drivers not installed")
        print("- NVIDIA Container Toolkit not configured")
        print("- Docker GPU runtime not enabled")
        return False

if __name__ == "__main__":
    success = test_cuda()
    sys.exit(0 if success else 1)
