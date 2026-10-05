"""Preview-bound linked-note saves with private receipts and resumable journals."""
import base64
from contextlib import contextmanager
import fcntl
import json
import os
import re
import stat
import uuid
import yaml

from private_capture import private_path
from vault_bridge import BridgeError, MAX_BYTES, SOURCE_BYTES, digest, open_directory, relative
from vault_check import UniqueLoader

STATE_LIMIT = 4 * 1024 * 1024


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')


def ensure_directory(path):
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_at(folder_fd, name, limit):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder_fd)
    except FileNotFoundError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise BridgeError('unsafe_or_oversized_file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise BridgeError('unsafe_or_oversized_file')
        return data
    finally:
        os.close(fd)


def atomic_at(folder_fd, name, data, expected=None, replace=False, temporary=None):
    """Same-directory staging; new files are linked exclusively, updates replace atomically."""
    temporary = temporary or '.ck-' + uuid.uuid4().hex + '.tmp'
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder_fd)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
        current = read_at(folder_fd, name, max(STATE_LIMIT, len(data)))
        actual = digest(current) if current is not None else None
        if actual != expected:
            raise BridgeError('target_changed')
        if replace:
            if current is not None:
                os.fchmod(fd, stat.S_IMODE(os.stat(name, dir_fd=folder_fd, follow_symlinks=False).st_mode) & 0o777)
                os.fsync(fd)
            os.replace(temporary, name, src_dir_fd=folder_fd, dst_dir_fd=folder_fd)
        else:
            # link fails rather than replacing a file created since the check above.
            os.link(temporary, name, src_dir_fd=folder_fd, dst_dir_fd=folder_fd, follow_symlinks=False)
        os.fsync(folder_fd)
    finally:
        os.close(fd)
        try:
            os.unlink(temporary, dir_fd=folder_fd)
        except FileNotFoundError:
            pass


