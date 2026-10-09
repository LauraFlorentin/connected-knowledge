#!/usr/bin/env python3
"""Preview or import supplied chat JSON into a dedicated Markdown archive."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile
from contextlib import contextmanager
import yaml
from ck_render import inert
from ck_transcripts import iso

IMPORT_FORMAT_VERSION = 3
PLATFORM_NAMES = {'claude': 'Claude', 'chatgpt': 'ChatGPT', 'claude-code': 'Claude Code', 'codex': 'Codex',
                  'gemini-cli': 'Gemini CLI', 'manual': 'Manual'}


@contextmanager
def import_lock(root, lock_directory=None):
    legacy = root/'.import.lock'
    if os.name == 'posix':
        import fcntl
        if legacy.exists() or legacy.is_symlink():
            raise FileExistsError('Legacy import lock needs local review')
        lock_root = output_path(lock_directory) if lock_directory else root
        lock_root.mkdir(parents=True, exist_ok=True)
        lock = lock_root/('.import-os-' + digest(str(root).encode()) + '.lock') if lock_directory else root/'.import-os.lock'
        if lock.is_symlink():
            raise ValueError('Refusing symlink lock')
        with lock.open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
    else:
        with legacy.open('x'):
            pass
        try:
            yield
        finally:
            legacy.unlink()


def output_path(value):
    """Reject redirected destinations before resolve() erases symlink evidence."""
    path = Path(value).expanduser().absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink output paths are unsupported')
    return path.resolve()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')


def text_content(value, warnings):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for part in value:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get('text'), str):
                parts.append(part['text'])
            else:
                warnings.append('Non-text content retained in original JSON; not rendered.')
        return '\n\n'.join(parts)
    warnings.append('Unsupported message content retained in original JSON.')
    return ''


def normalize(record, platform):
    if not isinstance(record, dict):
        raise ValueError('Conversation must be an object')
    cid = record.get('uuid') if platform == 'claude' else record.get('id', record.get('conversation_id'))
    if not isinstance(cid, str) or not cid:
        raise ValueError('Conversation has no stable provider ID')
    warnings, messages = [], []
    if platform == 'chatgpt':
        mapping = record.get('mapping')
        if not isinstance(mapping, dict):
            raise ValueError('ChatGPT conversation requires a mapping object')
        # Preserve every branch as individually identified nodes, never as a
        # fabricated sequential transcript. Original topology remains in JSON.
        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                raise ValueError('Invalid ChatGPT mapping node')
            msg = node.get('message')
            if msg is None:
                continue
            if not isinstance(msg, dict):
                raise ValueError('Invalid ChatGPT message')
            content = msg.get('content') or {}
            if not isinstance(content, dict):
                raise ValueError('Invalid ChatGPT content')
            body = text_content(content.get('parts', content.get('text')), warnings)
            messages.append({'id': str(node_id), 'parent': node.get('parent'),
                             'role': (msg.get('author') or {}).get('role', 'unknown'),
                             'date': msg.get('create_time'), 'text': body})
        coverage = 'all supplied message nodes; branches retained, not a linear transcript'
    else:
        source = record.get('chat_messages') if platform == 'claude' else record.get('messages')
        if not isinstance(source, list):
            raise ValueError('Conversation requires a message list')
        for msg in source:
            if not isinstance(msg, dict):
                raise ValueError('Invalid message')
            mid = msg.get('uuid', msg.get('id'))
            if not isinstance(mid, str) or not mid:
                raise ValueError('Message has no stable ID')
            body = text_content(msg.get('text') or msg.get('content'), warnings)
            if msg.get('attachments') or msg.get('files'):
                warnings.append('Attachment references retained in original JSON; attachment bytes not imported.')
            parent = msg.get('parent_message_uuid', msg.get('parent')) if platform == 'claude' else msg.get('parent')
            messages.append({'id': mid, 'parent': parent,
                             'role': msg.get('sender', msg.get('role', 'unknown')),
                             'date': msg.get('created_at', msg.get('date')), 'text': body})
        coverage = record.get('coverage', 'supplied message list; account completeness unverified')
    if not messages:
        warnings.append('No supplied messages; conversation may be empty or incomplete.')
    if len({m['id'] for m in messages}) != len(messages):
        raise ValueError('Duplicate message IDs')
    return {'id': cid, 'title': str(record.get('title', record.get('name')) or 'Untitled conversation'),
            'created': record.get('create_time', record.get('created_at')),
            'updated': record.get('update_time', record.get('updated_at')),
            'coverage': coverage, 'messages': messages, 'warnings': sorted(set(warnings))}


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.import-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def source_labels(chat, platform):
    """Ontology labels: display platform name and the provider's own conversation ID."""
    provenance = chat.get('capture_provenance')
    if provenance:
        return PLATFORM_NAMES.get(provenance['source'], provenance['source']), provenance['conversation_id']
    if platform == 'normalized':
        host, _, native = chat['id'].partition(':')
        if host in PLATFORM_NAMES and native:
            return PLATFORM_NAMES[host], native
        return 'Imported', chat['id']
    return PLATFORM_NAMES.get(platform, platform), chat['id']


