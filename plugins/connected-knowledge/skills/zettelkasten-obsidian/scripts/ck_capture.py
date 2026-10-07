"""Write one conversation into the vault: a conversation note plus its transcript.

Shared by the background sweep, ``/ck-add-session`` and the 1.6.0 migration.
Standard library only. Rules that keep two Macs and a person safe:

- A machine writes only conversations it holds; state stays outside the vault.
- A note that exists but is not in this machine's manifest is never overwritten:
  same ``id`` from another machine → "captured elsewhere"; different ``id`` → stop.
- Only the generated block and machine-owned properties of a note are rewritten.
- A shorter or diverging transcript never replaces a longer capture.
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import time

import ck_config
from ck_config import dumps, read_json, vault_path, write_atomic
import ck_render
from ck_transcripts import iso, surface as detect_surface

VERSION = 1
ASSISTANT = {'claude-code': 'Claude Code', 'codex': 'Codex', 'claude': 'Claude', 'chatgpt': 'ChatGPT',
             'gemini-cli': 'Gemini CLI', 'gemini': 'Gemini'}


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode('utf-8')).hexdigest()


def identity(host, account, native_id):
    return 'ck-' + digest(json.dumps([host, account, native_id], ensure_ascii=False))[:16]


def ids_digest(messages):
    return digest('\n'.join(m['id'] for m in messages))


def load_manifest(path):
    if not Path(path).exists():
        return {'schema': VERSION, 'items': {}}
    data = read_json(path, limit=64 * 1024 * 1024)
    if data.get('schema') != VERSION or not isinstance(data.get('items'), dict):
        raise ValueError('Unsupported capture manifest; keep it and ask for help')
    return data


def first_words(text, words=5):
    text = re.sub(r'`[^`]*`|https?://\S+|[^\w\s\'-]', ' ', text or '')
    return ' '.join(text.split()[:words])


def title_for(session, overrides, record):
    if overrides.get('title'):
        if len(overrides['title'].split()) > 5:
            raise ValueError('Titles have at most five words')
        return ck_render.clean_title(overrides['title'])
    if record and record.get('title'):
        return record['title']
    titles = session.get('titles', {})
    for key in ('custom', 'host'):
        if titles.get(key):
            return ck_render.clean_title(titles[key])
    first = next((m['text'] for m in session['messages'] if m['role'] == 'user' and m['text'].strip()), '')
    return ck_render.clean_title(first_words(first))


def slug(text, limit=60):
    text = re.sub(r'[\\/:*?"<>|#^\[\]\x00-\x1f%]', '-', text).strip(' .-')
    return text[:limit].rstrip(' .-') or 'Conversation'


def short_id(native_id):
    cleaned = re.sub(r'[^A-Za-z0-9]', '', native_id)
    return (cleaned or digest(native_id))[:8]


def note_paths(profile, session, title):
    folders = profile['folders']
    created = session.get('created') or iso(time.time())
    year, day = created[:4], created[:10]
    stem = day + ' ' + slug(title) + ' — ' + session['host'] + ' ' + short_id(session['native_id'])
    return (folders['sessions'] + '/' + year + '/' + stem + '.md',
            folders['transcripts'] + '/' + year + '/' + stem + '.transcript.md')


def relative_link(target, source_note):
    return os.path.relpath(target, str(PurePosixPath(source_note).parent)).replace(os.sep, '/')


def find_maps(vault, profile):
    """Topic maps: every Markdown file in the maps folder, by lowercase name."""
    folder = vault_path(vault, profile['folders']['maps'])
    found = {}
    if folder.is_dir():
        for path in sorted(folder.rglob('*.md')):
            if not path.is_symlink():
                found[path.stem.casefold()] = path.relative_to(Path(vault).resolve()).with_suffix('').as_posix()
    return found


def resolve_topics(vault, profile, names):
    if not names:
        return []
    maps = find_maps(vault, profile)
    unknown = [n for n in names if n.casefold() not in maps]
    if unknown:
        raise ValueError('Unknown topic: ' + ', '.join(unknown) + '. Known topics: '
                         + (', '.join(sorted(Path(p).name for p in maps.values())) or 'none yet'))
    return [maps[n.casefold()] for n in names]


def project_for(cfg, profile, session, overrides):
    name = overrides.get('project')
    if not name and session.get('directories'):
        name = ck_config.project_folder(cfg, session['directories'][0])
    if not name:
        return None, None
    entry = profile['projects'].get(name, {})
    note = entry.get('note') or profile['folders']['projects'] + '/' + slug(name, 80)
    return note, entry.get('category')


def project_note(note, name, category, now, profile):
    meta = {'schema_version': 1, 'id': 'ck-project-' + digest(note)[:12], 'note_type': 'entity',
            'entity_type': 'project'}
    if category:
        meta['category'] = category
    meta.update({'classification_status': 'provisional', 'review_status': 'draft', 'title': name,
                 'aliases': [], 'topics': [], 'created': now, 'updated': now})
    return ck_render.dump(ck_render.to_vault(meta, profile)) + ('# ' + name + '\n\nProject note created by Connected Knowledge the first '
                                   'time a conversation from this project was saved. Describe the project '
                                   'here; conversations link to this note.\n')


def read_existing(path):
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        raise ck_render.FrontmatterError('Note is not UTF-8 text')


def prepare(cfg, session, overrides=None, profile=None, manifest=None, now=None):
    """Work out labels, paths and actions. Writes nothing."""
    overrides = overrides or {}
    vault = Path(cfg['vault'])
    if not vault.is_dir():
        raise ValueError('The vault folder is not reachable on this Mac')
    profile = profile or ck_config.load_profile(vault)
    manifest = manifest if manifest is not None else {'schema': VERSION, 'items': {}}
    now = now or iso(time.time())
    account = ck_config.account(cfg, session['host'])
    cid = identity(session['host'], account, session['native_id'])
    record = manifest['items'].get(cid)
    title = title_for(session, overrides, record)
    note_rel, transcript_rel = (record['path'], record['transcript']) if record else note_paths(profile, session, title)
    project_rel, project_category = project_for(cfg, profile, session, overrides)
    category = overrides.get('category') or (record or {}).get('category') or project_category
    if category and category not in profile['categories']:
        raise ValueError('Category must be one of: ' + ', '.join(profile['categories']))
    topics = resolve_topics(vault, profile, overrides.get('topics'))
    machine = cfg['machine'] if session['host'] in ('claude-code', 'codex') else None
    surface = session.get('surface') or detect_surface(session['host'], session.get('surface_hint'), overrides.get('surface'))
    device = overrides.get('device')
    if device:
        ck_config.label(device, 'device')
    elif surface == 'remote-control':
        device = cfg.get('capture', {}).get('default_remote_device')
    elif machine and surface in ('cli', 'desktop', 'ide'):
        device = machine
    summary = overrides.get('summary') or (record or {}).get('summary')
    labels = {'id': cid, 'title': title, 'category': category, 'machine': machine, 'surface': surface,
              'summary': summary, 'note_link': note_rel[:-3],
              'transcript_link': relative_link(transcript_rel, note_rel),
              'project_link': project_rel, 'topic_links': topics,
              'origin': ('the local ' + session['platform'] + ' transcript on ' + machine) if machine
              else ('a ' + session['platform'] + ' export'),
              'account': account, 'device': device}
    return {'id': cid, 'record': record, 'labels': labels, 'profile': profile,
            'note': note_rel, 'transcript': transcript_rel, 'project': project_rel,
            'project_name': overrides.get('project') or (Path(project_rel).name if project_rel else None),
            'project_category': project_category, 'session': session, 'now': now,
            'explicit': {k for k in ('title', 'category', 'topics') if overrides.get(k)}}


def adopt_existing(plan, old):
    """Keep the person's title, category and topics unless new ones were given."""
    profile, labels = plan['profile'], plan['labels']
    for key in ('title', 'category', 'topics'):
        value = old.get(ck_render.field(profile, key))
        if key in plan['explicit'] or value in (None, '', []):
            continue
        if key == 'topics':
            if isinstance(value, list):
                labels['topic_links'] = [str(v)[2:-2] if str(v).startswith('[[') and str(v).endswith(']]') else str(v)
                                         for v in value]
        else:
            labels[key] = str(value)


