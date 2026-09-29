#!/usr/bin/env python3
"""Opt-in local Codex/Claude Code transcript adapter; hook or historical preview."""
import argparse
import json
from pathlib import Path
import sys
from chat_import import atomic_write, digest, encoded, run


def parse_transcript(raw, host, expected_session=None):
    messages, session_ids, projects, warnings = [], set(), set(), set()
    for number, line in enumerate(raw.decode('utf-8').splitlines(),1):
        if not line.strip(): continue
        try: row=json.loads(line)
        except ValueError: raise ValueError('Incomplete or invalid JSONL; retry after the writer finishes')
        if not isinstance(row,dict): raise ValueError('Unexpected transcript row')
        if host=='codex':
            data=row.get('payload',{})
            if row.get('type')=='session_meta':
                sid=data.get('id',data.get('session_id'))
                if sid: session_ids.add(sid)
                if data.get('cwd'): projects.add(data['cwd'])
            if row.get('type')!='response_item' or data.get('type')!='message': continue
            role=data.get('role')
            if role not in ('user','assistant'): continue
            mid=data.get('id') or ('ordinal-'+str(row['ordinal']) if isinstance(row.get('ordinal'),int) else 'line-'+str(number))
            parent=None
            content=data.get('content')
        elif host=='claude-code':
            if row.get('isSidechain'): continue
            sid=row.get('sessionId',row.get('session_id'))
            if sid: session_ids.add(sid)
            if row.get('cwd'): projects.add(row['cwd'])
            if row.get('type') not in ('user','assistant'): continue
            data=row.get('message',{})
            role=data.get('role',row['type'])
            mid=row.get('uuid');parent=row.get('parentUuid');content=data.get('content')
            if not mid: raise ValueError('Claude Code message UUID missing')
        else: raise ValueError('Unsupported host')
        if isinstance(content,str): text=content
        elif isinstance(content,list):
            parts=[]
            for block in content:
                if isinstance(block,dict) and block.get('type') in ('text','input_text','output_text') and isinstance(block.get('text'),str):
                    parts.append(block['text'])
                else: warnings.add('Non-text/tool content excluded from the Markdown conversation; retained in raw snapshot.')
            text='\n\n'.join(parts)
        else: raise ValueError('Unrecognized message content schema')
        if text:
            messages.append({'id':str(mid),'role':role,'text':text,'date':row.get('timestamp'),'parent':parent})
    if len(session_ids)!=1: raise ValueError('Missing or mixed session identity')
    sid=next(iter(session_ids))
    if expected_session and expected_session!=sid: raise ValueError('Hook/transcript session identity mismatch')
    if len(projects)!=1: raise ValueError('Missing or mixed project identity')
    if not messages: raise ValueError('No supported user/assistant text messages')
    if len({m['id'] for m in messages})!=len(messages): raise ValueError('Duplicate message identity; transcript needs reconciliation')
    return {'id':host+':'+sid,'title':host+' session '+sid,
            'coverage':'Observed local user/assistant text only; tool/system/non-text content excluded. Account completeness unverified.',
            'messages':messages,'capture_warnings':sorted(warnings)},next(iter(projects)),sid


def safe_file(path, roots):
    p=Path(path).expanduser()
    if not p.is_absolute(): raise ValueError('Transcript path must be absolute')
    if p.is_symlink() or any(a.is_symlink() for a in p.parents): raise ValueError('Symlink transcript paths are unsupported')
    p=p.resolve()
    if not any(p.is_relative_to(Path(r).expanduser().resolve()) for r in roots):
        raise ValueError('Transcript is outside selected source folders')
    if p.suffix!='.jsonl' or not p.is_file(): raise ValueError('Expected a local JSONL transcript')
    return p


