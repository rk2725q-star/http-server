"""
Unit tests for NetServe HTTP Request Parser.
Tests parsing of request lines, headers, query parameters, method restrictions, and security protections.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server.config import config
from server.http_parser import HTTPParserError, HTTPRequest, parse_request


class TestHTTPRequestParser(unittest.TestCase):
    """Test suite for HTTPRequestParser."""

    def test_valid_get_request(self):
        """Test parsing a standard GET request."""
        raw = (
            b"GET /index.html HTTP/1.1\r\n"
            b"Host: 127.0.0.1:8080\r\n"
            b"User-Agent: NetServe-Test\r\n"
            b"Accept: text/html\r\n"
            b"Connection: keep-alive\r\n\r\n"
        )
        req = parse_request(raw, client_ip="127.0.0.1")
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.path, "/index.html")
        self.assertEqual(req.clean_path, "/index.html")
        self.assertEqual(req.version, "HTTP/1.1")
        self.assertEqual(req.get_header("Host"), "127.0.0.1:8080")
        self.assertEqual(req.get_header("user-agent"), "NetServe-Test")
        self.assertTrue(req.is_keep_alive)
        self.assertEqual(req.client_ip, "127.0.0.1")

    def test_valid_head_request(self):
        """Test parsing a HEAD request."""
        raw = b"HEAD /about HTTP/1.1\r\nHost: localhost:8080\r\n\r\n"
        req = parse_request(raw)
        self.assertEqual(req.method, "HEAD")
        self.assertEqual(req.clean_path, "/about")
        self.assertEqual(req.version, "HTTP/1.1")

    def test_query_parameters(self):
        """Test parsing URL query parameters."""
        raw = b"GET /api/requests?limit=25&filter=active HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parse_request(raw)
        self.assertEqual(req.clean_path, "/api/requests")
        self.assertEqual(req.query_params.get("limit"), ["25"])
        self.assertEqual(req.query_params.get("filter"), ["active"])

    def test_keep_alive_close(self):
        """Test explicit Connection: close header."""
        raw = b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        req = parse_request(raw)
        self.assertFalse(req.is_keep_alive)

    def test_empty_request_raises_error(self):
        """Test that empty bytes raise 400 Bad Request."""
        with self.assertRaises(HTTPParserError) as ctx:
            parse_request(b"")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_malformed_request_line(self):
        """Test that invalid request line raises 400 Bad Request."""
        with self.assertRaises(HTTPParserError) as ctx:
            parse_request(b"INVALID REQUEST LINE\r\nHost: test\r\n\r\n")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_unsupported_method_raises_405(self):
        """Test that unsupported HTTP methods (e.g. DELETE) raise 405 Method Not Allowed."""
        with self.assertRaises(HTTPParserError) as ctx:
            parse_request(b"DELETE /api/resource HTTP/1.1\r\nHost: localhost\r\n\r\n")
        self.assertEqual(ctx.exception.status_code, 405)
        self.assertEqual(ctx.exception.method, "DELETE")

    def test_directory_traversal_detection(self):
        """Test that directory traversal sequences raise 400."""
        with self.assertRaises(HTTPParserError) as ctx:
            parse_request(b"GET /../../etc/passwd HTTP/1.1\r\nHost: localhost\r\n\r\n")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_null_byte_in_path(self):
        """Test that null byte in path raises 400."""
        with self.assertRaises(HTTPParserError) as ctx:
            parse_request(b"GET /index.html%00.png HTTP/1.1\r\nHost: localhost\r\n\r\n")
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
