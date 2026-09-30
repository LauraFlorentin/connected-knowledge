#!/usr/bin/env python3
"""Create an optional starter only after the user declines using an existing vault."""
import argparse
from pathlib import Path
import shutil
import sys
import yaml
from chat_import import output_path

def create(target,confirmed=False,ontology='default',categories=None):
    if not confirmed: raise ValueError('First establish that there is no existing vault the user wants to use')
    if ontology not in ('none','default','custom'): raise ValueError('Invalid ontology choice')
    if ontology == 'custom' and (not categories or any(not isinstance(c,str) or not c.strip() for c in categories)):
        raise ValueError('Custom ontology requires nonempty category labels')
    target=output_path(target)
    if target.exists(): raise ValueError('Target exists; refusing to merge into or replace a vault')
    target.mkdir(parents=True)
    templates=Path(__file__).resolve().parents[1]/'assets/templates'
    shutil.copytree(templates,target/'Templates')
    shutil.copyfile(templates.parent/'vault-guide.md',target/'VAULT-GUIDE.md')
    if ontology != 'default':
        for path in (target/'Templates').glob('*.md'):
            _, front, body = path.read_text().split('---',2)
            meta = yaml.safe_load(front)
            meta.pop('category',None)
            meta.pop('schema_version',None)
            path.write_text('---\n'+yaml.safe_dump(meta,sort_keys=False)+'---'+body.replace('choose category','optionally add a selected category'))
        guide = target/'VAULT-GUIDE.md'
        text = guide.read_text().replace('Keep categories Admin / Personal / Work in properties, without duplicating each note in three folder trees.',
            'Classification is disabled.' if ontology == 'none' else 'Optional category labels: '+', '.join(categories)+'. Do not guess a category.')
        text = text.replace('For the default skill schema, use `schema_version`, `id`, `note_type`, `category`, `title`, and applicable review/source fields.',
            'Use `id`, `note_type`, `title`, and applicable review/source fields. Category is optional; use generic validation for these templates.')
        guide.write_text(text)
    (target/'START HERE.md').write_text('''# Your optional starter

This is a minimal new workspace, created only after you chose not to use an existing vault. Open this folder as a vault in Obsidian. No app configuration or community plugins were installed.

1. Choose one useful source and preserve its reference and scope.
2. Copy the Source template into Sources when needed. Replace every placeholder; use a new UUID and your Admin, Personal or Work category.
3. Develop one reusable idea in Ideas, with reasoning, limits and an exact source locator. Do not turn every sentence into a note.
4. Link an existing related idea and explain why; if none exists, do not invent one.
5. Use your notes to answer a real question. Add Maps only when a reading path helps.

Keep automatic research captures in a separate reviewable inbox. Decide which deserve development. Templates are manual; replace placeholders and remove unused sections. The package worked example is fictional and is not your own research. Existing-vault users should adapt these conventions instead of copying this starter over their notes.
''')
    if ontology != 'default':
        path=target/'START HERE.md'
        path.write_text(path.read_text().replace('and your Admin, Personal or Work category','and only the metadata selected in your vault guide'))
    return target

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('target',type=Path); p.add_argument('--confirmed-no-existing-vault',action='store_true')
    p.add_argument('--ontology',choices=['none','default','custom'],default='default'); p.add_argument('--categories',nargs='*'); a=p.parse_args()
    try: print(create(a.target,a.confirmed_no_existing_vault,a.ontology,a.categories)); return 0
    except Exception as exc: print(str(exc),file=sys.stderr); return 2
if __name__=='__main__': sys.exit(main())
