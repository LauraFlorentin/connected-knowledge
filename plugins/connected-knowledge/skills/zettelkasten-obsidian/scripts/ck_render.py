"""Render conversation notes and transcripts as inert Markdown (standard library only).

Chat text is data. Before it reaches the vault, anything Obsidian or a community
plugin would act on is neutralised: code fences in non-allowlisted languages
(``dataviewjs``, ``query``, ``tasks``, ``base`` …) become ``text``, inline
Dataview queries are defused, and wikilinks, embeds, Markdown links and images,
tags, comments, HTML, task checkboxes and Dataview inline fields are escaped.
The exact original stays in the private raw copy.
"""
import hashlib
import json
import re

INERT_LANGUAGES = frozenset('''
text txt plain plaintext markdown md python py python3 javascript js mjs cjs typescript ts tsx jsx
json jsonc json5 jsonl yaml yml toml ini cfg conf xml html htm css scss sass less sql bash sh zsh
shell console terminal shell-session powershell ps1 bat cmd go golang rust rs java kotlin kt swift
c h cpp c++ cc hpp cs csharp objective-c objc ruby rb php perl pl lua r scala dart elixir ex erlang
haskell hs clojure ocaml fsharp diff patch dockerfile docker makefile make cmake graphql gql proto
protobuf csv tsv log nginx apache latex tex vim regex http svelte vue astro sol solidity zig nim julia
matlab groovy gradle terraform hcl nix applescript swiftui output stdout stderr
'''.split())
FENCE = re.compile(r'^( {0,3})(`{3,}|~{3,})(.*)$')
HEADING = re.compile(r'^( {0,3})(#{1,6})(?=\s|$)')
RULE = re.compile(r'^( {0,3})([-=_*])((?:\s*\2){2,})\s*$')
TASK = re.compile(r'^(\s*(?:[-*+]|\d+[.)])\s+)\[([ xX/-])\]')
TAG = re.compile(r'(^|(?<=[\s(\[{"\'>,;]))#(?=[^\s#\d\]\)])')
INLINE_FIELD = re.compile(r'(\w)::')
CODE_SPAN = re.compile(r'(`+)(.+?)\1')
MARK_BEGIN = '%% ck:begin — written by Connected Knowledge. Changes inside this block are replaced on the next update. %%'
MARK_END = '%% ck:end %%'
DATE_KEYS = ('created', 'updated', 'source_created', 'source_updated')
ISO = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d([+-]\d\d:\d\d|Z)$')
TITLE_UNSAFE = re.compile(r'[\[\]#|^<>:"/\\?*\x00-\x1f%]')


def escape_text(segment):
    segment = segment.replace('<', '&lt;').replace('%%', '\\%\\%')
    segment = segment.replace('[[', '\\[\\[').replace('![', '\\![').replace('](', ']\\(')
    segment = TAG.sub(lambda m: m.group(1) + '\\#', segment)
    return INLINE_FIELD.sub(lambda m: m.group(1) + ':\\:', segment)


def escape_line(line):
    line = HEADING.sub(lambda m: m.group(1) + '\\' + m.group(2), line, count=1)
    line = RULE.sub(lambda m: m.group(1) + '\\' + m.group(2) + m.group(3), line, count=1)
    line = TASK.sub(lambda m: m.group(1) + '\\[' + m.group(2) + ']', line, count=1)
    out, last = [], 0
    for span in CODE_SPAN.finditer(line):
        out.append(escape_text(line[last:span.start()]))
        code = span.group(2)
        if code.lstrip().startswith(('=', '$=')):
            # Dataview runs inline code that starts with "=" or "$=".
            code = '\u2060' + code
        out.append(span.group(1) + code + span.group(1))
        last = span.end()
    out.append(escape_text(line[last:]))
    return ''.join(out)


def inert(text):
    """Markdown that displays the same words but cannot run, link, embed or tag."""
    out, fence = [], None
    for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        match = FENCE.match(line)
        if fence is None:
            if match and not (match.group(2)[0] == '`' and '`' in match.group(3)):
                indent, marks, info = match.groups()
                language = info.strip().split()[0].lower() if info.strip() else ''
                fence = (marks[0], len(marks))
                out.append(indent + marks + (language if language in INERT_LANGUAGES or not language else 'text'))
                continue
            out.append(escape_line(line))
        else:
            if match and match.group(2)[0] == fence[0] and len(match.group(2)) >= fence[1] and not match.group(3).strip():
                fence = None
            out.append(line)
    if fence:
        # An unclosed fence would swallow the rest of the transcript.
        out.append(fence[0] * fence[1])
    return '\n'.join(out)


def one_line(text, limit=240):
    text = ' '.join(text.replace('`', '').split())
    if len(text) > limit:
        text = text[:limit].rsplit(' ', 1)[0] + ' …'
    return escape_line(text)


