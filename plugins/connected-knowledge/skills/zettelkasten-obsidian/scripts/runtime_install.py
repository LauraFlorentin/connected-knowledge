"""Stage, verify and switch private runtime generations while retaining private data."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import uuid

from install_support import path, read, encoded, digest, atomic, runtime_lock
from filesystem_setup import connection_plan, DEFAULT_NAME, TESTED_VERSION
from install_dependencies import NODE_VERSION

SCRIPTS = Path(__file__).resolve().parent
OWNER = 'connected-knowledge-managed-runtime-v1'
CURRENT = 'install-current.json'


def source_files():
    files = {'scripts/' + p.name: read(p) for p in SCRIPTS.iterdir()
             if p.is_file() and (p.suffix == '.py' or p.name.startswith('requirements'))}
    for name in ('capture-existing.md', 'capture-default.md'):
        files['assets/templates/' + name] = read(SCRIPTS.parent/'assets/templates'/name)
    return files


def current(root):
    file = root/CURRENT
    if not file.exists():
        return None
    value = json.loads(read(file))
    if value.get('owner') != OWNER or not re.fullmatch(r'[a-f0-9]{32}', value.get('generation', '')):
        raise ValueError('Invalid managed runtime pointer')
    if not path(root/'releases'/value['generation']).is_dir():
        raise ValueError('Managed runtime generation is missing')
    return value


def inspect(answers):
    if sys.platform not in ('darwin', 'linux') or sys.version_info < (3, 10):
        raise ValueError('The installer needs macOS/Linux and Python 3.10 or later')
    root = path(answers['runtime'])
    for directory in ('scripts', 'releases', 'install-backups'):
        path(root/directory)
    for parent in (SCRIPTS.parents[2], *SCRIPTS.parents):
        if parent == SCRIPTS.parents[2] or (parent/'.git').exists():
            if root == parent or root.is_relative_to(parent):
                raise ValueError('Keep the runtime outside plugin source and installation')
    owner = json.loads(read(root/'install-owner.json')) if (root/'install-owner.json').exists() else None
    if owner and owner != {'owner': OWNER, 'runtime': str(root)}:
        raise ValueError('This runtime belongs to a different installation')
    old = current(root)
    cfg_path, settings_path = root/'capture-config.json', root/'runtime.json'
    before = {name: read(root/name) if (root/name).exists() else None
              for name in ('capture-config.json', 'runtime.json', CURRENT)}
    initial = json.loads(read(root/'install-initial.json')) if (root/'install-initial.json').exists() else {}
    config = json.loads(before['capture-config.json']) if before['capture-config.json'] else initial.get('config')
    settings = json.loads(before['runtime.json']) if before['runtime.json'] else initial.get('settings')
    if bool(config) != bool(settings):
        raise ValueError('Incomplete private configuration; preserve it and inspect the original setup')
    legacy = bool(config and settings and (root/'scripts/private_runtime.py').is_file())
    if root.exists() and any(root.iterdir()) and not (owner or legacy):
        raise ValueError('Occupied destination is not a recognized runtime; nothing will be replaced')
    selected = answers.get('private')
    template_bytes = None
    if config:
        if selected is False:
            raise ValueError('Existing private settings are reused; disable the connection separately')
        if isinstance(selected, dict):
            expected = {'account': selected.get('account'),
                        'destination': str(path(selected['vault'])/'Inbox/ChatGPT Captures'),
                        'vocabulary': selected.get('vocabulary', 'existing'),
                        'template': str(path(selected['template'])) if selected.get('template') else str(root/'capture-template.md')}
            if any(config.get(k) != v for k, v in expected.items()) or settings.get('tunnel_id') != selected.get('tunnel_id'):
                raise ValueError('Existing private identities/settings differ; omit private choices to preserve them')
    elif selected:
        if not isinstance(selected, dict):
            raise ValueError('Fresh private setup needs the selected vault, account and tunnel ID')
        vault = path(selected['vault'])
        if not vault.is_dir() or root.is_relative_to(vault) or vault.is_relative_to(root):
            raise ValueError('Choose an existing vault separate from the runtime')
        account, tunnel = selected.get('account', '').strip(), selected.get('tunnel_id', '')
        if not account or len(account) > 128 or not re.fullmatch(r'tunnel_[a-z0-9]{32}', tunnel):
            raise ValueError('Select a non-secret account label and your existing tunnel ID')
        vocabulary = selected.get('vocabulary', 'existing')
        if vocabulary not in ('existing', 'default'):
            raise ValueError('Choose the existing vault property vocabulary')
        archive = vault/'Inbox/ChatGPT Captures'
        if archive.exists() and any(archive.iterdir()):
            raise ValueError('Existing capture archives require their original runtime configuration')
        if selected.get('template'):
            template = path(selected['template'])
            if not template.is_relative_to(vault) or template.suffix != '.md':
                raise ValueError('Choose a Markdown template inside the existing vault')
            read(template, 1024 * 1024)
        else:
            template_bytes = read(SCRIPTS.parent/'assets/templates'/('capture-' + vocabulary + '.md'))
            template = root/'capture-template.md'
        config = {'enabled': True, 'account': account, 'spool': str(root/'spool'),
                  'destination': str(archive), 'vocabulary': vocabulary,
                  'template': str(template), 'readable_names': True}
        settings = {'version': 1, 'tunnel_id': tunnel}
    if config:
        if not isinstance(config, dict) or not isinstance(settings, dict):
            raise ValueError('Private configuration must contain objects')
        archive = path(config['destination'])
        if root == archive or root.is_relative_to(archive) or archive.is_relative_to(root):
            raise ValueError('The runtime and source archive must be separate')
        if 'bridge' in answers:
            bridge = answers['bridge']
            if not isinstance(bridge, dict):
                raise ValueError('Supply the selected bridge settings as an object')
            config['vault_bridge'] = bridge
    elif 'bridge' in answers:
        raise ValueError('A vault bridge requires a private connection')
    fs = answers.get('filesystem', (old or {}).get('filesystem'))
    if fs is False:
        if old and old.get('filesystem'):
            raise ValueError('Disable an existing Filesystem connection in its host; upgrade preserves it')
        fs = None
    if fs:
        check = connection_plan(fs['host'], fs['directories'], version=fs.get('version', TESTED_VERSION),
                                name=fs.get('name', DEFAULT_NAME))
        if any(root == Path(p) or root.is_relative_to(p) or Path(p).is_relative_to(root)
               for p in check['directories']):
            raise ValueError('Filesystem access and private runtime storage must be separate')
        fs = {'host': fs['host'], 'directories': check['directories'], 'version': check['package_version'],
              'name': check['name'], 'register': fs.get('register', False)}
        if fs['register']:
            original = answers.get('filesystem') or (old or {}).get('filesystem')
            fs['host_config'] = str(path(original['host_config']))
            if fs['host'] == 'stdio':
                raise ValueError('Choose a supported host to register a connection')
            host_file = Path(fs['host_config'])
            expected_name = 'config.toml' if fs['host'] == 'codex' else 'claude_desktop_config.json'
            if (host_file.name != expected_name or host_file.is_relative_to(root)
                    or any(host_file.is_relative_to(p) for p in fs['directories'])):
                raise ValueError('Choose the host configuration file outside runtime and selected folders')
    if not config and not fs:
        raise ValueError('Select a private connection, optional Filesystem MCP, or an existing runtime to update')
    files = source_files()
    config_bytes = before['capture-config.json'] if config and 'bridge' not in answers and before['capture-config.json'] else encoded(config) if config else None
    settings_bytes = before['runtime.json'] or (encoded(settings) if settings else None)
    fingerprint = digest(encoded({'source': {n: digest(b) for n, b in files.items()},
                                  'config': digest(config_bytes) if config_bytes else None,
                                  'settings': digest(settings_bytes) if settings_bytes else None,
                                  'filesystem': fs, 'node': NODE_VERSION if fs else None}))
    report = {'mode': 'preview', 'runtime': str(root), 'operation': 'update' if old or legacy else 'install',
              'private_connection': bool(config), 'filesystem': fs,
              'up_to_date': bool(old and old['fingerprint'] == fingerprint),
              'downloads': ['isolated Python dependencies'] + (['official tunnel-client'] if config else [])
                           + (['verified Node.js ' + NODE_VERSION, 'pinned Filesystem MCP'] if fs else []),
              'preserves': ['vault notes', 'account and archive identities', 'tunnel identity and profiles',
                            'credentials', 'templates', 'spool and bridge journal', 'previous runtime generations'],
              'starts_connection': False}
    return report, {'root': root, 'old': old, 'before': before, 'config': config_bytes,
                    'settings': settings_bytes, 'template': template_bytes, 'files': files,
                    'fingerprint': fingerprint, 'filesystem': fs, 'legacy': legacy}


def launcher(entry):
    # The stable path lets existing launch agents and tunnel profiles keep their identities.
    return ('''#!/usr/bin/env python3
import json, os, re, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
pointer = root / "install-current.json"
if (root / "install-pending.json").exists():
    raise SystemExit("Runtime update interrupted; rerun the same installer to finish it.")
if not pointer.exists():
    raise SystemExit("Runtime setup is incomplete; rerun the installer.")
state = json.loads(pointer.read_text())
identity = state.get("generation", "")
if not re.fullmatch(r"[a-f0-9]{32}", identity):
    raise SystemExit("Invalid runtime generation")
release = root / "releases" / identity
entry = ENTRY
if entry == "filesystem_mcp.py":
    if not state.get("filesystem"):
        raise SystemExit("Filesystem MCP is not selected")
    command = release / "node/bin/node"
    args = [str(command), str(release / "filesystem/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js"), *state["filesystem"]["directories"]]
else:
    command = release / "venv/bin/python"
    args = [str(command), str(release / "scripts" / entry), *sys.argv[1:]]
os.execv(str(command), args)
'''.replace('ENTRY', repr(entry))).encode()


def validate_generation(generation, config, template, filesystem=None):
    python = generation/'venv/bin/python'
    # Validation uses selected settings for no-write checks only; the save trial below
    # always uses a separate temporary synthetic archive.
    code = '''import json,sys,tempfile
from pathlib import Path
from private_capture import capture
from capture_mcp import build_server
import keyring
cfg=json.load(sys.stdin)
payload={"source":"manual","conversation_id":"installer-test","capture_id":"one","title":"Installer trial","coverage":"excerpt","messages":[{"id":"m1","role":"user","text":"Synthetic installation trial."}]}
if cfg:
    probe=dict(cfg);probe['enabled']=True
    capture(probe,payload)
    if cfg.get('vault_bridge',{}).get('enabled'):
        from vault_bridge import VaultBridge
        VaultBridge(cfg).conventions()
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp).resolve()
    test={"enabled":True,"account":"installer-synthetic","spool":str(root/'spool'),"destination":str(root/'archive')}
    assert capture(test,payload,True)['written']==1
    assert capture(test,payload,True)['written']==0
'''
    cfg = json.loads(config) if config else None
    if template is not None and cfg:
        target = generation/'preview-template.md'
        atomic(target, template)
        cfg['template'] = str(target)
    result = subprocess.run([str(python), '-c', code], cwd=generation/'scripts', input=json.dumps(cfg),
                            text=True, capture_output=True)
    if result.returncode:
        raise ValueError('Runtime validation failed; inspect selected configuration and templates. No vault notes were written.')
    if filesystem:
        code = '''import asyncio,sys,tempfile
from pathlib import Path
from datetime import timedelta
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def test():
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary).resolve(); allowed=root/'Selected'; allowed.mkdir()
        original=allowed/'test.md'; original.write_text('Installer fixture')
        params=StdioServerParameters(command=sys.argv[1],args=[sys.argv[2],str(allowed)])
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=30)) as session:
                await session.initialize()
                assert not (await session.call_tool('read_text_file',{'path':str(original)})).isError
                target=allowed/'saved.md'
                assert not (await session.call_tool('write_file',{'path':str(target),'content':'Synthetic save'})).isError
                assert target.read_text()=='Synthetic save'
                assert (await session.call_tool('write_file',{'path':str(root/'outside.md'),'content':'Denied'})).isError
                assert not (root/'outside.md').exists()
asyncio.run(test())
'''
        subprocess.run([str(python), '-c', code, str(generation/'node/bin/node'),
                        str(generation/'filesystem/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js')],
                       check=True, timeout=60)


def finish_host(root, state):
    fs = state.get('filesystem')
    if not fs:
        return {'status': 'not-selected'}
    connection = {'command': str(root/'venv/bin/python'), 'args': [str(root/'scripts/filesystem_mcp.py')]}
    atomic(root/'filesystem-connection.json', encoded(connection))
    if not fs.get('register'):
        return {'status': 'prepared', 'file': str(root/'filesystem-connection.json')}
    generation = root/'releases'/state['generation']
    result = subprocess.run([str(generation/'venv/bin/python'), str(generation/'scripts/install_host.py')],
                            input=json.dumps({'host': fs['host'], 'config_path': fs['host_config'],
                                              'name': fs['name'], 'connection': connection, 'apply': True}),
                            text=True, capture_output=True)
    if result.returncode:
        return {'status': 'pending', 'hint': 'Runtime installed. Host connection needs review; rerun after resolving its path or name conflict.'}
    return json.loads(result.stdout)


def install(answers, apply=False):
    report, data = inspect(answers)
    if not apply:
        return report
    root = data['root']
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with runtime_lock(root):
        if not (root/'install-owner.json').exists() and not data['legacy']:
            if {p.name for p in root.iterdir()} != {'.runtime.lock'}:
                raise ValueError('Destination changed during installation; nothing will be replaced')
            atomic(root/'install-owner.json', encoded({'owner': OWNER, 'runtime': str(root)}))
        # Check again under the lock, and reject a live legacy connection too.
        report, data = inspect(answers)
        from private_runtime import status
        if report['up_to_date'] and not (root/'install-pending.json').exists():
            host = finish_host(root, data['old'])
            result = {**report, 'mode': 'unchanged', 'generation': data['old']['generation'], 'host_connection': host}
            atomic(root/'install-receipt.json', encoded(result))
            return result
        if status(root)['live']:
            raise ValueError('Stop the existing private connection before updating; it will keep its settings')
        if not (root/'install-owner.json').exists():
            atomic(root/'install-owner.json', encoded({'owner': OWNER, 'runtime': str(root)}))
        identity = uuid.uuid4().hex
        (root/'releases').mkdir(exist_ok=True, mode=0o700)
        generation = root/'releases'/identity
        generation.mkdir(mode=0o700)
        for name, content in data['files'].items():
            file = generation/name
            file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            atomic(file, content)
        from install_dependencies import build
        receipt = build(generation, bool(data['config']), data['filesystem'])
        validate_generation(generation, data['config'], data['template'], data['filesystem'])
        for name, before in data['before'].items():
            if (read(root/name) if (root/name).exists() else None) != before:
                raise ValueError('Private settings changed during installation; previous runtime remains selected')
        if status(root)['live']:
            raise ValueError('The connection started during installation; stop it before switching versions')
        (root/'install-backups').mkdir(exist_ok=True, mode=0o700)
        backup = root/'install-backups'/identity
        backup.mkdir(mode=0o700)
        for name in ('capture-config.json', 'runtime.json', CURRENT):
            if (root/name).exists():
                atomic(backup/name, read(root/name))
        state = {'owner': OWNER, 'generation': identity, 'fingerprint': data['fingerprint'],
                 'filesystem': data['filesystem'], 'private_connection': bool(data['config']),
                 'previous_generation': (data['old'] or {}).get('generation'), 'dependencies': receipt}
        atomic(generation/'installation.json', encoded(state))
        # Publication is brief and restartable. Stable launchers refuse to run
        # during an interrupted publication instead of mixing generations.
        atomic(root/'install-pending.json', encoded({'generation': identity}))
        (root/'scripts').mkdir(mode=0o700, exist_ok=True)
        for entry in ('private_runtime.py', 'capture_mcp.py', 'filesystem_mcp.py'):
            file = root/'scripts'/entry
            if file.exists():
                atomic(backup/entry, read(file))
            atomic(file, launcher(entry))
        if not (root/'venv').exists():
            (root/'venv').symlink_to(generation/'venv', target_is_directory=True)
        if data['config'] and not (root/'install-initial.json').exists():
            atomic(root/'install-initial.json', encoded({'config': json.loads(data['config']), 'settings': json.loads(data['settings'])}))
        if data['template'] is not None and not (root/'capture-template.md').exists():
            atomic(root/'capture-template.md', data['template'])
        for name, content in (('capture-config.json', data['config']), ('runtime.json', data['settings'])):
            if content is not None and (not (root/name).exists() or read(root/name) != content):
                atomic(root/name, content)
        atomic(root/CURRENT, encoded(state))
        (root/'install-pending.json').unlink()
        host = finish_host(root, state)
        result = {**report, 'mode': 'installed', 'generation': identity,
                  'previous_generation': state['previous_generation'], 'backup': str(backup),
                  'host_connection': host, 'dependencies': receipt}
        if data['config']:
            result['connect_command'] = shlex.join([str(root/'venv/bin/python'), str(root/'scripts/private_runtime.py'), 'run', '--runtime', str(root)])
        atomic(root/'install-receipt.json', encoded(result))
        return result
