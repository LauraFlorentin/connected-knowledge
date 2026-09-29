#!/usr/bin/env python3
"""Read-only inventory or comparison of existing vaults; JSON on stdout."""
import argparse
import json
from pathlib import Path
import sys
from vault_check import check
from vault_profile import file_inventory


def inspect(vault, config=None):
    root = Path(vault).resolve()
    if not root.is_dir(): raise ValueError('Vault directory not found')
    before = file_inventory(root)
    validation = check(root, 'generic', config)
    settings = {}
    for name in ('templates.json', 'core-plugins.json', 'community-plugins.json', 'app.json', 'appearance.json'):
        p = root/'.obsidian'/name
        settings[name] = json.loads(p.read_text()) if p.exists() else None
    guide = (config or {}).get('guide')
    after = file_inventory(root)
    return {'vault':str(root), 'files':before, 'settings':settings,
            'guide':{'path':guide, 'present':guide in before if guide else None},
            'validation':validation, 'unchanged_during_check':before == after,
            'changed_during_check':differences(before, after),
            'evidence':{'filesystem':'checked', 'ui_trial':'not_performed',
                        'sync':'not_verified', 'user_reported':[]}}


def differences(left, right):
    return {'only_left':sorted(left.keys()-right.keys()),
            'only_right':sorted(right.keys()-left.keys()),
            'changed':sorted(k for k in left.keys() & right.keys() if left[k] != right[k]),
            'identical':sorted(k for k in left.keys() & right.keys() if left[k] == right[k])}


def compare(left, right, left_config=None, right_config=None):
    if right_config is None: right_config = left_config
    a, b = inspect(left, left_config), inspect(right, right_config)
    for snapshot in (a, b):
        final = file_inventory(Path(snapshot['vault']))
        snapshot['unchanged_during_check'] = snapshot['unchanged_during_check'] and snapshot['files'] == final
        snapshot['end_of_comparison_changes'] = differences(snapshot['files'], final)
    return {'left':a, 'right':b, 'files':differences(a['files'], b['files']),
            'settings':differences(a['settings'], b['settings']),
            'limits':'Filesystem observations only. Differences do not authorize merges or fixes. '
                     'Hashes compare matching relative paths, not semantic identity. No UI or sync test.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vault', type=Path)
    parser.add_argument('--compare', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--other-config', type=Path)
    a = parser.parse_args()
    try:
        cfg = json.loads(a.config.read_text()) if a.config else None
        other = json.loads(a.other_config.read_text()) if a.other_config else cfg
        if a.other_config and not a.compare: raise ValueError('--other-config requires --compare')
        report = compare(a.vault, a.compare, cfg, other) if a.compare else inspect(a.vault, cfg)
        print(json.dumps(report, indent=2))
        snapshots = [report['left'], report['right']] if a.compare else [report]
        return int(any(not s['unchanged_during_check'] or s['validation']['errors'] for s in snapshots))
    except Exception as exc:
        print(json.dumps({'status':'failed', 'error':str(exc)})); return 2


if __name__ == '__main__': sys.exit(main())
