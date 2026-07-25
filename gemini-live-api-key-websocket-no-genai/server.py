#!/usr/bin/env python3
"""Server for Gemini Live API (No google-genai SDK Dependency)
Serves static frontend files without google-genai dependency.
"""

import asyncio
import mimetypes
import os
from aiohttp import web

HTTP_PORT = 8000


async def serve_static_file(request):
    """Serve static files from the frontend directory."""
    path = request.match_info.get("path", "index.html")

    # Security: prevent directory traversal
    path = path.lstrip("/")
    if ".." in path:
        return web.Response(text="Invalid path", status=400)

    # Default to index.html
    if not path or path == "/":
        path = "index.html"

    # Get the full file path - serve from frontend folder
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    file_path = os.path.join(frontend_dir, path)

    # Check if file exists
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return web.Response(text="File not found", status=404)

    # Determine content type
    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = "application/octet-stream"

    # Read and serve the file
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        return web.Response(body=content, content_type=content_type)
    except Exception as e:
        print(f"Error serving file {path}: {e}")
        return web.Response(text="Internal server error", status=500)


async def main():
    """Starts the HTTP server."""
    app = web.Application()

    # Static files
    app.router.add_get("/", serve_static_file)
    app.router.add_get("/{path:.*}", serve_static_file)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await site.start()

    print(f"""
╔════════════════════════════════════════════════════════════╗
║    Gemini Live API Server (No google-genai dependency)    ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  📱 Web Interface: http://localhost:{HTTP_PORT:<5}                   ║
║                                                            ║
║  Instructions:                                             ║
║  1. Open http://localhost:{HTTP_PORT} in your browser              ║
║  2. Enter your Gemini API Key directly in the UI           ║
║  3. Click Connect to start!                                ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")

    # Keep the server running
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
