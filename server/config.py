"""
Configuration module for NetServe HTTP Server.
Contains all server configuration constants and settings.
"""

import os
from pathlib import Path
from typing import Dict, List


class Config:
    """Server configuration class."""

    # Server binding
    HOST: str = os.getenv("NETSERVE_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("NETSERVE_PORT", "8080"))

    # Server identity
    SERVER_NAME: str = "NetServe"
    SERVER_VERSION: str = "1.0.0"
    PROTOCOL: str = "HTTP/1.1"

    # Concurrency
    MAX_WORKERS: int = int(os.getenv("NETSERVE_WORKERS", "8"))
    MAX_CONNECTIONS: int = 100

    # Timeouts (seconds)
    CONNECTION_TIMEOUT: float = 30.0
    REQUEST_TIMEOUT: float = 10.0

    # Request limits
    MAX_REQUEST_SIZE: int = 1024 * 1024  # 1 MB
    MAX_HEADER_SIZE: int = 8192          # 8 KB
    MAX_HEADERS: int = 100

    # Directories
    BASE_DIR: Path = Path(__file__).parent.parent
    PUBLIC_DIR: Path = BASE_DIR / "public"
    DASHBOARD_DIR: Path = BASE_DIR / "dashboard"
    LOG_DIR: Path = BASE_DIR / "logs"
    LOG_FILE: Path = LOG_DIR / "server.log"

    INDEX_FILES: List[str] = ["index.html", "index.htm"]

    # MIME types (additional and overrides for Python's mimetypes)
    MIME_TYPES: Dict[str, str] = {
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".eot": "application/vnd.ms-fontobject",
    }

    # Logging format
    LOG_FORMAT: str = "[{timestamp}] {client_ip} {method} {path} {status} {size}B {duration}ms"

    # Security
    ALLOWED_METHODS: List[str] = ["GET", "HEAD"]
    BLOCKED_PATHS: List[str] = ["..", "~", "//"]

    # Dashboard polling
    DASHBOARD_POLL_INTERVAL: int = 2000  # milliseconds
    MAX_RECENT_REQUESTS: int = 100
    MAX_LOG_ENTRIES: int = 1000

    @classmethod
    def validate(cls) -> None:
        """Validate configuration values and create required directories."""
        assert 1 <= cls.PORT <= 65535, "Port must be between 1 and 65535"
        assert cls.MAX_WORKERS > 0, "Max workers must be positive"
        assert cls.CONNECTION_TIMEOUT > 0, "Connection timeout must be positive"
        assert cls.MAX_REQUEST_SIZE > 0, "Max request size must be positive"

        # Ensure directories exist
        cls.PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
        cls.DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)


# Default configuration instance
config = Config()