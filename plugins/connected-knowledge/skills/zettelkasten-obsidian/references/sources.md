# Attribution and implementation provenance

Primary foundation: the user's installed `zettelkasten-obsidian` skill, including its integrated Zettelkasten Practice-derived note boundaries, reconciliation, exploration, synthesis and review guidance. Preserve those resources; do not install a second Practice workflow or impose its alternate schema.

The user supplied `zettelkasten-practice.zip` earlier in this conversation. Its source-context reference attributes inspiration to Edmund's [12 Principles](https://forum.obsidian.md/t/12-principles-for-using-zettelkasten/51679), with companion discussions on linking, structure, exploration, AI assistance and enjoyment. Its procedures and assessment exercises are original implementation guidance, not Luhmann's rules or validated standards. The integration retains that distinction. Those companion sources were reported in the uploaded skill; this release does not claim to have reverified every linked source.

## Setup sources inspected on 2026-09-27

- Edmund, [Setup Zettelkasten. But how?](https://forum.obsidian.md/t/setup-zettelkasten-but-how/85224): presents a five-level perspective and links alternative setups. Treat it as one author's framework, not an official or mandatory progression. The linked image was not transcribed.
- [New User: Zettlekasten-ish simple setup](https://forum.obsidian.md/t/new-user-zettlekasten-ish-simple-setup/84679): participants describe plain-Obsidian starting points, references and main notes, and adaptation through actual use. We adopt no note-count quota or requirement to start over.
- Edmund and replies, [Simplify Zettelkasten](https://forum.obsidian.md/t/simplify-zettelkasten-but-how/81090): discusses reducing unnecessary structure and adding tools when use reveals a need. Our optional starter is our design, not a copied starter kit.
- [Inspect and Adapt Process](https://forum.obsidian.md/t/inspect-and-adapt-process-but-how/36799): discusses process reflection and note-growth analytics. We retain task-based review and do not equate graph size or note count with knowledge quality. No forum code or graphics are included.

## Script assessment

The installed foundation had no PDF extractor or vault checker. We inspected [External Brain](https://github.com/Aznatkoiny/external-brain/tree/699f24d65500ae9e72cd43f142227056cc8b5144), specifically `scripts/extract_pdf.py`, `scripts/vault_lint.py`, its schemas and workflows. Its useful ideas include page-aware extraction, source hashes and deterministic checks. Its code assumes repository-relative folders and a different metadata schema; the linter uses a limited frontmatter parser. This package supplies newly implemented scripts with explicit paths, real YAML parsing, duplicate-ID checks and broader source handling. No upstream script code is vendored, and no upstream software license is assumed. Docling integration in that repository is a proposal, not an included dependency here.

All templates, the fictional worked example, collection protocol, manifests, and setup gates in this release are implementation choices for the user's requirements. Platform support is documented separately with dated official links.

## Maintenance additions inspected on 2026-09-28

Revisited the setup and simplification threads and followed [Explore and discover notes](https://forum.obsidian.md/t/explore-and-discover-notes-but-how/65386), which discusses several search approaches and structure notes. Our bounded reading protocol, stable-ID rules, memory-summary treatment, duplicate layers, update checks and short vault guide are original implementation choices. They do not require any particular folder count, mandatory links per note, Dataview, graph database or a progression through setup levels. The tradeoffs are explained in onboarding. Current platform evidence and unimplemented capture routes are separated in `future-chat-capture.md`.
