#!/usr/bin/env python3
"""One guided private-runtime install/update, with optional Filesystem MCP."""
import argparse
import json
from pathlib import Path
import sys

from runtime_install import install, current
from install_support import path, read
from filesystem_setup import DEFAULT_NAME, TESTED_VERSION


def ask(prompt, default=''):
    return input(prompt + (f' [{default}]' if default else '') + ': ').strip() or default


def wizard():
    print('Connected Knowledge install / update — macOS/Linux, Python 3.10+.')
    print('Existing notes, accounts, credentials and connection identities stay in place.')
    root = path(ask('Private runtime folder', str(Path.home()/'.local/share/connected-knowledge')))
    answers = {'runtime': str(root)}
    existing = (root/'capture-config.json').exists()
    config = json.loads(read(root/'capture-config.json')) if existing else {}
    vault = None
    old = current(root) if (root/'install-current.json').exists() else None
    if existing:
        print('Existing private connection found. Its settings will be reused.')
    elif ask('Install the private chat-to-vault connection? y/n', 'y').lower() == 'y':
        vault = path(ask('Existing vault folder'))
        choices = {'vault': str(vault), 'account': ask('Non-secret account label', 'personal-chatgpt'),
                   'vocabulary': ask('Property vocabulary: existing or default', 'existing')}
        template = ask('Source template path relative to vault (blank uses bundled template)')
        if template:
            choices['template'] = str(vault/template)
        print('Reuse your tunnel ID, or create one in your own Platform tunnel settings.')
        print('https://platform.openai.com/settings/organization/tunnels')
        print('No key is requested or stored by this installer.')
        choices['tunnel_id'] = ask('Tunnel ID')
        answers['private'] = choices
    if config.get('vault_bridge'):
        print('Existing vault reading, preview and save settings will be reused.')
    elif existing or answers.get('private'):
        if ask('Add scoped note reading and previews? y/n', 'n').lower() == 'y':
            vault = vault or path(ask('Existing vault folder'))
            guide = ask('Existing vault guide relative path', 'Vault Guide.md')
            folders = [p.strip() for p in ask('Selected note folders, separated by commas').split(',') if p.strip()]
            draft = ask('Folder for developed notes (must be within selected scope)', 'Knowledge')
            templates = {}
            while True:
                role = ask('Template role, for example idea or map (blank when done)')
                if not role:
                    break
                templates[role] = ask('Existing template path relative to vault')
            identities = [p.strip() for p in ask('Note identity fields, separated by commas', 'id').split(',') if p.strip()]
            save = ask('Enable saving developed notes into that folder? y/n', 'n').lower() == 'y'
            answers['bridge'] = {'enabled': True, 'write_enabled': save, 'root': str(vault),
                                 'guide': guide, 'templates': templates, 'note_folders': folders,
                                 'draft_folder': draft, 'identity_fields': identities,
                                 'state_directory': str(root/'vault-bridge-state')}
    if old and old.get('filesystem'):
        print('Existing managed Filesystem settings will be reused.')
    elif ask('Install optional Filesystem MCP for broader file access? y/n', 'n').lower() == 'y':
        print('Selected folders allow reading and writing. Client Roots may change effective scope.')
        folders = []
        while True:
            folder = ask('Existing absolute folder (blank when done)')
            if not folder:
                break
            folders.append(folder)
        host = ask('Host: codex, claude-desktop, or stdio', 'codex')
        fs = {'host': host, 'directories': folders, 'version': TESTED_VERSION, 'name': DEFAULT_NAME}
        if host != 'stdio' and ask('Add the named connection to this host, preserving other settings? y/n', 'y').lower() == 'y':
            default = Path.home()/'.codex/config.toml' if host == 'codex' else Path.home()/'Library/Application Support/Claude/claude_desktop_config.json' if sys.platform == 'darwin' else None
            fs.update(register=True, host_config=ask('Host configuration path', str(default) if default else ''))
        answers['filesystem'] = fs
    print(json.dumps(install(answers), indent=2))
    print('Installation downloads the selected dependencies. Stop an existing connection before updating.')
    if ask('Apply this setup now? y/n', 'n').lower() != 'y':
        return {'mode': 'preview', 'message': 'Nothing installed or changed.'}
    return install(answers, True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--wizard', action='store_true')
    choice.add_argument('--answers', help='Private selected setup answers JSON')
    choice.add_argument('--runtime', help='Update an existing runtime using its current settings')
    parser.add_argument('--apply', action='store_true', help='Install/update selected components; default is preview')
    args = parser.parse_args()
    try:
        if args.wizard:
            result = wizard()
        else:
            answers = json.loads(read(path(args.answers))) if args.answers else {'runtime': args.runtime}
            result = install(answers, args.apply)
        print(json.dumps(result, indent=2))
        if result.get('host_connection', {}).get('status') == 'pending':
            return 3
        return 0
    except (ValueError, OSError, EOFError, KeyError) as exc:
        print('Installation could not finish: ' + str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        # A dependency's exception may include subprocess arguments or private data.
        print('Installation could not finish (' + type(exc).__name__ + '). '
              'Previous versions and private state were retained. Rerun the same setup after resolving the error.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
