"""
HTTP Response Builder for NetServe.
Generates valid HTTP responses from structured data.
"""

import json
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Union

from .config import config


# Standard HTTP Status Codes
STATUS_CODES: Dict[int, str] = {
    200: "OK",
    201: "Created",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    413: "Payload Too Large",
    431: "Request Header Fields Too Large",
    500: "Internal Server Error",
    501: "Not Implemented",
    503: "Service Unavailable",
}


@dataclass
class HTTPResponse:
    """HTTP Response structure."""
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    version: str = "HTTP/1.1"

    def __post_init__(self):
        """Set default headers after initialization."""
        if "Date" not in self.headers:
            self.headers["Date"] = self._format_date()
        if "Server" not in self.headers:
            self.headers["Server"] = f"{config.SERVER_NAME}/{config.SERVER_VERSION}"
        if "Cache-Control" not in self.headers:
            self.headers["Cache-Control"] = "no-cache"

    @staticmethod
    def _format_date() -> str:
        """Format current UTC date in RFC 7231 / RFC 1123 format."""
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

    @property
    def status_text(self) -> str:
        """Get status text for status code."""
        return STATUS_CODES.get(self.status_code, "Unknown Status")

    @property
    def status_line(self) -> str:
        """Get HTTP status line."""
        return f"{self.version} {self.status_code} {self.status_text}"

    def add_header(self, name: str, value: str) -> None:
        """Add or update a header."""
        self.headers[name] = value

    def set_content_type(self, content_type: str) -> None:
        """Set Content-Type header."""
        self.headers["Content-Type"] = content_type

    def set_content_length(self, length: int) -> None:
        """Set Content-Length header."""
        self.headers["Content-Length"] = str(length)

    def set_connection(self, keep_alive: bool) -> None:
        """Set Connection header."""
        self.headers["Connection"] = "keep-alive" if keep_alive else "close"

    def to_bytes(self, is_head: bool = False) -> bytes:
        """
        Serialize HTTP response to bytes.

        Args:
            is_head: If True, only status line and headers are returned (body omitted).

        Returns:
            Raw HTTP response bytes.
        """
        # Ensure Content-Length is set based on actual body size
        if "Content-Length" not in self.headers:
            self.set_content_length(len(self.body))

        # Build status line and headers
        lines = [self.status_line]
        for name, value in self.headers.items():
            lines.append(f"{name}: {value}")

        # Empty line separating headers from body
        lines.append("")
        lines.append("")

        header_bytes = "\r\n".join(lines[:-1]).encode("latin-1", errors="replace") + b"\r\n"

        if is_head:
            return header_bytes

        return header_bytes + self.body


