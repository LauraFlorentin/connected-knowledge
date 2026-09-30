#!/usr/bin/env python3
"""Preview or install a scoped Codex Stop hook; never enable capture or grant trust."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

from chat_import import atomic_write, encoded
from export_bundle import check_output

PLUGIN = Path(__file__).resolve().parents[3]


def setup(project, config, python=sys.executable, apply=False):
    project = check_output(project)
    config = check_output(config)
    interpreter = Path(python).expanduser()
    if not project.is_dir():
        raise ValueError('Select an existing project directory')
    if not interpreter.is_absolute() or not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise ValueError('Select an absolute executable Python with the plugin dependencies')
    cfg = json.loads(config.read_text())
    if cfg.get('host') != 'codex' or cfg.get('enabled') is not False:
        raise ValueError('Use a Codex config with enabled set to false during hook setup')
    if str(project) not in {str(Path(p).resolve()) for p in cfg.get('projects', [])}:
        raise ValueError('Project must be explicitly selected in the capture configuration')
    target = check_output(project / '.codex/hooks.json')
    original = target.read_bytes() if target.exists() else None
    document = json.loads(original) if original is not None else {}
    if not isinstance(document, dict) or not isinstance(document.get('hooks', {}), dict):
        raise ValueError('Existing hook configuration must be an object with a hooks object')
    command = shlex.join(['env', 'PLUGIN_ROOT='+str(PLUGIN),
                         'CONNECTED_KNOWLEDGE_CODEX_CONFIG='+str(config),
                         str(interpreter), str(PLUGIN/'hooks/capture.py')])
    handler = {'type': 'command', 'command': command, 'timeout': 30}
    updated = copy.deepcopy(document)
    hooks = updated.setdefault('hooks', {})
    already = False
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            raise ValueError('Existing hook event must contain a list of matcher groups')
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('hooks'), list):
                raise ValueError('Existing hook matcher group is malformed')
            for existing in group['hooks']:
                if not isinstance(existing, dict):
                    raise ValueError('Existing hook handler is malformed')
                if existing == handler and event == 'Stop' and not group.get('matcher'):
                    if already:
                        raise ValueError('Duplicate capture hooks already exist; review them first')
                    already = True
                elif 'hooks/capture.py' in str(existing.get('command', '')):
                    raise ValueError('Another capture hook exists; review it before replacing or adding')
    if not already:
        hooks.setdefault('Stop', []).append({'hooks': [handler]})
    result = {'target': str(target), 'changed': not already, 'applied': False,
              'capture_enabled': False, 'hook_configuration': updated,
              'next_steps': [
                  'Keep this machine-specific hook file private; do not commit it.',
                  'Run Codex in this project and use /hooks to review and trust this exact Stop hook.',
                  'Use one capture route: disable any bundled Connected Knowledge capture hook in /hooks before using this project hook.',
                  'Test with a synthetic-only configuration and temporary archive before enabling real capture.',
                  'Enable only the selected private capture config after review; set enabled to false to stop capture.',
                  'After moving or upgrading the plugin/Python, disable capture and review the paths before regenerating the hook.']}
    if apply and not already:
        # Preserve the original alongside the private setup configuration, never in the plugin.
        backup = config.parent / ('hooks-before-' + hashlib.sha256(str(target).encode()).hexdigest()[:16] + '.json')
        check_output(backup)
        if original is not None:
            if backup.exists() and backup.read_bytes() != original:
                raise ValueError('A different hook backup exists; preserve it before retrying')
            if not backup.exists():
                atomic_write(backup, original)
        if (target.read_bytes() if target.exists() else None) != original:
            raise ValueError('Hooks changed during setup; preview again')
        atomic_write(target, encoded(updated))
        result['applied'] = True
        result['backup'] = str(backup) if original is not None else None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(setup(args.project, args.config, args.python, args.apply), indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
