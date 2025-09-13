"""
Concurrency utilities for optimizing MCP tool interactions and chart generation.
Provides batching, rate limiting, and resource management for concurrent operations.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ConcurrencyMetrics:
    """Metrics for tracking concurrent operation performance."""

    total_processing_time: float = 0.0
    data_retrieval_time: float = 0.0
    chart_generation_time: float = 0.0
    concurrent_operations_count: int = 0
    context_tokens_used: int = 0
    error_count_by_type: Dict[str, int] = None
    resource_utilization: Dict[str, float] = None

    def __post_init__(self):
        if self.error_count_by_type is None:
            self.error_count_by_type = {}
        if self.resource_utilization is None:
            self.resource_utilization = {}


class ConcurrencyManager:
    """Manages concurrent operations with rate limiting and resource pooling."""

    def __init__(
        self, max_concurrent_operations: int = 3, batch_size: int = 3, retry_attempts: int = 2, retry_delay: float = 1.0
    ):
        self.semaphore = asyncio.Semaphore(max_concurrent_operations)
        self.batch_size = batch_size
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.metrics = ConcurrencyMetrics()
        self._operation_start_time = None

    def create_batches(self, items: List[Any]) -> List[List[Any]]:
        """Create batches from a list of items."""
        return [items[i : i + self.batch_size] for i in range(0, len(items), self.batch_size)]

    async def execute_with_semaphore(
        self, operation: Callable, *args, operation_name: str = "operation", **kwargs
    ) -> Any:
        """Execute operation with semaphore-based rate limiting."""
        async with self.semaphore:
            start_time = time.time()
            try:
                logger.debug(f"Starting {operation_name}")
                result = await operation(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.debug(f"Completed {operation_name} in {execution_time:.2f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                error_type = type(e).__name__
                self.metrics.error_count_by_type[error_type] = self.metrics.error_count_by_type.get(error_type, 0) + 1
                logger.error(f"Failed {operation_name} after {execution_time:.2f}s: {e}")
                raise

    async def execute_with_retry(self, operation: Callable, *args, operation_name: str = "operation", **kwargs) -> Any:
        """Execute operation with retry logic."""
        last_exception = None

        for attempt in range(self.retry_attempts + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying {operation_name}, attempt {attempt + 1}")
                    await asyncio.sleep(self.retry_delay * attempt)

                return await self.execute_with_semaphore(operation, *args, operation_name=operation_name, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.retry_attempts:
                    logger.warning(f"Attempt {attempt + 1} failed for {operation_name}: {e}")
                else:
                    logger.error(f"All {self.retry_attempts + 1} attempts failed for {operation_name}: {e}")

        raise last_exception

    def start_timing(self):
        """Start timing for the overall operation."""
        self._operation_start_time = time.time()

    def end_timing(self):
        """End timing and update metrics."""
        if self._operation_start_time:
            self.metrics.total_processing_time = time.time() - self._operation_start_time

    def log_metrics(self):
        """Log performance metrics."""
        logger.info("=== Concurrency Metrics ===")
        logger.info(f"Total processing time: {self.metrics.total_processing_time:.2f}s")
        logger.info(f"Concurrent operations: {self.metrics.concurrent_operations_count}")
        logger.info(f"Context tokens used: {self.metrics.context_tokens_used}")
        if self.metrics.error_count_by_type:
            logger.info(f"Errors by type: {self.metrics.error_count_by_type}")
        logger.info("=========================")


async def gather_with_concurrency_limit(
    tasks: List[Callable], max_concurrent: int = 3, return_exceptions: bool = True
) -> List[Any]:
    """
    Execute tasks with concurrency limit using semaphore.

    Args:
        tasks: List of async callables to execute
        max_concurrent: Maximum number of concurrent operations
        return_exceptions: Whether to return exceptions instead of raising

    Returns:
        List of results from task execution
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def limited_task(task):
        async with semaphore:
            return await task()

    return await asyncio.gather(*[limited_task(task) for task in tasks], return_exceptions=return_exceptions)


def create_correlation_id() -> str:
    """Create a correlation ID for tracking concurrent operations."""
    return f"concurrent_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}"


class ResourcePool:
    """Resource pool for managing MCP clients and connections."""

    def __init__(self, max_resources: int = 5):
        self.max_resources = max_resources
        self._available_resources = asyncio.Queue(maxsize=max_resources)
        self._in_use = set()
        self._created_count = 0

    async def acquire(self, resource_factory: Callable) -> Any:
        """Acquire a resource from the pool or create a new one."""
        try:
            # Try to get an existing resource
            resource = self._available_resources.get_nowait()
            self._in_use.add(resource)
            return resource
        except asyncio.QueueEmpty:
            # Create new resource if under limit
            if self._created_count < self.max_resources:
                resource = await resource_factory()
                self._created_count += 1
                self._in_use.add(resource)
                return resource
            else:
                # Wait for a resource to become available
                resource = await self._available_resources.get()
                self._in_use.add(resource)
                return resource

    async def release(self, resource: Any):
        """Release a resource back to the pool."""
        if resource in self._in_use:
            self._in_use.remove(resource)
            await self._available_resources.put(resource)

    async def cleanup(self):
        """Clean up all resources in the pool."""
        while not self._available_resources.empty():
            try:
                resource = self._available_resources.get_nowait()
                # Cleanup logic for specific resource types can be added here
                del resource
            except asyncio.QueueEmpty:
                break
        self._created_count = 0
        self._in_use.clear()


def log_concurrent_operation(operation_name: str, correlation_id: str = None):
    """Decorator for logging concurrent operations."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            corr_id = correlation_id or create_correlation_id()
            start_time = time.time()

            logger.info(f"[{corr_id}] Starting {operation_name}")
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"[{corr_id}] Completed {operation_name} in {execution_time:.2f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"[{corr_id}] Failed {operation_name} after {execution_time:.2f}s: {e}")
                raise

        return wrapper

    return decorator
