# Connected Knowledge

Reusable knowledge and research workflows for Claude and ChatGPT, built around the Zettelkasten–Obsidian skill. Version **1.3.0**.

Develop conversations, documents and notes into sourced, connected knowledge. Adapt to an existing Obsidian vault, collect selected material into a reviewable inbox, retrieve relevant context, and revise notes without losing provenance.

Formerly **Zettelkasten Research**. The broader name describes the collection, research and knowledge workflows; the integrated Zettelkasten–Obsidian foundation and internal skill names remain intact.

## Start here

- [Guided first-run setup](plugins/connected-knowledge/skills/zettelkasten-obsidian/references/first-run.md)
- [ZIP and attachment support](plugins/connected-knowledge/skills/zettelkasten-obsidian/references/export-bundles.md)
- [Installation and platform support](docs/INSTALL.md)
- [Practical commands and usage](docs/USAGE.md)
- [Knowledge conventions and duplicate handling](docs/KNOWLEDGE-WORKFLOW.md)
- [Worked example](docs/WORKED-EXAMPLE.md)
- [Validation and limitations](docs/VALIDATION.md)
- [Release notes](docs/RELEASE-NOTES.md)

This is a plugin for supported AI hosts. It works with ordinary Obsidian Markdown files; it is not installed through Obsidian's community-plugin directory. Installation does not connect a vault or grant access to account chat history.

## Included

| Component | Purpose |
| --- | --- |
| Develop Knowledge (`zettelkasten-obsidian`) | Onboard, capture, develop, retrieve, synthesize and revise knowledge. |
| Collect Research (`research-collect`) | Collect explicitly selected sources into an inbox. |
| Ten command-line Python tools | Collect material, extract PDFs with page references, check vault structure, compare existing vaults, import supplied chat JSON, develop evidence-backed graph notes, adapt local agent transcripts, create an optional starter, prepare ZIP/attachment bundles, and guide first-run setup. |
| Templates and vault guide | Shared conventions for people and assistants. |
| Platform manifests | Claude and ChatGPT/Codex packaging with shared skill sources. |

The integrated Zettelkasten Practice guidance is preserved within the primary skill; a second Practice installation is unnecessary. Existing vault conventions take priority. The optional starter requires an explicit choice and refuses an existing target directory.

Supplied ChatGPT/Claude JSON import is available with preview, repeat detection and edit protection; see [history onboarding](plugins/connected-knowledge/skills/zettelkasten-obsidian/references/history-import.md). Account-history fetching, an active MCP service, semantic-search infrastructure and background scheduling are not implemented. See [future capture options](plugins/connected-knowledge/skills/zettelkasten-obsidian/references/future-chat-capture.md) for their requirements.

## Existing-vault validation

Validate local properties and role-scoped identities without changing your schema.
Inspect configured templates separately, distinguish excluded/external links from
missing targets, and compare settings and file hashes without writing to either vault.
See [profiles and comparison](plugins/connected-knowledge/skills/zettelkasten-obsidian/references/existing-vaults.md).
The extension adds one profile example and two report outlines; existing note templates are unchanged.

## Develop a graph from imported conversations

Search imported messages with source citations, prepare optional classifications and
linked notes, then preview and apply the proposal. Existing notes can be linked
without being rewritten. The assistant supplies the reasoning; the script verifies
source identity, evidence locators, links and write conflicts. See the
[graph workflow](plugins/connected-knowledge/skills/zettelkasten-obsidian/references/graph-development.md).
No embedding service or automatic semantic classifier is required or included.

## Local session history and ongoing capture

The opt-in [session adapter](plugins/connected-knowledge/skills/zettelkasten-obsidian/references/session-capture.md) converts selected Codex/Claude Code JSONL histories and can run from configured Stop/SessionEnd hooks. It defaults to preview and requires explicit source/project selection and enabled configuration for writes. Bundled hooks are included but capture is disabled until explicitly configured; see [activation](plugins/connected-knowledge/skills/zettelkasten-obsidian/references/bundled-hooks.md). Ordinary Claude account exports remain a separate route.

## Build distribution files

From the repository root, using Python 3.10 or later:

```bash
python3 tools/package.py
```

This creates the Claude upload ZIP, instruction bundle and plugin checksums under `distribution/`. Build these files before following the ZIP or instruction-bundle installation route. Generated distribution files and worked-example output are excluded from Git; native source installation uses the checked-in manifests and skills directly.

The shared source is under `plugins/connected-knowledge/skills/`. Edit the source, then rebuild distribution copies. The `docs/core-file-hashes.json` file records the baseline imported from the personal skills at release assembly; `distribution/plugin-sha256.json` records the current build.

## Run the local tests

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r plugins/connected-knowledge/skills/zettelkasten-obsidian/scripts/requirements-dev.txt
.venv/bin/python -m unittest discover -s plugins/connected-knowledge/skills/zettelkasten-obsidian/scripts/tests -v
```

On Windows, use `.venv\Scripts\python.exe`. Tests use synthetic temporary files. Platform installation and live-account integration are separate checks; see the validation report.

Keep real vaults, account exports, credentials, collector state and runtime configurations outside this source repository. Start collection from the disabled example under `config/`, selecting your own sources and destination.

## Design and attribution

Use stable note identities, traceable sources and explained links. Search for existing ideas before creating new ones. Preserve disagreements and uncertainty. Add organizational complexity only when it resolves an observed problem.

[Source attribution and implementation provenance](plugins/connected-knowledge/skills/zettelkasten-obsidian/references/sources.md) distinguishes the integrated skill foundation, Obsidian forum guidance and original scripts. Referenced external projects and articles retain their own terms; this repository does not assign them a new license.
