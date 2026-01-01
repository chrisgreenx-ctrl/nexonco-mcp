"""HTTP server wrapper for Nexonco MCP Server deployment on Render."""

import os
import logging

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from .server import create_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def health_check(request):
    """Health check endpoint for Render."""
    return JSONResponse({"status": "healthy", "service": "nexonco-mcp"})


async def version_info(request):
    """Version information endpoint."""
    return JSONResponse({
        "name": "nexonco-mcp",
        "version": "0.1.21",
        "description": "Clinical Evidence MCP Server for Precision Oncology"
    })


async def root_info(request):
    """Root endpoint with API information."""
    return JSONResponse({
        "service": "nexonco-mcp",
        "version": "0.1.21",
        "endpoints": {
            "/mcp": "MCP Streamable HTTP endpoint",
            "/health": "Health check endpoint",
            "/version": "Version information"
        }
    })


def create_app() -> Starlette:
    """Create and configure the Starlette application with MCP endpoint."""

    # Create the MCP server instance
    mcp_server = create_server()

    # Get the Streamable HTTP app from FastMCP (already has /mcp endpoint)
    mcp_app = mcp_server.streamable_http_app()

    # Configure CORS middleware
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]

    # Define additional routes
    routes = [
        Route("/", root_info, methods=["GET"]),
        Route("/health", health_check, methods=["GET"]),
        Route("/version", version_info, methods=["GET"]),
        # Mount the MCP app at root since it already handles /mcp internally
        Mount("/", app=mcp_app),
    ]

    app = Starlette(
        debug=os.getenv("DEBUG", "false").lower() == "true",
        routes=routes,
        middleware=middleware,
        on_startup=[lambda: logger.info("Nexonco MCP HTTP Server starting...")],
        on_shutdown=[lambda: logger.info("Nexonco MCP HTTP Server shutting down...")],
    )

    return app


def main():
    """Entry point for the HTTP server."""
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting Nexonco MCP HTTP Server on {host}:{port}")
    logger.info(f"MCP endpoint available at: http://{host}:{port}/mcp")

    app = create_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
