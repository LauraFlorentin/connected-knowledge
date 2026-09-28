#!/usr/bin/env python3
"""Offline fictional worked example; refuses to reuse an existing output folder."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from reportlab.pdfgen import canvas
import yaml

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'plugins/connected-knowledge/skills/zettelkasten-obsidian/scripts'
sys.path.insert(0,str(SCRIPTS))
import collect
import extract_pdf
import vault_check

def note(path,metadata,body):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('---\n'+yaml.safe_dump(metadata,sort_keys=False)+'---\n'+body)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',required=True,type=Path); a=p.parse_args()
    dest=a.output.resolve()
    if dest.exists(): p.error('Use an absent output directory; this never modifies an existing vault')
    dest.mkdir(parents=True); incoming=dest/'incoming'; incoming.mkdir()
    pdf=incoming/'Fictional-pilot.pdf'; c=canvas.Canvas(str(pdf))
    lines=['FICTIONAL TRAINING EXAMPLE - NOT REAL RESEARCH', 'Routine-case pilot: handling time decreased by 20 percent.', 'Escalations were excluded. Sample size was not recorded.', 'This fixture demonstrates provenance; it supports no real-world claim.']
    for i,line in enumerate(lines): c.drawString(35,760-i*22,line)
    c.showPage(); c.drawString(35,760,'FICTIONAL EXAMPLE: no measured escalation data are available.'); c.showPage(); c.save()
    cfg=dest/'collection.json'; cfg.write_text(json.dumps({'inbox':'inbox','ongoing_enabled':False,'sources':[{'id':'fictional-demo','kind':'local','enabled':True,'path':'incoming','glob':'*.pdf'}]},indent=2))
    first=collect.run(cfg); repeat=collect.run(cfg)
    record=json.loads(next((dest/'inbox/records').glob('*.json')).read_text())
    raw=dest/'inbox'/record['raw_path']; extraction=extract_pdf.extract(raw,dest/'extraction')
    # A fixture vault for this demonstration only, not a starter for the user's real notes.
    vault=dest/'fictional-example-vault'; (vault/'Attachments').mkdir(parents=True)
    shutil.copyfile(raw,vault/'Attachments/Fictional-pilot.pdf')
    common={'schema_version':1,'category':'Work','review_status':'draft'}
    note(vault/'Sources/Example pilot source.md',dict(common,id='example-source-001',note_type='source',title='Example pilot source',source_file='Attachments/Fictional-pilot.pdf',source_sha256=record['sha256'],evidence_kind='source-claim'),'''# Example pilot source

FICTIONAL TRAINING FIXTURE. Not user research or a real study.

## Source and coverage
Generated two-page PDF; text inspected on both physical pages. Page 1 reports a fictional 20% change for routine cases, excludes escalations and omits sample size. Page 2 states escalation measurements are absent.

[[Attachments/Fictional-pilot.pdf#page=1|Physical PDF page 1]]

## Derived knowledge
[[Ideas/A narrow pilot cannot establish overall improvement]] explains the limitation; it is an illustrative synthesis, not a verified empirical finding.
''')
    note(vault/'Ideas/A narrow pilot cannot establish overall improvement.md',dict(common,id='example-idea-001',note_type='idea',title='A narrow pilot cannot establish overall improvement',evidence_kind='agent-inference'),'''# A narrow pilot cannot establish overall improvement

FICTIONAL WORKED EXAMPLE.

## Claim and reasoning
The fictional routine-case result does not establish an overall improvement because escalation cases were excluded and their handling times and share are unknown. Generalization requires evidence on those cases and the case mix.

## Source and limit
Derived from [[Sources/Example pilot source]] and [[Attachments/Fictional-pilot.pdf#page=1|page 1]]. This is reasoning about a synthetic fixture, not advice based on real banking research. No independent corroboration exists.
''')
    note(vault/'Maps/Example research map.md',dict(common,id='example-map-001',note_type='map',title='Example research map'),'''# Example research map

FICTIONAL WORKED EXAMPLE. Question: what does the pilot establish?

1. Read [[Sources/Example pilot source]] for its scope.
2. Read [[Ideas/A narrow pilot cannot establish overall improvement]] for the inferred boundary.
3. Missing evidence: sample size, escalation measurements, and case mix.
''')
    before={str(p.relative_to(vault)):hashlib.sha256(p.read_bytes()).hexdigest() for p in vault.rglob('*') if p.is_file()}
    result=vault_check.check(vault,'zettelkasten')
    after={str(p.relative_to(vault)):hashlib.sha256(p.read_bytes()).hexdigest() for p in vault.rglob('*') if p.is_file()}
    assert before==after
    report={'first_collection':first['counts'],'repeat_collection':repeat['counts'],'extraction_status':extraction['status'],'pages':extraction['page_count'],'vault_check':result,'read_only_verified':True,'note_development':'Curated illustrative source, idea and map prepared for this fictional fixture; not an automated model evaluation.'}
    (dest/'worked-example-results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2)); return int(result['errors']>0)
if __name__=='__main__': sys.exit(main())
