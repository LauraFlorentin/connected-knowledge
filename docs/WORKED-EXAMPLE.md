# Worked example: collection to connected notes

Everything here is a fictional training fixture. The pilot result is invented to demonstrate evidence boundaries; it is not a real study or a claim about AI banking performance. No user vault or account is used.

## Reproduce

Install development dependencies, then choose an output directory that does not exist:

```bash
python -m pip install -r plugins/connected-knowledge/skills/zettelkasten-obsidian/scripts/requirements-dev.txt
python examples/run_example.py --output /path/to/new-demo-output
```

The script refuses to reuse an existing directory. It creates only a synthetic demonstration workspace. `examples/completed/` contains the run produced during validation, including the original PDF, inbox receipts, extraction text, developed notes and JSON findings. Recorded absolute input paths in that snapshot identify the build-time fixture; regenerate the example for paths on your computer.

## What happens

1. **Collect:** A two-page fictional PDF is created and explicitly selected as a local source. One original is archived, with a SHA-256, source identity, reference and coverage. No account or live feed is contacted.
2. **Repeat:** The identical collection is run again. It is recognized as unchanged and creates no duplicate capture.
3. **Extract:** Each physical PDF page becomes a labeled section. Metadata records two pages, text-only coverage and page statuses. The original bytes remain unchanged.
4. **Develop:** Curated example source, idea and map notes explain the limited fictional result. The source reports a routine-case improvement, excluding escalations and omitting sample size. The idea explains why that does not establish an overall improvement. The map links the source, interpretation and evidence gaps. This is a prepared illustrative example, not an automatic model-generated research evaluation.
5. **Check:** The checker inspects the three developed notes, links and PDF page reference, and verifies the preserved source hash. The demonstration confirms note bytes are unchanged by checking.

Observed run: first capture 1; repeat capture 0 and duplicate 1; extraction 2 pages; checker 0 errors and 0 warnings. See `completed/worked-example-results.json` for the actual machine-readable result.

A real workflow adds a review step: inspect the actual collected source, select what matters, then ask the core skill to develop notes in the existing vault's conventions. A successful script run does not establish that the paper's claims are true.
