#!/usr/bin/env python3
"""Private single-owner stdio MCP server; connect through an authorized tunnel."""
import os
from typing import Literal
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from private_capture import capture, load_config


def build_server(config_path):
    server = FastMCP('Connected Knowledge private capture', log_level='CRITICAL')

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                            idempotentHint=True, openWorldHint=False))
    def save_selected_capture(source: Literal['chatgpt', 'gemini-app', 'claude-app', 'manual'],
                              conversation_id: str, capture_id: str, title: str,
                              coverage: Literal['excerpt', 'summary', 'supplied-transcript'],
                              messages: list[dict]) -> dict:
        """Save only content explicitly selected by the user. Supply available text with stable message IDs and roles. Label summaries as summaries, excerpts as excerpts. Never claim full history access. Reuse returned/caller identities for retries and revisions; use a new capture_id for a separate selection. No destination or account arguments are accepted."""
        try:
            return capture(load_config(config_path), {
                'source': source, 'conversation_id': conversation_id,
                'capture_id': capture_id, 'title': title, 'coverage': coverage,
                'messages': messages}, apply=True)
        except Exception as exc:
            return {'status': 'error', 'error_type': type(exc).__name__}

    return server


if __name__ == '__main__':
    path = os.environ.get('CONNECTED_KNOWLEDGE_PRIVATE_CONFIG')
    if not path:
        raise SystemExit('Private configuration required')
    build_server(path).run(transport='stdio')