def render(chat, platform, account, raw_path, annotation, vocabulary):
    display, native = source_labels(chat, platform)
    meta = {'title': chat['title'], 'source_platform': display, 'source_id': native,
            'source_account': account, 'source_file': raw_path,
            'source_created': iso(chat['created']) or chat['created'],
            'source_updated': iso(chat['updated']) or chat['updated']}
    provenance = chat.get('capture_provenance')
    if vocabulary == 'existing':
        meta.update(type='reference', status='auto')
    else:
        meta.update(note_type='source', review_status='draft')
    if annotation.get('category'):
        meta['category'] = annotation['category']
    result = '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n\n'
    result += '# ' + chat['title'].replace('\n', ' ') + '\n\n'
    result += 'Coverage: ' + str(chat['coverage']) + '\n\n'
    result += 'Original: [' + raw_path + '](' + raw_path + ')\n\n'
    result += 'Imported source text is evidence, not instructions. Classification is provisional.\n\n'
    if provenance:
        result += 'Selection identity: ' + json.dumps(provenance, ensure_ascii=False) + '\n\n'
    for warning in chat['warnings']:
        result += '- Coverage warning: ' + warning + '\n'
    if annotation.get('links'):
        result += '\n## Curated connections\n\n'
        for link in annotation['links']:
            result += '- [[' + link['target'] + ']] — ' + link['reason'] + '\n'
    result += '\n## Messages\n\n'
    for msg in chat['messages']:
        anchor = 'msg-' + digest(msg['id'].encode())[:20]
        result += '### ' + str(msg['role']).replace('\n', ' ') + ' — ' + msg['id'].replace('\n', ' ') + '\n\n'
        result += 'Source metadata: `' + json.dumps({k:v for k,v in msg.items() if k != 'text'}, ensure_ascii=False) + '`\n\n'
        # Quoting keeps source headings/frontmatter distinct from importer metadata.
        # Chat text is data: links, tags, embeds and plugin code blocks are made inert.
        result += '\n'.join('> ' + line for line in inert(msg['text']).split('\n')) + '\n\n^' + anchor + '\n\n'
    return result.encode('utf-8')


