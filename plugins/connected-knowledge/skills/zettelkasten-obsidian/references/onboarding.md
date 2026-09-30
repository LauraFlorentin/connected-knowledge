# Onboard without replacing the user's system

For the unified setup questions and command-plan wizard, start with [first-run.md](first-run.md).

First establish whether the user has an Obsidian vault they want to use. Accept an answer already given. Ask: “Do you have an existing vault to use, or would you like a new starter?” A missing path, failed search, disconnected tool, or inaccessible device does not mean no vault exists. Continue preparing material if access is missing; do not create a replacement vault.

## Existing vault

Explain unfamiliar terms first: Obsidian is the application; a vault is the folder of Markdown notes and attachments it opens. A location is that folder's path on the device used for processing, not an Obsidian account name. A Mac path such as `/Users/yourname/Documents/My Knowledge` is illustrative and is not accessible to a cloud assistant merely because the user types it. A folder connection, supported local runtime or supplied files are still needed. Phone and desktop can hold synchronized copies; establish which copy is available for this operation.

By “sample of conventions,” mean a folder outline plus 2–3 representative Markdown notes and an existing template if any, with private content removed if preferred. Inspect how files are named, properties are written and links are formed. A screenshot can explain folder layout but does not provide editable note contents. If no conventions exist, offer the skill defaults rather than requiring the user to invent a system first.

Obtain its explicit path or authorized connector and intended work/personal boundary. Read local instructions and a small relevant sample. Inspect naming, folders, note types, metadata, templates, link styles, aliases, and how the user retrieves information. Propose a short mapping to our ontology. Preserve existing files, links and `.obsidian` configuration; no wholesale migration or plugin installation. Run `vault_check.py VAULT --profile generic` for a read-only baseline. Use its optional config for established fields; do not force our schema onto legacy notes.

Keep incoming captures in a separate user-chosen research inbox by default. Agree how selected material is promoted into the existing vault. Trial a small requested capture or proposed note before a broader change. Read/write access to a folder does not grant access to another vault.

Adapt `assets/vault-guide.md` into a short operating guide only when useful and authorized. Reuse an existing guide rather than create competing instructions. Four note templates already exist under `assets/templates`; adapt them, do not replace the vault's templates wholesale.

## No existing vault selected

Only after the user explicitly indicates there is no existing vault they want to use, offer the optional starter. Run `starter_vault.py TARGET --confirmed-no-existing-vault`. The target must not exist; the script refuses to merge into any existing directory. It creates a short guide and manual templates, not Obsidian configuration, plugins, or an active collector. Add Sources, Ideas and Maps only as real notes need them. Admin / Personal / Work are metadata categories, not mandatory folder trees.

Develop one real source into one useful idea with a source locator, an applicability limit, and an explained connection when one exists. Retrieve it to answer a question. Expand conventions only to solve observed friction. Examples in the package are synthetic demonstrations; never import them as the user's observations or real research findings.

## Source versus design

Edmund's setup discussion presents five levels as his framework and links multiple approaches. Do not assess the user against a required progression or official standard. Our explicit existing-vault gate, minimal starter, schema mappings and script flags are implementation decisions. See [sources.md](sources.md) for attribution and inspected companion discussions. The model image's internal labels were not transcribed; do not invent them.

Our interpretation of the setup and simplification discussions is to make complexity earn its place: add an alias after a retrieval miss, a map for a recurring question, or a collection tool for repeated capture work. Plain files, a short guide and explained links are the starting point. Stable IDs and provenance add a little authoring work but make safe updates and evidence tracing possible. Delaying embeddings and a graph database keeps the system portable but means semantic matching remains a review task. Keeping raw sources separately preserves evidence but increases storage. These are our tradeoffs, not forum requirements.
