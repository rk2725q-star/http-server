"""
Unit tests for NetServe Router, ResponseBuilder, and Static File Resolution.
"""

import json
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server.config import config
from server.http_parser import HTTPRequest
from server.response import HTTPResponse, ResponseBuilder
from server.router import router
from server.utils import get_mime_type, is_safe_path, resolve_file_path


class TestRouterAndResponse(unittest.TestCase):
    """Test suite for Router, ResponseBuilder, and Utils."""

    def test_api_status_route(self):
        """Test GET /api/status handler."""
        req = HTTPRequest(method="GET", path="/api/status")
        resp = router.route(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp.headers["Content-Type"])

        data = json.loads(resp.body.decode("utf-8"))
        self.assertEqual(data["server"], "NetServe")
        self.assertEqual(data["status"], "running")
        self.assertIn("uptime", data)

    def test_api_stats_route(self):
        """Test GET /api/stats handler."""
        req = HTTPRequest(method="GET", path="/api/stats")
        resp = router.route(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp.headers["Content-Type"])

        data = json.loads(resp.body.decode("utf-8"))
        self.assertIn("total_requests", data)
        self.assertIn("status_distribution", data)

    def test_api_network_route(self):
        """Test GET /api/network handler."""
        req = HTTPRequest(method="GET", path="/api/network")
        resp = router.route(req)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.body.decode("utf-8"))
        self.assertIn("server_ip", data)
        self.assertIn("listening_port", data)

    def test_static_home_route(self):
        """Test GET / serves index.html."""
        req = HTTPRequest(method="GET", path="/")
        resp = router.route(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers["Content-Type"])
        self.assertIn(b"NetServe", resp.body)

    def test_clean_url_resolution(self):
        """Test clean URLs without .html extension (e.g. /about -> /about.html)."""
        req = HTTPRequest(method="GET", path="/about")
        resp = router.route(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers["Content-Type"])
        self.assertIn(b"About NetServe", resp.body)

    def test_404_not_found(self):
        """Test requesting a nonexistent path returns 404."""
        req = HTTPRequest(method="GET", path="/nonexistent-path-abc-123")
        resp = router.route(req)
        self.assertEqual(resp.status_code, 404)

    def test_mime_type_lookup(self):
        """Test MIME type detection for various file extensions."""
        self.assertIn("text/html", get_mime_type("index.html"))
        self.assertIn("text/css", get_mime_type("style.css"))
        self.assertIn("javascript", get_mime_type("app.js"))
        self.assertEqual(get_mime_type("photo.png"), "image/png")
        self.assertEqual(get_mime_type("image.svg"), "image/svg+xml")

    def test_path_safety_check(self):
        """Test is_safe_path blocks path traversal attempts."""
        self.assertTrue(is_safe_path("/css/style.css"))
        self.assertTrue(is_safe_path("/about"))
        self.assertFalse(is_safe_path("/../etc/passwd"))
        self.assertFalse(is_safe_path("/../../secret.txt"))
        self.assertFalse(is_safe_path("index.html\x00.png"))


if __name__ == "__main__":
    unittest.main()
