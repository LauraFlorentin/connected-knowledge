#!/usr/bin/env python3
"""Create a new vault only after the user declines using an existing one.

Two variants with the same folders, labels and entry points: ``templates`` adds
a Templates/ folder for Obsidian's core Templates plugin; ``no-templates`` keeps
every note shape in the Vault Guide instead. ``full`` creates the whole folder
structure now; ``minimal`` creates only the entry points and lets folders appear
when the first note needs them. Nothing under ``.obsidian/`` is ever written.
Standard library only.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import uuid

ASSETS = Path(__file__).resolve().parents[1]/'assets'
NOTE_TEMPLATES = ('source', 'conversation', 'idea', 'decision', 'entity', 'artifact', 'map')
FOLDERS = ('Inbox', 'Sources/AI Conversations', 'Sources/Documents', 'Ideas', 'Decisions', 'Entities',
           'Projects', 'Maps', 'Attachments/AI Transcripts', 'Attachments/Session Files', '_meta/index')
SHAPE_NAMES = {'source': 'Source (article, PDF, page)', 'conversation': 'Conversation saved by hand',
               'idea': 'Idea', 'decision': 'Decision', 'entity': 'Person, organization or project',
               'artifact': 'Something you made', 'map': 'Topic map'}
TOPIC = re.compile(r'^[^\[\]#|^:/\\*"<>?\x00-\x1f]{1,60}$')


def output_path(value):
    """Reject redirected destinations before resolve() erases symlink evidence."""
    path = Path(value).expanduser().absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink output paths are unsupported')
    return path.resolve()


def check_topics(topics):
    topics = [t.strip() for t in topics or []]
    if any(not TOPIC.match(t) or t.strip('. ') != t for t in topics):
        raise ValueError('Topic names may not contain [ ] # | ^ : / \\ * " < > ? or start or end with a dot')
    if len({t.casefold() for t in topics}) != len(topics):
        raise ValueError('Topic names must be unique')
    return topics


def template_text(name, ontology):
    text = (ASSETS/'templates'/(name + '.md')).read_text()
    return text.replace('category:\n', '') if ontology == 'none' else text


def topic_map(name, now):
    text = template_text('map', 'default').replace('category:\n', '')
    text = text.replace('"{{date:YYYYMMDDHHmmss}}"', '"' + str(uuid.uuid4()) + '"')
    text = text.replace('{{date:YYYY-MM-DDTHH:mm:ssZ}}', now).replace('{{title}}', name)
    return text.replace('classification_status: provisional', 'classification_status: reviewed')


def guide(ontology, categories, variant, topics):
    if ontology == 'none':
        category = 'Not used in this vault.'
    else:
        category = ', '.join(categories[:-1]) + ' or ' + categories[-1] if len(categories) > 1 else categories[0]
        category += ': what the note is for, not what it mentions. Leave it empty rather than guess'
    if topics:
        topic_text = '[[Home]] links to your main topics: ' + ', '.join('[[Maps/' + t + '|' + t + ']]' for t in topics) + '.'
    else:
        topic_text = ('[[Home]] will link to your main topics. Create one map per main topic in `Maps/` '
                      'and list it on Home.')
    if variant == 'templates':
        shapes = ('## Templates\n\nThe `Templates/` folder has one template per kind of note. To use them in '
                  'Obsidian: Settings → Core plugins → turn on Templates, then set its template folder '
                  'location to `Templates`. In a new note, run "Templates: Insert template". Obsidian '
                  'fills in the title, date and a time-based `id`.')
    else:
        blocks = []
        for name in NOTE_TEMPLATES:
            blocks.append('### ' + SHAPE_NAMES[name] + '\n\n````markdown\n' + template_text(name, ontology) + '````')
        shapes = ('## Note shapes\n\nThis vault has no templates folder. To start a note by hand, copy one '
                  'of the blocks below into a new note and replace `{{title}}` and the dates; for `id`, '
                  'use the current date and time as digits, for example 20261007143000. An agent can '
                  'do this for you.\n\n' + '\n\n'.join(blocks))
    text = (ASSETS/'vault-guide.md').read_text()
    return text.replace('{{topics}}', topic_text).replace('{{categories}}', category).replace('{{shapes}}', shapes)


def files(ontology='default', categories=None, variant='no-templates', structure='full', topics=None, now=None):
    """Everything the starter would create, as {relative path: text or None for a folder}."""
    if ontology not in ('none', 'default', 'custom'):
        raise ValueError('Invalid ontology choice')
    if ontology == 'custom' and (not categories or any(not isinstance(c, str) or not c.strip() for c in categories)):
        raise ValueError('Custom ontology requires nonempty category labels')
    if variant not in ('templates', 'no-templates'):
        raise ValueError('Choose the templates or no-templates variant')
    if structure not in ('full', 'minimal'):
        raise ValueError('Choose the full or minimal structure')
    categories = ['Admin', 'Personal', 'Work'] if ontology == 'default' else (categories or []) if ontology == 'custom' else []
    topics = check_topics(topics)
    now = now or datetime.now().astimezone().replace(microsecond=0).isoformat()
    out = {folder: None for folder in (FOLDERS if structure == 'full' else ())}
    main = '\n'.join('- [[Maps/' + t + '|' + t + ']]' for t in topics) or '- Add a link to each main topic map here.'
    out['Home.md'] = ((ASSETS/'home.md').read_text().replace('{{id}}', str(uuid.uuid4()))
                      .replace('{{created}}', now).replace('{{main_topics}}', main))
    out['Vault Guide.md'] = guide(ontology, categories, variant, topics)
    out['AGENTS.md'] = (ASSETS/'agents.md').read_text()
    out['CLAUDE.md'] = 'Read AGENTS.md before working in this vault.\n\n@AGENTS.md\n'
    out['GEMINI.md'] = 'Read AGENTS.md before working in this vault.\n'
    for topic in topics:
        out['Maps/' + topic + '.md'] = topic_map(topic, now)
    if variant == 'templates':
        for name in NOTE_TEMPLATES:
            out['Templates/' + name.capitalize() + '.md'] = template_text(name, ontology)
    profile = {'schema': 1, 'variant': variant, 'categories': categories, 'fields': {}, 'values': {},
               'folders': {'sessions': 'Sources/AI Conversations', 'transcripts': 'Attachments/AI Transcripts',
                           'session_files': 'Attachments/Session Files', 'projects': 'Projects',
                           'maps': 'Maps', 'index': '_meta/index'},
               'projects': {}}
    if variant == 'templates':
        profile['template_folders'] = ['Templates']
    out['_meta/ck/vault.json'] = json.dumps(profile, indent=2, ensure_ascii=False) + '\n'
    return out


def create(target, confirmed=False, ontology='default', categories=None, variant='no-templates',
           structure='full', topics=None):
    if not confirmed:
        raise ValueError('First establish that there is no existing vault the user wants to use')
    plan = files(ontology, categories, variant, structure, topics)
    target = output_path(target)
    if target.exists():
        raise ValueError('Target exists; refusing to merge into or replace a vault')
    target.mkdir(parents=True)
    for name, content in sorted(plan.items()):
        path = target.joinpath(*name.split('/'))
        if content is None:
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    return target


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('target', type=Path)
    p.add_argument('--confirmed-no-existing-vault', action='store_true')
    p.add_argument('--ontology', choices=['none', 'default', 'custom'], default='default')
    p.add_argument('--categories', nargs='*')
    p.add_argument('--variant', choices=['templates', 'no-templates'], default='no-templates')
    p.add_argument('--structure', choices=['full', 'minimal'], default='full')
    p.add_argument('--topic', action='append', dest='topics', default=[])
    p.add_argument('--preview', action='store_true', help='List what would be created; write nothing')
    a = p.parse_args()
    try:
        if a.preview:
            plan = files(a.ontology, a.categories, a.variant, a.structure, a.topics)
            print(json.dumps({'mode': 'preview', 'target': str(a.target),
                              'folders': sorted(k for k, v in plan.items() if v is None),
                              'files': sorted(k for k, v in plan.items() if v is not None)}, indent=2))
        else:
            print(create(a.target, a.confirmed_no_existing_vault, a.ontology, a.categories, a.variant,
                         a.structure, a.topics))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
