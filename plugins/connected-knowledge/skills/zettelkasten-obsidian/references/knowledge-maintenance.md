# Find, reconcile and revise knowledge

Preserve the existing ontology and integrated Practice workflows. The following contracts are implementation choices, not additional Zettelkasten rules. Use them with accessible files or equivalent authorized search/read/update tools. Do not promise duplicate-free content without inspecting the destination.

## Identity and provenance

- Reuse a note's immutable `id`; titles, aliases, categories and filenames can change. Generate a UUID only for a new note. Never derive identity solely from its title or present a local ID as a provider ID.
- Identify imported sources with platform + local account/workspace alias + provider conversation/document ID. Identify their revisions separately by source version or content hash. Use a local mapping when provider IDs are unavailable and report uncertain matches.
- Use descriptive filenames and links resolvable in the actual vault. Prefer a vault-relative target when basenames collide. An `id` property is not automatically an Obsidian link target; keep the ID-to-path mapping accurate when renaming.
- Keep original files, transcripts and source dates separate from generated text and note dates. Identify the passage, message, page or section supporting each substantial claim. If no locator is available, say so instead of fabricating one.
- Distinguish source claim, user statement, assistant interpretation and adopted decision in the body, at claim level when a note is mixed. `review_status: reviewed` is an editorial state, not proof of truth. Record uncertainty in words and explain what would resolve it; avoid invented numerical confidence.

## Retrieve only the necessary context

1. Read the vault's short operating guide and scoped instructions when available; reuse a known mapping. Inspect a directory listing or existing index to find likely paths. Do not load the full archive or every attachment into the model.
2. Translate the question into named entities, claim terms, aliases, project and time scope. Search titles/properties first, then full text using the host's tools or `rg`. Search can scan files without sending every file to the model.
3. Read the most relevant map and a small candidate set; 3–8 notes is a starting budget, not a quota or a hard cap. Read the supporting source passages and at least the relevant objections, competing accounts or superseded decisions when present.
4. Follow only links that could materially affect the answer. Expand the search if gaps or contradictions require it. Stop when the requested answer is supported or a specific missing source prevents resolution.
5. Keep a compact working context: question; inspected note IDs/paths and source locators; supported claims; interpretations; conflicts; gaps; freshness. Answer with links to inspected notes, scope and uncertainty. A search miss is not proof that no note exists.

Example local discovery, with task-specific literal terms and an actual vault path:

```bash
rg -l -i -g '*.md' -g '!Templates/**' -e 'fundraising' -e 'investor pipeline' /path/to/vault
```

An index or map is a navigation aid, not the source of truth. Open target notes before relying on summaries. Add a generated index, semantic search or embeddings only after repeated retrieval failures justify it; record indexing scope and refresh state. Those components are not implemented by this package.

## Reconcile duplicates at three layers

| Layer | Match and action | Limits |
| --- | --- | --- |
| Captured bytes | Stable source identity plus hash; unchanged capture creates no new receipt/version. | Implemented by `collect.py` for its supported inputs. Different config source IDs are separate identities; a changed export is a new file version. |
| Imported conversations/documents | Match provider identity; compare version; update the existing source record. | Required importer contract, not an included bulk ChatGPT/Claude parser. A file hash alone cannot reconcile a changing conversation. |
| Ideas, entities and decisions | Search aliases and propositions; read candidates; compare meaning, scope and time. Reuse or revise the canonical note when equivalent. | Semantic judgment is fallible. Similarity scores and matching titles are candidates, not automatic merge authority. |

Apply `note-development.md` for same, extended, distinct and conflicting ideas. Keep separate sources even when they support one idea: two reports are provenance, not necessarily unwanted duplicates. Keep temporal changes and real disagreements visible. Track a remembered claim and a later transcript as evidence for the same canonical claim, rather than creating a second personal fact note.

On an uncertain match, preserve a proposed update with candidate links; do not silently create a competing canonical note or destructively merge. If the vault is inaccessible, mark duplicate checking as pending. Report what was actually checked, new, reused, changed, excluded and unresolved; do not invent counts or guarantee zero semantic duplicates.

## Revise without losing knowledge

Read the current file and record its version/hash before editing. Compare again before committing a write, using atomic or conditional updates where available. On changed content, reread and reconcile rather than overwriting. After an uncertain write response, look up the note ID and content before retrying.

Update only affected sections, preserving user prose, identity and original evidence. For a substantive change, add a short dated revision with what changed, why and its source. A correction need not create a new note. Mark supersession only when replacement is evidenced; newer does not automatically mean better. If a source is contradicted or corrected, flag affected derived claims and inspect them before changing conclusions.

Before a rename or requested merge, find inbound links, headings and block references. Keep the canonical note ID, record retired IDs/aliases in a merge record, and repair links in scope; aliases alone do not guarantee filename-link repair. Keep a redirect note when callers cannot all be updated. Do not delete original sources merely because derived ideas merged. Respect exclusions and deliberate deletion on later imports.

Run the read-only checker before/after relevant changes and compare findings. It catches structural issues, not semantic duplicates or truth; unresolved findings remain visible. Index/guide updates belong to the same change when a path or convention changes. No silent mass rewrite or reorganization.

## Seed from remembered personal context

A request such as “add what you know about me” can seed useful context, but cannot reconstruct all prior chats. First identify the actual scope available: current messages, memory summary, retrieved past passages or supplied files. Follow the host's personal-context retrieval rules when source recovery is needed. Do not treat remembered summaries as verbatim user statements or evidence of the current state.

When the user requests this action, prepare a concise source note titled for the context summary. Use the existing `source` type, `review_status: draft`, `source_coverage: visible_context`, and body text explicitly saying which material is memory-derived. Omit unknown provider IDs, original dates and quotations. Record the summary's preparation date separately. Use a table of claim, origin/locator, known timeframe, uncertainty and existing note match. Do not dump unrelated sensitive details into broadly shared project notes or cross an established work/personal boundary.

Search the intended vault first. Reuse relevant entity, project or decision notes; avoid a separate note for every remembered fact. Preserve conflicting/possibly outdated recollections for review instead of guessing. Label model interpretations as such, never as user decisions. Write only to an authorized destination; without access, deliver a provisional import draft and state that duplicate checking remains pending. A hypothetical question is not a request to publish a personal profile.

When original evidence arrives later, attach it to the existing claim, correct its status, and retain the summary's actual provenance. Memory seeding and export import are complementary routes, not interchangeable completeness levels.