def finalize(plan):
    """Render the transcript and the canonical properties from the final labels."""
    labels, session, record = plan['labels'], plan['session'], plan['record']
    plan['transcript_text'] = ck_render.transcript(session, labels)
    meta = {'schema_version': 1, 'id': plan['id'], 'note_type': 'source'}
    if labels['category']:
        meta['category'] = labels['category']
    meta.update({'classification_status': 'provisional', 'review_status': 'draft', 'title': labels['title'],
                 'source_platform': session['platform'], 'source_account': labels['account'],
                 'source_id': session['native_id'], 'source_coverage': session.get('coverage', 'full_export'),
                 'source_created': session.get('created'), 'source_updated': session.get('updated'),
                 'source_machine': labels['machine'], 'source_device': labels['device'],
                 'source_surface': labels['surface']})
    if plan['project']:
        meta['project'] = '[[' + plan['project'] + ']]'
    meta['topics'] = ['[[' + t + ']]' for t in labels['topic_links']]
    meta.update({'source_file': plan['transcript'], 'source_sha256': digest(plan['transcript_text']),
                 'created': (record or {}).get('created') or plan['now'], 'updated': plan['now']})
    plan['meta'] = {k: v for k, v in meta.items() if v is not None}
    return plan


def decide(cfg, plan, recreate=False):
    """Compare the plan with the vault. Returns (status, note text or None, reason)."""
    vault, profile, record, session = cfg['vault'], plan['profile'], plan['record'], plan['session']
    note_file = vault_path(vault, plan['note'])
    transcript_file = vault_path(vault, plan['transcript'])
    if record:
        shorter = len(session['messages']) < record['message_count']
        if shorter or (not record.get('migrated') and
                       ids_digest(session['messages'][:record['message_count']]) != record['ids_sha']):
            return 'diverged', None, 'The transcript is shorter than, or differs from, the saved conversation; nothing was replaced.'
        if transcript_file.exists() and digest(transcript_file.read_bytes()) != record['transcript_sha']:
            return 'conflict', None, 'The transcript file was edited by hand; it was not replaced.'
        if not note_file.exists() and not recreate:
            return 'deleted', None, 'The conversation note was deleted; it was not recreated.'
    existing = None
    if note_file.exists():
        try:
            existing = read_existing(note_file)
            old, _ = ck_render.split_note(existing)
        except ck_render.FrontmatterError as exc:
            return 'conflict', None, 'The existing note could not be read safely (' + str(exc) + ').'
        if not record:
            same = old.get(ck_render.field(profile, 'id')) == plan['id']
            if not same:
                return 'conflict', None, 'A different note already uses this file name.'
            if old.get(ck_render.field(profile, 'source_machine')) not in (None, cfg['machine']):
                return 'elsewhere', None, 'Captured elsewhere (' + str(old.get('source_machine')) + ').'
        adopt_existing(plan, old)
    if transcript_file.exists() and not record:
        # Our own transcript from an interrupted run may be replaced; anything else stays.
        try:
            owner, _ = ck_render.split_note(read_existing(transcript_file))
        except ck_render.FrontmatterError:
            owner = {}
        if owner.get('transcript_of') != plan['id']:
            return 'conflict', None, 'A different transcript file already uses this name.'
    finalize(plan)
    try:
        text = ck_render.conversation_note(session, plan['labels'], plan['meta'], profile, existing,
                                           explicit=plan['explicit'])
    except ck_render.FrontmatterError as exc:
        return 'conflict', None, str(exc) + '; the note was not changed.'
    if record and existing is not None and digest(plan['transcript_text']) == record['transcript_sha']:
        if strip_updated(text) == strip_updated(existing):
            return 'unchanged', None, 'Already up to date.'
    return ('updated' if record or existing else 'created'), text, ''


