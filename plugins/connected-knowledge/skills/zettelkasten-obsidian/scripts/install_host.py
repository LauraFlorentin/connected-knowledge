"""Merge only the explicitly selected Filesystem host entry; preserve other settings."""
import json
from pathlib import Path
import sys
import uuid
from install_support import path, read, atomic


def configure(host, config_path, name, connection, apply=False):
    target = path(config_path)
    before = read(target) if target.exists() else None
    if host == 'codex':
        import tomlkit
        document = tomlkit.parse(before.decode() if before else '')
        servers = document.setdefault('mcp_servers', tomlkit.table())
    elif host == 'claude-desktop':
        document = json.loads(before) if before else {}
        servers = document.setdefault('mcpServers', {})
    else:
        raise ValueError('Host registration supports codex and claude-desktop')
    if not isinstance(servers, dict):
        raise ValueError('Malformed host server configuration')
    if name in servers:
        existing = servers[name]
        if not isinstance(existing, dict) or any(existing.get(k) != v for k, v in connection.items()):
            raise ValueError('Connection name is already used by different settings; preserve it and choose another name')
        # Leave enabled state, approval policies and extra user options untouched.
        return {'status': 'reused', 'file': str(target), 'name': name}
    servers[name] = connection
    after = (tomlkit.dumps(document) if host == 'codex' else json.dumps(document, indent=2) + '\n').encode()
    result = {'status': 'prepared', 'file': str(target), 'name': name}
    if not apply:
        return result
    if (read(target) if target.exists() else None) != before:
        raise ValueError('Host settings changed during preparation; retry without overwriting them')
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if before is not None:
        backup = target.with_name(target.name + '.connected-knowledge-backup-' + uuid.uuid4().hex)
        atomic(backup, before)
        result['backup'] = str(backup)
    atomic(target, after)
    result['status'] = 'registered'
    return result


if __name__ == '__main__':
    data = json.load(sys.stdin)
    try:
        print(json.dumps(configure(**data)))
    except Exception as exc:
        # Existing host settings may contain secrets; do not echo document/errors.
        print(json.dumps({'status': 'error', 'type': type(exc).__name__,
                          'hint': 'Inspect the selected host path and connection-name conflicts; existing settings were preserved.'}))
        raise SystemExit(1)