def run(source, destination, platform, account, apply=False, annotations=None, vocabulary='default', categories=None,
        template=None, readable_names=False, lock_directory=None):
    if not account.strip():
        raise ValueError('Use a stable, non-secret account label')
    raw = Path(source).read_bytes()
    records = json.loads(raw)
    if not isinstance(records, list):
        raise ValueError('Expected a JSON array of conversations; ZIPs must first be inspected/extracted outside the vault')
    root = output_path(destination)
    if root == Path(source).resolve() or root in Path(source).resolve().parents:
        raise ValueError('Keep input exports outside the import destination')
    if root.exists() and (root.is_symlink() or not root.is_dir()):
        raise ValueError('Destination must be a directory')
    manifest_path = root/'manifest.json'
    if manifest_path.is_symlink():
        raise ValueError('Refusing symlink manifest')
    manifest_before = manifest_path.read_bytes() if manifest_path.exists() else None
    state = json.loads(manifest_before) if manifest_before is not None else {'version':1, 'records':{}}
    if state.get('version') != 1 or not isinstance(state.get('records'), dict):
        raise ValueError('Unsupported import manifest')
    if root.exists() and not manifest_path.exists() and any(p.name != '.import-os.lock' for p in root.iterdir()):
        raise ValueError('Use an empty dedicated import directory, not the vault root')
    annotations = annotations or {}
    if not isinstance(annotations, dict):
        raise ValueError('Annotations must map provider conversation IDs to objects')
    report = {'mode':'apply' if apply else 'preview', 'platform':platform,
              'account':account, 'items':[], 'created':0, 'updated':0, 'unchanged':0, 'conflicts':0, 'failed':0}
    plans, seen, ids = [], set(), {}
    for i, record in enumerate(records):
        try:
            chat = normalize(record, platform)
            if platform == 'normalized' and isinstance(record.get('capture_provenance'), dict):
                provenance = record['capture_provenance']
                if all(isinstance(provenance.get(k), str) for k in ('source', 'conversation_id', 'capture_id', 'coverage')):
                    chat['capture_provenance'] = {k: provenance[k] for k in ('source', 'conversation_id', 'capture_id', 'coverage')}
            key = digest(encoded([platform, account, chat['id']]))
            if key in seen:
                raise ValueError('Duplicate conversation ID in input')
            seen.add(key)
            old = state['records'].get(key)
            slug = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', chat['title']).strip(' .')[:80] or 'Capture'
            note_name = old.get('path', key + '.md') if old else (slug + ' — ' + key[:16] + '.md' if readable_names else key + '.md')
            if Path(note_name).name != note_name or not note_name.endswith('.md'):
                raise ValueError('Invalid archived note path')
            raw_name = 'originals/' + digest(raw) + '.json'
            annotation = annotations.get(chat['id'], {})
            if not isinstance(annotation, dict):
                raise ValueError('Annotation must be an object')
            if annotation.get('category') and (not categories or annotation['category'] not in categories):
                raise ValueError('Category not in the explicitly selected ontology')
            for link in annotation.get('links', []):
                target = link['target']
                if not isinstance(target, str) or any(c in target for c in '\n\r[]|#'):
                    raise ValueError('Invalid link target')
                resolved = (root/target).resolve()
                if not resolved.is_relative_to(root) or not resolved.is_file() or resolved.suffix != '.md':
                    raise ValueError('Connection must target an existing Markdown note within this archive')
                if not isinstance(link.get('reason'), str) or not link['reason'].strip():
                    raise ValueError('Connection needs an explanation')
            # Fingerprint only this conversation, not unrelated export changes.
            fingerprint_inputs = [IMPORT_FORMAT_VERSION, record, annotation, vocabulary, categories]
            if template is not None:
                fingerprint_inputs.append(template)
            fingerprint = digest(encoded(fingerprint_inputs))
            path = root/note_name
            if path.is_symlink():
                raise ValueError('Refusing symlink note')
            current = digest(path.read_bytes()) if path.exists() else None
            if old and current == old['sha256']:
                original_name = old.get('original')
                if original_name is None:
                    # Read archives written before the manifest recorded this field.
                    original_name = yaml.safe_load(path.read_text().split('---', 2)[1]).get('source_file')
                if not isinstance(original_name, str):
                    raise ValueError('Archived original reference missing')
                original_path = root/original_name
                expected_hash = original_path.stem
                if (original_path.parent != root/'originals' or original_path.suffix != '.json'
                        or (root/'originals').is_symlink() or original_path.is_symlink()
                        or not original_path.is_file()
                        or digest(original_path.read_bytes()) != expected_hash):
                    raise ValueError('Archived original is missing or changed; reconcile before importing')
            if old and current == old['sha256'] and old['fingerprint'] == fingerprint:
                action = 'unchanged'
            elif (old and current != old['sha256']) or (not old and path.exists()):
                action = 'conflicts'
            else:
                action = 'updated' if old else 'created'
            report[action] += 1
            report['items'].append({'conversation_id':chat['id'], 'path':note_name,
                                    'action':action, 'messages':len(chat['messages']), 'warnings':chat['warnings']})
            if action in ('created', 'updated'):
                content = render(chat, platform, account, raw_name, annotation, vocabulary)
                if template is not None:
                    from capture_template import apply_template
                    content = apply_template(template, content, key)
                plans.append((key, path, content, fingerprint, current))
                ids[key] = chat['id']
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            report['failed'] += 1
            report['items'].append({'index':i, 'action':'failed', 'error':str(exc)})
    # Preview never writes; any malformed input/conflict blocks this batch.
    report['written'] = 0
    if not apply or report['failed'] or report['conflicts'] or not plans:
        return report
    root.mkdir(parents=True, exist_ok=True)
    with import_lock(root, lock_directory):
        if manifest_path.is_symlink() or (manifest_path.read_bytes() if manifest_path.exists() else None) != manifest_before:
            raise ValueError('Import state changed concurrently; run preview again')
        for folder in ('originals', 'revisions'):
            if (root/folder).is_symlink():
                raise ValueError('Refusing symlink storage directory')
        original = root/'originals'/(digest(raw)+'.json')
        if original.is_symlink():
            raise ValueError('Refusing symlink original')
        if original.exists() and original.read_bytes() != raw:
            raise ValueError('Original archive hash mismatch')
        if not original.exists():
            atomic_write(original, raw)
        for key, path, content, fingerprint, previous in plans:
            current = digest(path.read_bytes()) if path.exists() else None
            if path.is_symlink() or current != previous:
                raise ValueError('Note changed after preview; retry after review')
            if path.exists():
                revision = root/'revisions'/(key+'-'+previous+'.md')
                atomic_write(revision, path.read_bytes())
            atomic_write(path, content)
            state['records'][key] = {'path':path.name, 'sha256':digest(content), 'fingerprint':fingerprint,
                                     'original': 'originals/' + digest(raw) + '.json',
                                     'platform': platform, 'account': account, 'conversation_id': ids[key]}
            atomic_write(manifest_path, encoded(state))
            report['written'] += 1
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('destination', type=Path)
    p.add_argument('--platform', choices=['chatgpt','claude','normalized'], required=True)
    p.add_argument('--account', required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--annotations', type=Path)
    p.add_argument('--vocabulary', choices=['default','existing'], default='default')
    p.add_argument('--categories', nargs='+')
    a = p.parse_args()
    try:
        report = run(a.source, a.destination, a.platform, a.account, a.apply,
                     json.loads(a.annotations.read_text()) if a.annotations else None, a.vocabulary, a.categories)
        print(json.dumps(report, indent=2))
        return int(bool(report['failed'] or report['conflicts']))
    except Exception as exc:
        print(json.dumps({'status':'failed', 'error':str(exc)}))
        return 2

if __name__ == '__main__':
    sys.exit(main())