def strip_updated(text):
    return re.sub(r'^updated: .*$', '', text, count=1, flags=re.M)


def write(cfg, paths, plan, text, raw, raw_suffix='.jsonl'):
    vault = cfg['vault']
    session = plan['session']
    raw_file = paths['raw']/session['host']/(re.sub(r'[^A-Za-z0-9._-]', '-', session['native_id']) + raw_suffix)
    ck_config.private_dir(raw_file.parent)
    if not raw_file.exists() or raw_file.read_bytes() != raw:
        write_atomic(raw_file, raw)  # one raw copy per session, replaced as it grows
    write_atomic(vault_path(vault, plan['transcript']), plan['transcript_text'], 0o644)
    if plan['project']:
        project_file = vault_path(vault, plan['project'] + '.md')
        if not project_file.exists():
            # A new project starts with its first conversation's category, still provisional.
            write_atomic(project_file, project_note(plan['project'], plan['project_name'],
                                                    plan['project_category'] or plan['labels']['category'],
                                                    plan['now'], plan['profile']), 0o644)
    write_atomic(vault_path(vault, plan['note']), text, 0o644)
    return raw_file


def record_for(plan, text):
    meta, session = plan['meta'], plan['session']
    return {'host': session['host'], 'native_id': session['native_id'], 'path': plan['note'],
            'transcript': plan['transcript'], 'note_sha': digest(text), 'transcript_sha': meta['source_sha256'],
            'message_count': len(session['messages']), 'ids_sha': ids_digest(session['messages']),
            'title': plan['labels']['title'], 'summary': plan['labels']['summary'],
            'category': plan['labels']['category'], 'created': meta['created'],
            'index': {k: v for k, v in {
                'id': plan['id'], 'path': plan['note'], 'title': plan['labels']['title'],
                'category': plan['labels']['category'], 'platform': session['platform'],
                'machine': plan['labels']['machine'], 'device': meta.get('source_device'),
                'surface': meta.get('source_surface'), 'project': Path(plan['project']).name if plan['project'] else None,
                'topics': [Path(t).name for t in plan['labels']['topic_links']],
                'source_created': meta.get('source_created'), 'source_updated': meta.get('source_updated'),
                'messages': len(session['messages'])}.items() if v not in (None, [])}}


