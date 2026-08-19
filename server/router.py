"""
Routing module for NetServe.
Maps request paths to specific API handlers or static file resolution.
"""

import socket
from typing import Callable, Dict, Optional

from .config import config
from .http_parser import HTTPRequest
from .logger import request_logger
from .monitor import monitor
from .response import HTTPResponse, ResponseBuilder
from .utils import resolve_file_path

# Route handler signature
RouteHandler = Callable[[HTTPRequest], HTTPResponse]


class Router:
    """HTTP request router supporting static assets and JSON API endpoints."""

    def __init__(self):
        self.routes: Dict[str, RouteHandler] = {}
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Register default endpoints and handlers."""
        # JSON REST APIs
        self.add_route("/api/status", self.handle_status)
        self.add_route("/api/stats", self.handle_stats)
        self.add_route("/api/requests", self.handle_requests)
        self.add_route("/api/logs", self.handle_logs)
        self.add_route("/api/network", self.handle_network)

        # Dashboard View
        self.add_route("/dashboard", self.handle_dashboard)

        # Predefined HTML Pages
        self.add_route("/", self.handle_home)
        self.add_route("/about", self.handle_about)
        self.add_route("/docs", self.handle_docs)

        # Favicon
        self.add_route("/favicon.ico", self.handle_favicon)

    def add_route(self, path: str, handler: RouteHandler) -> None:
        """Register a route path and its handler."""
        self.routes[path] = handler

    def route(self, request: HTTPRequest) -> HTTPResponse:
        """
        Route an incoming HTTPRequest to the appropriate handler or static file.

        Args:
            request: Parsed HTTPRequest

        Returns:
            HTTPResponse object
        """
        path = request.clean_path

        # 1. Exact match in registered API/page routes
        if path in self.routes:
            return self.routes[path](request)

        # 2. Try static file resolution (css, js, images, html)
        return self.handle_static(request)

    def handle_home(self, request: HTTPRequest) -> HTTPResponse:
        """Handle root / route."""
        home_path = config.PUBLIC_DIR / "index.html"
        if home_path.exists():
            return ResponseBuilder.file_response(home_path, request.is_keep_alive)
        return ResponseBuilder.not_found("/", request.is_keep_alive)

    def handle_about(self, request: HTTPRequest) -> HTTPResponse:
        """Handle /about route."""
        about_path = config.PUBLIC_DIR / "about.html"
        if about_path.exists():
            return ResponseBuilder.file_response(about_path, request.is_keep_alive)
        return ResponseBuilder.not_found("/about", request.is_keep_alive)

    def handle_docs(self, request: HTTPRequest) -> HTTPResponse:
        """Handle /docs route."""
        docs_path = config.PUBLIC_DIR / "docs.html"
        if docs_path.exists():
            return ResponseBuilder.file_response(docs_path, request.is_keep_alive)
        return ResponseBuilder.not_found("/docs", request.is_keep_alive)

    def handle_dashboard(self, request: HTTPRequest) -> HTTPResponse:
        """Handle /dashboard route."""
        dashboard_path = config.DASHBOARD_DIR / "dashboard.html"
        if dashboard_path.exists():
            return ResponseBuilder.file_response(dashboard_path, request.is_keep_alive)
        return ResponseBuilder.not_found("/dashboard", request.is_keep_alive)

    def handle_static(self, request: HTTPRequest) -> HTTPResponse:
        """Handle static file lookup in public or dashboard directory."""
        file_path, is_directory = resolve_file_path(request.clean_path)

        if file_path is None:
            return ResponseBuilder.not_found(request.clean_path, request.is_keep_alive)

        return ResponseBuilder.file_response(file_path, request.is_keep_alive)

    def handle_status(self, request: HTTPRequest) -> HTTPResponse:
        """Handle GET /api/status."""
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = config.HOST

        data = {
            "server": config.SERVER_NAME,
            "status": "running",
            "host": config.HOST,
            "port": config.PORT,
            "server_ip": local_ip,
            "uptime": monitor.get_uptime_str(),
            "uptime_seconds": round(monitor.get_uptime(), 1),
            "active_connections": monitor.active_connections,
            "version": config.SERVER_VERSION,
            "protocol": config.PROTOCOL,
        }
        return ResponseBuilder.json(data, keep_alive=request.is_keep_alive)

    def handle_stats(self, request: HTTPRequest) -> HTTPResponse:
        """Handle GET /api/stats."""
        data = monitor.get_stats_summary()
        return ResponseBuilder.json(data, keep_alive=request.is_keep_alive)

    def handle_requests(self, request: HTTPRequest) -> HTTPResponse:
        """Handle GET /api/requests."""
        raw_limit = request.query_params.get("limit", ["50"])[0]
        try:
            limit = max(1, min(int(raw_limit), 100))
        except ValueError:
            limit = 50

        requests = monitor.get_recent_requests(limit)
        return ResponseBuilder.json({"requests": requests, "count": len(requests)}, keep_alive=request.is_keep_alive)

    def handle_logs(self, request: HTTPRequest) -> HTTPResponse:
        """Handle GET /api/logs."""
        raw_limit = request.query_params.get("limit", ["100"])[0]
        try:
            limit = max(1, min(int(raw_limit), 500))
        except ValueError:
            limit = 100

        logs = request_logger.get_recent_logs(limit)
        return ResponseBuilder.json({"logs": logs, "count": len(logs)}, keep_alive=request.is_keep_alive)

    def handle_network(self, request: HTTPRequest) -> HTTPResponse:
        """Handle GET /api/network."""
        data = monitor.get_network_info()
        return ResponseBuilder.json(data, keep_alive=request.is_keep_alive)

    def handle_favicon(self, request: HTTPRequest) -> HTTPResponse:
        """Handle GET /favicon.ico."""
        favicon_path = config.PUBLIC_DIR / "favicon.ico"
        if favicon_path.exists():
            return ResponseBuilder.file_response(favicon_path, request.is_keep_alive)
        return ResponseBuilder.no_content(request.is_keep_alive)


# Global router singleton
router = Router()