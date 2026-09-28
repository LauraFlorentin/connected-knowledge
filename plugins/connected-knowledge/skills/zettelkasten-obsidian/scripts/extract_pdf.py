#!/usr/bin/env python3
"""Page-aware, non-destructive PDF extraction. Requires pypdf >=5,<7."""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from pypdf import PdfReader

VERSION = '1'

def extract(source, output, min_chars=30):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file():
        raise ValueError('Input PDF does not exist')
    data = source.read_bytes()
    if not data.startswith(b'%PDF-'):
        raise ValueError('Input does not have a PDF signature')
    digest = hashlib.sha256(data).hexdigest()
    if output == source or output in source.parents:
        raise ValueError('Output must be a separate extraction directory')
    output.mkdir(parents=True, exist_ok=True)
    target = output / (digest + '-v' + VERSION + '-min' + str(min_chars))
    if target.exists():
        report = json.loads((target / 'metadata.json').read_text())
        if report['sha256'] != digest:
            raise ValueError('Cached source identity mismatch')
        for name, expected in report['output_hashes'].items():
            if hashlib.sha256((target / name).read_bytes()).hexdigest() != expected:
                raise ValueError('Cached extraction changed; use a different output directory')
        return dict(report, output_dir=str(target), reused=True)
    reader = PdfReader(source)
    if reader.is_encrypted and not reader.decrypt(''):
        raise ValueError('Encrypted PDF requires an unlocked copy; original was not changed')
    pages, sections = [], []
    for number, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ''
            status = 'needs_visual_review' if len(''.join(text.split())) < min_chars else 'text_extracted'
            error = None
        except Exception as exc:
            text, status, error = '', 'unreadable', str(exc)
        pages.append({'pdf_page': number, 'characters': len(text), 'status': status, 'error': error})
        sections.append(f'## PDF page {number}\n\n{text}\n')
    if not pages:
        raise ValueError('PDF contains no pages')
    report = {'extractor_version': VERSION, 'source_name': source.name, 'sha256': digest,
              'page_count': len(pages), 'pages': pages, 'coverage': 'page_text_only',
              'status': 'needs_review' if any(p['status'] != 'text_extracted' for p in pages) else 'text_extracted',
              'limitations': 'No OCR. Sparse pages may be scanned, blank, or unreadable. Text extraction does not validate tables, figures, reading order, or facts.',
              'output_hashes': {}}
    with tempfile.TemporaryDirectory(dir=output, prefix='.extract-') as temp:
        work = Path(temp)
        content = '# Extracted PDF text\n\nPhysical PDF page numbers; printed labels may differ.\n\n' + '\n'.join(sections)
        (work / 'document.md').write_text(content, encoding='utf-8')
        report['output_hashes']['document.md'] = hashlib.sha256((work / 'document.md').read_bytes()).hexdigest()
        (work / 'metadata.json').write_text(json.dumps(report, indent=2)+'\n')
        # Rename only into an absent directory; concurrent extraction must not replace a cache.
        os.rename(work, target)
    return dict(report, output_dir=str(target), reused=False)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('pdf', type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--min-chars', type=int, default=30)
    a = p.parse_args()
    try:
        if a.min_chars < 1: raise ValueError('--min-chars must be positive')
        result = extract(a.pdf, a.output, a.min_chars)
        print(json.dumps(result, indent=2))
        return 1 if result['status'] == 'needs_review' else 0
    except Exception as exc:
        print(json.dumps({'status':'failed','error':str(exc)}))
        return 2
if __name__ == '__main__': sys.exit(main())