def write_index(cfg, profile, manifest):
    """This machine's own index file; other machines write their own."""
    lines = [json.dumps(item['index'], ensure_ascii=False, sort_keys=True)
             for _, item in sorted(manifest['items'].items(), key=lambda kv: kv[1]['index'].get('source_created', ''))]
    path = vault_path(cfg['vault'], profile['folders']['index'] + '/conversations.' + cfg['machine'] + '.jsonl')
    data = '\n'.join(lines) + ('\n' if lines else '')
    if not path.exists() or path.read_text(encoding='utf-8') != data:
        write_atomic(path, data, 0o644)


def capture(cfg, session, raw, overrides=None, apply=False, paths=None, recreate=False, raw_suffix='.jsonl',
            migrated=False):
    """Preview (default) or write one conversation. Returns a short report."""
    paths = paths or (ck_config.state(cfg) if apply else None)
    manifest_file = paths['manifest'] if paths else Path(cfg['state'])/'manifest.json'
    manifest = load_manifest(manifest_file) if manifest_file.exists() else {'schema': VERSION, 'items': {}}
    plan = prepare(cfg, session, overrides, manifest=manifest)
    status, text, reason = decide(cfg, plan, recreate)
    report = {'status': status, 'id': plan['id'], 'title': plan['labels']['title'],
              'category': plan['labels']['category'], 'project': plan['project'],
              'topics': plan['labels']['topic_links'], 'platform': session['platform'],
              'machine': plan['labels']['machine'], 'device': plan['labels']['device'],
              'surface': plan['labels']['surface'], 'messages': len(session['messages']),
              'note': plan['note'], 'transcript': plan['transcript'], 'skipped': session.get('skipped', {})}
    if reason:
        report['reason'] = reason
    if not apply or text is None:
        if not apply and text is not None:
            report['status'] = 'preview'
            report['would'] = status
        return report
    write(cfg, paths, plan, text, raw, raw_suffix)
    manifest['items'][plan['id']] = record_for(plan, text)
    if migrated:
        # Rebuilt from an older archive, so message boundaries may differ from a
        # live capture of the same session; the next live capture may replace it.
        manifest['items'][plan['id']]['migrated'] = True
    write_atomic(manifest_file, dumps(manifest))
    write_index(cfg, plan['profile'], manifest)
    return report
