"""
Utility functions for NetServe.
Contains file path resolution, MIME detection, formatting, and safety checks.
"""

import mimetypes
import os
from pathlib import Path
from typing import Optional, Tuple

from .config import config

# Initialize standard MIME types
mimetypes.init()
for ext, mime in config.MIME_TYPES.items():
    mimetypes.add_type(mime, ext)


def get_mime_type(file_path: str) -> str:
    """
    Get MIME type for a file path.

    Args:
        file_path: Path to file (as string or Path)

    Returns:
        MIME type string
    """
    path_str = str(file_path).lower()

    # Check custom MIME type overrides first
    for ext, mime in config.MIME_TYPES.items():
        if path_str.endswith(ext):
            return mime

    # Fallback to system mimetypes
    mime_type, _ = mimetypes.guess_type(path_str)
    if mime_type:
        return mime_type

    return "application/octet-stream"


def is_safe_path(path: str) -> bool:
    """
    Check if a path string is safe against traversal attacks.

    Args:
        path: Path string to check

    Returns:
        True if safe, False otherwise
    """
    if "\x00" in path:
        return False

    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    for part in parts:
        if part in ("..", "~"):
            return False

    return True


def resolve_file_path(request_path: str) -> Tuple[Optional[Path], bool]:
    """
    Resolve request path to filesystem path with strict security checks.
    Searches PUBLIC_DIR and DASHBOARD_DIR. Supports clean URLs without .html extension.

    Args:
        request_path: Requested path (e.g., "/about", "/css/style.css", "/dashboard.js")

    Returns:
        Tuple of (resolved_path, is_directory)
        Returns (None, False) if file does not exist or violates security checks.
    """
    if not is_safe_path(request_path):
        return None, False

    clean = request_path.lstrip("/")
    if not clean:
        clean = "index.html"

    public_dir = config.PUBLIC_DIR.resolve()
    dashboard_dir = config.DASHBOARD_DIR.resolve()

    candidate_paths = []

    # 1. Exact match in public directory
    candidate_paths.append((public_dir / clean).resolve())

    # 2. Append .html in public directory (for clean URLs like /about -> /about.html)
    if not clean.endswith((".html", ".htm", ".css", ".js", ".json", ".png", ".jpg", ".svg", ".ico", ".txt")):
        candidate_paths.append((public_dir / f"{clean}.html").resolve())

    # 3. Match in dashboard directory (e.g., /dashboard.css, /dashboard.js)
    candidate_paths.append((dashboard_dir / clean).resolve())

    # 4. Match stripped 'dashboard/' prefix in dashboard directory
    if clean.startswith("dashboard/"):
        stripped = clean[len("dashboard/"):]
        if stripped:
            candidate_paths.append((dashboard_dir / stripped).resolve())
        else:
            candidate_paths.append((dashboard_dir / "dashboard.html").resolve())

    for target in candidate_paths:
        try:
            # Security verification: target must be inside PUBLIC_DIR or DASHBOARD_DIR
            is_in_public = str(target).startswith(str(public_dir))
            is_in_dashboard = str(target).startswith(str(dashboard_dir))

            if not (is_in_public or is_in_dashboard):
                continue

            if target.exists():
                if target.is_dir():
                    # Check for index files inside directory
                    for idx in config.INDEX_FILES:
                        idx_target = target / idx
                        if idx_target.exists() and idx_target.is_file():
                            return idx_target, False
                    return None, True  # Directory without index file
                elif target.is_file():
                    return target, False
        except Exception:
            continue

    return None, False


def format_bytes(bytes_count: int) -> str:
    """Format byte count into human-readable representation."""
    val = float(bytes_count)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if val < 1024.0:
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{val:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds into a clean human-readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    rem_seconds = int(seconds % 60)

    if minutes < 60:
        return f"{minutes}m {rem_seconds:02d}s"

    hours = int(minutes // 60)
    rem_minutes = int(minutes % 60)
    return f"{hours}h {rem_minutes:02d}m {rem_seconds:02d}s"