class PrivateStore:
    def __init__(self, bridge):
        cfg = bridge.settings
        if cfg.get('write_enabled') is not True:
            raise BridgeError('writes_disabled')
        value = cfg.get('state_directory')
        if not isinstance(value, str):
            raise BridgeError('save_state_required')
        self.path = private_path(value)
        if self.path == bridge.root or self.path in bridge.root.parents or bridge.root in self.path.parents:
            raise BridgeError('invalid_save_state')
        self.owner = {'version': 1, 'vault': digest(str(bridge.root).encode())}
        self.fd = None

    @contextmanager
    def locked(self):
        self.fd = ensure_directory(self.path)
        lock = None
        try:
            if self.read('owner.json') is None and os.listdir(self.fd):
                raise BridgeError('save_state_not_empty')
            lock = os.open('save.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
            info = os.fstat(lock)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise BridgeError('invalid_save_state')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise BridgeError('save_busy') from None
            owner = self.read('owner.json')
            if owner is None:
                if set(os.listdir(self.fd)) != {'save.lock'}:
                    raise BridgeError('save_state_not_empty')
                self.write('owner.json', self.owner)
            elif owner != self.owner:
                raise BridgeError('save_state_owner_mismatch')
            yield self
        finally:
            if lock is not None:
                os.close(lock)
            os.close(self.fd)
            self.fd = None

    def read(self, name):
        data = read_at(self.fd, name, STATE_LIMIT)
        return None if data is None else json.loads(data)

    def write(self, name, value):
        data = encoded(value)
        if len(data) > STATE_LIMIT:
            raise BridgeError('save_state_too_large')
        before = read_at(self.fd, name, STATE_LIMIT)
        atomic_at(self.fd, name, data, expected=digest(before) if before is not None else None,
                  replace=True)


def identities(content, fields):
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', content, re.S)
    if content.startswith('---') and not match:
        raise BridgeError('invalid_frontmatter')
    if not match:
        return {}
    meta = yaml.load(match.group(1), Loader=UniqueLoader)
    if not isinstance(meta, dict):
        raise BridgeError('invalid_frontmatter')
    result = {}
    for field in fields:
        if field in meta:
            value = meta[field]
            if not isinstance(value, str) or not value.strip():
                raise BridgeError('invalid_note_identity')
            result[field] = value
    return result


def identity_check(bridge, notes):
    fields = bridge.settings.get('identity_fields', ['id'])
    if (not isinstance(fields, list) or not fields or len(fields) > 12
            or any(not isinstance(f, str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{0,63}', f) for f in fields)):
        raise BridgeError('invalid_identity_configuration')
    drafts = {bridge.note_path(str(bridge.output / relative(n['name']))): n['content'] for n in notes}
    existing = {}
    total = 0
    for path in bridge.inventory():
        doc = bridge.document(path)
        total += len(doc['content'].encode('utf-8'))
        if total > 16 * 1024 * 1024:
            raise BridgeError('scope_too_large')
        existing[path] = doc
    seen = {}
    for path, content in drafts.items():
        after = identities(content, fields)
        if path in existing:
            before = identities(existing[path]['content'], fields)
            if any(after.get(k) != v for k, v in before.items()):
                raise BridgeError('note_identity_changed')
        for field, value in after.items():
            if (field, value) in seen:
                raise BridgeError('duplicate_note_identity')
            seen[field, value] = path
        for other, doc in existing.items():
            if other in drafts:
                continue
            if doc['content'] == content:
                raise BridgeError('duplicate_note_content')
            other_ids = identities(doc['content'], fields)
            if any(other_ids.get(k) == v for k, v in after.items()):
                raise BridgeError('duplicate_note_identity')


def snapshot_check(bridge, report, targets):
    for ref, expected in report['snapshots'].items():
        if ref in targets:
            continue
        actual = digest(bridge.read_bytes(relative(ref), SOURCE_BYTES))
        if actual != expected:
            raise BridgeError('source_or_convention_changed')


def current_hash(bridge, path):
    try:
        return digest(bridge.read_bytes(relative(path)))
    except FileNotFoundError:
        return None


def write_note(bridge, item):
    path = bridge.note_path(item['path'])
    if path.parent != bridge.output:
        raise BridgeError('invalid_save_target')
    fd = ensure_directory(bridge.root / path.parent)
    try:
        # Reject a renamed ancestor before touching a target via the held descriptor.
        check = open_directory(bridge.root / path.parent)
        try:
            a, b = os.fstat(fd), os.fstat(check)
            if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                raise BridgeError('target_changed')
        finally:
            os.close(check)
        atomic_at(fd, path.name, item['content'].encode('utf-8'),
                  expected=item['before_sha256'], replace=item['before_sha256'] is not None, temporary=item['stage'])
    finally:
        os.close(fd)


def clean_staging(bridge, item):
    """Remove only this journal's staging file, including a link left by process death."""
    stage = item.get('stage')
    if not isinstance(stage, str) or not re.fullmatch(r'\.ck-[a-f0-9]{32}\.tmp', stage):
        raise BridgeError('invalid_save_state')
    path = bridge.note_path(item['path'])
    try:
        parent = open_directory(bridge.root / path.parent)
    except FileNotFoundError:
        return
    fd = None
    try:
        try:
            fd = os.open(stage, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        except FileNotFoundError:
            return
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink not in (1, 2) or info.st_size > MAX_BYTES:
            raise BridgeError('unsafe_staging_file')
        data = os.read(fd, MAX_BYTES + 1)
        expected = item['content'].encode('utf-8')
        if (info.st_nlink == 1 and not expected.startswith(data)) or (info.st_nlink == 2 and data != expected):
            raise BridgeError('unsafe_staging_file')
        if info.st_nlink == 2:
            target = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if (target.st_dev, target.st_ino) != (info.st_dev, info.st_ino):
                raise BridgeError('unsafe_staging_file')
        os.unlink(stage, dir_fd=parent)
        os.fsync(parent)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def receipt(bridge, journal, status, written, code=None):
    items = []
    for item in journal['targets']:
        try:
            state = 'saved' if current_hash(bridge, item['path']) == item['after_sha256'] else 'pending_or_changed'
        except (OSError, ValueError):
            state = 'unreadable'
        items.append({'path': item['path'], 'record_id': item['record_id'],
                      'sha256': item['after_sha256'], 'state': state})
    result = {'status': status, 'written': written, 'preview_id': journal['preview_id'],
              'entry_point': journal['report']['entry_point'], 'notes': items,
              'revision_receipt': journal['preview_id'],
              'checks': 'Read-back and scoped links checked; native Obsidian rendering and factual accuracy unverified.'}
    if code:
        result['code'] = code
    return result


def save(bridge, notes, entry_point, preview_id):
    if not isinstance(notes, list) or not 1 <= len(notes) <= 10:
        raise BridgeError('invalid_plan')
    if not isinstance(preview_id, str) or not re.fullmatch(r'[a-f0-9]{64}', preview_id):
        raise BridgeError('invalid_preview_id')
    store = PrivateStore(bridge)
    request = {'notes': notes, 'entry_point': entry_point, 'scope_sha256': bridge.scope_sha256}
    request_sha = digest(encoded(request))
    name = preview_id + '.json'
    with store.locked():
        journal = store.read(name)
        ledger = store.read('notes.json') or {'version': 1, 'notes': {}}
        if ledger.get('version') != 1 or not isinstance(ledger.get('notes'), dict):
            raise BridgeError('invalid_save_state')
        if journal is not None:
            if (journal.get('version') != 1 or journal.get('preview_id') != preview_id
                    or journal.get('request_sha256') != request_sha
                    or journal.get('report', {}).get('scope_sha256') != bridge.scope_sha256):
                raise BridgeError('save_request_changed')
            report = journal['report']
            report_without_id = {k: v for k, v in report.items() if k != 'preview_id'}
            if digest(encoded(report_without_id)) != preview_id:
                raise BridgeError('invalid_save_state')
            wanted = {str(bridge.output / relative(n['name'])): n['content'] for n in notes}
            if (len(journal['targets']) != len(wanted)
                    or set(wanted) != {t['path'] for t in journal['targets']}
                    or len({t['record_id'] for t in journal['targets']}) != len(wanted)):
                raise BridgeError('invalid_save_state')
            for target in journal['targets']:
                if (not isinstance(target.get('record_id'), str)
                        or not re.fullmatch(r'[a-f0-9]{32}', target['record_id'])
                        or target['content'] != wanted[target['path']]
                        or target['after_sha256'] != digest(target['content'].encode('utf-8'))
                        or target['before_sha256'] != report['snapshots'][target['path']]):
                    raise BridgeError('invalid_save_state')
                prior = base64.b64decode(target['before_bytes'], validate=True) if target['before_bytes'] is not None else None
                if (digest(prior) if prior is not None else None) != target['before_sha256']:
                    raise BridgeError('invalid_save_state')
            if journal.get('complete'):
                if any(current_hash(bridge, t['path']) != t['after_sha256'] for t in journal['targets']):
                    raise BridgeError('saved_note_changed')
                return receipt(bridge, journal, 'unchanged', 0)
        else:
            report = bridge.preview(notes, entry_point)
            if report['preview_id'] != preview_id:
                raise BridgeError('preview_changed')
            if report['conflicts']:
                raise BridgeError('preview_conflict')
            identity_check(bridge, notes)
            targets = []
            for item in report['items']:
                before = bridge.read_bytes(relative(item['path'])) if item['before_sha256'] is not None else None
                if (digest(before) if before is not None else None) != item['before_sha256']:
                    raise BridgeError('target_changed')
                old = ledger['notes'].get(item['path'])
                if old and before is None:
                    raise BridgeError('managed_note_missing')
                targets.append({'path': item['path'], 'content': item['content'],
                                'before_sha256': item['before_sha256'],
                                'before_bytes': base64.b64encode(before).decode() if before is not None else None,
                                'after_sha256': digest(item['content'].encode('utf-8')),
                                'record_id': old['record_id'] if old else uuid.uuid4().hex,
                                'stage': '.ck-' + uuid.uuid4().hex + '.tmp'})
            journal = {'version': 1, 'preview_id': preview_id, 'request_sha256': request_sha,
                       'report': report, 'targets': targets, 'complete': False}
            store.write(name, journal)  # Durable originals and intent precede any vault writes.
        written = 0
        targets = {t['path'] for t in journal['targets']}
        try:
            for target in journal['targets']:
                clean_staging(bridge, target)
            snapshot_check(bridge, journal['report'], targets)
            identity_check(bridge, notes)
            # Validate the entire batch before the first mutation, including recovery.
            for target in journal['targets']:
                actual = current_hash(bridge, target['path'])
                if actual not in (target['before_sha256'], target['after_sha256']):
                    raise BridgeError('target_changed')
                old = ledger['notes'].get(target['path'])
                if old and old['record_id'] != target['record_id']:
                    raise BridgeError('note_identity_changed')
            for target in journal['targets']:
                snapshot_check(bridge, journal['report'], targets)
                actual = current_hash(bridge, target['path'])
                if actual != target['after_sha256']:
                    write_note(bridge, target)
                    written += 1
                if current_hash(bridge, target['path']) != target['after_sha256']:
                    raise BridgeError('read_back_failed')
                ledger['notes'][target['path']] = {'record_id': target['record_id'], 'sha256': target['after_sha256']}
                store.write('notes.json', ledger)
            snapshot_check(bridge, journal['report'], targets)
            journal['complete'] = True
            store.write(name, journal)
            return receipt(bridge, journal, 'saved' if written else 'unchanged', written)
        except (OSError, ValueError) as exc:
            code = str(exc) if isinstance(exc, BridgeError) else 'save_interrupted'
            return receipt(bridge, journal, 'incomplete', written, code)
