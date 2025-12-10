"""
MCP Server Diagnostics
======================

Utilities for diagnosing MCP server health and connectivity.
"""

from typing import List


def diagnose_stuck_tool(tool_name: str, duration: float) -> List[str]:
    """
    Provide diagnostic suggestions for stuck tools.

    Args:
        tool_name: Name of the stuck tool
        duration: How long it's been running (seconds)

    Returns:
        List of diagnostic suggestions
    """
    suggestions = []

    if "linear" in tool_name.lower():
        suggestions.extend([
            "Linear MCP Server Issues:",
            "- Check Linear API status: https://status.linear.app",
            f"- Tool '{tool_name}' has been running for {duration:.0f}s",
            "- Large queries (limit > 100) can timeout",
            "- Try reducing query limit or filtering results",
            "- Check LINEAR_API_KEY is still valid",
        ])

    if "puppeteer" in tool_name.lower():
        suggestions.extend([
            "Puppeteer MCP Server Issues:",
            "- Check if browser process is hung",
            "- Page might be slow to load or unresponsive",
            "- Network requests on page might be timing out",
        ])

    if not suggestions:
        suggestions.extend([
            f"Tool '{tool_name}' has been running for {duration:.0f}s",
            "Possible causes:",
            "- Network connectivity issues",
            "- MCP server crash or hang",
            "- API rate limiting or timeout",
            "- Large response payload",
        ])

    suggestions.extend([
        "",
        "Recovery options:",
        "- Wait longer (some operations are legitimately slow)",
        "- Interrupt (Ctrl+C) and restart with different parameters",
        "- Check MCP server logs for errors",
        "- File a bug report if this persists",
    ])

    return suggestions
