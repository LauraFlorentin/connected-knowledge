"""Machine configuration, vault profile and private state (standard library only).

One configuration file per Mac, never synced and never inside a vault:
``~/.config/connected-knowledge/config.json`` (``$XDG_CONFIG_HOME`` is honoured).
``CONNECTED_KNOWLEDGE_HOME`` replaces that folder, for tests and unusual setups.
Everything here must keep working on the stock macOS Python 3.9, because the
hooks import it.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import time

SCHEMA = 1
LIMIT = 1024 * 1024
HOSTS = ('claude-code', 'codex')
ROLES = ('hub', 'satellite')
LABEL = re.compile(r'^[a-z0-9][a-z0-9-]{0,39}$')
SESSION_ID = re.compile(r'^[A-Za-z0-9._-]{1,128}$')
DEFAULT_TRANSCRIPT_ROOTS = {'claude-code': ['~/.claude/projects'],
                            'codex': ['~/.codex/sessions', '~/.codex/archived_sessions']}
DEFAULT_FOLDERS = {
    'sessions': 'Sources/AI Conversations',
    'transcripts': 'Attachments/AI Transcripts',
    'session_files': 'Attachments/Session Files',
    'projects': 'Projects',
    'maps': 'Maps',
    'index': '_meta/index',
}
DEFAULT_CATEGORIES = ['Admin', 'Personal', 'Work']
PROFILE = '_meta/ck/vault.json'


def config_dir(env=None):
    env = os.environ if env is None else env
    if env.get('CONNECTED_KNOWLEDGE_HOME'):
        return Path(env['CONNECTED_KNOWLEDGE_HOME']).expanduser()
    base = env.get('XDG_CONFIG_HOME') or str(Path.home()/'.config')
    return Path(base).expanduser()/'connected-knowledge'


def config_path(env=None):
    return config_dir(env)/'config.json'


def default_state(env=None):
    env = os.environ if env is None else env
    if env.get('CONNECTED_KNOWLEDGE_HOME'):
        return config_dir(env)/'state'
    base = env.get('XDG_STATE_HOME') or str(Path.home()/'.local/state')
    return Path(base).expanduser()/'connected-knowledge'


def absolute(value, label):
    if not isinstance(value, str) or not value:
        raise ValueError(label + ' must be an absolute path')
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(label + ' must be an absolute path')
    return path


def no_symlinks(path, label):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(label + ' must not pass through a symlink')
    return path


def inside(child, parent):
    child, parent = Path(child).resolve(), Path(parent).resolve()
    return child == parent or parent in child.parents


def label(value, name, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str) or not LABEL.match(value):
        raise ValueError(name + ' must be a short lowercase label such as mac-mini')
    return value


def validate(cfg):
    if not isinstance(cfg, dict) or cfg.get('schema') != SCHEMA:
        raise ValueError('Unsupported machine configuration; run /ck-setup again')
    label(cfg.get('machine'), 'machine')
    if cfg.get('role') not in ROLES:
        raise ValueError('role must be hub or satellite')
    vault = absolute(cfg.get('vault'), 'vault')
    state = absolute(cfg.get('state'), 'state')
    if inside(state, vault) or inside(vault, state):
        raise ValueError('Keep machine state outside the vault')
    if cfg.get('python') is not None:
        absolute(cfg['python'], 'python')
    accounts = cfg.get('accounts', {})
    if not isinstance(accounts, dict) or any(not isinstance(k, str) for k in accounts):
        raise ValueError('accounts must map vendors to labels')
    for vendor, value in accounts.items():
        label(value, 'accounts.' + vendor)
    capture = cfg.get('capture', {})
    if not isinstance(capture, dict) or not isinstance(capture.get('enabled', False), bool):
        raise ValueError('capture.enabled must be true or false')
    hosts = capture.get('hosts', [])
    if not isinstance(hosts, list) or any(h not in HOSTS for h in hosts):
        raise ValueError('capture.hosts may contain only ' + ', '.join(HOSTS))
    for key in ('roots', 'exclude'):
        values = capture.get(key, [])
        if not isinstance(values, list):
            raise ValueError('capture.' + key + ' must be a list of absolute folders')
        for value in values:
            if inside(absolute(value, 'capture.' + key), vault):
                raise ValueError('Capture folders must be outside the vault')
    if capture.get('enabled') and not capture.get('roots'):
        raise ValueError('Choose at least one capture folder before switching capture on')
    idle = capture.get('idle_minutes', 10)
    if type(idle) is not int or not 1 <= idle <= 1440:
        raise ValueError('capture.idle_minutes must be a whole number from 1 to 1440')
    label(capture.get('default_remote_device'), 'capture.default_remote_device', optional=True)
    roots = capture.get('transcript_roots', {})
    if not isinstance(roots, dict) or any(h not in HOSTS or not isinstance(v, list) for h, v in roots.items()):
        raise ValueError('capture.transcript_roots must map hosts to folder lists')
    for values in roots.values():
        for value in values:
            absolute(value, 'capture.transcript_roots')
    return cfg


def read_json(path, limit=LIMIT):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing a symlinked file: ' + path.name)
    if path.stat().st_size > limit:
        raise ValueError('File exceeds size limit: ' + path.name)
    return json.loads(path.read_bytes())


def load(path=None):
    """Return the validated machine configuration, or None when there is none."""
    path = Path(path) if path else config_path()
    if not path.exists():
        return None
    return validate(read_json(path))


def write_atomic(path, data, mode=0o600):
    path = Path(path)
    if isinstance(data, str):
        data = data.encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('Refusing to write through a symlink: ' + path.name)
    fd, name = tempfile.mkstemp(prefix='.ck-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, str(path))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def dumps(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def save(cfg, path=None):
    validate(cfg)
    path = Path(path) if path else config_path()
    private_dir(path.parent)
    write_atomic(path, dumps(cfg))
    return path


def private_dir(path, vault=None):
    """Create (or check) a 0700 folder that is not inside the vault."""
    path = no_symlinks(Path(path).expanduser(), 'Private folder')
    if not path.is_absolute():
        raise ValueError('Private folders must be absolute')
    if vault is not None and (inside(path, vault) or inside(vault, path)):
        raise ValueError('Keep machine state outside the vault')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(str(path), 0o700)
    return path


def state(cfg):
    """Private state folders for this machine; created 0700 on first use."""
    root = private_dir(absolute(cfg['state'], 'state'), cfg['vault'])
    paths = {'root': root}
    for name in ('queue', 'failed', 'raw', 'locks', 'logs'):
        paths[name] = private_dir(root/name)
    paths['manifest'] = root/'manifest.json'
    return paths


@contextmanager
def try_lock(path):
    """Non-blocking OS lock. Yields False when another process holds it.

    The kernel releases the lock when its holder dies, so a killed capture can
    never leave a lock behind.
    """
    import fcntl
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing a symlinked lock')
    with open(str(path), 'a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def transcript_roots(cfg, host):
    custom = cfg.get('capture', {}).get('transcript_roots', {}).get(host)
    return [Path(p).expanduser() for p in (custom or DEFAULT_TRANSCRIPT_ROOTS[host])]


def in_scope(cfg, directory):
    """Return the capture root containing ``directory`` minus excludes, else None."""
    if not isinstance(directory, str) or not directory or not Path(directory).is_absolute():
        return None
    capture = cfg.get('capture', {})
    for excluded in capture.get('exclude', []):
        if inside(directory, Path(excluded).expanduser()):
            return None
    for root in capture.get('roots', []):
        root = Path(root).expanduser()
        if inside(directory, root):
            return root
    return None


def project_folder(cfg, directory):
    """Project name: the first folder below the matching capture root, if any."""
    root = in_scope(cfg, directory)
    if root is None:
        return None
    relative = Path(directory).resolve().relative_to(root.resolve()).parts
    return relative[0] if relative else None


def account(cfg, platform):
    vendor = {'claude-code': 'claude', 'claude': 'claude', 'codex': 'openai',
              'chatgpt': 'openai', 'gemini-cli': 'google', 'gemini': 'google'}.get(platform, platform)
    return cfg.get('accounts', {}).get(vendor, 'personal')


# ---------------------------------------------------------------- vault profile

def relative_folder(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(name + ' must be a vault-relative folder')
    parts = PurePosixPath(value).parts
    if PurePosixPath(value).is_absolute() or '..' in parts or '.' in parts or (parts and parts[0] == '.obsidian'):
        raise ValueError(name + ' must stay inside the vault and outside .obsidian')
    return value


def validate_profile(profile):
    if not isinstance(profile, dict) or profile.get('schema', SCHEMA) != SCHEMA:
        raise ValueError('Unsupported vault profile')
    folders = profile.get('folders', {})
    if not isinstance(folders, dict):
        raise ValueError('folders must be an object')
    for key, value in folders.items():
        relative_folder(value, 'folders.' + key)
    fields = profile.get('fields', {})
    if not isinstance(fields, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in fields.items()):
        raise ValueError('fields must map property names to nonempty names')
    values = profile.get('values', {})
    if not isinstance(values, dict) or any(not isinstance(v, dict) for v in values.values()):
        raise ValueError('values must map property names to value mappings')
    categories = profile.get('categories', DEFAULT_CATEGORIES)
    if not isinstance(categories, list) or any(not isinstance(c, str) or not c.strip() for c in categories):
        raise ValueError('categories must be a list of names')
    projects = profile.get('projects', {})
    if not isinstance(projects, dict):
        raise ValueError('projects must be an object')
    for name, entry in projects.items():
        if not isinstance(entry, dict):
            raise ValueError('projects.' + name + ' must be an object')
        if 'note' in entry:
            relative_folder(entry['note'], 'projects.' + name + '.note')
        if entry.get('category') is not None and entry['category'] not in categories:
            raise ValueError('projects.' + name + '.category is not one of the vault categories')
    if profile.get('variant', 'no-templates') not in ('templates', 'no-templates', 'adopted'):
        raise ValueError('variant must be templates, no-templates or adopted')
    return profile


def load_profile(vault):
    """The vault's shared profile with defaults filled in (read-only)."""
    vault = Path(vault)
    path = vault/PROFILE
    profile = read_json(path) if path.exists() else {}
    validate_profile(profile)
    merged = dict(profile)
    merged['folders'] = dict(DEFAULT_FOLDERS, **profile.get('folders', {}))
    merged.setdefault('fields', {})
    merged.setdefault('values', {})
    merged.setdefault('categories', list(DEFAULT_CATEGORIES))
    merged.setdefault('projects', {})
    merged['present'] = path.exists()
    return merged


