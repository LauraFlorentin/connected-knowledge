# Connected Knowledge — 1.4.0

Start with the [guided private ChatGPT setup](plugins/connected-knowledge/skills/zettelkasten-obsidian/references/private-setup.md) for selected saves, or the general first-run guide for history import and local agent hooks. Capture stays inactive until explicitly configured.

A reusable knowledge and research plugin built around the existing Zettelkasten–Obsidian skill, preserving its integrated Practice workflows and ontology.

Start with `docs/INSTALL.md` for Claude and ChatGPT routes. Both use the same files under `plugins/connected-knowledge/skills/`; the Claude upload ZIP and instruction bundle are generated distribution copies, not separate implementations.

The plugin contains two skills:

- **Develop Knowledge** (`zettelkasten-obsidian`): onboard, capture, develop, explore, synthesize, review, extract PDFs and check vaults.
- **Collect Research** (`research-collect`): configure selected sources and collect raw material into a reviewable inbox, separately from note development.

## First conversation

“Use Develop Knowledge (`zettelkasten-obsidian`). I have an existing vault I want to use / I do not have a vault I want to use. My goal is ____. Help me choose the smallest useful setup.”

If an existing vault is inaccessible, supply a folder outline and representative notes or continue preparing drafts. Do not create a substitute just because access is missing. The optional starter script requires an explicit choice and refuses any existing target directory. Nothing in this delivery creates your actual vault.

## Collect only selected material

Begin with `config/collection.disabled.json`. It deliberately has no sources and ongoing collection is disabled. Choose local files, URLs, feeds or an authorized connector export. Pick an inbox and run once before enabling anything recurring. The collector records versions, duplicates, exclusions, failures and incomplete captures. No sources or schedules were enabled for you.

Read `docs/USAGE.md` for commands and `docs/WORKED-EXAMPLE.md` for an offline demonstration. Read `docs/VALIDATION.md` for actual test results and remaining limits.

Read `docs/KNOWLEDGE-WORKFLOW.md` for vault basics, bounded retrieval, duplicate handling, memory-derived context and future chat capture options. Existing vault conventions take precedence. Supplied-history import, selected capture, and developed knowledge are distinct workflows; no all-account history fetcher or semantic-search service is installed.

## Components

Implemented: plugin manifests, two skills, source/knowledge tools, supplied-history import, opt-in local hooks, private selected-save MCP, guided runtime setup, template support, and an experimental Gemini CLI extension. No public hosted service, email authentication, or universal all-account chat capture is included.

This is an AI-host plugin, not an Obsidian community plugin. Obsidian remains the reader/editor for ordinary Markdown. Your linked notes are a knowledge network; no graph database is installed.
