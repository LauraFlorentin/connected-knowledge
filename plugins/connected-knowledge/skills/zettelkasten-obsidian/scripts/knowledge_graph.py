#!/usr/bin/env python3
"""Inspect imported chats and apply evidence-backed graph proposals as Markdown."""
import argparse
import json
from pathlib import Path
import re
import sys
import yaml
from chat_import import atomic_write, digest, encoded, normalize
from vault_check import UniqueLoader

KINDS = {'idea', 'decision', 'entity', 'map', 'review'}
RELATIONS = {'supports', 'challenges', 'extends', 'applies', 'related', 'supersedes'}


def safe_path(root, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError('Expected a relative path')
    if any(c in name for c in '\n\r[]|#') or '..' in Path(name).parts:
        raise ValueError('Unsafe Markdown path')
    path = root/name
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path leaves the selected vault')
    current = root
    for part in Path(name).parts:
        current = current/part
        if current.is_symlink():
            raise ValueError('Symlinks are not supported')
    return path


def metadata(data):
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', data.decode('utf-8'), re.S)
    if not match:
        raise ValueError('Missing frontmatter')
    result = yaml.load(match.group(1), Loader=UniqueLoader)
    if not isinstance(result, dict):
        raise ValueError('Frontmatter must be a mapping')
    return result


def load_sources(vault, archive):
    root = Path(vault).resolve()
    folder = safe_path(root, archive)
    manifest = safe_path(root, (folder/'manifest.json').relative_to(root).as_posix())
    state = json.loads(manifest.read_bytes())
    if state.get('version') != 1:
        raise ValueError('Unsupported archive version')
    snapshots, originals, sources = {manifest: digest(manifest.read_bytes())}, {}, {}
    for key, record in state['records'].items():
        note = safe_path(root, (folder/record['path']).relative_to(root).as_posix())
        data = note.read_bytes()
        if digest(data) != record['sha256']:
            raise ValueError('Imported note changed; reconcile before graph development: '+note.name)
        meta = metadata(data)
        original_name = record.get('original', meta.get('source_file'))
        original = safe_path(root, (folder/original_name).relative_to(root).as_posix())
        if original not in originals:
            raw = original.read_bytes()
            if digest(raw) != original.stem:
                raise ValueError('Original export hash mismatch')
            originals[original] = json.loads(raw)
            snapshots[original] = digest(raw)
        platform, account, cid = meta['conversation_source'], meta['account_label'], meta['conversation_id']
        if key != digest(encoded([platform, account, cid])):
            raise ValueError('Archive identity mismatch')
        matches = [r for r in originals[original] if
                   (r.get('uuid') if platform == 'claude' else r.get('id', r.get('conversation_id'))) == cid]
        if len(matches) != 1:
            raise ValueError('Source record missing or ambiguous')
        chat = normalize(matches[0], platform)
        sources[key] = dict(chat, key=key, path=note.relative_to(root).as_posix(),
                            sha256=digest(data), platform=platform, account=account)
        snapshots[note] = digest(data)
    return sources, snapshots


def search(vault, archive, query='', limit=20):
    if not 1 <= limit <= 100:
        raise ValueError('Limit must be between 1 and 100')
    sources, _ = load_sources(vault, archive)
    terms = query.casefold().split()
    hits = []
    for key, source in sources.items():
        for message in source['messages']:
            haystack = (source['title']+' '+message['text']).casefold()
            score = sum(term in haystack for term in terms)
            if terms and score == 0:
                continue
            anchor = 'msg-'+digest(message['id'].encode())[:20]
            hits.append({'source':key, 'source_sha256':source['sha256'], 'title':source['title'],
                         'message':message['id'], 'role':message['role'], 'date':message['date'],
                         'parent':message['parent'], 'text':message['text'],
                         'citation':source['path']+'#^'+anchor, 'score':score})
    hits.sort(key=lambda h:(-h['score'], h['source'], h['message']))
    return {'query':query, 'matching_messages':len(hits), 'results':hits[:limit],
            'truncated':len(hits)>limit, 'method':'lexical search; scores are not evidence strength'}


def sentence(value, label):
    if not isinstance(value, str) or not value.strip() or '\n' in value or '\r' in value or '[[' in value or '](' in value:
        raise ValueError(label+' must be a nonempty single line')
    return value


def apply_plan(vault, archive, output, plan, apply=False, categories=None, vocabulary='default'):
    root = Path(vault).resolve()
    if vocabulary not in ('default', 'existing'):
        raise ValueError('Unknown vocabulary')
    folder = safe_path(root, output)
    archive_path = safe_path(root, archive)
    if folder == root or folder.is_relative_to(archive_path) or archive_path.is_relative_to(folder):
        raise ValueError('Graph output must be separate from the source archive')
    if not isinstance(plan, dict) or plan.get('version') != 1 or not isinstance(plan.get('notes'), list):
        raise ValueError('Expected version 1 plan with a notes array')
    sources, snapshots = load_sources(root, archive)
    state_path = safe_path(root, (folder/'.graph-state.json').relative_to(root).as_posix())
    state_before = state_path.read_bytes() if state_path.exists() else None
    state = json.loads(state_before) if state_before else {'version':1, 'notes':{}}
    if state.get('version') != 1:
        raise ValueError('Unsupported graph state')
    nodes, paths, rendered, edges = {}, {}, {}, []
    for note in plan['notes']:
        nid = note.get('id')
        if not isinstance(nid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', nid) or nid in nodes:
            raise ValueError('Note IDs must be unique safe identifiers')
        if note.get('kind') not in KINDS:
            raise ValueError('Unsupported note kind')
        sentence(note.get('title'), 'Title')
        if not isinstance(note.get('body'), str) or not note['body'].strip():
            raise ValueError('Each note needs a body')
        if '[[' in note['body'] or '](' in note['body']:
            raise ValueError('Use structured evidence and links rather than unchecked links in body')
        if note.get('category') and (not categories or note['category'] not in categories):
            raise ValueError('Category is not in the selected ontology')
        if not isinstance(note.get('evidence'), list) or not note['evidence']:
            raise ValueError('Each note requires message evidence')
        nodes[nid] = note
        paths[nid] = safe_path(root, (folder/(nid+'.md')).relative_to(root).as_posix())
    for nid, note in nodes.items():
        path = paths[nid]
        meta = {'title':note['title']}
        if vocabulary == 'existing':
            meta.update(type=note['kind'], status='auto')
            if note['kind'] == 'review': meta['review_kind'] = 'conversation'
            if note['kind'] == 'decision': meta['decision_state'] = 'proposed'
        else:
            meta.update(note_type='artifact' if note['kind'] == 'review' else note['kind'], review_status='draft')
            if note['kind'] == 'review': meta['artifact_type'] = 'report'
            if note['kind'] == 'decision': meta['decision_status'] = 'proposed'
        if note.get('category'): meta['category'] = note['category']
        text = '---\n'+yaml.safe_dump(meta,allow_unicode=True,sort_keys=False)+'---\n\n# '+note['title']+'\n\n'
        text += 'Assistant-authored proposal; factual accuracy and classification need review.\n\n'+note['body']+'\n\n## Evidence\n\n'
        for evidence in note['evidence']:
            source = sources.get(evidence.get('source'))
            if not source or evidence.get('source_sha256') != source['sha256']:
                raise ValueError('Unknown or changed source; prepare a fresh proposal')
            mids = {m['id'] for m in source['messages']}
            mid = evidence.get('message')
            if mid not in mids:
                raise ValueError('Evidence message not found')
            reason = sentence(evidence.get('reason'), 'Evidence explanation')
            target = source['path']+'#^msg-'+digest(mid.encode())[:20]
            text += '- [['+target+']] — '+reason+'\n'
            edges.append({'from':path.relative_to(root).as_posix(),'to':target,'relation':'derives_from','reason':reason})
        if note.get('links'): text += '\n## Connections\n\n'
        for link in note.get('links', []):
            relation = link.get('relation')
            reason = sentence(link.get('reason'), 'Connection explanation')
            if relation not in RELATIONS:
                raise ValueError('Unknown relationship')
            if ('node' in link) == ('target' in link):
                raise ValueError('Link requires exactly one node or existing target')
            if 'node' in link:
                target_path = paths.get(link['node'])
                if target_path is None: raise ValueError('Unknown proposal node')
            else:
                target_path = safe_path(root, link['target'])
                if target_path.suffix != '.md' or not target_path.is_file():
                    raise ValueError('Existing link target must be a Markdown file')
                snapshots[target_path] = digest(target_path.read_bytes())
            target = target_path.relative_to(root).as_posix()
            text += '- [['+target+']] — '+relation+': '+reason+'\n'
            edges.append({'from':path.relative_to(root).as_posix(),'to':target,'relation':relation,'reason':reason})
        rendered[nid] = text.encode('utf-8')
    report = {'mode':'apply' if apply else 'preview','items':[], 'edges':edges, 'written':0,'conflicts':0}
    writes = []
    for nid, content in rendered.items():
        path = paths[nid]
        before = path.read_bytes() if path.exists() else None
        old = state['notes'].get(nid)
        if (old and (before is None or digest(before) != old['sha256'])) or (not old and before is not None):
            action = 'conflict'; report['conflicts'] += 1
        else:
            action = 'unchanged' if before == content else ('updated' if old else 'created')
            if action != 'unchanged': writes.append((nid,path,content,before))
        report['items'].append({'id':nid,'path':path.relative_to(root).as_posix(),'action':action})
    if not apply or report['conflicts'] or not writes: return report
    folder.mkdir(parents=True, exist_ok=True)
    lock = safe_path(root, (folder/'.graph.lock').relative_to(root).as_posix())
    with lock.open('x'): pass
    try:
        if (state_path.read_bytes() if state_path.exists() else None) != state_before:
            raise ValueError('Graph state changed; retry')
        for path, expected in snapshots.items():
            safe_path(root, path.relative_to(root).as_posix())
            if digest(path.read_bytes()) != expected: raise ValueError('Source or target changed after preview')
        for nid,path,content,before in writes:
            safe_path(root, path.relative_to(root).as_posix())
            if (path.read_bytes() if path.exists() else None) != before: raise ValueError('Note changed after preview')
            if before is not None:
                revision = safe_path(root,(folder/'.revisions'/(nid+'-'+digest(before)+'.md')).relative_to(root).as_posix())
                atomic_write(revision,before)
            atomic_write(path,content)
            state['notes'][nid] = {'path':path.relative_to(root).as_posix(),'sha256':digest(content)}
            atomic_write(state_path,encoded(state))
            report['written'] += 1
    finally:
        lock.unlink()
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('vault',type=Path);p.add_argument('--archive',required=True)
    p.add_argument('--query',default='');p.add_argument('--limit',type=int,default=20)
    p.add_argument('--plan',type=Path);p.add_argument('--output',default='Knowledge')
    p.add_argument('--apply',action='store_true');p.add_argument('--categories',nargs='+')
    p.add_argument('--vocabulary',choices=['default','existing'],default='default')
    a=p.parse_args()
    try:
        if a.apply and not a.plan: raise ValueError('--apply requires a reviewed plan')
        result = apply_plan(a.vault,a.archive,a.output,json.loads(a.plan.read_text()),a.apply,a.categories,a.vocabulary) if a.plan else search(a.vault,a.archive,a.query,a.limit)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return int(bool(result.get('conflicts')))
    except Exception as exc:
        print(json.dumps({'status':'failed','error':str(exc)}));return 2

if __name__=='__main__':sys.exit(main())
