# Explore and synthesize knowledge

Use existing ontology fields throughout. A structure note is `note_type: map`; an application remains an idea. Represent a named project as an entity with `entity_type: project`, and a written deliverable as an artifact with the appropriate `artifact_type`. Do not add top-level note types or require new folders. Produce ordinary prose when no saved note is requested.

## Explore a question

Use the bounded retrieval and evidence-context protocol in [knowledge-maintenance.md](knowledge-maintenance.md). It makes navigation useful to both people and assistants without requiring a separate search database.

1. Identify the question and useful output. Infer a reasonable scope if clear; ask only when the missing detail materially changes the task.
2. Search distinctive terms and synonyms; inspect candidate notes and relevant maps. If retrieval fails, state the searched scope rather than claiming the idea does not exist.
3. Read both ends of a proposed conceptual connection. Follow relevant neighbors, counterarguments, boundary conditions, and missing explanatory steps.
4. Stop when evidence is sufficient for the requested answer, a missing source blocks progress, or the agreed limit is reached. Without a limit, use a bounded first pass; do not traverse the whole vault recursively.
5. Separate what inspected material supports, what you infer by combining it, and what remains hypothetical. Report a useful answer and the smallest remaining investigation.

If no vault is available, use supplied notes only and state that scope. Do not fabricate retrieval results or existing targets. Repair an unsuccessful search with a useful alias or navigation link only when edits are in scope.

## Explain connections

Distinguish provenance, conceptual reasoning, and navigation. Topic similarity can justify grouping or further search but not an evidential claim. Name the reason for support, conflict, extension, or application using the existing relationship vocabulary. Describe prerequisites, qualifications, and analogies in prose when no existing relationship fits; do not silently expand the enum. Explain where an analogy fails. No minimum link count is required, and backlinks alone do not require reciprocal edits.

## Build a map

Give a map a guiding question, scope, starting points, ordered argument or reading path, and important disagreements or gaps. Use verified targets for completed links and clearly mark suggested targets. Group by reasoning role rather than collecting every matching tag. Revise the route when the argument changes.

## Synthesize an output

Start with the reader, question, and requested form. Retrieve supporting notes and objections. For a complex output, build an evidence table:

| Planned assertion | Inspected note or source | Evidence strength and limits | Missing work |
| --- | --- | --- | --- |

Populate only with actual material. Several notes citing one study are not independent corroboration. Distinguish a source inspected directly from a source described only in another note. Retain known locators without inventing passages or page numbers.

Arrange the draft around its argument: problem, explanation, evidence, objections, and implications as needed. Write connective reasoning explicitly. Do not assume concatenated notes establish a conclusion. Preserve disagreement and qualify assertions to match evidence. If the user requests a draft despite gaps, mark those gaps and deliver the draft.

Before delivery, check substantive assertions against evidence and flag missing verification. Follow current-source and browsing requirements when external verification is needed; do not imply a notes-only synthesis independently verifies current facts. Save only through the main skill's authorized destination workflow.
