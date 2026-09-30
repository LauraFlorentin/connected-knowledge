#!/usr/bin/env python3
"""Build a guided, reviewable setup plan without importing history or enabling hooks."""
import argparse
import json
from pathlib import Path
import shlex
import sys
from chat_import import atomic_write, encoded, digest
from export_bundle import check_output, prepare

SCRIPTS = Path(__file__).resolve().parent


def plan(answers, directory):
    directory = check_output(directory)
    vault = check_output(answers['vault'])
    mode = answers.get('vault_mode')
    if mode not in ('existing','starter'):
        raise ValueError('Choose existing or starter vault')
    if mode == 'existing' and not vault.is_dir():
        raise ValueError('Existing vault unavailable; supply its real path, not a replacement')
    if mode == 'starter' and vault.exists():
        raise ValueError('Starter target must not already exist')
    if directory == vault or directory.is_relative_to(vault) or vault.is_relative_to(directory):
        raise ValueError('Keep setup/runtime storage separate from the vault')
    vocabulary = answers.get('vocabulary','default')
    if mode == 'starter':
        vocabulary = 'default'
    if vocabulary not in ('default','existing'):
        raise ValueError('Choose a supported property vocabulary after reading the vault guide')
    ontology = answers.get('ontology','none')
    if ontology not in ('none','default','custom'):
        raise ValueError('Choose none, default or custom ontology')
    categories = [] if ontology == 'none' else ['Admin','Personal','Work'] if ontology == 'default' else answers.get('categories',[])
    if (ontology == 'custom' and not categories) or not isinstance(categories,list) or any(not isinstance(c,str) or not c.strip() for c in categories) or len(set(categories)) != len(categories):
        raise ValueError('Custom categories must be unique nonempty strings')
    steps = []
    def step(label, script, *args):
        steps.append({'label':label,'argv':[sys.executable,str(SCRIPTS/script),*map(str,args)]})
    if mode == 'starter':
        step('Create the explicitly selected new starter', 'starter_vault.py', vault,
             '--confirmed-no-existing-vault','--ontology',ontology,*(['--categories',*categories] if ontology == 'custom' else []))
    else:
        step('Read-only baseline; read the existing vault guide first','vault_check.py',vault,'--profile','generic')
    history = answers.get('history',[])
    if not isinstance(history,list):
        raise ValueError('History must be a list of explicitly selected exports')
    for i, item in enumerate(history):
        platform = item['platform']
        if platform not in ('claude','chatgpt','normalized'):
            raise ValueError('Unsupported export platform')
        account = item.get('account','').strip()
        if not account:
            raise ValueError('Each source needs a stable non-secret account label')
        source = Path(item['source']).expanduser()
        if not source.is_absolute() or not source.is_file():
            raise ValueError('Select an existing absolute export path')
        source = source.resolve()
        if source.is_relative_to(vault) or source.is_relative_to(directory):
            raise ValueError('Keep original exports outside the vault and setup directory')
        if source.suffix.lower() == '.zip':
            member = item.get('conversation_member')
            if not member:
                raise ValueError('Inspect ZIP and select its exact conversation JSON member first')
            attachments = item.get('attachments',[])
            prepare(source,conversation=member,platform=platform,attachments=attachments)
            bundle = directory/('bundle-'+str(i+1))
            args = [source,'--destination',bundle,'--conversation-member',member,'--platform',platform]
            for attachment in attachments:
                args.extend(['--attachment',attachment])
            step('Preview selected ZIP and attachments', 'export_bundle.py',*args)
            step('Prepare private bundle after reviewing selection','export_bundle.py',*args,'--apply')
            source = bundle/'conversations.json'
        elif source.suffix.lower() != '.json':
            raise ValueError('Choose JSON or ZIP; local agent history uses capture configuration')
        dest = vault/'ChatArchive'/(platform+'-'+digest(encoded(account))[:16])
        args = [source,dest,'--platform',platform,'--account',account,'--vocabulary',vocabulary]
        if categories:
            args.extend(['--categories',*categories])
        step('Preview history; add --apply only after reviewing this result','chat_import.py',*args)
    captures = []
    for item in answers.get('capture',[]):
        host = item.get('host')
        if host not in ('codex','claude-code') or any(c['host']==host for c in captures):
            raise ValueError('Choose at most one capture configuration per supported host')
        account = item.get('account','').strip()
        if not account:
            raise ValueError('Capture needs a non-secret account label')
        for field in ('transcript_roots','projects'):
            if not item.get(field) or any(not Path(p).is_absolute() or not Path(p).is_dir() for p in item[field]):
                raise ValueError('Select existing absolute capture roots and exact project directories')
        for folder in item['transcript_roots']:
            root = Path(folder).resolve()
            for output in (directory, vault/'ChatArchive'):
                if output == root or output.is_relative_to(root) or root.is_relative_to(output):
                    raise ValueError('Keep capture transcript roots separate from runtime and archive output')
        cfg = {'host':host,'enabled':False,'account':account,
               'transcript_roots':item['transcript_roots'],'projects':item['projects'],
               'spool':str(directory/('spool-'+host)), 'destination':str(vault/'ChatArchive'/host),
               'vocabulary':vocabulary}
        captures.append(cfg)
        step('Preview selected local history; capture is disabled','session_capture.py',
             '--config',directory/('capture-'+host+'.json'),'--history')
    return {'version':1,'vault_mode':mode,'vault':str(vault),'vocabulary':vocabulary,
            'ontology':ontology,'categories':categories,'history':history,'capture':captures,'steps':steps,
            'scope':'Setup plan only. No imports, starter creation, classifications or hooks have run.'}


