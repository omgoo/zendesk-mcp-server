"""Zendesk MCP Server package"""

import asyncio


def main():
    """Entry point for the Zendesk MCP server"""
    from .server import main as server_main
    asyncio.run(server_main())


__version__ = "0.1.0"
__all__ = ["main"]
