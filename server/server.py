"""
NetServe HTTP Server - Main Server Implementation.
A multi-threaded TCP socket HTTP/1.1 server built with standard library socket and threading.
"""

import signal
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Set, Tuple

from .config import config
from .http_parser import HTTPParserError, HTTPRequest, parse_request
from .logger import request_logger, server_logger
from .monitor import RequestRecord, monitor
from .response import HTTPResponse, ResponseBuilder
from .router import router


class ClientHandler:
    """Handles an individual client TCP connection lifecycle."""

    def __init__(self, client_socket: socket.socket, client_address: Tuple[str, int], server=None):
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_ip = client_address[0] if client_address else "127.0.0.1"
        self.server = server
        self.running = True

    def handle(self) -> None:
        """Main connection loop supporting HTTP/1.1 persistent connections (Keep-Alive)."""
        monitor.connection_opened()

        try:
            self.client_socket.settimeout(config.CONNECTION_TIMEOUT)

            while self.running:
                # 1. Read raw HTTP request data from TCP socket
                raw_data = self._read_request()
                if not raw_data or not self.running:
                    break

                start_time = time.time()
                parsed_request: Optional[HTTPRequest] = None

                # 2. Parse HTTP request and route to handler
                try:
                    parsed_request = parse_request(raw_data, self.client_ip)
                    response = router.route(parsed_request)
                except HTTPParserError as e:
                    if e.status_code == 405:
                        response = ResponseBuilder.method_not_allowed(e.method)
                    elif e.status_code == 413:
                        response = ResponseBuilder.payload_too_large(str(e))
                    elif e.status_code == 431:
                        response = ResponseBuilder.headers_too_large(str(e))
                    else:
                        response = ResponseBuilder.bad_request(str(e))
                except Exception as e:
                    server_logger.log_error(f"Internal request processing error: {e}")
                    response = ResponseBuilder.internal_error(str(e))

                # 3. Calculate latency
                duration_ms = (time.time() - start_time) * 1000.0

                # 4. Check if HEAD request (strip body)
                is_head = (parsed_request.method == "HEAD") if parsed_request else False

                # 5. Transmit HTTP response over TCP socket
                self._send_response(response, is_head=is_head)

                # 6. Extract telemetry metadata
                method = parsed_request.method if parsed_request else "UNKNOWN"
                path = parsed_request.clean_path if parsed_request else "UNKNOWN"
                body_size = len(response.body)

                # 7. Log request to console and server.log
                request_logger.log_request(
                    client_ip=self.client_ip,
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    response_size=body_size,
                    duration_ms=duration_ms
                )

                # 8. Record telemetry in real-time network monitor
                monitor.record_request(RequestRecord(
                    timestamp=time.time(),
                    client_ip=self.client_ip,
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    response_size=body_size,
                    duration_ms=duration_ms
                ))

                # 9. Handle Keep-Alive vs Connection: Close
                if not parsed_request or not parsed_request.is_keep_alive:
                    break

        except (socket.timeout, TimeoutError):
            pass  # Idle connection timed out
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError):
            pass  # Client disconnected
        except Exception as e:
            server_logger.log_error(f"Client handler exception: {e}")
        finally:
            monitor.connection_closed()
            self._close()

    def _read_request(self) -> Optional[bytes]:
        """
        Read HTTP request bytes from the TCP socket buffer.
        Detects header boundary (\\r\\n\\r\\n) and respects Content-Length for body.
        """
        buffer = bytearray()
        headers_complete = False
        content_length = 0

        while self.running:
            try:
                chunk = self.client_socket.recv(4096)
                if not chunk:
                    break  # Peer closed socket

                buffer.extend(chunk)

                # Check if HTTP headers are fully received
                if not headers_complete:
                    header_end = buffer.find(b"\r\n\r\n")
                    if header_end == -1:
                        header_end = buffer.find(b"\n\n")

                    if header_end != -1:
                        headers_complete = True
                        header_text = buffer[:header_end].decode("iso-8859-1", errors="replace")
                        content_length = self._parse_content_length(header_text)

                        # Enforce maximum header & request size
                        if len(buffer) > config.MAX_REQUEST_SIZE:
                            raise HTTPParserError("Payload Too Large", 413)

                # Check if full payload body has arrived
                if headers_complete:
                    header_end = buffer.find(b"\r\n\r\n")
                    offset = 4 if header_end != -1 else 2
                    if header_end == -1:
                        header_end = buffer.find(b"\n\n")

                    body_len = len(buffer) - (header_end + offset)
                    if body_len >= content_length:
                        break

            except (socket.timeout, TimeoutError):
                if buffer:
                    break
                raise
            except Exception:
                break

        return bytes(buffer) if buffer else None

    def _parse_content_length(self, header_text: str) -> int:
        """Extract integer value from Content-Length header."""
        for line in header_text.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                if key.strip().lower() == "content-length":
                    try:
                        return max(0, int(val.strip()))
                    except ValueError:
                        return 0
        return 0

    def _send_response(self, response: HTTPResponse, is_head: bool = False) -> None:
        """Send complete HTTP response bytes through TCP socket."""
        try:
            payload = response.to_bytes(is_head=is_head)
            self.client_socket.sendall(payload)
        except Exception:
            pass

    def _close(self) -> None:
        """Close socket connection cleanly and deregister from server."""
        self.running = False
        if self.server:
            self.server._deregister_handler(self)
        try:
            self.client_socket.close()
        except Exception:
            pass