def clean_title(text, words=5):
    text = TITLE_UNSAFE.sub(' ', text or '')
    text = re.sub(r'[*_~`=]', '', text)
    return ' '.join(text.split()[:words]).strip(' .-—') or 'Untitled conversation'


# --------------------------------------------------------------- flat YAML

class FrontmatterError(ValueError):
    pass


def scalar(value, key=None):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    value = str(value)
    if key in DATE_KEYS and ISO.match(value):
        return value
    return json.dumps(value, ensure_ascii=False)


def dump(meta):
    lines = ['---']
    for key, value in meta.items():
        if isinstance(value, list):
            if not value:
                lines.append(key + ': []')
            else:
                lines.append(key + ':')
                lines.extend('  - ' + scalar(item) for item in value)
        else:
            text = scalar(value, key)
            lines.append(key + ':' + (' ' + text if text else ''))
    return '\n'.join(lines + ['---']) + '\n'


def parse_scalar(text):
    text = text.strip()
    if text == '' or text in ('null', '~', 'Null', 'NULL'):
        return None
    if text in ('true', 'True', 'TRUE'):
        return True
    if text in ('false', 'False', 'FALSE'):
        return False
    if text.startswith('"'):
        try:
            return json.loads(text)
        except ValueError:
            raise FrontmatterError('Unsupported quoted value')
    if text.startswith("'"):
        if not text.endswith("'") or len(text) < 2:
            raise FrontmatterError('Unterminated quoted value')
        return text[1:-1].replace("''", "'")
    if text[0] in '|>{&*!%@`':
        raise FrontmatterError('Unsupported YAML construct')
    if re.match(r'^-?\d+$', text):
        return int(text)
    return text


def split_inline_list(text):
    items, current, quote = [], '', None
    for char in text:
        if quote:
            current += char
            if char == quote:
                quote = None
        elif char in '"\'':
            quote = char
            current += char
        elif char == ',':
            items.append(current)
            current = ''
        else:
            current += char
    if quote:
        raise FrontmatterError('Unterminated quoted list item')
    if current.strip():
        items.append(current)
    return [parse_scalar(item) for item in items]


def split_note(text):
    """Return (frontmatter dict, body). Only flat properties are supported."""
    if not text.startswith('---\n'):
        raise FrontmatterError('Note has no frontmatter')
    end = text.find('\n---\n', 3)
    if end >= 0:
        body = text[end + 5:]
    elif text.endswith('\n---'):
        end, body = len(text) - 4, ''
    else:
        raise FrontmatterError('Unterminated frontmatter')
    meta, open_list = {}, None
    for line in text[4:end].split('\n'):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        item = re.match(r'^\s*-(?:\s+(.*))?$', line)
        if item:
            if open_list is None:
                raise FrontmatterError('List item without a property')
            if meta[open_list] is None:
                meta[open_list] = []
            meta[open_list].append(parse_scalar(item.group(1) or ''))
            continue
        match = re.match(r'^([A-Za-z_][\w .-]*?)\s*:(?:\s+(.*))?$', line)
        if not match or line[0].isspace():
            raise FrontmatterError('Unsupported frontmatter line')
        key, value = match.group(1), (match.group(2) or '').strip()
        if key in meta:
            raise FrontmatterError('Duplicate property: ' + key)
        open_list = None
        if value == '':
            meta[key], open_list = None, key
        elif value.startswith('[') and value.endswith(']'):
            meta[key] = split_inline_list(value[1:-1])
        else:
            meta[key] = parse_scalar(value)
    return meta, body


# ------------------------------------------------------------ vocabulary

def to_vault(meta, profile):
    """Apply an adopted vault's own property names and values."""
    fields, values = profile.get('fields', {}), profile.get('values', {})
    out = {}
    for key, value in meta.items():
        mapping = values.get(key, {})
        if isinstance(value, str) and value in mapping:
            value = mapping[value]
        out[fields.get(key, key)] = value
    return out


def field(profile, name):
    return profile.get('fields', {}).get(name, name)


# --------------------------------------------------------------- rendering

def anchor(message_id):
    return 'm-' + hashlib.sha256(message_id.encode('utf-8')).hexdigest()[:10]


def speaker(role, platform):
    if role == 'user':
        return 'You'
    if role == 'command':
        return 'Command'
    return {'Claude Code': 'Claude', 'Claude': 'Claude', 'Codex': 'Codex', 'ChatGPT': 'ChatGPT'}.get(platform, 'Assistant')


def clock(stamp, previous_day=None):
    if not stamp:
        return ''
    day, time_of_day = stamp[:10], stamp[11:16]
    return time_of_day if day == previous_day else day + ' ' + time_of_day