def vault_path(vault, relative):
    """Resolve a vault-relative path, refusing symlinks and escapes."""
    root = Path(vault).resolve()
    path = root.joinpath(*PurePosixPath(relative).parts)
    current = root
    for part in PurePosixPath(relative).parts:
        current = current/part
        if current.is_symlink():
            raise ValueError('Refusing a symlink inside the vault: ' + relative)
    if not inside(path, root):
        raise ValueError('Path leaves the vault: ' + relative)
    return path


# ------------------------------------------------------------------- the queue

def queue_name(host, session_id):
    if not SESSION_ID.match(session_id):
        session_id = hashlib.sha256(session_id.encode('utf-8')).hexdigest()[:32]
    return host + '-' + session_id + '.json'


def enqueue(paths, host, event, surface=None, now=None):
    """Record that a session changed. Never opens the transcript."""
    now = time.time() if now is None else now
    queue = paths['queue']/queue_name(host, event['session_id'])
    entry = {}
    if queue.exists():
        try:
            entry = read_json(queue)
        except (ValueError, OSError):
            entry = {}
    entry.update({'schema': SCHEMA, 'host': host, 'session_id': event['session_id'],
                  'transcript_path': event['transcript_path'], 'cwd': entry.get('cwd') or event['cwd'],
                  'updated': now, 'events': int(entry.get('events', 0)) + 1})
    entry.setdefault('first_seen', now)
    if event.get('hook_event_name') == 'SessionEnd':
        entry['ended'] = True
    if surface and not entry.get('surface'):
        entry['surface'] = surface
    write_atomic(queue, dumps(entry))
    return queue


def queued(paths):
    entries = []
    for path in sorted(paths['queue'].glob('*.json')):
        try:
            entries.append((path, read_json(path)))
        except (ValueError, OSError):
            entries.append((path, None))
    return entries
