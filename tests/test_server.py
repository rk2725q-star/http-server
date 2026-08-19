"""
Integration tests for NetServe HTTP Server.
Launches a real TCP socket server and sends raw HTTP socket requests to verify full networking roundtrip.
"""

import json
import socket
import sys
import threading
import time
import unittest
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server.config import config
from server.server import NetServeServer


class TestServerIntegration(unittest.TestCase):
    """End-to-end TCP socket integration tests."""

    TEST_HOST = "127.0.0.1"
    TEST_PORT = 18080

    @classmethod
    def setUpClass(cls):
        """Start the NetServe TCP server on a dedicated test port in a background thread."""
        cls.server = NetServeServer(host=cls.TEST_HOST, port=cls.TEST_PORT, workers=4)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()

        # Allow time for socket bind & listen
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        """Shutdown the test server."""
        cls.server.stop()
        time.sleep(0.3)

    def _send_socket_request(self, request_bytes: bytes) -> bytes:
        """Helper to open a raw TCP socket, send bytes, and receive the response."""
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.settimeout(3.0)
        try:
            client_sock.connect((self.TEST_HOST, self.TEST_PORT))
            client_sock.sendall(request_bytes)

            is_head = request_bytes.strip().startswith(b"HEAD")
            response_buffer = bytearray()

            while True:
                try:
                    chunk = client_sock.recv(4096)
                    if not chunk:
                        break
                    response_buffer.extend(chunk)

                    # For HEAD requests, once headers arrive, we are done
                    if is_head and b"\r\n\r\n" in response_buffer:
                        break

                    # Check Content-Length completion
                    if b"\r\n\r\n" in response_buffer:
                        header_end = response_buffer.find(b"\r\n\r\n")
                        header_text = response_buffer[:header_end].decode("iso-8859-1", errors="replace")
                        
                        content_len = 0
                        has_cl = False
                        for line in header_text.splitlines():
                            if line.lower().startswith("content-length:"):
                                try:
                                    content_len = int(line.split(":")[1].strip())
                                    has_cl = True
                                except ValueError:
                                    pass

                        if has_cl:
                            body_len = len(response_buffer) - (header_end + 4)
                            if body_len >= content_len:
                                break
                except socket.timeout:
                    break

            return bytes(response_buffer)
        finally:
            client_sock.close()

    def test_raw_socket_get_home(self):
        """Test sending a raw HTTP/1.1 GET request over TCP socket."""
        raw_req = (
            b"GET / HTTP/1.1\r\n"
            b"Host: 127.0.0.1:18080\r\n"
            b"Connection: close\r\n\r\n"
        )
        response_bytes = self._send_socket_request(raw_req)

        self.assertTrue(response_bytes.startswith(b"HTTP/1.1 200 OK\r\n"))
        self.assertIn(b"Server: NetServe/1.0.0", response_bytes)
        self.assertIn(b"Content-Type: text/html", response_bytes)
        self.assertIn(b"NetServe", response_bytes)

    def test_raw_socket_head_request(self):
        """Test HEAD request returns headers but no body."""
        raw_req = (
            b"HEAD / HTTP/1.1\r\n"
            b"Host: 127.0.0.1:18080\r\n"
            b"Connection: close\r\n\r\n"
        )
        response_bytes = self._send_socket_request(raw_req)

        self.assertTrue(response_bytes.startswith(b"HTTP/1.1 200 OK\r\n"))
        self.assertIn(b"Content-Length:", response_bytes)

        header_end = response_bytes.find(b"\r\n\r\n")
        self.assertNotEqual(header_end, -1)
        body = response_bytes[header_end + 4:]
        self.assertEqual(len(body), 0, "HEAD response must contain 0 body bytes")

    def test_raw_socket_api_status(self):
        """Test GET /api/status JSON endpoint over socket."""
        raw_req = (
            b"GET /api/status HTTP/1.1\r\n"
            b"Host: 127.0.0.1:18080\r\n"
            b"Connection: close\r\n\r\n"
        )
        response_bytes = self._send_socket_request(raw_req)

        self.assertTrue(response_bytes.startswith(b"HTTP/1.1 200 OK\r\n"))
        self.assertIn(b"Content-Type: application/json", response_bytes)

        header_end = response_bytes.find(b"\r\n\r\n")
        body_json = json.loads(response_bytes[header_end + 4:].decode("utf-8"))
        self.assertEqual(body_json["server"], "NetServe")
        self.assertEqual(body_json["status"], "running")

    def test_raw_socket_404_error(self):
        """Test requesting invalid route returns 404 over socket."""
        raw_req = (
            b"GET /path-that-does-not-exist-999 HTTP/1.1\r\n"
            b"Host: 127.0.0.1:18080\r\n"
            b"Connection: close\r\n\r\n"
        )
        response_bytes = self._send_socket_request(raw_req)
        self.assertTrue(response_bytes.startswith(b"HTTP/1.1 404 Not Found\r\n"))

    def test_concurrent_socket_clients(self):
        """Test multiple client threads sending requests simultaneously."""
        results = []
        errors = []

        def worker(i):
            try:
                path = "/api/status" if i % 2 == 0 else "/"
                req = f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:18080\r\nConnection: close\r\n\r\n".encode("utf-8")
                res = self._send_socket_request(req)
                if res.startswith(b"HTTP/1.1 200 OK"):
                    results.append(True)
                else:
                    errors.append(f"Unexpected status in thread {i}: {res[:30]}")
            except Exception as e:
                errors.append(f"Thread {i} failed: {e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent request errors: {errors}")
        self.assertEqual(len(results), 10, "All 10 concurrent requests must succeed")


if __name__ == "__main__":
    unittest.main()
