"""
Google API Connection Manager - Fixes SSL and connection pool issues
Implements singleton pattern for proper connection reuse and resource management.
"""

import asyncio
import logging
import os
import time
from threading import Lock
from typing import Any, Dict, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import build_http

logger = logging.getLogger(__name__)


class GoogleSlidesConnectionManager:
    """Singleton connection manager for Google Slides API to prevent SSL issues."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._service = None
        self._service_lock = asyncio.Lock()
        self._connection_count = 0
        self._max_connections = 3
        self._initialized = True
        logger.info("GoogleSlidesConnectionManager initialized")

    def _create_service_with_connection_pooling(self):
        """Create Google Slides service with proper HTTP connection pooling and authentication."""
        try:
            # Load service account credentials explicitly
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not credentials_path:
                credentials_path = "./scalapay/scalapay_mcp_kam/credentials.json"

            if not os.path.exists(credentials_path):
                raise Exception(f"Credentials file not found: {credentials_path}")

            # Load credentials from service account file
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/presentations", "https://www.googleapis.com/auth/drive"],
            )
            logger.info(f"Loaded service account credentials from {credentials_path}")

            # Build service with explicit credentials (Google API client handles HTTP internally)
            service = build("slides", "v1", credentials=credentials, cache_discovery=False)
            logger.info("Google Slides service created with connection pooling and explicit authentication")
            return service

        except Exception as e:
            logger.error(f"Failed to create Google Slides service: {e}")
            raise

    async def get_service(self):
        """Get Google Slides service instance with connection management."""
        async with self._service_lock:
            if self._service is None:
                self._service = self._create_service_with_connection_pooling()
            return self._service

    def get_service_sync(self):
        """Synchronous version for compatibility with existing code."""
        if self._service is None:
            self._service = self._create_service_with_connection_pooling()
        return self._service

    async def reset_connection(self):
        """Reset connection pool if issues are detected."""
        async with self._service_lock:
            logger.warning("Resetting Google Slides service connection")
            self._service = None
            self._connection_count = 0

    def reset_connection_sync(self):
        """Synchronous version of reset_connection for use in non-async contexts."""
        logger.warning("Resetting Google Slides service connection (sync)")
        self._service = None
        self._connection_count = 0


class PresentationLockManager:
    """Manages locks per presentation to prevent race conditions."""

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()

    async def acquire_lock(self, presentation_id: str) -> asyncio.Lock:
        """Get or create a lock for the specified presentation."""
        async with self._locks_lock:
            if presentation_id not in self._locks:
                self._locks[presentation_id] = asyncio.Lock()
            return self._locks[presentation_id]

    async def execute_with_lock(self, presentation_id: str, func, *args, **kwargs):
        """Execute function with presentation-specific lock."""
        lock = await self.acquire_lock(presentation_id)
        async with lock:
            return await func(*args, **kwargs)


class BatchOperationCircuitBreaker:
    """Circuit breaker pattern for batch operations to prevent cascading failures."""

    def __init__(self, failure_threshold: int = 2, reset_timeout: int = 30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.success_count_in_half_open = 0
        self._lock = asyncio.Lock()

    async def call_with_circuit_breaker(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            # Check if circuit breaker should transition states
            current_time = time.time()

            if self.state == "OPEN":
                if current_time - self.last_failure_time > self.reset_timeout:
                    logger.info("Circuit breaker transitioning from OPEN to HALF_OPEN")
                    self.state = "HALF_OPEN"
                    self.success_count_in_half_open = 0
                else:
                    logger.warning("Circuit breaker is OPEN - rejecting request")
                    raise Exception("Circuit breaker is OPEN - falling back to sequential processing")

        try:
            # Execute the function
            result = await func(*args, **kwargs)

            # Handle success
            async with self._lock:
                if self.state == "HALF_OPEN":
                    self.success_count_in_half_open += 1
                    if self.success_count_in_half_open >= 2:  # Require 2 successes to fully recover
                        logger.info("Circuit breaker transitioning from HALF_OPEN to CLOSED")
                        self.state = "CLOSED"
                        self.failure_count = 0
                elif self.state == "CLOSED":
                    # Reset failure count on success
                    self.failure_count = 0

            return result

        except Exception as e:
            # Handle failure
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = current_time

                error_msg = str(e).lower()

                # Check for critical errors that should immediately open circuit
                if any(
                    critical_error in error_msg
                    for critical_error in ["ssl", "connection", "timeout", "segmentation", "memory"]
                ):
                    logger.error(f"Critical error detected: {e}")
                    self.failure_count = self.failure_threshold  # Force circuit open

                if self.failure_count >= self.failure_threshold:
                    logger.error(f"Circuit breaker opening after {self.failure_count} failures")
                    self.state = "OPEN"
                elif self.state == "HALF_OPEN":
                    # Failed in half-open, go back to open
                    logger.warning("Circuit breaker failed in HALF_OPEN, returning to OPEN")
                    self.state = "OPEN"

            raise

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state for monitoring."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "time_since_last_failure": time.time() - self.last_failure_time if self.last_failure_time > 0 else 0,
        }


# Global singletons for the application
connection_manager = GoogleSlidesConnectionManager()
presentation_locks = PresentationLockManager()
circuit_breaker = BatchOperationCircuitBreaker()