class NetServeServer:
    """Multi-threaded TCP Socket HTTP Web Server."""

    def __init__(self, host: str = config.HOST, port: int = config.PORT,
                 workers: int = config.MAX_WORKERS):
        self.host = host
        self.port = port
        self.workers = workers
        self.server_socket: Optional[socket.socket] = None
        self.executor: Optional[ThreadPoolExecutor] = None
        self.running = False
        self._shutdown_event = threading.Event()
        self._active_handlers: Set[ClientHandler] = set()
        self._handlers_lock = threading.Lock()

    def _register_handler(self, handler: ClientHandler) -> None:
        with self._handlers_lock:
            self._active_handlers.add(handler)

    def _deregister_handler(self, handler: ClientHandler) -> None:
        with self._handlers_lock:
            self._active_handlers.discard(handler)

    def start(self) -> None:
        """Initialize TCP socket, bind, listen, and start worker pool."""
        self.running = True

        # 1. Create TCP IPv4 Streaming Socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # 2. Set SO_REUSEADDR socket option to reuse port immediately after restart
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # 3. Bind to host and port
        try:
            self.server_socket.bind((self.host, self.port))
        except OSError as e:
            server_logger.log_error(f"Failed to bind socket to {self.host}:{self.port} - {e}")
            sys.exit(1)

        # 4. Listen for incoming TCP connection requests
        self.server_socket.listen(config.MAX_CONNECTIONS)

        # 5. Initialize ThreadPoolExecutor for concurrent worker threads
        self.executor = ThreadPoolExecutor(
            max_workers=self.workers,
            thread_name_prefix="NetServe-Worker"
        )

        # 6. Display startup console banner
        server_logger.log_startup(self.host, self.port, self.workers)

        # 7. Setup signal handling for graceful termination
        try:
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGINT, self._signal_handler)
                signal.signal(signal.SIGTERM, self._signal_handler)
        except (ValueError, AttributeError):
            pass

        # 8. Start main connection accept loop
        self._accept_loop()

    def _accept_loop(self) -> None:
        """Continuous accept loop dispatching incoming sockets to worker threads."""
        if not self.server_socket:
            return

        self.server_socket.settimeout(0.5)

        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                handler = ClientHandler(client_socket, client_address, server=self)
                self._register_handler(handler)
                if self.executor and not self._shutdown_event.is_set():
                    self.executor.submit(handler.handle)
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                if self.running:
                    server_logger.log_error("Socket accept failed unexpectedly.")
                break

    def _signal_handler(self, signum, frame) -> None:
        """Handle termination signals (Ctrl+C, SIGTERM)."""
        server_logger.log_info(f"Shutdown signal received ({signum}). Initiating graceful shutdown...")
        self.stop()

    def stop(self) -> None:
        """Stop server, close active sockets, release socket port, and terminate worker threads."""
        if not self.running:
            return

        self.running = False
        self._shutdown_event.set()

        # Close all active client connections immediately
        with self._handlers_lock:
            for handler in list(self._active_handlers):
                try:
                    handler._close()
                except Exception:
                    pass
            self._active_handlers.clear()

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        if self.executor:
            try:
                self.executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

        server_logger.log_shutdown()


def run_server(host: str = config.HOST, port: int = config.PORT, workers: int = config.MAX_WORKERS) -> None:
    """
    Configure and launch the NetServe server instance.

    Args:
        host: IP host to bind to
        port: Listening port
        workers: Worker thread pool size
    """
    config.HOST = host
    config.PORT = port
    config.MAX_WORKERS = workers
    config.validate()

    server = NetServeServer(host=host, port=port, workers=workers)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    run_server()