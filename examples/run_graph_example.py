#!/usr/bin/env python3
"""Synthetic, temporary import-to-graph example; no real vault or API calls."""
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/connected-knowledge/skills/zettelkasten-obsidian/scripts'))
from chat_import import run
from knowledge_graph import search, apply_plan
from vault_check import check

with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary).resolve();vault=root/'vault';vault.mkdir()
    export=root/'export.json'
    export.write_text(json.dumps([{'id':'demo','title':'Garden questions','messages':[
        {'id':'user-1','role':'user','text':'Can mint grow in partial shade?'}]}]))
    imported=run(export,vault/'Archive','normalized','demo',True,vocabulary='existing')
    hit=search(vault,'Archive','mint')['results'][0]
    evidence={'source':hit['source'],'source_sha256':hit['source_sha256'],'message':hit['message'],
              'reason':'The user raised a research question; no answer is established.'}
    plan={'version':1,'notes':[
        {'id':'mint-question','kind':'idea','title':'Investigate mint light needs','category':'Personal',
         'body':'Check a reliable horticultural source about partial shade.','evidence':[evidence]},
        {'id':'garden-map','kind':'map','title':'Garden research questions','category':'Personal',
         'body':'Start with the open question about mint.','evidence':[evidence],
         'links':[{'node':'mint-question','relation':'related','reason':'An unresolved question to investigate.'}]}]}
    result=apply_plan(vault,'Archive','Knowledge',plan,True,['Personal'],'existing')
    validation=check(vault,'generic')
    repeat=apply_plan(vault,'Archive','Knowledge',plan,True,['Personal'],'existing')
    assert imported['written']==1 and result['written']==2
    assert validation['errors']==0 and validation['warnings']==0 and repeat['written']==0
    print(json.dumps({'imported':1,'graph_notes':2,'edges':result['edges'],
                      'checker_errors':0,'checker_warnings':0,'repeat_writes':0},indent=2))