def transcript(session, labels):
    meta = {'transcript_of': labels['id'], 'source_platform': session['platform'],
            'source_id': session['native_id'], 'title': labels['title']}
    lines = ['# Transcript: ' + labels['title'], '',
             'Conversation note: [[' + labels['note_link'] + '|' + labels['title'] + ']]', '',
             'Written by Connected Knowledge from ' + labels['origin'] + '. It is replaced when the '
             'conversation continues, so do not edit it; add your thoughts to the conversation note. '
             'Links, tags and code from the conversation are shown as plain text.', '']
    day = None
    for number, message in enumerate(session['messages'], 1):
        heading = '## ' + str(number) + ' · ' + speaker(message['role'], session['platform'])
        when = clock(message.get('time'), day)
        if message.get('time'):
            day = message['time'][:10]
        lines.append(heading + (' · ' + when if when else ''))
        lines.append('')
        if message['role'] == 'command':
            lines.append('`' + message['text'].replace('`', '') + '`')
        elif message['text'].strip():
            lines.append(inert(message['text'].strip('\n')))
        if message.get('tools'):
            lines.extend(['', '_Tools used: ' + escape_text(', '.join(sorted(set(message['tools'])))) + '_'])
        lines.extend(['', '^' + anchor(message['id']), ''])
    return dump(meta) + '\n'.join(lines).rstrip('\n') + '\n'


def generated_block(session, labels):
    category = labels.get('category')
    heading = '# ' + ('[' + category + '] ' if category else '') + labels['title']
    first = next((m['text'] for m in session['messages'] if m['role'] == 'user' and m['text'].strip()), '')
    counts = {}
    for message in session['messages']:
        counts[message['role']] = counts.get(message['role'], 0) + 1
    skipped = session.get('skipped', {})
    hidden = skipped.get('meta', 0) + skipped.get('wrapper', 0)
    where = session['platform'] + (' on ' + labels['machine'] if labels.get('machine') else '')
    if labels.get('surface') and labels['surface'] != 'cli':
        where += ' (' + labels['surface'] + ')'
    lines = [MARK_BEGIN, heading, '', '## In brief',
             labels.get('summary') or 'Not summarised yet. Ask your assistant to summarise this conversation.',
             '']
    if first:
        lines += ['Started with: “' + one_line(first) + '”', '']
    lines += ['## Read the source',
              '[Full transcript](<' + labels['transcript_link'] + '>) · ' + str(len(session['messages']))
              + ' messages · ' + where,
              'Coverage: what you and the assistant wrote. Tool calls are listed by name only'
              + ('; ' + str(hidden) + ' system or harness messages are left out' if hidden else '') + '.', '',
              '## Details']
    if labels.get('project_link'):
        lines.append('- Project: [[' + labels['project_link'] + ']]')
    if labels.get('topic_links'):
        lines.append('- Topics: ' + ', '.join('[[' + t + ']]' for t in labels['topic_links']))
    if session.get('created'):
        start, end = session['created'][:16].replace('T', ' '), (session.get('updated') or '')[:16].replace('T', ' ')
        if end and end != start:
            start += ' → ' + (end[11:] if end[:10] == start[:10] else end)
        lines.append('- When: ' + start)
    parts = [str(counts[role]) + (' from ' + speaker(role, session['platform']) if role != 'command'
                                  else ' command' + ('s' if counts[role] > 1 else ''))
             for role in ('user', 'assistant', 'command') if counts.get(role)]
    lines.append('- Messages: ' + ', '.join(parts).replace('from You', 'from you'))
    lines.append(MARK_END)
    return '\n'.join(lines)


NEW_NOTE_TAIL = '\n\n## My notes\n\n\n## Derived knowledge\nNone yet.\n'
USER_KEYS = ('title', 'category', 'classification_status', 'review_status', 'topics', 'aliases', 'project')


def conversation_note(session, labels, meta, profile, existing=None, explicit=()):
    """Full note text. With ``existing`` text, only the generated block and the
    machine-owned properties change; the person's properties and text stay,
    except properties the person explicitly set again (``explicit``)."""
    block = generated_block(session, labels)
    meta = to_vault(meta, profile)
    if existing is None:
        return dump(meta) + block + NEW_NOTE_TAIL
    old, body = split_note(existing)
    start, end = body.find(MARK_BEGIN), body.find(MARK_END)
    if start < 0 or end < start or body.count(MARK_BEGIN) != 1 or body.count(MARK_END) != 1:
        raise FrontmatterError('The generated block markers were changed')
    merged = dict(meta)
    for key in USER_KEYS:
        name = field(profile, key)
        if name in old and key not in explicit:
            merged[name] = old[name]
    for name in (field(profile, 'created'), ):
        if old.get(name):
            merged[name] = old[name]
    for name, value in old.items():
        if name not in merged:
            merged[name] = value
    return dump(merged) + body[:start] + block + body[end + len(MARK_END):]
