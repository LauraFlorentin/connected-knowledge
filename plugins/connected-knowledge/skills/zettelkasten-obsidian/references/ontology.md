# Knowledge ontology

Use this as the default vocabulary, not as a requirement to populate every field. Prefer established vault fields when they express the same meaning. Preserve schema compatibility on updates. Propose new top-level types only when an actual example cannot be represented; do not silently grow a new ontology in each chat.

Contents: [Notes and metadata](#notes-and-metadata), [Technical component vocabulary](#technical-component-vocabulary), [Relationships](#relationships), [Example source note](#example-source-note), [Derived-note shapes](#derived-note-shapes).

## Notes and metadata

Use `schema_version: 1` for newly generated notes following this schema. Keep structured properties flat; put explanations and relationship evidence in the body.

| Field | Meaning and values |
| --- | --- |
| `id` | Stable note identifier. Reuse existing identity. A locally generated UUID is permitted; do not present it as a provider-assigned identifier. |
| `note_type` | `source`, `idea`, `decision`, `entity`, `artifact`, or `map`. |
| `category` | `Admin`, `Personal`, or `Work`, as defined in SKILL.md. |
| `title` | At most five words for conversation/source titles. Use a concise claim or idea title for developed knowledge; do not truncate its meaning merely to meet the chat-title limit. |
| `classification_status` | `provisional` or `reviewed`; reviewed means confirmed by the user or a completed classification review, not fact-checked. |
| `review_status` | `draft`, `reviewed`, or `disputed`; keep factual validation separate from editorial review. |
| `source_platform` | Observed origin, such as `ChatGPT`, `Claude`, `Kimi`, `Outlook`, `Gmail`, or `Notes`. Do not guess a model version. |
| `source_account` | Optional account/workspace identifier used for matching and separation. Avoid copying an email address when a local account alias suffices. |
| `source_id` | Provider conversation/message/document identifier when available. Omit if unknown. |
| `source_url` | Existing source reference, if available. Do not publish a share link to manufacture a locator. |
| `source_coverage` | `full_export`, `excerpt`, or `visible_context`. “Full export” describes the supplied source record, not a claim that every account chat or attachment exists. |
| `created` / `updated` | Note timestamps; distinguish these from the original source dates. Use ISO 8601 and a timezone when time is known. |
| `source_created` / `source_updated` | Source timestamps, if known. Never fill these with the import time. |
| `project` | Quoted wikilink to a known project, if applicable. |
| `topics` | A small list of canonical topic links; omit unsupported topics. |
| `aliases` | Alternate names for the same entity or concept. Do not merge people on name similarity alone. |
| `entity_type` | For entity notes: `person`, `organization`, `project`, or `topic`. |
| `artifact_type` | Kind of deliverable: e.g. `plugin`, `report`, `workflow`, `dashboard`, or `code`. A conversation about a plugin is still a source note. |
| `components` | Implemented and inspected component kinds from the table below. Omit when only plans or unverified reports are available. |
| `proposed_components` | Planned component kinds. |
| `reported_components` | Components a source says exist but which have not been inspected. |
| `artifact_status` | `proposed`, `in_progress`, or `implemented`; do not imply implementation just because a source describes a design. |
| `decision_status` | `proposed`, `adopted`, or `superseded`. Populate adoption only with evidence. |

For a simple capture, use only `schema_version`, `id`, `note_type`, `category`, `title`, and the source/review fields that apply. Add technical fields only for relevant artifacts. A new empty `components` list must not imply that an artifact was inspected and has no components.

## Optional source integrity fields

Use `source_file` for a vault-relative preserved original and `source_sha256` for its observed SHA-256. Use `evidence_kind` only where helpful: `personal-observation`, `source-claim`, `agent-inference`, or `mixed`. These optional fields do not change note types or imply factual review. An inbox receipt is a staging artifact outside the developed-note schema; promote selected content deliberately.

## Technical component vocabulary

| Value | Classification test |
| --- | --- |
| `skill` | Reusable instructions and supporting resources, generally with a SKILL.md entrypoint. |
| `mcp_server` | An implementation exposing tools/resources through MCP. |
| `mcp_integration` | Configuration or client integration connecting to an existing MCP server. This does not create a new server. |
| `hook` | An event handler registered with a host that supports that event. A desired trigger alone is proposed. |
| `agent` | A configured agent with a defined role and capabilities. An ordinary prompt does not necessarily constitute an agent component. |
| `script` | Executable code for processing or automation. A script may be invoked by a hook or skill. |

Inspect the host and manifest when needed. Claude Code, Codex, Claude's chat app, and Obsidian have different plugin mechanisms; record the target host and do not imply portability just because a package contains Markdown. A skill is not automatically installed in both ChatGPT and Claude.

## Relationships

Use a small vocabulary with explicit direction. A relationship line should explain its meaning and identify the evidence. Only encode relationships that are useful for retrieval or reasoning.

| Relationship | Direction and interpretation |
| --- | --- |
| `discusses` | Source to topic/entity: the source actually discusses it. |
| `derived_from` | Idea/decision/artifact to source: identify the supporting passage or message. |
| `belongs_to` | Note/artifact to project: explicitly associated with that initiative. |
| `contains` | Plugin/package to an actual component. Label proposed membership separately. |
| `uses` | Skill/workflow/artifact to a tool or component it calls or depends on. |
| `triggers` | Registered hook to its action/workflow. |
| `supports` | Evidence or argument to a claim, with an explanation. |
| `contradicts` | Note to another claim/account that it conflicts with; explain the scope. |
| `extends` | Idea to an earlier idea that it develops. |
| `applies` | Decision/artifact to a principle put into use. |
| `supersedes` | New adopted decision to the replaced decision, with date and evidence. |

For simple relationships, quoted wikilinks can be used in flat list properties. For several relationships with distinct evidence or uncertainty, write them in a body table instead of nested YAML. Reuse a dedicated decision or relationship note only if dates/evidence justify it.

Obsidian's default graph renders note links. The relationship names above remain text or metadata unless additional tooling interprets them. It does not become a typed graph query engine merely because the notes contain these properties.

## Example source note

This is illustrative, not an actual captured conversation. Replace example content with observed content; omit unknown values.

```markdown
---
schema_version: 1
id: "example-source-001"
note_type: source
category: Work
title: "Design knowledge capture plugin"
classification_status: provisional
review_status: draft
source_platform: Claude
source_coverage: excerpt
artifact_type: plugin
artifact_status: proposed
proposed_components:
  - skill
  - mcp_integration
---

# Design knowledge capture plugin

## Source
Supplied excerpt; no provider identifier or source URL was supplied.

## Original excerpt
### User message 1
We could package the classification instructions and connect to an existing vault server.

## Summary
The user proposed packaging a skill and an integration with an existing MCP server.

## Decisions and open questions
No implementation or adoption is established. The target host remains unspecified.

## Proposed links
Knowledge capture — suggested topic; vault existence has not been checked.
```

## Derived-note shapes

- **Idea:** Title expressing the idea; statement in clear words; reasoning; applicability and limits; source passages; explained connections. Mark assistant synthesis as such. A useful note can be brief.
- **Decision:** Decision statement; adopted/proposed status; decision-maker if explicit; decision date if known; rationale; source; superseded decision if applicable. Omit unknown owner/date rather than inventing one.
- **Entity:** Canonical name; aliases; observed identity context; sourced relationships. Create only entities useful across notes, rather than a separate note for every proper noun.
- **Artifact:** Purpose; target host; proposed/reported/inspected components; implementation evidence; originating sources; project link if known.
- **Map:** A guiding question or topic overview with an intentional reading path through existing notes. Explain groupings rather than reproducing a tag dump.
