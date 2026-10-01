#!/usr/bin/env python3
"""Gemini AfterAgent selected-workspace opt-in bootstrap, without transcript reads."""
import json
import os
from pathlib import Path
import sys

LIMIT = 1024 * 1024


def main():
    location = os.environ.get('CONNECTED_KNOWLEDGE_GEMINI_CONFIG')
    if not location:
        return
    scripts = Path(__file__).resolve().parents[1] / 'skills/zettelkasten-obsidian/scripts'
    # Validate private opt-in using stdlib before importing PyYAML-dependent core.
    path = Path(location).expanduser()
    plugin = Path(__file__).resolve().parents[1]
    repository = plugin.parents[1] if plugin.parent.name == 'plugins' else plugin
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)) or path.resolve().is_relative_to(repository):
        raise ValueError('Invalid private configuration')
    if path.stat().st_size > LIMIT:
        raise ValueError('Configuration too large')
    cfg = json.loads(path.read_bytes())
    if cfg.get('enabled') is not True:
        return
    if cfg.get('host') != 'gemini-cli':
        raise ValueError('Wrong host')
    raw = sys.stdin.read(LIMIT + 1)
    if len(raw.encode()) > LIMIT:
        raise ValueError('Event too large')
    event = json.loads(raw)
    if event.get('hook_event_name') != 'AfterAgent' or event.get('stop_hook_active'):
        return
    projects = cfg.get('projects', [])
    if not projects or any(not isinstance(p, str) or not Path(p).is_absolute() for p in projects):
        raise ValueError('Select absolute workspaces')
    cwd = event.get('cwd')
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        raise ValueError('Missing workspace')
    if Path(cwd).resolve() not in {Path(p).resolve() for p in projects}:
        return
    for key in ('session_id', 'timestamp', 'prompt', 'prompt_response'):
        if not isinstance(event.get(key), str) or not event[key]:
            raise ValueError('Incomplete completed event')
    sys.path.insert(0, str(scripts))
    from private_capture import capture
    capture(cfg, {'source': 'gemini-cli', 'conversation_id': event['session_id'],
                  'capture_id': event['timestamp'], 'title': 'Gemini CLI completed turn',
                  'coverage': 'completed-turn', 'messages': [
                      {'id': 'user', 'role': 'user', 'text': event['prompt']},
                      {'id': 'assistant', 'role': 'assistant', 'text': event['prompt_response']}]}, True)


if __name__ == '__main__':
    try:
        main()
        code = 0
    except Exception as exc:
        print('Connected Knowledge Gemini capture failed (' + type(exc).__name__ + ').', file=sys.stderr)
        code = 1
    print('{}')
    sys.exit(code)