def capture(config, transcript, apply=False, event=None):
    host=config.get('host')
    roots=config.get('transcript_roots',[]);allowed=config.get('projects',[])
    if not roots or not allowed: raise ValueError('Select transcript_roots and projects first')
    if event and event.get('hook_event_name') not in ('Stop','SessionEnd'):
        return {'status':'skipped','reason':'Unsupported hook event'}
    if event and (event.get('agent_id') or event.get('agent_transcript_path')):
        return {'status':'skipped','reason':'Subagent capture not selected'}
    path=safe_file(transcript,roots)
    raw=path.read_bytes()
    chat,project,sid=parse_transcript(raw,host,event.get('session_id') if event else None)
    project_path=Path(project).resolve()
    if project_path not in {Path(p).expanduser().resolve() for p in allowed}:
        return {'status':'excluded','reason':'Project not selected'}
    if event and Path(event.get('cwd','')).resolve()!=project_path: raise ValueError('Hook project mismatch')
    if event and event.get('last_assistant_message'):
        assistants=[m['text'] for m in chat['messages'] if m['role']=='assistant']
        if not assistants or assistants[-1]!=event['last_assistant_message']:
            raise ValueError('Final assistant message not yet reflected in transcript; retry at a later event')
    report={'status':'preview','host':host,'session_id':sid,'messages':len(chat['messages']),
            'warnings':chat['capture_warnings'],'written':0}
    if not apply:return report
    if config.get('enabled') is not True: raise ValueError('Capture is disabled in configuration')
    account=config.get('account')
    if not isinstance(account,str) or not account.strip():raise ValueError('Select a non-secret account label')
    spool=Path(config['spool']).expanduser();destination=Path(config['destination']).expanduser()
    if not spool.is_absolute() or not destination.is_absolute():raise ValueError('Spool and destination must be absolute')
    if spool.is_symlink() or destination.is_symlink():raise ValueError('Symlink destinations unsupported')
    spool=spool.resolve();destination=destination.resolve()
    if spool==destination or spool.is_relative_to(destination) or destination.is_relative_to(spool):
        raise ValueError('Use separate private spool and archive directories')
    spool.mkdir(parents=True,exist_ok=True)
    lock=spool/'.capture.lock'
    with lock.open('x'):pass
    try:
        # Per-session checkpoint prevents a compacted/truncated snapshot from
        # replacing a longer archive. No suffix-only transcript updates.
        key=digest(encoded([host,account,sid]))
        previous=spool/(key+'.json')
        if previous.is_symlink():raise ValueError('Symlink checkpoint unsupported')
        if previous.exists():
            old=json.loads(previous.read_bytes())
            old_ids=[m['id'] for m in old['messages']];new_ids=[m['id'] for m in chat['messages']]
            if new_ids[:len(old_ids)]!=old_ids:raise ValueError('Transcript shrank or history changed; reconcile instead of replacing')
        for folder in ('raw','normalized'):
            if (spool/folder).is_symlink():raise ValueError('Symlink spool directory unsupported')
        source=spool/'raw'/(digest(raw)+'.jsonl')
        if source.is_symlink():raise ValueError('Symlink snapshot unsupported')
        if source.exists() and source.read_bytes()!=raw:raise ValueError('Raw snapshot integrity failure')
        if not source.exists():atomic_write(source,raw)
        chat['raw_snapshot']=str(source)
        normalized=encoded([chat]);input_path=spool/'normalized'/(digest(normalized)+'.json')
        if input_path.is_symlink():raise ValueError('Symlink normalized input unsupported')
        atomic_write(input_path,normalized)
        imported=run(input_path,destination,'normalized',account,True,
                     vocabulary=config.get('vocabulary','default'))
        if imported['failed'] or imported['conflicts']:raise ValueError('Archive conflict; inspect importer report: '+json.dumps(imported))
        atomic_write(previous,encoded(chat))
        report.update(status='captured' if imported['written'] else 'unchanged',written=imported['written'])
        atomic_write(spool/'last-result.json',encoded(report))
    finally:lock.unlink()
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--transcript',type=Path)
    p.add_argument('--hook',action='store_true')
    p.add_argument('--history',action='store_true')
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    try:
        config=json.loads(a.config.read_text())
        if sum((a.hook,a.history,a.transcript is not None))!=1:
            raise ValueError('Choose exactly one of --hook, --history, or --transcript')
        if a.history:
            files=sorted({p for folder in config.get('transcript_roots',[])
                          for p in Path(folder).expanduser().rglob('*.jsonl') if 'subagents' not in p.parts})
            results=[]
            for path in files:
                try: results.append(capture(config,path,a.apply))
                except Exception as exc: results.append({'status':'failed','file':path.name,'error':str(exc)})
            print(json.dumps({'files':len(files),'results':results},indent=2))
            return int(any(r['status']=='failed' for r in results))
        event=json.load(sys.stdin) if a.hook else None
        path=event.get('transcript_path') if event else a.transcript
        if not path:raise ValueError('No transcript available')
        report=capture(config,path,a.apply,event)
        # Hook stdout never injects captured text or workflow instructions.
        print('{}' if a.hook else json.dumps(report,indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'status':'failed','error':str(exc)}),file=sys.stderr)
        if a.hook:print('{}')
        return 1 if a.hook else 2

if __name__=='__main__':sys.exit(main())
