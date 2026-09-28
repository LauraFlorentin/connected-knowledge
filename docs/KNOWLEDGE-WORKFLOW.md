# A knowledge base that stays understandable

Obsidian is the app; a vault is the folder of notes and attachments it opens. “Location” means that folder's path on the device used for processing. Giving a cloud assistant a Mac path does not make the folder accessible. A supported local connection or supplied files are still required. See [Obsidian storage](https://help.obsidian.md/Files+and+folders/How+Obsidian+stores+data).

If you already use a vault, a folder outline and 2–3 representative Markdown notes show its conventions: naming, properties, templates and link styles. We adapt to these. If you have only installed Obsidian and want a new vault, the optional starter already includes four note templates and now a short adaptable vault guide. No live vault has been created by this package update.

## Conventions shared by you, Claude and ChatGPT

| Concern | Practical default |
| --- | --- |
| Identity | One stable ID per note; changing a title does not create a new identity. |
| Categories | Admin / Personal / Work as properties. Preserve existing folder organization. |
| Sources | Retain origin, known source ID/dates and exact passage/page/message locators. Preserve originals when supplied. |
| Claims | Separate what a source says, what you said, what an assistant infers and what you adopted. |
| Links | Explain why a link supports, contradicts, extends or applies an idea. A similar topic is not evidence. |
| Retrieval | Read the short vault guide, search terms/aliases, inspect a relevant map and a few notes, then follow useful evidence and counterarguments. |
| Revision | Read before editing, preserve user prose and ID, note substantive changes, and check affected links. |

The graph comes from meaningful note links. A graph database, embedding service and mandatory folder hierarchy are not installed. Search tools may scan many files while the assistant reads only selected results.

## Four everyday requests

1. **“Add this source.”** Preserve its origin and coverage in the review inbox, check source identity, and flag missing captures.
2. **“Develop this into notes.”** Search for equivalent ideas, reuse or revise canonical notes, and create only useful new claims/decisions. Link to the exact source and explain uncertainty.
3. **“What do my notes say about this?”** Retrieve a bounded set of notes and supporting passages, preserve objections and cite what was actually inspected. Expand the search if the evidence is insufficient.
4. **“Update what we know.”** Compare new evidence with the existing claim and timeframe. Keep disagreements until resolved; do not treat the newest suggestion as an adopted decision.

These are skill-guided workflows, not a background service. Direct writes require the intended accessible vault.

## Duplicates: what is enforced and what needs judgment

The collector already skips unchanged inputs with the same configured source identity and content hash. A changed export is a new raw version, not a newly reconciled set of conversations. The platform-specific history importer still needs implementation against actual exports; its contract is to match platform/account/conversation ID and update existing records.

For ideas, search the proposition, aliases, scope and time before adding anything. Reuse the canonical idea and add evidence when equivalent. Keep distinct source records and real disagreements. Ambiguous matches become review items. Neither a clean vault-check report nor similar titles prove semantic deduplication. No honest system can guarantee that all differently worded duplicate ideas are automatically recognized; this package supplies the review discipline and structural checks.

## “Add everything you know about me”

This can produce a useful provisional context summary without downloading account history. It covers only accessible context and remembered/retrieved information, not every original conversation. Memories can be incomplete or outdated, and the model may lack original wording or dates.

The workflow labels memory-derived material, searches the vault for existing matches, and updates relevant notes rather than making a new note for every fact. It separates your statements from model interpretations. When a later export supplies original evidence, that evidence is attached to the same canonical claim. A future correction revises it; a conflicting account remains visible until resolved. Without vault access, the output is a draft with duplicate checks pending. This update has not created a personal profile from your memories.

## Future chats directly from apps

Two independent pieces are needed: a way to capture the selected chat content at a supported event, and a connection that can search/read/update the vault or inbox. An MCP destination alone does not fetch all app history.

For a convenient first integration, use an explicit “save this” action backed by an authorized destination. For unattended capture, Work/Codex has documented hooks; Claude Code has its own hooks. These require deployed adapters, actual transcript/event access and tests on the chosen runtime. They do not establish all-chat capture across every native-app mode. Browser extensions cover the browser surfaces they support, and an API-based chat client can log only conversations passing through that client. Export requests remain manual in the package.

The core's `references/future-chat-capture.md` contains dated official links, a route table, mobile/desktop reachability requirements and a setup checklist. No connector, hook or scheduler has been enabled. No source or trigger has been selected on your behalf.

## Why start simply

Edmund's [setup discussion](https://forum.obsidian.md/t/setup-zettelkasten-but-how/85224) offers one author's levels and alternative approaches. His [simplification discussion](https://forum.obsidian.md/t/simplify-zettelkasten-but-how/81090) asks what structure and tools actually help. The linked [retrieval discussion](https://forum.obsidian.md/t/explore-and-discover-notes-but-how/65386) describes different ways to search and navigate.

Our implementation interprets this as adding structure to resolve observed friction: an alias after a search miss, a map for a recurring question, an automation for repeated capture work. Stable IDs and provenance cost a little effort but support reliable revision. Plain Markdown is portable but does not provide automatic semantic merging. Separate raw sources preserve evidence but use more storage. These are our engineering choices, not a required forum progression.
