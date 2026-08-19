"""
Logging module for NetServe.
Handles formatted request logging to console (with ANSI colors) and logs/server.log.
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import config


class RequestLogger:
    """Thread-safe request logger for console and persistent log files."""

    def __init__(self, log_file: Optional[Path] = None):
        self.log_file = log_file or config.LOG_FILE
        self._lock = threading.RLock()
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        """Ensure the log directory exists."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_request(self, client_ip: str, method: str, path: str,
                    status_code: int, response_size: int, duration_ms: float) -> None:
        """
        Log an HTTP request to console and log file.

        Args:
            client_ip: Client IP address
            method: HTTP method
            path: Clean request path
            status_code: HTTP status code
            response_size: Response body size in bytes
            duration_ms: Response time in milliseconds
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Format log line
        log_line = config.LOG_FORMAT.format(
            timestamp=timestamp,
            client_ip=client_ip if client_ip else "127.0.0.1",
            method=method,
            path=path,
            status=status_code,
            size=response_size,
            duration=f"{duration_ms:.1f}"
        )

        # Print colorized console output
        self._print_console(log_line, status_code)

        # Append to log file
        self._write_file(log_line)

    def _print_console(self, log_line: str, status_code: int) -> None:
        """Print log line to stdout with color-coded status."""
        if status_code >= 500:
            color = "\033[91m"  # Bright Red
        elif status_code >= 400:
            color = "\033[93m"  # Bright Yellow
        elif status_code >= 300:
            color = "\033[96m"  # Cyan
        else:
            color = "\033[92m"  # Green

        reset = "\033[0m"
        print(f"{color}{log_line}{reset}")

    def _write_file(self, log_line: str) -> None:
        """Write log line to file in a thread-safe manner."""
        with self._lock:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(log_line + "\n")
            except Exception:
                pass

    def get_recent_logs(self, limit: int = 100) -> List[str]:
        """
        Retrieve recent log entries from the server log file.

        Args:
            limit: Maximum number of lines to return

        Returns:
            List of log lines (newest first)
        """
        with self._lock:
            try:
                if not self.log_file.exists():
                    return []
                with open(self.log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                trimmed = [line.strip() for line in lines if line.strip()]
                return list(reversed(trimmed[-limit:]))
            except Exception:
                return []


class ServerLogger:
    """General server event and lifecycle logger."""

    def __init__(self):
        self.start_time = time.time()

    def log_startup(self, host: str, port: int, workers: int) -> None:
        """Log the standard NetServe startup banner."""
        banner = f"""
========================================
           NETSERVE HTTP SERVER
========================================

Host       : {host}
Port       : {port}
Protocol   : {config.PROTOCOL}
Mode       : Development
Workers    : {workers}

Server running at:
http://{host}:{port}

Dashboard:
http://{host}:{port}/dashboard

========================================
"""
        print(banner)

    def log_shutdown(self) -> None:
        """Log server shutdown notification with total uptime."""
        uptime = int(time.time() - self.start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60
        print(f"\n[NetServe] Server shutting down. Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def log_error(self, message: str) -> None:
        """Log server-level error message."""
        print(f"\033[91m[ERROR] {message}\033[0m")

    def log_info(self, message: str) -> None:
        """Log server informational message."""
        print(f"\033[94m[INFO] {message}\033[0m")


# Global singleton loggers
request_logger = RequestLogger()
server_logger = ServerLogger()