def save_setup(answers,directory,apply=False):
    result = plan(answers,directory)
    if not apply:
        return result
    dest = check_output(directory)
    if dest.exists():
        raise ValueError('Setup directory already exists; preserve it and select a new destination')
    # Exclusive directory creation makes repeated setup fail without replacing prior choices.
    dest.mkdir(parents=True,mode=0o700)
    atomic_write(dest/'setup.json',encoded(result))
    for cfg in result['capture']:
        atomic_write(dest/('capture-'+cfg['host']+'.json'),encoded(cfg))
    text = '# Your setup plan\n\n'+result['scope']+'\n\nRead your vault guide before executing these steps. Commands are supplied as separate reviewable actions, not a script to run blindly.\n\n'
    text += 'Ontology: '+result['ontology']+'. Categories are optional annotations, not automatic classifications. Capture remains disabled.\n\n'
    for s in result['steps']:
        text += '## '+s['label']+'\n\n```sh\n'+shlex.join(s['argv'])+'\n```\n\n'
    for cfg in result['capture']:
        variable = 'CONNECTED_KNOWLEDGE_CODEX_CONFIG' if cfg['host']=='codex' else 'CONNECTED_KNOWLEDGE_CLAUDE_CODE_CONFIG'
        text += 'Bundled '+cfg['host']+' capture: set `'+variable+'` in the host launch environment to `'+str(dest/('capture-'+cfg['host']+'.json'))+'`. Set `CONNECTED_KNOWLEDGE_PYTHON` to the Python environment with dependencies. The config remains disabled.\n\n'
    text += 'After history import, use graph-development.md for evidence-backed proposals. Follow bundled-hooks.md and test a synthetic session before enabling configuration and trusting the bundled hook. Do not duplicate it with a manual registration. Preserve the setup folder when retrying an interrupted setup; do not overwrite it.\n'
    atomic_write(dest/'NEXT-STEPS.md',text.encode())
    return result


def wizard():
    mode = input('Vault: existing or starter? [existing] ').strip() or 'existing'
    a = {'vault_mode':mode,'vault':input('Absolute vault path: ').strip(),
         'vocabulary':input('Properties: existing (type/status) or default? [existing] ').strip() or 'existing',
         'ontology':input('Categories: none, default (Admin/Personal/Work), or custom? [none] ').strip() or 'none',
         'history':[],'capture':[]}
    if a['ontology']=='custom':
        a['categories']=[s.strip() for s in input('Comma-separated categories: ').split(',')]
    while True:
        source=input('Absolute JSON/ZIP export path (blank to finish history selection): ').strip()
        if not source:break
        item={'source':source,'platform':input('Platform: claude, chatgpt, normalized: ').strip(),
              'account':input('Stable non-secret account label: ').strip()}
        if source.lower().endswith('.zip'):
            inventory=prepare(source)
            print(json.dumps({'members':inventory['members']},indent=2))
            item['conversation_member']=input('Exact conversation JSON member: ').strip()
            item['attachments']=[]
            while True:
                path=input('Exact attachment member (blank to finish): ').strip()
                if not path:break
                item['attachments'].append(path)
        a['history'].append(item)
    for host in ('codex','claude-code'):
        if input('Prepare disabled '+host+' capture? [y/N] ').strip().lower()!='y':continue
        a['capture'].append({'host':host,'account':input('Account label: ').strip(),
            'transcript_roots':[input('Absolute transcript root: ').strip()],
            'projects':[input('Absolute project directory: ').strip()]})
    return a


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--answers',type=Path)
    mode.add_argument('--wizard',action='store_true')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--apply',action='store_true',help='Save setup files only; never execute planned actions')
    a=p.parse_args()
    try:
        answers=wizard() if a.wizard else json.loads(a.answers.read_text())
        print(json.dumps(save_setup(answers,a.output,a.apply),indent=2))
        return 0
    except Exception as e:
        print(json.dumps({'error':str(e)}),file=sys.stderr)
        return 2

if __name__=='__main__':sys.exit(main())
