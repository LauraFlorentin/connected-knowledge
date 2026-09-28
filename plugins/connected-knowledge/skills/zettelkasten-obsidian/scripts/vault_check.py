#!/usr/bin/env python3
"""Read-only vault checks. Requires PyYAML and pypdf. JSON report on stdout."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import yaml
from pypdf import PdfReader

class UniqueLoader(yaml.SafeLoader): pass

def unique_mapping(loader, node, deep=False):
    result = {}
    for k, v in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in result: raise ValueError(f'Duplicate YAML key: {key}')
        result[key] = loader.construct_object(v, deep=deep)
    return result
UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

ENUMS = {'note_type': ['source','idea','decision','entity','artifact','map'],
         'category':['Admin','Personal','Work'], 'review_status':['draft','reviewed','disputed'],
         'classification_status':['provisional','reviewed'], 'decision_status':['proposed','adopted','superseded'],
         'artifact_status':['proposed','in_progress','implemented']}
LISTS = ['aliases','topics','components','proposed_components','reported_components']

def body_only(text):
    return re.sub(r'`[^`\n]*`', '', re.sub(r'^(`{3,}|~{3,}).*?^\1\s*$', '', text, flags=re.M|re.S))

def check(vault, profile='auto', config=None):
    root = Path(vault).resolve()
    if not root.is_dir(): raise ValueError('Vault directory not found')
    cfg = config or {}
    fields = cfg.get('fields', {})
    excluded = {'.obsidian','.git','Templates','templates', *cfg.get('exclude_dirs',[])}
    findings, texts, ids, names, field_types = [], {}, defaultdict(list), defaultdict(list), defaultdict(set)
    def add(code, path, message, severity='error'):
        findings.append({'severity':severity,'code':code,'path':str(path.relative_to(root)), 'message':message})
    files = [p for p in root.rglob('*') if p.is_file() and not p.is_symlink() and not any(x in excluded or x.startswith('.') for x in p.relative_to(root).parts)]
    for f in files:
        names[f.name.casefold()].append(f)
        if f.suffix.lower()=='.md': names[f.stem.casefold()].append(f)
    parsed = {}
    for f in files:
        if f.suffix.lower()!='.md': continue
        try: text = f.read_text(encoding='utf-8-sig')
        except Exception as exc: add('unreadable',f,str(exc)); continue
        texts[f] = text
        fm = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)',text,re.S)
        meta = {}
        if text.startswith('---') and not fm: add('frontmatter',f,'Unterminated YAML frontmatter')
        if fm:
            try:
                meta = yaml.load(fm.group(1), Loader=UniqueLoader) or {}
                if not isinstance(meta,dict): raise ValueError('Frontmatter must be a mapping')
            except Exception as exc: add('yaml',f,str(exc)); meta={}
        parsed[f] = meta
        for key,value in meta.items():
            if value is not None: field_types[key].add(type(value).__name__)
        ident = meta.get(fields.get('id','id'))
        if ident is not None:
            if not isinstance(ident,str) or not ident: add('id-type',f,'Identifier must be a nonempty string')
            else: ids[ident].append(f)
        strict = profile=='zettelkasten' or (profile=='auto' and meta.get('schema_version')==1)
        required = cfg.get('required', ['schema_version','id','note_type','category','title'] if strict else [])
        for key in required:
            actual=fields.get(key,key)
            if actual not in meta or meta[actual] in (None,''): add('required',f,f'Missing {actual}')
        if strict:
            if meta.get('schema_version') != 1: add('schema-version',f,'Expected schema_version: 1')
            for key, allowed in ENUMS.items():
                actual=fields.get(key,key)
                if actual in meta and meta[actual] not in cfg.get('enums',{}).get(key,allowed): add('enum',f,f'Invalid {actual}: {meta[actual]!r}')
            for key in LISTS:
                value=meta.get(fields.get(key,key))
                if value is not None and (not isinstance(value,list) or any(not isinstance(x,str) for x in value)):
                    add('list-type',f,f'{key} must be a list of strings')
        if 'source_file' in meta and 'source_sha256' in meta:
            target=(root/str(meta['source_file'])).resolve()
            if not target.is_relative_to(root): add('source-path',f,'Source is outside vault')
            elif not target.is_file(): add('source-missing',f,'Source file missing')
            elif hashlib.sha256(target.read_bytes()).hexdigest()!=meta['source_sha256']: add('source-drift',f,'Source bytes differ from recorded hash')
    for ident, matches in ids.items():
        if len(matches)>1:
            for f in matches: add('duplicate-id',f,f'{ident}: '+', '.join(str(x.relative_to(root)) for x in matches))
    for key, types in field_types.items():
        if len(types)>1:
            for f,meta in parsed.items():
                if key in meta: add('inconsistent-type',f,f'{key} has types {sorted(types)} across vault','warning')
    for name, matches in names.items():
        if len(set(matches))>1 and not name.endswith('.md'):
            for f in set(matches): add('duplicate-name',f,f'Ambiguous short name: {name}','warning')
    for f,text in texts.items():
        clean=body_only(text)
        links=[(m.group(1).split('|')[0],True) for m in re.finditer(r'!?\[\[([^\]\n]+)\]\]',clean)]
        links += [(m.group(1).strip('<>'),False) for m in re.finditer(r'(?<!!)\[[^\]\n]*\]\(([^)\s]+)\)',clean)]
        for raw,wiki in links:
            if urlsplit(raw).scheme or raw.startswith('//'): continue
            path,sep,anchor=unquote(raw).partition('#')
            target=None
            if not path: target=f
            else:
                candidates=[]
                bases=[root/path,f.parent/path] if wiki else [f.parent/path]
                for base in bases:
                    for q in [base,Path(str(base)+'.md')] if wiki else [base]:
                        q=q.resolve()
                        if q.is_relative_to(root) and q in files: candidates.append(q)
                if not candidates and wiki and '/' not in path: candidates=names.get(path.casefold(),[])
                candidates=list(set(candidates))
                if len(candidates)==1: target=candidates[0]
                else:
                    add('ambiguous-link' if candidates else 'broken-link',f,raw); continue
            if sep and anchor:
                if target.suffix.lower()=='.pdf' and anchor.startswith('page='):
                    try:
                        n=int(anchor[5:].split('&')[0]); total=len(PdfReader(target).pages)
                        if not 1<=n<=total: raise ValueError(f'Page {n} outside 1..{total}')
                    except Exception as exc: add('pdf-page',f,f'{raw}: {exc}')
                elif target.suffix.lower()=='.md':
                    dest=body_only(texts.get(target,''))
                    headings=re.findall(r'^#{1,6}\s+(.+?)\s*#*$',dest,re.M)
                    slug=lambda x: re.sub(r'[^\w\- ]','',x.casefold()).replace(' ','-')
                    if anchor.startswith('^'):
                        exists=bool(re.search(r'\^'+re.escape(anchor[1:])+r'\s*$',dest,re.M))
                    else: exists=anchor.casefold() in [h.casefold() for h in headings] or anchor in [slug(h) for h in headings]
                    if not exists: add('missing-anchor',f,raw,'warning')
    return {'vault':str(root),'profile':profile,'files_checked':len(texts),'errors':sum(x['severity']=='error' for x in findings),'warnings':sum(x['severity']=='warning' for x in findings),'findings':findings,
            'limits':'Structural checks only; no truth validation. Basic inline Markdown and wikilinks; complex Markdown reference links, escaped syntax and Obsidian renderer edge cases need human review.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('vault',type=Path); p.add_argument('--profile',choices=['auto','generic','zettelkasten'],default='auto')
    p.add_argument('--config',type=Path); p.add_argument('--strict',action='store_true')
    a=p.parse_args()
    try:
        result=check(a.vault,a.profile,json.loads(a.config.read_text()) if a.config else None)
        print(json.dumps(result,indent=2)); return int(result['errors']>0 or (a.strict and result['warnings']>0))
    except Exception as exc: print(json.dumps({'status':'failed','error':str(exc)})); return 2
if __name__=='__main__': sys.exit(main())
