#!/usr/bin/env python3
"""Connected Knowledge commands: doctor, setup, capture, add-session, topics, migrate.

Behind /ck-setup, /ck-help and /ck-add-session on every host. Prints JSON.
Everything previews by default; ``--apply`` writes. Standard library only,
except ``migrate``, which reads 1.6.0 archives with the importer.
"""
import argparse
from contextlib import nullcontext
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

import ck_capture
import ck_config
import ck_render
import ck_sweep
import ck_transcripts

SCRIPTS = Path(__file__).resolve().parent
PLUGIN = SCRIPTS.parents[2]
EXPORT_DAYS = 35
VENDORS = {'claude': 'Claude', 'openai': 'ChatGPT', 'google': 'Google (Gemini)'}


def version():
    try:
        return json.loads((PLUGIN/'.claude-plugin/plugin.json').read_text())['version']
    except (OSError, ValueError, KeyError):
        return 'unknown'


def now_iso():
    return ck_transcripts.iso(time.time())


def read_state_json(cfg, name, default):
    path = Path(cfg['state'])/name
    try:
        return ck_config.read_json(path) if path.exists() else default
    except (ValueError, OSError):
        return default


def write_state_json(cfg, name, data):
    paths = ck_config.state(cfg)
    ck_config.write_atomic(paths['root']/name, ck_config.dumps(data))


# ------------------------------------------------------------------ doctor

