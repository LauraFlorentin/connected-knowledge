#!/usr/bin/env python3
"""Shared selected-content inbox; no provider history or network access."""
import argparse
import fcntl
import json
from pathlib import Path
import sys
from chat_import import atomic_write, digest, encoded, normalize, run

LIMIT = 1024 * 1024
SCRIPT_ROOT = Path(__file__).resolve().parent
PLUGIN = next((parent for parent in SCRIPT_ROOT.parents
               if (parent/'plugin.json').is_file() and (parent/'skills').is_dir()), SCRIPT_ROOT)
REPOSITORY = PLUGIN.parents[1] if PLUGIN.parent.name == 'plugins' else PLUGIN


def private_path(value):
    p = Path(value).expanduser()
    if not p.is_absolute() or any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('Use absolute non-symlink private paths')
    p = p.resolve()
    if p == REPOSITORY or p.is_relative_to(REPOSITORY):
        raise ValueError('Runtime data must be outside plugin source and installation')
    return p


def load_config(value):
    path = private_path(value)
    if path.stat().st_size > LIMIT:
        raise ValueError('Configuration too large')
    cfg = json.loads(path.read_bytes())
    if not isinstance(cfg, dict):
        raise ValueError('Configuration must be an object')
    return cfg


def settings(cfg):
    if cfg.get('enabled') is not True:
        raise ValueError('Capture is disabled')
    account = cfg.get('account')
    if not isinstance(account, str) or not account.strip():
        raise ValueError('Select a non-secret account label')
    spool, archive = (private_path(cfg[k]) for k in ('spool', 'destination'))
    if spool == archive or spool.is_relative_to(archive) or archive.is_relative_to(spool):
        raise ValueError('Spool and archive must be separate')
    return account, spool, archive


def validate(payload):
    if not isinstance(payload, dict) or len(encoded(payload)) > LIMIT:
        raise ValueError('Invalid or oversized capture')
    for k in ('source', 'conversation_id', 'capture_id', 'title'):
        if not isinstance(payload.get(k), str) or not payload[k].strip() or len(payload[k]) > 512:
            raise ValueError('Missing bounded capture identity')
    if payload['source'] not in ('chatgpt', 'gemini-app', 'gemini-cli', 'claude-app', 'manual'):
        raise ValueError('Unsupported source')
    if payload.get('coverage') not in ('excerpt', 'summary', 'supplied-transcript', 'completed-turn'):
        raise ValueError('Select accurate coverage')
    record = {'id': digest(encoded([payload['source'], payload['conversation_id'], payload['capture_id']])),
              'title': payload['title'], 'messages': payload.get('messages'),
              'coverage': payload['coverage'], 'capture_provenance': {
                  k: payload[k] for k in ('source', 'conversation_id', 'capture_id', 'coverage')}}
    normalize(record, 'normalized')
    if not record['messages']:
        raise ValueError('Capture has no supplied content')
    for message in record['messages']:
        if message.get('role') not in ('user', 'assistant', 'system', 'unknown') or not isinstance(message.get('text'), str):
            raise ValueError('Supply explicit text and role for each message')
    return record


def capture(cfg, payload, apply=False):
    account, spool, archive = settings(cfg)
    record = validate(payload)
    template = None
    if cfg.get('template'):
        path = Path(cfg['template']).expanduser()
        if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)) or path.stat().st_size > LIMIT:
            raise ValueError('Select an absolute bounded non-symlink Markdown template')
        template = path.read_text()
        from capture_template import apply_template
        from chat_import import render
        apply_template(template, render(normalize(record, 'normalized'), 'normalized', account,
                                        'originals/preview.json', {}, cfg.get('vocabulary', 'existing')), record['id'])
    receipt = {'status': 'preview', 'coverage': payload['coverage'],
               'receipt': digest(encoded([account, record['id']])), 'messages': len(record['messages'])}
    if not apply:
        return receipt
    spool.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = private_path(str(spool / '.private-capture.lock'))
    # OS releases this lock after process termination; no stale sentinel recovery.
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        data = encoded([record])
        source = private_path(str(spool / (digest(data) + '.json')))
        if source.exists() and source.read_bytes() != data:
            raise ValueError('Spool integrity failure')
        if not source.exists():
            atomic_write(source, data)
        report = run(source, archive, 'normalized', account, True,
                     vocabulary=cfg.get('vocabulary', 'existing'), template=template,
                     readable_names=cfg.get('readable_names', True), lock_directory=spool)
        if report['failed'] or report['conflicts']:
            raise ValueError('Archive conflict; reconcile privately')
        receipt.update(status='saved' if report['written'] else 'unchanged', written=report['written'])
        receipt['notes'] = [item['path'] for item in report['items'] if 'path' in item]
        return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    try:
        cfg = load_config(args.config)
        settings(cfg)  # Disabled configurations do not consume supplied content.
        raw = sys.stdin.read(LIMIT + 1)
        if len(raw.encode('utf-8')) > LIMIT:
            raise ValueError('Capture too large')
        print(json.dumps(capture(cfg, json.loads(raw), args.apply)))
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error_type': type(exc).__name__}))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
