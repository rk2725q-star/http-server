"""
HTTP Request Parser for NetServe.
Parses raw HTTP requests into structured Python objects.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from .config import config


@dataclass
class HTTPRequest:
    """Parsed HTTP request structure."""
    method: str = ""
    path: str = "/"
    version: str = "HTTP/1.1"
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, list] = field(default_factory=dict)
    body: bytes = b""
    client_ip: str = ""
    raw_request: bytes = b""

    @property
    def clean_path(self) -> str:
        """Return path without query string or fragment."""
        clean = self.path.split("?")[0].split("#")[0]
        return clean if clean else "/"

    @property
    def is_keep_alive(self) -> bool:
        """Check if connection should be kept alive."""
        connection = self.get_header("Connection", "").lower()
        if connection == "keep-alive":
            return True
        if connection == "close":
            return False
        # HTTP/1.1 defaults to keep-alive; HTTP/1.0 defaults to close
        return self.version == "HTTP/1.1"

    def get_header(self, name: str, default: str = "") -> str:
        """Get header value case-insensitively."""
        target = name.lower()
        for k, v in self.headers.items():
            if k.lower() == target:
                return v
        return default


class HTTPParserError(Exception):
    """Exception raised when HTTP parsing fails."""
    def __init__(self, message: str, status_code: int = 400, method: str = ""):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.method = method


class HTTPRequestParser:
    """Parses HTTP requests from raw bytes."""

    # HTTP request line regex: METHOD PATH HTTP/X.Y
    REQUEST_LINE_PATTERN = re.compile(
        r"^([A-Z]+)\s+(\S+)\s+(HTTP/\d\.\d)$"
    )

    def __init__(self, client_ip: str = ""):
        self.client_ip = client_ip

    def parse(self, data: bytes) -> HTTPRequest:
        """
        Parse raw HTTP request bytes into HTTPRequest object.

        Args:
            data: Raw request bytes

        Returns:
            Parsed HTTPRequest object

        Raises:
            HTTPParserError: If parsing fails
        """
        if not data or not data.strip():
            raise HTTPParserError("Empty request", 400)

        if len(data) > config.MAX_REQUEST_SIZE:
            raise HTTPParserError("Payload Too Large", 413)

        request = HTTPRequest(client_ip=self.client_ip, raw_request=data)

        # Split request into headers and body
        try:
            header_end = data.index(b"\r\n\r\n")
            header_data = data[:header_end]
            request.body = data[header_end + 4:]
        except ValueError:
            # Fallback for \n\n line endings
            if b"\n\n" in data:
                header_end = data.index(b"\n\n")
                header_data = data[:header_end]
                request.body = data[header_end + 2:]
            else:
                # No body separator found, treat all as headers
                header_data = data
                request.body = b""

        # Decode headers
        header_text = header_data.decode("iso-8859-1", errors="replace")
        lines = header_text.replace("\r\n", "\n").split("\n")

        if not lines or not lines[0].strip():
            raise HTTPParserError("Empty request line", 400)

        # Parse request line
        request_line = lines[0].strip()
        match = self.REQUEST_LINE_PATTERN.match(request_line)
        if not match:
            raise HTTPParserError("Malformed request line", 400)

        request.method = match.group(1).upper()
        raw_path = match.group(2)
        request.version = match.group(3)

        # Validate HTTP method
        if request.method not in config.ALLOWED_METHODS:
            raise HTTPParserError(f"Method {request.method} not allowed", 405, method=request.method)

        # Parse headers
        total_header_size = len(header_data)
        if total_header_size > config.MAX_HEADER_SIZE:
            raise HTTPParserError("Request Header Fields Too Large", 431)

        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                raise HTTPParserError("Malformed header syntax", 400)

            name, value = line.split(":", 1)
            name = name.strip()
            value = value.strip()

            if not name:
                raise HTTPParserError("Empty header name", 400)

            request.headers[name] = value

        # Header count check
        if len(request.headers) > config.MAX_HEADERS:
            raise HTTPParserError("Too many headers", 431)

        # Parse and unquote URL path & query parameters
        parsed_url = urlparse(raw_path)
        decoded_path = unquote(parsed_url.path)
        request.path = decoded_path if decoded_path else "/"
        request.query_params = parse_qs(parsed_url.query, keep_blank_values=True)

        # Security: Check for path traversal and forbidden characters
        self._validate_path(request.path)

        return request

    def _validate_path(self, path: str) -> None:
        """Validate path for security issues."""
        # Check for null bytes
        if "\x00" in path:
            raise HTTPParserError("Path contains null byte", 400)

        # Check for directory traversal sequences
        normalized_path = path.replace("\\", "/")
        parts = normalized_path.split("/")
        for part in parts:
            if part == "..":
                raise HTTPParserError("Directory traversal detected", 400)


def parse_request(data: bytes, client_ip: str = "") -> HTTPRequest:
    """
    Convenience function to parse HTTP request.

    Args:
        data: Raw request bytes
        client_ip: Client IP address

    Returns:
        Parsed HTTPRequest object
    """
    parser = HTTPRequestParser(client_ip)
    return parser.parse(data)