class ResponseBuilder:
    """Builds HTTP responses for various scenarios."""

    @staticmethod
    def ok(body: Union[str, bytes] = "", content_type: str = "text/html; charset=utf-8",
           keep_alive: bool = True) -> HTTPResponse:
        """Build 200 OK response."""
        if isinstance(body, str):
            body = body.encode("utf-8")
        resp = HTTPResponse(status_code=200, body=body)
        resp.set_content_type(content_type)
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def created(body: Union[str, bytes, dict] = "", content_type: str = "application/json; charset=utf-8",
                keep_alive: bool = True) -> HTTPResponse:
        """Build 201 Created response."""
        if isinstance(body, dict):
            body = json.dumps(body, indent=2).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        resp = HTTPResponse(status_code=201, body=body)
        resp.set_content_type(content_type)
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def no_content(keep_alive: bool = True) -> HTTPResponse:
        """Build 204 No Content response."""
        resp = HTTPResponse(status_code=204, body=b"")
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def not_found(path: str = "", keep_alive: bool = True) -> HTTPResponse:
        """Build 404 Not Found response."""
        custom_404 = config.PUBLIC_DIR / "404.html"
        if custom_404.exists():
            try:
                with open(custom_404, "rb") as f:
                    body = f.read()
                resp = HTTPResponse(status_code=404, body=body)
                resp.set_content_type("text/html; charset=utf-8")
                resp.set_connection(keep_alive)
                return resp
            except Exception:
                pass

        body = ResponseBuilder._error_body(404, "Not Found", f"The requested resource '{path}' was not found on this server.")
        resp = HTTPResponse(status_code=404, body=body)
        resp.set_content_type("text/html; charset=utf-8")
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def method_not_allowed(method: str = "", allowed: list = None, keep_alive: bool = True) -> HTTPResponse:
        """Build 405 Method Not Allowed response."""
        allowed = allowed or config.ALLOWED_METHODS
        allowed_str = ", ".join(allowed)
        body = ResponseBuilder._error_body(
            405,
            "Method Not Allowed",
            f"HTTP method '{method}' is not supported for this route. Allowed methods: {allowed_str}"
        )
        resp = HTTPResponse(status_code=405, body=body)
        resp.set_content_type("text/html; charset=utf-8")
        resp.add_header("Allow", allowed_str)
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def bad_request(message: str = "Bad Request", keep_alive: bool = True) -> HTTPResponse:
        """Build 400 Bad Request response."""
        body = ResponseBuilder._error_body(400, "Bad Request", message)
        resp = HTTPResponse(status_code=400, body=body)
        resp.set_content_type("text/html; charset=utf-8")
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def payload_too_large(message: str = "Payload Too Large", keep_alive: bool = False) -> HTTPResponse:
        """Build 413 Payload Too Large response."""
        body = ResponseBuilder._error_body(413, "Payload Too Large", message)
        resp = HTTPResponse(status_code=413, body=body)
        resp.set_content_type("text/html; charset=utf-8")
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def headers_too_large(message: str = "Request Header Fields Too Large", keep_alive: bool = False) -> HTTPResponse:
        """Build 431 Request Header Fields Too Large response."""
        body = ResponseBuilder._error_body(431, "Request Header Fields Too Large", message)
        resp = HTTPResponse(status_code=431, body=body)
        resp.set_content_type("text/html; charset=utf-8")
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def internal_error(message: str = "Internal Server Error", keep_alive: bool = True) -> HTTPResponse:
        """Build 500 Internal Server Error response."""
        custom_500 = config.PUBLIC_DIR / "500.html"
        if custom_500.exists():
            try:
                with open(custom_500, "rb") as f:
                    body = f.read()
                resp = HTTPResponse(status_code=500, body=body)
                resp.set_content_type("text/html; charset=utf-8")
                resp.set_connection(keep_alive)
                return resp
            except Exception:
                pass

        body = ResponseBuilder._error_body(500, "Internal Server Error", message)
        resp = HTTPResponse(status_code=500, body=body)
        resp.set_content_type("text/html; charset=utf-8")
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def json(data: Union[dict, list], status_code: int = 200, keep_alive: bool = True) -> HTTPResponse:
        """Build JSON response."""
        body = json.dumps(data, indent=2).encode("utf-8")
        resp = HTTPResponse(status_code=status_code, body=body)
        resp.set_content_type("application/json; charset=utf-8")
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def file_response(file_path: Union[str, Path], keep_alive: bool = True) -> HTTPResponse:
        """Build response for serving a static file."""
        path_obj = Path(file_path)
        try:
            with open(path_obj, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            return ResponseBuilder.not_found(str(file_path), keep_alive)
        except PermissionError:
            body = ResponseBuilder._error_body(403, "Forbidden", "Access to this file is restricted.")
            resp = HTTPResponse(status_code=403, body=body)
            resp.set_content_type("text/html; charset=utf-8")
            resp.set_connection(keep_alive)
            return resp
        except Exception as e:
            return ResponseBuilder.internal_error(f"Error reading file: {e}", keep_alive)

        # Determine MIME type
        ext = path_obj.suffix.lower()
        mime_type = config.MIME_TYPES.get(ext)
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(path_obj))
        if not mime_type:
            mime_type = "application/octet-stream"

        resp = HTTPResponse(status_code=200, body=body)
        resp.set_content_type(mime_type)
        resp.set_connection(keep_alive)
        return resp

    @staticmethod
    def _error_body(status_code: int, title: str, detail: str) -> bytes:
        """Generate a sleek, dark technical HTML error page fallback."""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{status_code} {title} | NetServe</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background: #0b0f19;
            color: #f1f5f9;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .card {{
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 48px;
            max-width: 520px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
        }}
        .badge {{
            display: inline-block;
            padding: 6px 16px;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            border-radius: 20px;
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            margin-bottom: 20px;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}
        .code {{
            font-size: 72px;
            font-weight: 800;
            color: #ef4444;
            line-height: 1;
            margin-bottom: 12px;
            letter-spacing: -2px;
        }}
        h1 {{
            font-size: 24px;
            font-weight: 700;
            color: #f8fafc;
            margin-bottom: 12px;
        }}
        p {{
            color: #94a3b8;
            font-size: 15px;
            line-height: 1.6;
            margin-bottom: 24px;
        }}
        .detail {{
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13px;
            color: #38bdf8;
            background: #060911;
            border: 1px solid #1e293b;
            padding: 14px;
            border-radius: 8px;
            margin-bottom: 28px;
            text-align: left;
            word-break: break-all;
        }}
        .actions {{
            display: flex;
            gap: 12px;
            justify-content: center;
            flex-wrap: wrap;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
        }}
        .btn-primary {{
            background: #2563eb;
            color: white;
        }}
        .btn-primary:hover {{
            background: #1d4ed8;
        }}
        .btn-secondary {{
            background: #1e293b;
            color: #cbd5e1;
            border: 1px solid #334155;
        }}
        .btn-secondary:hover {{
            background: #334155;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">HTTP Error</div>
        <div class="code">{status_code}</div>
        <h1>{title}</h1>
        <p>NetServe encountered an issue handling your HTTP request.</p>
        <div class="detail">&gt; {detail}</div>
        <div class="actions">
            <a href="/" class="btn btn-primary">Home Page</a>
            <a href="/dashboard" class="btn btn-secondary">Server Dashboard</a>
        </div>
    </div>
</body>
</html>"""
        return html.encode("utf-8")