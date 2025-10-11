"""
Shared utilities for AI-Adv project
This directory contains shared utilities used across multiple services.
"""

# Import main classes for easy access
from .gpu_memory_manager import GPUMemoryManager, ModelType, get_gpu_manager

__all__ = ['GPUMemoryManager', 'ModelType', 'get_gpu_manager']