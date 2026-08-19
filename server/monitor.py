"""
Network Monitoring module for NetServe.
Tracks server metrics, request distributions, latencies, and traffic telemetry.
"""

import socket
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from .config import config


@dataclass
class RequestRecord:
    """Record of an individual HTTP request for real-time telemetry."""
    timestamp: float
    client_ip: str
    method: str
    path: str
    status_code: int
    response_size: int
    duration_ms: float


class NetworkMonitor:
    """Thread-safe network and server metrics engine using reentrant locks."""

    def __init__(self):
        self._lock = threading.RLock()
        self.start_time = time.time()

        # Cumulative counters
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.not_found_count: int = 0
        self.server_error_count: int = 0
        self.total_bytes_served: int = 0
        self.total_response_time_ms: float = 0.0

        # Request tracking
        self.recent_requests: deque = deque(maxlen=config.MAX_RECENT_REQUESTS)
        self.method_counts: Dict[str, int] = defaultdict(int)
        self.status_counts: Dict[int, int] = defaultdict(int)
        self.route_counts: Dict[str, int] = defaultdict(int)
        self.client_ips: set = set()

        # Active connection tracking
        self.active_connections: int = 0
        self.peak_connections: int = 0

        # Time-series rate tracking (timestamps of requests within last 60 seconds)
        self._request_timestamps: deque = deque(maxlen=2000)

    def record_request(self, record: RequestRecord) -> None:
        """Record a completed request in monitoring metrics."""
        with self._lock:
            self.total_requests += 1
            self.total_bytes_served += record.response_size
            self.total_response_time_ms += record.duration_ms

            if 200 <= record.status_code < 400:
                self.successful_requests += 1
            else:
                self.failed_requests += 1

            if record.status_code == 404:
                self.not_found_count += 1
            elif record.status_code >= 500:
                self.server_error_count += 1

            # Update distributions
            self.method_counts[record.method] += 1
            self.status_counts[record.status_code] += 1
            self.route_counts[record.path] += 1
            if record.client_ip:
                self.client_ips.add(record.client_ip)

            # Store recent request record
            self.recent_requests.append(record)

            # Add timestamp for req/min calculation
            self._request_timestamps.append(record.timestamp)

    def connection_opened(self) -> None:
        """Record a newly accepted client socket connection."""
        with self._lock:
            self.active_connections += 1
            if self.active_connections > self.peak_connections:
                self.peak_connections = self.active_connections

    def connection_closed(self) -> None:
        """Record a closed client socket connection."""
        with self._lock:
            self.active_connections = max(0, self.active_connections - 1)

    def get_uptime(self) -> float:
        """Get server uptime in seconds."""
        return time.time() - self.start_time

    def get_uptime_str(self) -> str:
        """Get formatted uptime string (HH:MM:SS)."""
        uptime = int(self.get_uptime())
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_average_response_time(self) -> float:
        """Get average response time in milliseconds."""
        with self._lock:
            if self.total_requests == 0:
                return 0.0
            return self.total_response_time_ms / self.total_requests

    def get_requests_per_minute(self) -> float:
        """Calculate requests per minute over the last 60-second window."""
        with self._lock:
            now = time.time()
            cutoff = now - 60.0
            # Clean old timestamps
            while self._request_timestamps and self._request_timestamps[0] < cutoff:
                self._request_timestamps.popleft()
            return float(len(self._request_timestamps))

    def get_most_requested_route(self) -> str:
        """Get the most frequently requested route."""
        with self._lock:
            if not self.route_counts:
                return "N/A"
            return max(self.route_counts.items(), key=lambda x: x[1])[0]

    def get_status_distribution(self) -> Dict[str, int]:
        """Get distribution grouped by status classes."""
        with self._lock:
            dist = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
            for code, count in self.status_counts.items():
                if 200 <= code < 300:
                    dist["2xx"] += count
                elif 300 <= code < 400:
                    dist["3xx"] += count
                elif 400 <= code < 500:
                    dist["4xx"] += count
                elif 500 <= code < 600:
                    dist["5xx"] += count
            return dist

    def get_method_distribution(self) -> Dict[str, int]:
        """Get HTTP method distribution."""
        with self._lock:
            return dict(self.method_counts)

    def get_top_routes(self, limit: int = 5) -> List[Dict[str, any]]:
        """Get top requested routes sorted by hit count."""
        with self._lock:
            sorted_routes = sorted(self.route_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            return [{"route": r, "hits": count} for r, count in sorted_routes]

    def get_recent_requests(self, limit: int = 50) -> List[Dict]:
        """Get recent requests formatted for JSON API consumption (most recent first)."""
        with self._lock:
            items = list(self.recent_requests)[-limit:]
            return [
                {
                    "timestamp": datetime.fromtimestamp(r.timestamp).strftime("%H:%M:%S"),
                    "client_ip": r.client_ip,
                    "method": r.method,
                    "path": r.path,
                    "status": r.status_code,
                    "duration_ms": round(r.duration_ms, 2),
                    "size_bytes": r.response_size
                }
                for r in reversed(items)
            ]

    def get_stats_summary(self) -> Dict:
        """Get full statistical summary for API and dashboard."""
        with self._lock:
            avg_resp = round(self.total_response_time_ms / self.total_requests, 2) if self.total_requests > 0 else 0.0
            error_rate = round((self.failed_requests / self.total_requests * 100), 1) if self.total_requests > 0 else 0.0

            return {
                "server": config.SERVER_NAME,
                "version": config.SERVER_VERSION,
                "uptime": self.get_uptime_str(),
                "uptime_seconds": round(self.get_uptime(), 1),
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "error_rate_pct": error_rate,
                "not_found_count": self.not_found_count,
                "server_error_count": self.server_error_count,
                "total_bytes_served": self.total_bytes_served,
                "average_response_time_ms": avg_resp,
                "requests_per_minute": self.get_requests_per_minute(),
                "active_connections": self.active_connections,
                "peak_connections": self.peak_connections,
                "unique_clients": len(self.client_ips),
                "most_requested_route": self.get_most_requested_route(),
                "status_distribution": self.get_status_distribution(),
                "method_distribution": self.get_method_distribution(),
                "top_routes": self.get_top_routes(6),
            }

    def get_network_info(self) -> Dict:
        """Get network-level connection and socket telemetry."""
        with self._lock:
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
            except Exception:
                local_ip = config.HOST

            return {
                "server_name": config.SERVER_NAME,
                "protocol": config.PROTOCOL,
                "server_ip": local_ip,
                "bind_host": config.HOST,
                "listening_port": config.PORT,
                "max_workers": config.MAX_WORKERS,
                "active_clients": self.active_connections,
                "peak_connections": self.peak_connections,
                "total_connections_handled": self.total_requests,
                "uptime": self.get_uptime_str(),
                "bytes_transferred": self.total_bytes_served,
                "connection_timeout": config.CONNECTION_TIMEOUT,
                "socket_reused": True,
            }


# Global monitor singleton
monitor = NetworkMonitor()