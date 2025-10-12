"""
Centralized GPU Memory Manager
Handles dynamic loading/offloading of LLM, Image, and Video models based on available GPU memory
"""

import logging
import requests
import torch
import gc
import time
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

class ModelType(Enum):
    LLM = "llm"
    IMAGE = "image"
    VIDEO = "video"

@dataclass
class ModelInfo:
    model_type: ModelType
    service_name: str
    offload_endpoint: str
    reload_endpoint: str
    estimated_memory_gb: float
    priority: int  # Higher number = higher priority (kept longer)
    is_loaded: bool = False
    last_used: float = 0.0

class GPUMemoryManager:
    """Intelligent GPU Memory Manager for multi-model coordination"""
    
    def __init__(self, logger: logging.Logger, memory_threshold_gb: float = 28.0):
        self.logger = logger
        self.memory_threshold_gb = memory_threshold_gb  # Trigger offload when above this
        self.models: Dict[ModelType, ModelInfo] = {}
        self.setup_models()
    
    def setup_models(self):
        """Initialize model configurations"""
        self.models = {
            ModelType.LLM: ModelInfo(
                model_type=ModelType.LLM,
                service_name="llm-service",
                offload_endpoint="http://llm-service:11434/api/offload",
                reload_endpoint="http://llm-service:11434/api/load",  # May not exist
                estimated_memory_gb=8.0,
                priority=1,  # Lowest priority
                is_loaded=True  # Assume loaded initially
            ),
            ModelType.IMAGE: ModelInfo(
                model_type=ModelType.IMAGE,
                service_name="image-generator",
                offload_endpoint="http://image-generator:5001/offload-to-cpu",
                reload_endpoint="http://image-generator:5001/reload-to-gpu",
                estimated_memory_gb=16.0,
                priority=2,  # Medium priority
                is_loaded=True  # Assume loaded initially
            ),
            ModelType.VIDEO: ModelInfo(
                model_type=ModelType.VIDEO,
                service_name="video-generator",
                offload_endpoint="http://video-generator:5003/offload-svd",
                reload_endpoint="http://video-generator:5003/load-svd",  # We'll need to create this
                estimated_memory_gb=12.0,
                priority=3,  # Highest priority
                is_loaded=False  # Loaded on demand
            )
        }
    
    def get_gpu_memory_info(self) -> Tuple[float, float, float]:
        """Get current GPU memory usage in GB"""
        try:
            if torch.cuda.is_available():
                memory_allocated = torch.cuda.memory_allocated() / (1024**3)
                memory_reserved = torch.cuda.memory_reserved() / (1024**3)
                total_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                memory_free = total_memory - memory_allocated  # Use allocated, not reserved
                return memory_allocated, memory_reserved, memory_free
            return 0.0, 0.0, 32.0  # Default for RTX 5090
        except Exception as e:
            self.logger.warning(f"Could not get GPU memory info: {e}")
            return 0.0, 0.0, 32.0
    
    def notify_model_loaded(self, model_type: ModelType):
        """Notify the GPU manager that a model has been loaded by the service"""
        model_info = self.models.get(model_type)
        if model_info:
            model_info.is_loaded = True
            model_info.last_used = time.time()
            self.logger.info(f"Model {model_type.value} marked as loaded")
    
    def notify_model_offloaded(self, model_type: ModelType):
        """Notify the GPU manager that a model has been offloaded by the service"""
        model_info = self.models.get(model_type)
        if model_info:
            model_info.is_loaded = False
            self.logger.info(f"Model {model_type.value} marked as offloaded")

    def log_memory_status(self, context: str = ""):
        """Log current GPU memory status"""
        allocated, reserved, free = self.get_gpu_memory_info()
        self.logger.info(f"GPU Memory Status {context}", extra={
            "memory_allocated_gb": round(allocated, 2),
            "memory_reserved_gb": round(reserved, 2),
            "memory_free_gb": round(free, 2),
            "models_loaded": [model.model_type.value for model in self.models.values() if model.is_loaded],
            "event": "gpu_memory_status"
        })
    
    def offload_model(self, model_type: ModelType) -> bool:
        """Offload a specific model to CPU"""
        model = self.models.get(model_type)
        if not model or not model.is_loaded:
            return True  # Already offloaded
        
        try:
            self.logger.info(f"Offloading {model_type.value} model to CPU")
            response = requests.post(model.offload_endpoint, timeout=30)
            
            if response.status_code == 200:
                model.is_loaded = False
                self.logger.info(f"{model_type.value} model offloaded successfully")
                return True
            elif response.status_code == 404:
                self.logger.warning(f"{model_type.value} offload endpoint not implemented")
                return False
            else:
                self.logger.warning(f"{model_type.value} offload failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Could not reach {model_type.value} service for offloading: {e}")
            return False
        except Exception as e:
            self.logger.warning(f"Could not offload {model_type.value} model: {e}")
            return False
    
    def load_model(self, model_type: ModelType) -> bool:
        """Load a specific model to GPU"""
        model = self.models.get(model_type)
        if not model or model.is_loaded:
            return True  # Already loaded
        
        try:
            self.logger.info(f"Loading {model_type.value} model to GPU")
            response = requests.post(model.reload_endpoint, timeout=30)
            
            if response.status_code == 200:
                model.is_loaded = True
                model.last_used = time.time()
                self.logger.info(f"{model_type.value} model loaded successfully")
                return True
            elif response.status_code == 404:
                self.logger.warning(f"{model_type.value} load endpoint not implemented, assuming manual loading")
                return True  # Assume it will be loaded manually
            else:
                self.logger.warning(f"{model_type.value} load failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Could not reach {model_type.value} service for loading: {e}")
            return True  # Assume manual loading
        except Exception as e:
            self.logger.warning(f"Could not load {model_type.value} model: {e}")
            return False
    
    def free_gpu_memory(self):
        """Clear GPU cache and run garbage collection"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        gc.collect()
    
    def get_models_to_offload(self, requesting_model: ModelType, required_memory_gb: float) -> List[ModelType]:
        """Determine which models to offload to make space"""
        _, reserved, free = self.get_gpu_memory_info()
        
        # If we have enough free memory, no need to offload
        if free >= required_memory_gb:
            self.logger.info(f"Sufficient memory available ({free:.1f}GB free, {required_memory_gb:.1f}GB needed)")
            return []
        
        # Calculate total memory needed to free
        memory_to_free = required_memory_gb - free + 2.0  # 2GB buffer
        
        # Get loaded models sorted by priority (lowest first) and last used time
        loaded_models = [
            (model_type, model) for model_type, model in self.models.items() 
            if model.is_loaded and model_type != requesting_model
        ]
        
        # Sort by priority (ascending) then by last_used (ascending - oldest first)
        loaded_models.sort(key=lambda x: (x[1].priority, x[1].last_used))
        
        models_to_offload = []
        memory_freed = 0.0
        
        for model_type, model in loaded_models:
            if memory_freed >= memory_to_free:
                break
            models_to_offload.append(model_type)
            memory_freed += model.estimated_memory_gb
            
        self.logger.info(f"Planning to offload models for {requesting_model.value}", extra={
            "models_to_offload": [m.value for m in models_to_offload],
            "memory_to_free_gb": round(memory_to_free, 2),
            "estimated_memory_freed_gb": round(memory_freed, 2)
        })
        
        return models_to_offload
    
    def ensure_gpu_space(self, requesting_model: ModelType, required_memory_gb: Optional[float] = None) -> bool:
        """Ensure sufficient GPU space for a model, offloading others if necessary"""
        
        # Use estimated memory if not provided
        if required_memory_gb is None:
            model_info = self.models.get(requesting_model)
            required_memory_gb = model_info.estimated_memory_gb if model_info else 8.0
        
        self.log_memory_status(f"before {requesting_model.value} load")
        
        # Get models that need to be offloaded
        models_to_offload = self.get_models_to_offload(requesting_model, required_memory_gb)
        
        # Offload models in order
        for model_type in models_to_offload:
            success = self.offload_model(model_type)
            if success:
                self.free_gpu_memory()
                time.sleep(1)  # Brief pause for memory cleanup
            else:
                self.logger.warning(f"Failed to offload {model_type.value}, continuing anyway")
        
        # Update last used time for requesting model
        if requesting_model in self.models:
            self.models[requesting_model].last_used = time.time()
        
        self.log_memory_status(f"after offloading for {requesting_model.value}")
        return True
    
    def request_model_access(self, requesting_model: ModelType, required_memory_gb: Optional[float] = None) -> bool:
        """Request access to a model, handling all necessary offloading and loading"""
        
        self.logger.info(f"Requesting access to {requesting_model.value} model")
        
        # Ensure GPU space by offloading other models
        self.ensure_gpu_space(requesting_model, required_memory_gb)
        
        # For VIDEO model, don't auto-load via HTTP - let the service handle it
        # This prevents double-loading conflicts
        if requesting_model == ModelType.VIDEO:
            self.logger.info("GPU space prepared for video model - service will handle loading")
        else:
            # Load the requesting model if not already loaded
            model_info = self.models.get(requesting_model)
            if model_info and not model_info.is_loaded:
                success = self.load_model(requesting_model)
                if not success:
                    self.logger.error(f"Failed to load {requesting_model.value} model")
                    return False
        
        # Update usage tracking
        model_info = self.models.get(requesting_model)
        if model_info:
            model_info.last_used = time.time()
        
        self.log_memory_status(f"after {requesting_model.value} access granted")
        return True
    
    def release_model_access(self, model_type: ModelType, keep_loaded: bool = True):
        """Release access to a model (update usage tracking, optionally offload)"""
        self.logger.info(f"Releasing access to {model_type.value} model (keep_loaded={keep_loaded})")
        
        if not keep_loaded:
            self.offload_model(model_type)
            self.free_gpu_memory()
        
        # Update last used time
        if model_type in self.models:
            self.models[model_type].last_used = time.time()
    
    def get_status(self) -> Dict:
        """Get current status of all models and GPU memory"""
        allocated, reserved, free = self.get_gpu_memory_info()
        
        return {
            "gpu_memory": {
                "allocated_gb": round(allocated, 2),
                "reserved_gb": round(reserved, 2),
                "free_gb": round(free, 2),
                "threshold_gb": self.memory_threshold_gb
            },
            "models": {
                model_type.value: {
                    "loaded": model.is_loaded,
                    "estimated_memory_gb": model.estimated_memory_gb,
                    "priority": model.priority,
                    "last_used": model.last_used,
                    "service": model.service_name
                }
                for model_type, model in self.models.items()
            }
        }

# Global instance
_gpu_manager: Optional[GPUMemoryManager] = None

def get_gpu_manager(logger: logging.Logger) -> GPUMemoryManager:
    """Get or create the global GPU memory manager instance"""
    global _gpu_manager
    if _gpu_manager is None:
        _gpu_manager = GPUMemoryManager(logger)
    return _gpu_manager