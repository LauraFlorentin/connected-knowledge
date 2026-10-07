#!/usr/bin/env python3
"""Hook entry point: standard library only, inert until /ck-setup switches capture on.

With a machine configuration (~/.config/connected-knowledge/config.json) the hook
only queues "this session changed" and never opens a transcript; a background
sweep captures the session once it is idle. Without one, the older opt-in
environment-variable configuration (1.3–1.6) still works unchanged.
"""
import json
import os
from pathlib import Path
import sys

LIMIT = 1024 * 1024
PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN/'skills/zettelkasten-obsidian/scripts'


def private_path(value):
    p = Path(value).expanduser()
    if not p.is_absolute() or any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('Use absolute, non-symlink private paths')
    p = p.resolve()
    if p == PLUGIN or PLUGIN in p.parents:
        raise ValueError('Configuration and output must be outside the installed plugin')
    return p


def read_event():
    payload = sys.stdin.read(LIMIT+1)
    if len(payload) > LIMIT:
        raise ValueError('Hook event exceeds size limit')
    event = json.loads(payload)
    if not isinstance(event,dict):
        raise ValueError('Hook event must be an object')
    return event


def queue(host, cfg):
    """Record the session in this machine's queue; never read the transcript."""
    import ck_config
    capture = cfg['capture']
    if not capture.get('enabled') or host not in capture.get('hosts', []):
        return 0
    event = read_event()
    name = event.get('hook_event_name')
    if event.get('agent_id') or event.get('agent_transcript_path'):
        return 0
    import ck_sweep
    if name in ('Stop', 'SessionEnd'):
        if not all(isinstance(event.get(k),str) and event[k] for k in ('cwd','session_id','transcript_path')):
            raise ValueError('Hook event identity or transcript path missing')
        if not Path(event['transcript_path']).is_absolute():
            raise ValueError('Transcript path must be absolute')
        if ck_config.in_scope(cfg, event['cwd']) is None:
            return 0
        paths = ck_config.state(cfg)
        queued = ck_config.enqueue(paths, host, event, os.environ.get('CLAUDE_CODE_ENTRYPOINT'))
        # During one long session, sessions that went quiet elsewhere still get saved.
        if name == 'Stop' and ck_sweep.others_due(cfg, paths, queued.name):
            ck_sweep.spawn()
    if name in ('SessionStart', 'SessionEnd'):
        ck_sweep.spawn()
    return 0


def legacy(host):
    variable = 'CONNECTED_KNOWLEDGE_CODEX_CONFIG' if host == 'codex' else 'CONNECTED_KNOWLEDGE_CLAUDE_CODE_CONFIG'
    location = os.environ.get(variable)
    if not location:
        return 0
    path = private_path(location)
    if not path.exists():
        return 0
    if path.stat().st_size > LIMIT:
        raise ValueError('Capture config exceeds size limit')
    cfg = json.loads(path.read_text())
    if not isinstance(cfg,dict):
        raise ValueError('Capture configuration must be an object')
    if cfg.get('enabled') is not True:
        return 0
    if cfg.get('host') != host:
        raise ValueError('Capture configuration belongs to a different host')
    event = read_event()
    if event.get('hook_event_name') not in ('Stop','SessionEnd') or event.get('agent_id') or event.get('agent_transcript_path'):
        return 0
    if not all(isinstance(event.get(k),str) and event[k] for k in ('cwd','session_id','transcript_path')):
        raise ValueError('Hook event identity or transcript path missing')
    if not Path(event['cwd']).is_absolute():
        raise ValueError('Hook project must be absolute')
    projects = cfg.get('projects',[])
    if not projects or any(not isinstance(p,str) or not Path(p).is_absolute() for p in projects):
        raise ValueError('Select absolute project directories')
    if Path(event['cwd']).resolve() not in {Path(p).resolve() for p in projects}:
        return 0
    for field in ('spool','destination'):
        private_path(cfg[field])
    # No third-party imports or transcript access occur before the opt-in gates.
    try:
        from session_capture import capture
    except ImportError as exc:
        raise ValueError('Capture Python dependencies missing; configure CONNECTED_KNOWLEDGE_PYTHON') from exc
    capture(cfg,event['transcript_path'],apply=True,event=event)
    return 0


def main():
    # Codex also supplies CLAUDE_PLUGIN_ROOT; its own variable distinguishes it.
    host = 'codex' if os.environ.get('PLUGIN_ROOT') else 'claude-code' if os.environ.get('CLAUDE_PLUGIN_ROOT') else None
    if host is None:
        return 0
    sys.path.insert(0, str(SCRIPTS))
    import ck_config
    cfg = ck_config.load()
    if cfg is not None:
        return queue(host, cfg)
    return legacy(host)


if __name__ == '__main__':
    try:
        code = main()
    except Exception as exc:
        # Avoid printing exported identifiers, paths or message content in host logs.
        print('Connected Knowledge capture failed ('+type(exc).__name__+'); run /ck-help or a manual preview.',file=sys.stderr)
        code = 1
    print('{}')
    sys.exit(code)
