#!/usr/bin/env python3
"""Private single-owner stdio MCP server; connect through an authorized tunnel."""
import os
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from private_capture import capture, load_config


class SelectedMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=512, description='Stable caller or host message identifier; reuse on retries.')
    role: Literal['user', 'assistant', 'system', 'unknown']
    text: str = Field(description='Exact user-selected text. Use this field, not content.')
    date: str | int | float | None = Field(default=None, description='Original source timestamp when actually available; never invent a date.')
    parent: str | None = Field(default=None, description='Original parent message ID when available.')


def build_server(config_path):
    server = FastMCP('Connected Knowledge private capture', log_level='CRITICAL')

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                            idempotentHint=True, openWorldHint=False))
    def save_selected_capture(source: Literal['chatgpt', 'gemini-app', 'claude-app', 'manual'],
                              conversation_id: str, capture_id: str, title: str,
                              coverage: Literal['excerpt', 'summary', 'supplied-transcript'],
                              messages: list[SelectedMessage]) -> dict:
        """Save only content explicitly selected by the user. Supply available text with stable message IDs and roles. Label summaries as summaries, excerpts as excerpts. Never claim full history access. Reuse returned/caller identities for retries and revisions; use a new capture_id for a separate selection. No destination or account arguments are accepted."""
        try:
            return capture(load_config(config_path), {
                'source': source, 'conversation_id': conversation_id,
                'capture_id': capture_id, 'title': title, 'coverage': coverage,
                'messages': [message.model_dump(exclude_none=True) for message in messages]}, apply=True)
        except Exception as exc:
            hints = {'Capture is disabled': 'Enable selected capture in your private configuration.',
                     'Archive conflict; reconcile privately': 'A note or preserved original changed. Review it locally; no content was overwritten.',
                     'Supply explicit text and role for each message': 'Each message needs id, role, and text fields.'}
            return {'status': 'error', 'error_type': type(exc).__name__,
                    'hint': hints.get(str(exc), 'Check the private configuration, selected template, and local archive. No source content is included in this error.')}

    return server


if __name__ == '__main__':
    path = os.environ.get('CONNECTED_KNOWLEDGE_PRIVATE_CONFIG')
    if not path:
        raise SystemExit('Private configuration required')
    build_server(path).run(transport='stdio')