def doctor(cfg_path=None, suggest=False):
    path = Path(cfg_path) if cfg_path else ck_config.config_path()
    report = {'version': version(), 'python': '.'.join(map(str, sys.version_info[:3])),
              'python_ok': {'capture': sys.version_info >= (3, 9), 'tools': sys.version_info >= (3, 10)},
              'config': str(path) if path.exists() else None,
              'legacy_hook_configs': sorted(k for k in os.environ if k.startswith('CONNECTED_KNOWLEDGE_') and k.endswith('_CONFIG'))}
    try:
        cfg = ck_config.load(path)
    except ValueError as exc:
        report['config_error'] = str(exc)
        cfg = None
    if cfg is None:
        report['state'] = 'not-set-up'
        if suggest:
            report['next'] = next_steps(report)
        return report
    vault = Path(cfg['vault'])
    report.update(machine=cfg['machine'], role=cfg['role'])
    report['vault'] = {'path': str(vault), 'reachable': vault.is_dir()}
    capture = cfg['capture']
    queue_dir, failed_dir = Path(cfg['state'])/'queue', Path(cfg['state'])/'failed'
    report['capture'] = {'enabled': capture.get('enabled', False), 'hosts': capture.get('hosts', []),
                         'folders': len(capture.get('roots', [])),
                         'queued': len(list(queue_dir.glob('*.json'))) if queue_dir.is_dir() else 0,
                         'parked': len(list(failed_dir.glob('*.json'))) if failed_dir.is_dir() else 0,
                         'last_sweep': read_state_json(cfg, 'last-sweep.json', {}).get('finished')}
    manifest = read_state_json(cfg, 'manifest.json', {'items': {}})
    items = manifest.get('items', {})
    report['captured'] = len(items)
    report['unlabelled'] = sum(1 for item in items.values() if not item.get('category'))
    report['attention'] = read_state_json(cfg, 'attention.json', {})
    report['backfill'] = read_state_json(cfg, 'backfill.json', {}).get('finished')
    exports = read_state_json(cfg, 'exports.json', {})
    report['exports'] = {}
    for vendor in cfg.get('accounts', {}):
        if vendor in VENDORS:
            last = exports.get(vendor)
            age = None
            if last:
                age = int((time.time() - datetime.fromisoformat(last).timestamp()) // 86400)
            report['exports'][vendor] = {'last_import': last, 'days_ago': age}
    if report['vault']['reachable']:
        try:
            profile = ck_config.load_profile(vault)
            report['vault']['profile'] = profile['present']
            report['vault']['variant'] = profile.get('variant')
            report['topics'] = sorted(Path(p).name for p in ck_capture.find_maps(vault, profile).values())
        except ValueError as exc:
            report['vault']['profile_error'] = str(exc)
    report['state'] = 'ready' if report['vault']['reachable'] else 'vault-unreachable'
    if suggest:
        report['next'] = next_steps(report)
    return report


def next_steps(report):
    """One suggestion, one alternative and "stop here", chosen from the actual state."""
    options = []
    if report['state'] == 'not-set-up':
        options.append({'command': '/ck-setup', 'why': 'Connected Knowledge is not set up on this Mac yet.'})
    elif report['state'] == 'vault-unreachable':
        options.append({'command': '/ck-setup vault', 'why': 'The vault folder cannot be reached from this Mac.'})
    else:
        if report['captured'] == 0:
            options.append({'command': '/ck-add-session current', 'why': 'Nothing is captured yet; save this conversation as a first trial.'})
        if not report.get('backfill'):
            options.append({'command': '/ck-add-session all', 'why': 'Older local sessions on this Mac are not saved yet, and hosts delete old transcripts.'})
        if report.get('role') == 'hub':
            for vendor, info in sorted(report.get('exports', {}).items()):
                if info['days_ago'] is None or info['days_ago'] > EXPORT_DAYS:
                    when = 'has never been imported' if info['days_ago'] is None else 'was last imported ' + str(info['days_ago']) + ' days ago'
                    options.append({'command': 'ask: import my ' + VENDORS[vendor] + ' export',
                                    'why': 'Your ' + VENDORS[vendor] + ' account export ' + when + '.'})
                    break
        if report.get('unlabelled'):
            options.append({'command': 'ask: classify my unlabelled conversations',
                            'why': str(report['unlabelled']) + ' conversations have no category yet.'})
        if not report['capture']['enabled']:
            options.append({'command': '/ck-setup capture', 'why': 'Automatic capture is off on this Mac.'})
        options.append({'command': 'ask: develop one conversation into notes',
                        'why': 'Turn a saved conversation into linked idea and decision notes.'})
    first = options[0]
    alternative = options[1] if len(options) > 1 else None
    return {'suggestion': first, 'alternative': alternative, 'stop': 'stop here'}


# ------------------------------------------------------------------ setup

def scan_vault(vault, limit=2000):
    """Read-only look at an existing vault: property names, values and folders."""
    names, values, folders, guide = {}, {}, set(), None
    for path in sorted(vault.rglob('*.md'))[:limit]:
        relative = path.relative_to(vault)
        if any(part.startswith('.') for part in relative.parts) or path.is_symlink():
            continue
        if len(relative.parts) > 1:
            folders.add(relative.parts[0])
        if relative.as_posix().casefold() in ('vault guide.md', 'vault-guide.md'):
            guide = relative.as_posix()
        try:
            meta, _ = ck_render.split_note(path.read_text(encoding='utf-8'))
        except (ck_render.FrontmatterError, UnicodeDecodeError, OSError):
            continue
        for key, value in meta.items():
            names[key] = names.get(key, 0) + 1
            if isinstance(value, str) and len(value) <= 40:
                values.setdefault(key, {})
                values[key][value] = values[key].get(value, 0) + 1
    return {'properties': names, 'values': values, 'folders': sorted(folders), 'guide': guide}


def propose_adoption(vault):
    """Map the plugin's labels onto the names an existing vault already uses."""
    scan = scan_vault(vault)
    fields, values = {}, {}
    seen = scan['values']
    if 'type' in scan['properties'] and 'note_type' not in scan['properties']:
        fields['note_type'] = 'type'
        known = seen.get('type', {})
        mapping = {}
        if 'reference' in known and 'source' not in known:
            mapping['source'] = 'reference'
        if mapping:
            values['note_type'] = mapping
    if 'status' in scan['properties'] and 'review_status' not in scan['properties']:
        fields['review_status'] = 'status'
        if 'auto' in seen.get('status', {}) and 'draft' not in seen.get('status', {}):
            values['review_status'] = {'draft': 'auto'}
    folders = dict(ck_config.DEFAULT_FOLDERS)
    if 'Sources' not in scan['folders'] and 'Inbox' in scan['folders']:
        folders['sessions'] = 'Inbox/AI Conversations'
    categories = sorted(seen.get('category', {})) or list(ck_config.DEFAULT_CATEGORIES)
    profile = {'schema': 1, 'variant': 'adopted', 'fields': fields, 'values': values,
               'folders': folders, 'categories': categories, 'projects': {}}
    additions = ['_meta/ck/vault.json'] + [folders[k] for k in ('sessions', 'transcripts', 'index')
                                            if not (vault/folders[k]).exists()]
    paragraph = ('## AI history\n\nConnected Knowledge saves one short note per AI conversation in `'
                 + folders['sessions'] + '/` and the full transcript in `' + folders['transcripts']
                 + '/`. It rewrites only the block between the `ck:begin` and `ck:end` comments in those '
                 'notes. Transcripts are generated; do not edit them.\n')
    return {'scan': {k: scan[k] for k in ('folders', 'guide')}, 'property_names': sorted(scan['properties']),
            'profile': profile, 'additions': additions, 'guide': scan['guide'], 'guide_paragraph': paragraph}


def machine_config(answers, existing=None):
    capture = dict({'enabled': False, 'hosts': ['claude-code', 'codex'], 'roots': [], 'exclude': [],
                    'idle_minutes': 10, 'default_remote_device': None},
                   **(existing or {}).get('capture', {}), **answers.get('capture', {}))
    cfg = {'schema': 1, 'machine': answers.get('machine') or (existing or {}).get('machine'),
           'role': answers.get('role') or (existing or {}).get('role') or 'hub',
           'vault': str(Path(answers.get('vault') or (existing or {}).get('vault', '')).expanduser()),
           'state': str(Path(answers.get('state') or (existing or {}).get('state') or ck_config.default_state()).expanduser()),
           'accounts': answers.get('accounts', (existing or {}).get('accounts', {'claude': 'personal', 'openai': 'personal'})),
           'capture': capture}
    if answers.get('python') or (existing or {}).get('python'):
        cfg['python'] = answers.get('python') or existing.get('python')
    return ck_config.validate(cfg)


def setup(answers, apply=False, cfg_path=None):
    path = Path(cfg_path) if cfg_path else ck_config.config_path()
    existing = ck_config.load(path) if path.exists() else None
    cfg = machine_config(answers, existing)
    vault = Path(cfg['vault'])
    mode = answers.get('vault_mode', 'existing' if vault.exists() else 'new')
    plan = {'mode': 'apply' if apply else 'preview', 'config_file': str(path), 'config': cfg,
            'replaces_config': existing is not None, 'vault_mode': mode,
            'python3_on_path': shutil.which('python3')}
    if mode == 'new':
        import starter_vault
        new = answers.get('new_vault', {})
        files = starter_vault.files(new.get('ontology', 'default'), new.get('categories'), new.get('variant', 'no-templates'),
                                    new.get('structure', 'full'), new.get('topics'))
        if vault.exists():
            raise ValueError('A new vault needs a folder that does not exist yet')
        plan['vault'] = {'folders': sorted(k for k, v in files.items() if v is None),
                         'files': sorted(k for k, v in files.items() if v is not None)}
    elif mode == 'existing':
        if not vault.is_dir():
            raise ValueError('The existing vault folder was not found; check the path')
        proposal = propose_adoption(vault)
        if answers.get('adopt'):
            proposal['profile'].update(answers['adopt'])
        ck_config.validate_profile(proposal['profile'])
        present = (vault/ck_config.PROFILE).exists()
        plan['vault'] = dict(proposal, keeps_existing_profile=present)
        plan['vault']['update_guide'] = bool(answers.get('update_guide') and proposal['guide'])
    else:
        raise ValueError('vault_mode must be new or existing')
    if not apply:
        return plan
    if existing is not None:
        backup = path.with_name('config.json.bak-' + time.strftime('%Y%m%d%H%M%S'))
        shutil.copy2(str(path), str(backup))
        plan['config_backup'] = str(backup)
    if mode == 'new':
        new = answers.get('new_vault', {})
        starter_vault.create(vault, True, new.get('ontology', 'default'), new.get('categories'),
                             new.get('variant', 'no-templates'), new.get('structure', 'full'), new.get('topics'))
    else:
        profile_file = ck_config.vault_path(vault, ck_config.PROFILE)
        if not profile_file.exists():
            ck_config.write_atomic(profile_file, json.dumps(plan['vault']['profile'], indent=2, ensure_ascii=False) + '\n', 0o644)
        for key in ('sessions', 'transcripts', 'index'):
            ck_config.vault_path(vault, plan['vault']['profile']['folders'][key]).mkdir(parents=True, exist_ok=True)
        if plan['vault']['update_guide']:
            guide = ck_config.vault_path(vault, plan['vault']['guide'])
            text = guide.read_text(encoding='utf-8')
            if '## AI history' not in text:
                ck_config.write_atomic(guide, text.rstrip('\n') + '\n\n' + plan['vault']['guide_paragraph'], 0o644)
    ck_config.save(cfg, path)
    ck_config.state(cfg)
    return plan


def capture_switch(on, hosts=None, cfg_path=None, apply=False):
    path = Path(cfg_path) if cfg_path else ck_config.config_path()
    cfg = ck_config.load(path)
    if cfg is None:
        raise ValueError('Run /ck-setup first')
    cfg['capture']['enabled'] = on
    if hosts:
        cfg['capture']['hosts'] = hosts
    ck_config.validate(cfg)
    result = {'mode': 'apply' if apply else 'preview', 'capture': cfg['capture']['enabled'],
              'hosts': cfg['capture']['hosts'], 'folders': cfg['capture']['roots']}
    if on and not shutil.which('python3') and not os.environ.get('CONNECTED_KNOWLEDGE_PYTHON'):
        result['warning'] = 'python3 was not found on PATH; hooks would show an error on every turn.'
    if apply:
        ck_config.save(cfg, path)
    return result


# ------------------------------------------------------------- add-session

def host_of(path, cfg):
    for host in ck_config.HOSTS:
        if any(ck_config.inside(path, root) for root in ck_config.transcript_roots(cfg, host)):
            return host
    raise ValueError('That file is not in a Claude Code or Codex transcript folder')


def locate(cfg, target, session_id=None, cwd=None, host=None):
    hosts = [host] if host else list(ck_config.HOSTS)
    if target in (None, 'current'):
        candidates = []
        for h in hosts:
            found = ck_transcripts.find(cfg, h, session_id=session_id) if session_id else \
                ck_transcripts.find(cfg, h, directory=cwd or os.getcwd())
            if found:
                candidates.append((found.stat().st_mtime, h, found))
        if not candidates:
            raise ValueError('No transcript for the current session was found on this Mac')
        _, h, found = max(candidates)
        return h, found
    if target == 'latest':
        candidates = [(p.stat().st_mtime, h, p) for h in hosts for p in ck_transcripts.all_transcripts(cfg, h)[:1]]
        if not candidates:
            raise ValueError('No local transcripts were found')
        _, h, found = max(candidates)
        return h, found
    if target.endswith('.jsonl') or '/' in target:
        path = Path(target).expanduser()
        return host or host_of(path, cfg), path
    for h in hosts:
        found = ck_transcripts.find(cfg, h, session_id=target)
        if found:
            return h, found
    raise ValueError('No transcript with that session ID was found')


def add_session(cfg, target='current', overrides=None, apply=False, session_id=None, cwd=None, host=None):
    overrides = {k: v for k, v in (overrides or {}).items() if v}
    if target == 'all':
        return backfill(cfg, apply, host)
    h, path = locate(cfg, target, session_id, cwd, host)
    if not apply:
        return ck_sweep.capture_file(cfg, h, path, overrides, False, require_scope=False)
    paths = ck_config.state(cfg)
    for _ in range(60):
        with ck_config.try_lock(paths['locks']/'capture.lock') as locked:
            if locked:
                return ck_sweep.capture_file(cfg, h, path, overrides, True, paths, recreate=True, require_scope=False)
        time.sleep(0.5)
    raise ValueError('Another capture is running; try again in a minute')


def backfill(cfg, apply=False, host=None):
    """Every local transcript in the capture folders that is not saved yet."""
    report = {'mode': 'apply' if apply else 'preview', 'found': 0, 'new': 0, 'out_of_scope': 0,
              'failed': 0, 'written': 0, 'examples': []}
    paths = ck_config.state(cfg) if apply else None
    with (ck_config.try_lock(paths['locks']/'capture.lock') if apply else nullcontext(True)) as locked:
        if not locked:
            raise ValueError('Another capture is running; try again in a minute')
        for h in [host] if host else cfg['capture'].get('hosts') or list(ck_config.HOSTS):
            for path in ck_transcripts.all_transcripts(cfg, h):
                report['found'] += 1
                start = ck_transcripts.first_directory(path)
                if not start or ck_config.in_scope(cfg, start) is None:
                    report['out_of_scope'] += 1
                    continue
                try:
                    result = ck_sweep.capture_file(cfg, h, path, None, apply, paths)
                except ValueError:
                    report['failed'] += 1
                    continue
                if result['status'] == 'unchanged':
                    continue
                report['new'] += result['status'] in ('preview', 'created', 'updated')
                report['written'] += result['status'] in ('created', 'updated')
                if len(report['examples']) < 10:
                    report['examples'].append({k: result.get(k) for k in ('status', 'title', 'project', 'messages')})
    if apply:
        write_state_json(cfg, 'backfill.json', {'finished': now_iso(), 'written': report['written']})
    return report


# ------------------------------------------------------------------ topics

def topics(cfg):
    vault = Path(cfg['vault'])
    profile = ck_config.load_profile(vault)
    tree = {}
    for link in ck_capture.find_maps(vault, profile).values():
        try:
            meta, _ = ck_render.split_note(ck_config.vault_path(vault, link + '.md').read_text(encoding='utf-8'))
        except ck_render.FrontmatterError:
            meta = {}
        parents = [str(t)[2:-2] for t in (meta.get('topics') or []) if str(t).startswith('[[')]
        tree[Path(link).name] = {'map': link, 'parent': Path(parents[0]).name if parents else None}
    return {'topics': tree, 'main': sorted(name for name, t in tree.items() if not t['parent'])}


def topic_add(cfg, name, parent=None, apply=False):
    import starter_vault
    name = starter_vault.check_topics([name])[0]
    vault = Path(cfg['vault'])
    profile = ck_config.load_profile(vault)
    maps = ck_capture.find_maps(vault, profile)
    if name.casefold() in maps:
        raise ValueError('That topic already exists')
    link = profile['folders']['maps'] + '/' + name
    text = starter_vault.topic_map(name, now_iso())
    if parent:
        parent_link = ck_capture.resolve_topics(vault, profile, [parent])[0]
        text = text.replace('topics: []', 'topics:\n  - "[[' + parent_link + ']]"', 1)
        listing, heading = ck_config.vault_path(vault, parent_link + '.md'), '## Subtopics'
    else:
        listing, heading = ck_config.vault_path(vault, 'Home.md'), '## Main topics'
    result = {'mode': 'apply' if apply else 'preview', 'create': link + '.md',
              'list_in': listing.relative_to(vault.resolve()).as_posix() if listing.exists() else None}
    if not apply:
        return result
    target = ck_config.vault_path(vault, link + '.md')
    ck_config.write_atomic(target, text, 0o644)
    if listing.exists():
        current = listing.read_text(encoding='utf-8')
        entry = '- [[' + link + '|' + name + ']]'
        if heading in current and entry not in current:
            current = current.replace(heading + '\n', heading + '\n' + entry + '\n', 1)
            ck_config.write_atomic(listing, current, 0o644)
        elif heading not in current:
            result['note'] = 'Add a link to the new topic in ' + result['list_in'] + ' by hand.'
    return result


# ----------------------------------------------------------------- migrate

LEGACY_HOSTS = {'claude': ('claude', 'Claude'), 'chatgpt': ('chatgpt', 'ChatGPT')}


def legacy_session(source, record, cfg):
    import chat_import
    if source in LEGACY_HOSTS:
        host, platform = LEGACY_HOSTS[source]
        chat = chat_import.normalize(record, source)
        native, surface = chat['id'], 'account-export'
    else:
        chat = chat_import.normalize(record, 'normalized')
        host, _, native = chat['id'].partition(':')
        if host not in ck_transcripts.PLATFORMS or not native:
            raise ValueError('Not a migratable conversation: ' + chat['id'])
        platform, surface = ck_transcripts.PLATFORMS[host], None
        raw = record.get('raw_snapshot')
        if raw and Path(raw).is_file():
            # The private spool still holds the original transcript: read it exactly as a live capture would.
            raw_bytes = Path(raw).read_bytes()
            return ck_transcripts.parse(raw_bytes, host, native), raw_bytes, '.jsonl'
    roles = {'human': 'user', 'user': 'user', 'assistant': 'assistant'}
    messages = [{'id': m['id'], 'role': roles[m['role']], 'text': m['text'] or '',
                 'time': ck_transcripts.iso(m.get('date'))}
                for m in chat['messages'] if m.get('role') in roles and (m.get('text') or '').strip()]
    times = [m['time'] for m in messages if m['time']]
    session = {'host': host, 'platform': platform, 'native_id': native, 'session_ids': [native],
               'messages': messages, 'directories': [], 'titles': {'custom': chat['title']} if chat['title'] != 'Untitled conversation' else {},
               'created': ck_transcripts.iso(chat.get('created')) or (times[0] if times else None),
               'updated': ck_transcripts.iso(chat.get('updated')) or (times[-1] if times else None),
               'surface': surface, 'coverage': 'full_export', 'skipped': {}}
    return session, json.dumps(record, ensure_ascii=False, sort_keys=True).encode('utf-8'), '.json'


def migrate(cfg, archive, apply=False):
    """Move a 1.6.0 archive (ChatArchive/…) to conversation notes. The old folder is left as it is."""
    import yaml
    from chat_import import digest
    archive = Path(archive).expanduser().resolve()
    state = json.loads((archive/'manifest.json').read_bytes())
    if state.get('version') != 1:
        raise ValueError('Not a 1.6.0 archive manifest')
    report = {'mode': 'apply' if apply else 'preview', 'archive': str(archive), 'migrated': 0,
              'unchanged': 0, 'human_edited': [], 'failed': [], 'items': []}
    paths = ck_config.state(cfg) if apply else None
    originals = {}
    for key, entry in sorted(state['records'].items()):
        note = archive/entry['path']
        try:
            data = note.read_bytes()
            if digest(data) != entry['sha256']:
                report['human_edited'].append(entry['path'])
                continue
            meta = yaml.safe_load(data.decode('utf-8').split('---', 2)[1])
            original = archive/(entry.get('original') or meta['source_file'])
            if original not in originals:
                originals[original] = json.loads(original.read_bytes())
            # 1.7.0 archives keep identity in the manifest; 1.6.0 notes carry it as properties.
            source = entry.get('platform') or meta['conversation_source']
            cid = entry.get('conversation_id') or meta['conversation_id']
            matches = [r for r in originals[original] if (r.get('uuid') if source == 'claude'
                                                          else r.get('id', r.get('conversation_id'))) == cid]
            if len(matches) != 1:
                raise ValueError('Original conversation missing or ambiguous')
            if matches[0].get('capture_provenance'):
                raise ValueError('Selected saves stay in their inbox; they are not migrated')
            session, raw, suffix = legacy_session(source, matches[0], cfg)
            result = ck_capture.capture(cfg, session, raw, None, apply, paths, raw_suffix=suffix, migrated=True)
        except Exception as exc:
            report['failed'].append({'note': entry['path'], 'error': str(exc)[:200]})
            continue
        status = result['status']
        report['migrated'] += status in ('created', 'updated', 'preview')
        report['unchanged'] += status == 'unchanged'
        report['items'].append({k: result.get(k) for k in ('status', 'title', 'note', 'reason') if result.get(k)})
    if apply and report['migrated']:
        write_state_json(cfg, 'migrated.json', dict(read_state_json(cfg, 'migrated.json', {}),
                                                    **{str(archive): now_iso()}))
    return report


# -------------------------------------------------------------------- CLI

def load_answers(value):
    if value.strip().startswith('{'):
        return json.loads(value)
    return json.loads(Path(value).expanduser().read_text())


def require(cfg_path):
    cfg = ck_config.load(cfg_path)
    if cfg is None:
        raise ValueError('Connected Knowledge is not set up on this Mac yet; run /ck-setup first')
    return cfg


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, help='Machine configuration file (default: ~/.config/connected-knowledge/config.json)')
    sub = parser.add_subparsers(dest='command', required=True)
    d = sub.add_parser('doctor')
    d.add_argument('--next', action='store_true')
    s = sub.add_parser('setup')
    s.add_argument('--answers', required=True, help='JSON text or a path to a JSON file')
    s.add_argument('--apply', action='store_true')
    c = sub.add_parser('capture')
    c.add_argument('switch', choices=['on', 'off'])
    c.add_argument('--host', action='append', choices=list(ck_config.HOSTS))
    c.add_argument('--apply', action='store_true')
    a = sub.add_parser('add-session')
    a.add_argument('target', nargs='?', default='current', help='current, latest, all, a session ID or a transcript path')
    a.add_argument('--session-id')
    a.add_argument('--host', choices=list(ck_config.HOSTS))
    a.add_argument('--cwd')
    a.add_argument('--title')
    a.add_argument('--category')
    a.add_argument('--project')
    a.add_argument('--topic', action='append', dest='topics')
    a.add_argument('--device')
    a.add_argument('--summary')
    a.add_argument('--apply', action='store_true')
    sub.add_parser('sweep')
    sub.add_parser('topics')
    t = sub.add_parser('topic-add')
    t.add_argument('name')
    t.add_argument('--parent')
    t.add_argument('--apply', action='store_true')
    m = sub.add_parser('migrate')
    m.add_argument('archive')
    m.add_argument('--apply', action='store_true')
    i = sub.add_parser('mark-import')
    i.add_argument('vendor', choices=sorted(VENDORS))
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            result = doctor(args.config, args.next)
        elif args.command == 'setup':
            result = setup(load_answers(args.answers), args.apply, args.config)
        elif args.command == 'capture':
            result = capture_switch(args.switch == 'on', args.host, args.config, args.apply)
        elif args.command == 'add-session':
            overrides = {'title': args.title, 'category': args.category, 'project': args.project,
                         'topics': args.topics, 'device': args.device, 'summary': args.summary}
            session_id = args.session_id if args.session_id and '${' not in args.session_id else None
            result = add_session(require(args.config), args.target, overrides, args.apply, session_id, args.cwd, args.host)
        elif args.command == 'sweep':
            result = ck_sweep.sweep(require(args.config))
        elif args.command == 'topics':
            result = topics(require(args.config))
        elif args.command == 'topic-add':
            result = topic_add(require(args.config), args.name, args.parent, args.apply)
        elif args.command == 'migrate':
            result = migrate(require(args.config), args.archive, args.apply)
        else:
            cfg = require(args.config)
            exports = read_state_json(cfg, 'exports.json', {})
            exports[args.vendor] = now_iso()
            write_state_json(cfg, 'exports.json', exports)
            result = {'recorded': args.vendor, 'when': exports[args.vendor]}
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
