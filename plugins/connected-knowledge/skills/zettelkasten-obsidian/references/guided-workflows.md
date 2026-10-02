# Guided Connected Knowledge workflows

Use conversational, step-by-step guidance when the user explicitly invokes Connected Knowledge without a concrete task, asks for help getting started, or requests a guided workflow. An invocation with a specific task starts that task directly. A mention during plugin development is not a request to onboard or save knowledge.

## Choose a starting task

For a bare invocation, briefly say that you can help turn selected material into connected notes, then offer this numbered menu:

1. Set up or connect an Obsidian vault.
2. Save notes from past conversations.
3. Save this conversation or a selected excerpt.
4. Add and connect a document or research source.
5. Explore, organize or check existing notes.

Ask which task the user wants to start with; accept a number or free-text answer. Adapt choices to known context, and offer “resume” when a task is already underway. Reuse known vault and template choices. Do not force setup before a task that can be prepared without vault access.

## Guide the selected task

Explain the intended result and give a short roadmap of three to five user-facing steps. Then present only the next unresolved action or question, with a brief reason and what the user should expect. Step-by-step refers to user actions and visible progress, not disclosure of internal reasoning.

Carry out authorized work yourself where tools permit. Continue through independent steps without repeatedly asking “continue?” or making the user perform checks the assistant can perform. Pause for missing source material, a required choice or an action only the user can complete. Reuse earlier authorization; choosing a menu task does not authorize unrelated imports, wholesale reorganization or ongoing collection.

After each meaningful milestone, state what is done and the next step. Use plain language and avoid dumping commands or all technical setup requirements at once. If a step fails, explain the specific gap and a practical recovery step, retaining completed work. Let the user skip, switch, pause or stop; resume from actual evidence rather than restarting the menu. Keep progress in the conversation; persist a checklist only when requested or already within the task's save scope. Across new chats, use accessible prior records or ask a focused question rather than claiming persistent state.

## Task routes

- **Vault setup:** Establish existing versus explicitly requested new vault; inspect its guide and templates if accessible; identify only missing conventions or access; trial one small authorized capture; verify its starting page and source navigation. Follow [onboarding.md](onboarding.md), [first-run.md](first-run.md) and [readable-captures.md](readable-captures.md). An inaccessible existing vault remains the intended vault, not permission to create a replacement.
- **Past conversations:** Select platform and particular supplied exports, excerpts or authorized local transcripts; explain how to provide the chosen input if needed; inspect actual format and coverage; preview identities and destination; perform the requested import and selected note development; verify links and report coverage. Follow [history-import.md](history-import.md), [export-bundles.md](export-bundles.md) or [session-capture.md](session-capture.md). Installation grants no all-account history access. An import request alone does not authorize developing every imported chat.
- **Current conversation:** Establish available content and whether the user wants prepared Markdown or a vault save; reuse the confirmed destination and template; check identities and existing notes; save or prepare the requested source and useful derived notes; verify and return one starting link. Follow [capture.md](capture.md), [knowledge-maintenance.md](knowledge-maintenance.md) and [readable-captures.md](readable-captures.md). State excerpt coverage when earlier messages are unavailable.
- **Document/research:** Select the specific material; inspect and attribute it; preserve attachments only within scope; connect useful source and idea notes; verify the reading path. Use [sources.md](sources.md) and [readable-captures.md](readable-captures.md). Route collection requests to the companion research-collect skill; collected inbox material is not automatically developed knowledge.
- **Explore/organize/check:** Clarify the question or bounded area; inspect relevant conventions and notes; answer or prepare scoped changes; apply requested changes and verify. Use [knowledge-development.md](knowledge-development.md), [existing-vaults.md](existing-vaults.md) or [review.md](review.md). A check remains read-only unless repairs are requested.

Use [private-setup.md](private-setup.md) only when a private selected-save connection is requested; future capture is a separate opt-in task. Explain actual host access and device limitations when they affect the next step.

## Complete, then suggest the next task

Finish with the outcome, one primary starting link when available, and material unfinished checks or source limits. Distinguish prepared, imported, reviewed and saved results. A file check cannot certify Obsidian display.

Suggest one relevant next task, plus an optional alternative or “stop here.” For example: after vault setup, offer to save one selected past conversation; after an import, offer to develop one imported conversation; after a source save, offer to explore its connections or add another source. Use actual completed work to choose the suggestion and avoid repeatedly offering completed setup.

Wait for the user's choice before starting the suggested task unless the user already requested that sequence. On acceptance, give that task's short roadmap and continue the same next-step guidance. A completion suggestion does not enable hooks, scheduling, synchronization or access to new sources.

## Review scenarios

- Bare invocation: short menu and one choice question; no vault writes or scans.
- “Save this excerpt” with a known vault: start the save route directly, reusing choices.
- Existing vault inaccessible: prepare useful material and explain the access step; create no replacement.
- Past chat ZIP: inspect and preview selected scope; report actual coverage, not all-account access.
- “Done” after a manual setup step: check available evidence, then advance without repeating setup.
- Completed import: suggest selected note development, wait for a choice, then guide that task.
- User switches or stops: preserve completed work and follow the new direction without forced chaining.

These are conversational instructions for a tool-using host assistant, not a native wizard or guaranteed host event. The host selects its model and settings; use direct goals, explicit scope and observable completion criteria rather than model-specific API parameters.
