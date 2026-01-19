"""Ollama parallelism detection and management.

Ollama supports two levels of concurrent processing:
1. OLLAMA_MAX_LOADED_MODELS: Multiple models loaded concurrently (default: 3 * GPUs)
2. OLLAMA_NUM_PARALLEL: Parallel requests per model (default: 4 or 1 based on VRAM)

This module auto-detects Ollama's capacity and provides optimal concurrency settings.

See: https://github.com/ollama/ollama/blob/main/docs/faq.md#how-does-ollama-handle-concurrent-requests
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx


@dataclass(frozen=True, slots=True)
class OllamaCapacity:
    """Detected Ollama server capacity."""
    
    num_parallel: int
    """Max parallel requests per model."""
    
    max_loaded_models: int
    """Max models loaded concurrently."""
    
    has_gpu: bool
    """Whether GPU inference is available."""
    
    total_vram_mb: int
    """Total VRAM in MB (0 if CPU-only)."""
    
    @property
    def effective_concurrency(self) -> int:
        """Total concurrent requests the server can handle.
        
        For single-model use: num_parallel
        For multi-model use: num_parallel * min(max_loaded_models, models_in_use)
        """
        return self.num_parallel * self.max_loaded_models
    
    @property
    def recommended_tasks(self) -> int:
        """Recommended max_parallel_tasks for Naaru.
        
        Conservative: 80% of effective_concurrency to leave headroom.
        """
        return max(4, int(self.effective_concurrency * 0.8))


# Default capacity when detection fails
DEFAULT_CAPACITY = OllamaCapacity(
    num_parallel=4,
    max_loaded_models=3,
    has_gpu=True,
    total_vram_mb=0,
)

# CPU-only capacity (lower parallelism)
CPU_CAPACITY = OllamaCapacity(
    num_parallel=4,
    max_loaded_models=3,
    has_gpu=False,
    total_vram_mb=0,
)


@cache
def get_ollama_env_config() -> dict[str, int | None]:
    """Read Ollama config from environment variables.
    
    Returns:
        Dict with num_parallel, max_loaded_models, max_queue from env
    """
    return {
        "num_parallel": _parse_int_env("OLLAMA_NUM_PARALLEL"),
        "max_loaded_models": _parse_int_env("OLLAMA_MAX_LOADED_MODELS"),
        "max_queue": _parse_int_env("OLLAMA_MAX_QUEUE"),
    }


def _parse_int_env(key: str) -> int | None:
    """Parse integer from environment variable."""
    val = os.environ.get(key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            return None
    return None


async def detect_ollama_capacity(
    base_url: str = "http://localhost:11434",
    timeout: float = 5.0,
) -> OllamaCapacity:
    """Auto-detect Ollama server capacity.
    
    Queries the Ollama API to determine:
    - GPU availability and VRAM
    - Configured parallelism settings
    
    Falls back to environment variables or defaults if detection fails.
    
    Args:
        base_url: Ollama server URL
        timeout: Request timeout in seconds
        
    Returns:
        OllamaCapacity with detected or default values
    """
    import httpx
    
    # Start with environment config
    env_config = get_ollama_env_config()
    num_parallel = env_config.get("num_parallel")
    max_loaded_models = env_config.get("max_loaded_models")
    
    # Try to detect from server
    has_gpu = True
    total_vram_mb = 0
    
    try:
        async with httpx.AsyncClient() as client:
            # Query server info (undocumented but works)
            # Ollama exposes GPU info in model details
            response = await client.get(
                f"{base_url}/api/tags",
                timeout=timeout,
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                
                # Check if any model has GPU details
                for model in models:
                    details = model.get("details", {})
                    # Ollama includes GPU info in some responses
                    if "gpu" in str(details).lower():
                        has_gpu = True
                        break
                
                # Try to get more detailed info from a loaded model
                if models:
                    model_name = models[0].get("name", "")
                    if model_name:
                        info_response = await client.post(
                            f"{base_url}/api/show",
                            json={"name": model_name},
                            timeout=timeout,
                        )
                        if info_response.status_code == 200:
                            # Parse GPU/VRAM info if available
                            pass  # Ollama doesn't expose this directly yet
            
    except Exception:
        # Detection failed, use defaults
        pass
    
    # Apply defaults based on GPU availability
    if num_parallel is None:
        # Ollama default: 4 if sufficient VRAM, else 1
        num_parallel = 4 if has_gpu else 4  # Both default to 4 now
    
    if max_loaded_models is None:
        # Ollama default: 3 * num_gpus, or 3 for CPU
        max_loaded_models = 3
    
    return OllamaCapacity(
        num_parallel=num_parallel,
        max_loaded_models=max_loaded_models,
        has_gpu=has_gpu,
        total_vram_mb=total_vram_mb,
    )


def detect_ollama_capacity_sync(
    base_url: str = "http://localhost:11434",
    timeout: float = 5.0,
) -> OllamaCapacity:
    """Synchronous version of detect_ollama_capacity."""
    try:
        import httpx
        
        env_config = get_ollama_env_config()
        num_parallel = env_config.get("num_parallel")
        max_loaded_models = env_config.get("max_loaded_models")
        
        if num_parallel is not None and max_loaded_models is not None:
            # All config from env, no need to query server
            return OllamaCapacity(
                num_parallel=num_parallel,
                max_loaded_models=max_loaded_models,
                has_gpu=True,
                total_vram_mb=0,
            )
        
        # Quick check if Ollama is running
        response = httpx.get(f"{base_url}/api/tags", timeout=timeout)
        if response.status_code == 200:
            return OllamaCapacity(
                num_parallel=num_parallel or 4,
                max_loaded_models=max_loaded_models or 3,
                has_gpu=True,
                total_vram_mb=0,
            )
    except Exception:
        pass
    
    return DEFAULT_CAPACITY


@dataclass
class OllamaSemaphore:
    """Semaphore for limiting concurrent Ollama requests.
    
    Respects the detected num_parallel limit to avoid overwhelming
    the Ollama server.
    
    Usage:
        sem = OllamaSemaphore.for_capacity(capacity)
        async with sem:
            result = await model.generate(...)
    """
    
    max_concurrent: int
    _semaphore: asyncio.Semaphore = field(init=False)
    
    def __post_init__(self):
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
    
    async def __aenter__(self):
        await self._semaphore.acquire()
        return self
    
    async def __aexit__(self, *args):
        self._semaphore.release()
    
    @classmethod
    def for_capacity(cls, capacity: OllamaCapacity) -> "OllamaSemaphore":
        """Create semaphore based on detected capacity."""
        return cls(max_concurrent=capacity.num_parallel)
    
    @classmethod
    async def auto_detect(
        cls,
        base_url: str = "http://localhost:11434",
    ) -> "OllamaSemaphore":
        """Create semaphore with auto-detected capacity."""
        capacity = await detect_ollama_capacity(base_url)
        return cls.for_capacity(capacity)


# Global semaphore (lazy-initialized)
_global_semaphore: OllamaSemaphore | None = None


async def get_ollama_semaphore(
    base_url: str = "http://localhost:11434",
) -> OllamaSemaphore:
    """Get or create global Ollama semaphore.
    
    The semaphore limits concurrent requests to respect Ollama's
    OLLAMA_NUM_PARALLEL setting.
    """
    global _global_semaphore
    
    if _global_semaphore is None:
        _global_semaphore = await OllamaSemaphore.auto_detect(base_url)
    
    return _global_semaphore


def reset_ollama_semaphore() -> None:
    """Reset global semaphore (for testing or config changes)."""
    global _global_semaphore
    _global_semaphore = None
