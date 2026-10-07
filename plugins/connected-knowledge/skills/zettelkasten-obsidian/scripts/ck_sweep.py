#!/usr/bin/env python3
"""Capture queued sessions once they are idle or ended (standard library only).

Hooks only queue "this session changed". This sweep reads each transcript once,
under an OS lock that dies with its process, keeps one raw copy outside the vault
and writes one conversation note plus one transcript. A crash leaves the queue
entry in place, so the next sweep retries.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import ck_capture
import ck_config
import ck_transcripts

MAX_ATTEMPTS = 5
ATTENTION = ('diverged', 'conflict', 'elsewhere', 'deleted', 'failed')


def capture_file(cfg, host, transcript, overrides=None, apply=False, paths=None, recreate=False,
                 expected=None, require_scope=True):
    path = ck_transcripts.safe_transcript(transcript, cfg, host)
    raw = path.read_bytes()
    session = ck_transcripts.parse(raw, host, path.stem)
    if expected and expected not in session['session_ids']:
        raise ValueError('The transcript belongs to a different session')
    if require_scope and (not session['directories'] or ck_config.in_scope(cfg, session['directories'][0]) is None):
        return {'status': 'out-of-scope', 'reason': 'The session started outside your capture folders.',
                'platform': session['platform'], 'messages': len(session['messages'])}
    return ck_capture.capture(cfg, session, raw, overrides, apply, paths, recreate)


def remember(paths, entry, result):
    """Keep a short list of conversations that need a person's attention."""
    path = paths['root']/'attention.json'
    data = ck_config.read_json(path) if path.exists() else {}
    key = entry.get('host', '?') + ':' + entry.get('session_id', '?')
    if result.get('status') in ATTENTION:
        data[key] = {'status': result['status'], 'reason': result.get('reason', ''),
                     'title': result.get('title'), 'when': ck_transcripts.iso(time.time())}
    else:
        data.pop(key, None)
    ck_config.write_atomic(path, ck_config.dumps(data))


def sweep(cfg, now=None, only=None, paths=None):
    """Process the queue. ``only`` forces the listed session IDs regardless of idle time."""
    now = time.time() if now is None else now
    paths = paths or ck_config.state(cfg)
    idle = cfg.get('capture', {}).get('idle_minutes', 10) * 60
    report = {'status': 'done', 'captured': 0, 'unchanged': 0, 'waiting': 0, 'attention': 0, 'retry': 0, 'results': []}
    with ck_config.try_lock(paths['locks']/'capture.lock') as locked:
        if not locked:
            report['status'] = 'busy'
            return report
        for queue_file, entry in ck_config.queued(paths):
            if entry is None or entry.get('host') not in ck_config.HOSTS:
                queue_file.replace(paths['failed']/queue_file.name)
                continue
            if only and entry.get('session_id') not in only:
                continue
            transcript = Path(entry.get('transcript_path', ''))
            changed = max(entry.get('updated', 0), transcript.stat().st_mtime if transcript.is_file() else 0)
            if not only and not entry.get('ended') and now - changed < idle:
                report['waiting'] += 1
                continue
            try:
                result = capture_file(cfg, entry['host'], transcript, {'surface': entry.get('surface')}, True,
                                      paths, expected=entry.get('session_id'))
            except Exception as exc:  # retried by the next sweep, then parked
                entry['attempts'] = int(entry.get('attempts', 0)) + 1
                entry['last_error'] = type(exc).__name__ + ': ' + str(exc)[:200]
                if entry['attempts'] >= MAX_ATTEMPTS:
                    ck_config.write_atomic(paths['failed']/queue_file.name, ck_config.dumps(entry))
                    queue_file.unlink()
                    remember(paths, entry, {'status': 'failed', 'reason': entry['last_error']})
                    report['attention'] += 1
                else:
                    ck_config.write_atomic(queue_file, ck_config.dumps(entry))
                    report['retry'] += 1
                report['results'].append({'status': 'error', 'error': entry['last_error']})
                continue
            # A turn that ended while we were capturing re-queued the session; keep it for the next sweep.
            try:
                latest = ck_config.read_json(queue_file)
            except (OSError, ValueError):
                latest = entry
            if latest.get('events') == entry.get('events'):
                queue_file.unlink()
            remember(paths, entry, result)
            status = result['status']
            report['captured'] += status in ('created', 'updated')
            report['unchanged'] += status == 'unchanged'
            report['attention'] += status in ATTENTION
            report['results'].append({k: result.get(k) for k in ('status', 'title', 'note', 'reason') if result.get(k)})
    ck_config.write_atomic(paths['root']/'last-sweep.json',
                           ck_config.dumps(dict(report, finished=ck_transcripts.iso(time.time()), results=len(report['results']))))
    return report


def others_due(cfg, paths, current, now=None):
    """True when another queued session has ended or gone quiet (checked from queue files only)."""
    now = time.time() if now is None else now
    idle = cfg.get('capture', {}).get('idle_minutes', 10) * 60
    for queue_file, entry in ck_config.queued(paths):
        if queue_file.name == current or entry is None:
            continue
        if entry.get('ended') or now - entry.get('updated', now) >= idle:
            return True
    return False


def spawn(python=None):
    """Start a sweep in the background without making the host wait."""
    subprocess.Popen([python or sys.executable, str(Path(__file__).resolve()), '--quiet'],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    try:
        cfg = ck_config.load(args.config)
        if cfg is None or not cfg['capture'].get('enabled'):
            report = {'status': 'off'}
        else:
            report = sweep(cfg)
    except Exception as exc:
        if not args.quiet:
            print(json.dumps({'status': 'failed', 'error': str(exc)}), file=sys.stderr)
        return 1
    if not args.quiet:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
