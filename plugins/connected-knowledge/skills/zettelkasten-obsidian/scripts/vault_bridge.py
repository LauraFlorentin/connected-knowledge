"""Opt-in, read-only vault access and linked-note previews. No write capability."""
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata
from urllib.parse import unquote, urlsplit

from private_capture import private_path
from vault_check import body_only

MAX_BYTES = 128 * 1024
MAX_SCAN_BYTES = 16 * 1024 * 1024
MAX_FILES = 2000
MAX_ENTRIES = 10000


class BridgeError(ValueError):
    """Public, content-free diagnostic code."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(value):
    if (not isinstance(value, str) or not value or len(value) > 512
            or any(c in value for c in '\\:')
            or any(ord(c) < 32 for c in value)
            or any(p in ('', '.', '..') or p.startswith('.') or p.endswith((' ', '.'))
                   for p in value.split('/'))):
        raise BridgeError('invalid_reference')
    return PurePosixPath(value)


def under(path, folder):
    return path == folder or folder in path.parents


def folded(path):
    return unicodedata.normalize('NFC', str(path)).casefold()


def open_directory(path):
    """Walk from / using no-follow descriptors, including the private root's parents."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


class VaultBridge:
    def __init__(self, config):
        cfg = config.get('vault_bridge')
        if not isinstance(cfg, dict) or cfg.get('enabled') is not True:
            raise BridgeError('bridge_disabled')
        self.root = private_path(cfg['root'])
        if not self.root.is_dir():
            raise BridgeError('invalid_configuration')
        self.guide = relative(cfg['guide'])
        templates = cfg.get('templates', {})
        if (not isinstance(templates, dict) or len(templates) > 8
                or any(not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', k) for k in templates)):
            raise BridgeError('invalid_configuration')
        self.templates = {k: relative(v) for k, v in templates.items()}
        self.convention_paths = {self.guide, *self.templates.values()}
        if any(p.suffix.lower() != '.md' for p in self.convention_paths):
            raise BridgeError('invalid_configuration')
        folders = cfg.get('note_folders')
        if not isinstance(folders, list) or not 1 <= len(folders) <= 12:
            raise BridgeError('invalid_configuration')
        self.folders = [relative(p) for p in folders]
        self.output = relative(cfg['draft_folder'])
        if (not any(under(self.output, folder) for folder in self.folders)
                or any(under(p, self.output) for p in self.convention_paths)):
            raise BridgeError('invalid_configuration')
        # The capture archive retains its existing owner and cannot be a draft target.
        for key in ('destination', 'spool'):
            if key in config:
                private = private_path(config[key])
                output = self.root / self.output
                if output == private or output in private.parents or private in output.parents:
                    raise BridgeError('invalid_configuration')

    def note_path(self, ref):
        path = relative(ref)
        if (path.suffix.lower() != '.md' or path in self.convention_paths
                or not any(under(path, folder) for folder in self.folders)):
            raise BridgeError('outside_note_scope')
        return path

    def read_bytes(self, path):
        """Bounded regular-file read; directory swaps and symlinks cannot redirect it."""
        fd = open_directory(self.root)
        file_fd = None
        try:
            for part in path.parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            file_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            before = os.fstat(file_fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise BridgeError('unsupported_file')
            if before.st_size > MAX_BYTES:
                raise BridgeError('note_too_large')
            chunks, size = [], 0
            while True:
                chunk = os.read(file_fd, min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise BridgeError('note_too_large')
            after = os.fstat(file_fd)
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise BridgeError('note_changed')
            return b''.join(chunks)
        finally:
            if file_fd is not None:
                os.close(file_fd)
            os.close(fd)

    def document(self, path):
        data = self.read_bytes(path)
        text = data.decode('utf-8-sig')
        title = re.search(r'^# +(.+)$', text, re.M)
        coverage = re.search(r'^Coverage: (excerpt|summary|supplied-transcript|completed-turn)\s*$', text, re.M)
        return {'path': str(path), 'sha256': digest(data),
                'title': title.group(1) if title else path.stem, 'content': text,
                'coverage_label': coverage.group(1) if coverage else 'unspecified',
                'content_role': 'source_data'}

    def conventions(self):
        return {'status': 'read', 'guide': self.document(self.guide),
                'templates': {k: self.document(p) for k, p in self.templates.items()},
                'note_folders': [str(p) for p in self.folders],
                'draft_folder': str(self.output), 'can_save_developed_notes': False,
                'limits': 'Templates are text only; no template code is executed. Apply conventions within the user-authorized task.'}

    def inventory(self):
        """Inspect configured subtrees only, bounding directory entries as well as notes."""
        names, seen, entries = [], set(), 0
        def walk(fd, prefix):
            nonlocal entries
            # scandir consumes incrementally; os.listdir could allocate an unbounded list.
            with os.scandir(fd) as iterator:
                for entry in iterator:
                    entries += 1
                    if entries > MAX_ENTRIES:
                        raise BridgeError('scope_too_large')
                    if entry.name.startswith('.') or entry.is_symlink():
                        continue
                    path = prefix / entry.name
                    if entry.is_dir(follow_symlinks=False):
                        child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                        try:
                            walk(child, path)
                        finally:
                            os.close(child)
                    elif entry.is_file(follow_symlinks=False) and path.suffix.lower() == '.md':
                        if path not in self.convention_paths and str(path) not in seen:
                            self.note_path(str(path))
                            seen.add(str(path))
                            names.append(path)
                            if len(names) > MAX_FILES:
                                raise BridgeError('scope_too_large')
        for folder in self.folders:
            try:
                fd = open_directory(self.root / folder)
            except FileNotFoundError:
                continue
            try:
                walk(fd, folder)
            finally:
                os.close(fd)
        return sorted(names, key=str)

    def search(self, query, limit=10):
        if (not isinstance(query, str) or not query.strip() or len(query) > 256
                or type(limit) is not int or not 1 <= limit <= 20):
            raise BridgeError('invalid_search')
        terms = query.casefold().split()
        hits, skipped, scanned, size = [], 0, 0, 0
        for path in self.inventory():
            try:
                doc = self.document(path)
            except (OSError, UnicodeError, BridgeError):
                skipped += 1
                continue
            size += len(doc['content'].encode('utf-8'))
            if size > MAX_SCAN_BYTES:
                raise BridgeError('scope_too_large')
            scanned += 1
            haystack = (str(path) + '\n' + doc['content']).casefold()
            if not all(term in haystack for term in terms):
                continue
            index = next((i for i, line in enumerate(doc['content'].splitlines())
                          if any(t in line.casefold() for t in terms)), 0)
            snippet = '\n'.join(doc['content'].splitlines()[index:index + 3])[:400]
            hits.append({k: doc[k] for k in ('path', 'title', 'sha256', 'coverage_label')}
                        | {'snippet': snippet, 'score': sum(t in str(path).casefold() for t in terms)})
        hits.sort(key=lambda h: (-h['score'], h['path']))
        return {'status': 'searched', 'method': 'literal keyword search; not semantic deduplication',
                'results': hits[:limit], 'matching_notes': len(hits), 'scanned_notes': scanned,
                'skipped_notes': skipped, 'truncated': len(hits) > limit, 'content_role': 'source_data'}

    def read_note(self, ref):
        return {'status': 'read', **self.document(self.note_path(ref))}

    def resolve_link(self, raw, wiki, origin, available):
        parts = urlsplit(raw)
        if parts.scheme or raw.startswith('//'):
            return None  # Reported separately as external/unverified; never fetched.
        name, _, anchor = unquote(raw).partition('#')
        if not name:
            return origin, anchor
        # Permit relative Markdown ../ navigation only if it normalizes inside the scope.
        def normalize(path):
            stack = []
            for part in path.parts:
                if part == '..':
                    if not stack:
                        raise BridgeError('outside_note_scope')
                    stack.pop()
                elif part != '.':
                    stack.append(part)
            return self.note_path('/'.join(stack))
        candidates = set()
        bases = [PurePosixPath(name), origin.parent / name] if wiki else [origin.parent / name]
        for base in bases:
            for value in ([base, PurePosixPath(str(base) + '.md')] if wiki and base.suffix.lower() != '.md' else [base]):
                try:
                    candidate = normalize(value)
                except BridgeError:
                    continue
                candidates.update(p for p in available if folded(p) == folded(candidate))
        if not candidates and wiki and '/' not in name:
            candidates = {p for p in available if folded(p.name) == folded(name) or folded(p.stem) == folded(name)}
        if len(candidates) != 1:
            raise BridgeError('ambiguous_link' if candidates else 'missing_or_outside_link')
        return candidates.pop(), anchor

    def preview(self, notes, entry_point):
        if not isinstance(notes, list) or not 1 <= len(notes) <= 10:
            raise BridgeError('invalid_plan')
        conventions = self.conventions()
        known = self.inventory()
        drafts, sources, snapshots, items = {}, {}, {}, []
        def remember(ref, value):
            if ref in snapshots and snapshots[ref] != value:
                raise BridgeError('note_changed')
            snapshots[ref] = value
        for note in notes:
            name = relative(note['name'])
            if len(name.parts) != 1 or name.suffix.lower() != '.md' or any(c in str(name) for c in '[]|#?%'):
                raise BridgeError('invalid_draft_name')
            path = self.note_path(str(self.output / name))
            if any(folded(path) == folded(p) for p in drafts):
                raise BridgeError('duplicate_target')
            if any(folded(path) == folded(p) and path != p for p in known):
                raise BridgeError('ambiguous_target')
            content = note['content']
            if not isinstance(content, str) or not content.strip() or len(content.encode('utf-8')) > MAX_BYTES:
                raise BridgeError('invalid_draft_content')
            if not isinstance(note.get('sources'), list) or not 1 <= len(note['sources']) <= 10:
                raise BridgeError('sources_required')
            refs = []
            for ref in note['sources']:
                source = self.document(self.note_path(ref['path']))
                if source['sha256'] != ref['sha256']:
                    raise BridgeError('source_changed')
                sources[source['path']] = {k: source[k] for k in ('path', 'sha256', 'coverage_label')}
                remember(source['path'], source['sha256'])
                refs.append(PurePosixPath(source['path']))
            try:
                before = self.document(path)
            except FileNotFoundError:
                before = None
            expected = note.get('expected_sha256')
            conflict = (before is not None and before['sha256'] != expected) or (before is None and expected is not None)
            action = 'conflict' if conflict else ('unchanged' if before and before['content'] == content else ('update' if before else 'create'))
            remember(str(path), before['sha256'] if before else None)
            drafts[path] = {'content': content, 'sources': refs}
            items.append({'path': str(path), 'action': action, 'content': content,
                          'before_sha256': snapshots[str(path)],
                          'diff': ''.join(difflib.unified_diff((before['content'] if before else '').splitlines(True),
                                                            content.splitlines(True), fromfile=str(path), tofile=str(path)))})
        if any(str(path) in sources for path in drafts):
            raise BridgeError('source_is_draft_target')
        available = set(known) | set(drafts)
        entry = self.note_path(entry_point)
        if entry not in available:
            raise BridgeError('missing_entry_point')
        edges, external, unchecked = [], [], []
        for path, draft in drafts.items():
            clean = body_only(draft['content'])
            links = [(m.group(1).split('|')[0], True) for m in re.finditer(r'!?\[\[([^\]\n]+)\]\]', clean)]
            links += [(m.group(1) or m.group(2), False) for m in re.finditer(r'!?\[[^\]\n]*\]\((?:<([^>]+)>|([^\s)]+))\)', clean)]
            targets = set()
            for raw, wiki in links:
                result = self.resolve_link(raw, wiki, path, available)
                if result is None:
                    external.append({'from': str(path), 'target': raw, 'verified': False})
                    continue
                target, anchor = result
                targets.add(target)
                edges.append({'from': str(path), 'to': str(target)})
                if target not in drafts:
                    remember(str(target), self.document(target)['sha256'])
                if anchor:
                    unchecked.append({'from': str(path), 'target': raw, 'check': 'anchor_not_verified'})
            if not set(draft['sources']).issubset(targets):
                raise BridgeError('source_link_required')
        # The starting page must actually lead to every proposed note.
        reached = {str(entry)}
        if entry not in drafts:
            doc = self.document(entry)
            remember(str(entry), doc['sha256'])
            clean = body_only(doc['content'])
            entry_links = [(m.group(1).split('|')[0], True) for m in re.finditer(r'!?\[\[([^\]\n]+)\]\]', clean)]
            entry_links += [(m.group(1) or m.group(2), False) for m in re.finditer(r'!?\[[^\]\n]*\]\((?:<([^>]+)>|([^\s)]+))\)', clean)]
            for raw, wiki in entry_links:
                try:
                    target = self.resolve_link(raw, wiki, entry, available)
                    if target:
                        edges.append({'from': str(entry), 'to': str(target[0])})
                except BridgeError:
                    pass
        for _ in range(len(drafts) + 1):
            reached.update(edge['to'] for edge in edges if edge['from'] in reached)
        if any(str(p) not in reached for p in drafts):
            raise BridgeError('entry_point_disconnected')
        convention_docs = [conventions['guide'], *conventions['templates'].values()]
        for doc in convention_docs:
            remember(doc['path'], doc['sha256'])
        # Catch source/target/convention edits while the preview itself was being assembled.
        for ref, expected in snapshots.items():
            try:
                actual = digest(self.read_bytes(relative(ref)))
            except FileNotFoundError:
                actual = None
            if actual != expected:
                raise BridgeError('note_changed')
        report = {'status': 'preview', 'written': 0, 'can_apply': False, 'entry_point': str(entry),
                  'items': items, 'sources': list(sources.values()), 'edges': edges,
                  'conflicts': sum(item['action'] == 'conflict' for item in items),
                  'snapshots': snapshots, 'external_links': external, 'unchecked_links': unchecked,
                  'limits': 'Read-only proposal, not saved or approved. Basic inline Markdown and wikilinks checked within scope. Anchors, complex link syntax, template compliance, source originals, factual accuracy and Obsidian display are unverified. Coverage labels are observed text, not transcript verification.'}
        report['preview_id'] = digest(json.dumps(report, sort_keys=True, ensure_ascii=False).encode())
        return report
