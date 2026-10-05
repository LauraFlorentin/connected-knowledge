#!/usr/bin/env python3
"""Opt-in upstream stdio trial using only synthetic temporary folders.

Requires the development MCP dependency, Node.js and npx. Running this command
downloads/executes the specified upstream npm package; ordinary tests do not.
"""
import argparse
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'plugins/connected-knowledge/skills/zettelkasten-obsidian/scripts'))
from filesystem_setup import connection_plan


def text_content(result):
    return '\n'.join(item.text for item in result.content if item.type == 'text')


async def trial(version, npx=None):
    with tempfile.TemporaryDirectory(prefix='ck-filesystem-trial-') as temporary:
        root = Path(temporary).resolve()
        allowed, outside = root/'Selected Notes', root/'Outside'
        allowed.mkdir()
        outside.mkdir()
        note = allowed/'Fictional garden.md'
        note.write_text('Fictional pears.\n', encoding='utf-8')
        original = outside/'Untouched.md'
        original.write_text('Outside scope.\n', encoding='utf-8')
        (allowed/'outside-link').symlink_to(outside, target_is_directory=True)
        plan = connection_plan('stdio', [allowed], version=version, npx=npx)
        connection = plan['connection']
        # Keep dependency downloads and process working directory in the trial, too.
        env = {**os.environ, 'npm_config_cache': str(root/'npm-cache')}
        parameters = StdioServerParameters(command=connection['command'], args=connection['args'],
                                           cwd=str(root), env=env)
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=90)) as session:
                await session.initialize()
                tools = {tool.name for tool in (await session.list_tools()).tools}
                assert {'read_text_file', 'write_file', 'edit_file', 'move_file',
                        'list_allowed_directories', 'search_files'} <= tools
                async def call(name, arguments, error=False):
                    result = await session.call_tool(name, arguments)
                    assert bool(result.isError) == error, (name, text_content(result))
                    return text_content(result)
                scope = await call('list_allowed_directories', {})
                assert str(allowed) in scope and str(outside) not in scope, scope
                assert 'Fictional pears.' in await call('read_text_file', {'path': str(note)})
                assert str(note) in await call('search_files', {'path': str(allowed), 'pattern': '*.md'})
                saved = allowed/'Fictional draft.md'
                await call('write_file', {'path': str(saved), 'content': 'Draft pears.\n'})
                edit = {'path': str(saved), 'edits': [{'oldText': 'pears', 'newText': 'apples'}]}
                await call('edit_file', {**edit, 'dryRun': True})
                assert saved.read_text() == 'Draft pears.\n'
                await call('edit_file', edit)
                assert 'Draft apples.' in await call('read_text_file', {'path': str(saved)})
                moved = allowed/'Renamed draft.md'
                await call('move_file', {'source': str(saved), 'destination': str(moved)})
                assert not saved.exists() and moved.read_text() == 'Draft apples.\n'
                for forbidden in (original, allowed/'../Outside/Untouched.md',
                                  allowed/'outside-link/Untouched.md'):
                    await call('read_text_file', {'path': str(forbidden)}, error=True)
                    await call('write_file', {'path': str(forbidden), 'content': 'Must not write'}, error=True)
                await call('write_file', {'path': str(outside/'New.md'), 'content': 'Must not create'}, error=True)
                assert original.read_text() == 'Outside scope.\n' and not (outside/'New.md').exists()

        # A Roots-capable client replaces the command-line scope; verify that
        # documented behavior so setup instructions cannot imply a fixed sandbox.
        async def list_roots(_context):
            return types.ListRootsResult(roots=[types.Root(uri=outside.as_uri(), name='Synthetic replacement')])
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write, list_roots_callback=list_roots,
                                     read_timeout_seconds=timedelta(seconds=90)) as session:
                await session.initialize()
                for _ in range(30):
                    scope = text_content(await session.call_tool('list_allowed_directories', {}))
                    if str(outside) in scope and str(allowed) not in scope:
                        break
                    await asyncio.sleep(0.1)
                else:
                    raise AssertionError('Client Roots did not replace command-line scope: ' + scope)
                assert (await session.call_tool('read_text_file', {'path': str(note)})).isError
                assert not (await session.call_tool('read_text_file', {'path': str(original)})).isError
        return {'package_version': version, 'synthetic_stdio_trial': 'pass',
                'read_search_write_preview_edit_move': 'pass',
                'outside_traversal_symlink_denial': 'pass', 'client_roots_replacement': 'pass',
                'native_host_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True, help='Exact stable package version to download and execute')
    parser.add_argument('--npx', help='Absolute npx executable')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(asyncio.wait_for(trial(args.version, args.npx), timeout=180)), indent=2))


if __name__ == '__main__':
    main()
