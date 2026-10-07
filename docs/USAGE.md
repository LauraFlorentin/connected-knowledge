# Practical use

## Commands

| Command | Codex | What it does |
| --- | --- | --- |
| `/ck-setup [resume \| status \| capture \| apps \| vault <path>]` | `$ck-setup` | Choose or create the vault, label this Mac, pick capture folders, switch capture on. `apps` offers the optional Filesystem MCP for chat in the Claude desktop app |
| `/ck-help [topic]` | `$ck-help` | Status of this Mac and vault, a menu, and the most useful next step |
| `/ck-add-session [current \| latest \| all \| <session-id> \| <path>]` | `$ck-add-session` | Save a session now as a conversation note plus transcript |

Each command previews before writing and ends with one suggested next step, one
alternative, and "stop here". Gemini CLI uses the same `/ck-…` names.

`/ck-add-session` options: `--title` (at most five words), `--category`,
`--topic` (repeatable; must name an existing topic map), `--project`, `--device`
(where you typed, for example `iphone`), `--summary`. `all` saves every local
session in your capture folders that is not saved yet. Claude Code deletes old
transcripts after a while, so run it soon after setup.

## The script behind the commands

The commands call one script, which you can also run yourself. It prints JSON and
writes nothing without `--apply`. It needs only the standard library.

```bash
CORE=/absolute/path/to/connected-knowledge/plugins/connected-knowledge/skills/zettelkasten-obsidian
CK="$CORE/scripts/ck.py"
python3 "$CK" doctor --next                       # status and next step
python3 "$CK" setup --answers answers.json        # preview; add --apply to write
python3 "$CK" capture on                          # preview; add --apply to switch on
python3 "$CK" add-session current                 # preview; add --apply to save
python3 "$CK" add-session all                     # every local session not yet saved
python3 "$CK" topics                              # the topic tree
python3 "$CK" topic-add "Raised beds" --parent "Gardening" --apply
python3 "$CK" sweep                               # capture queued sessions now
python3 "$CK" migrate /path/to/Vault/ChatArchive/claude-code   # 1.6.0 archives; needs PyYAML
python3 "$CK" mark-import claude                  # record that a Claude export was imported
```

The answers file for `setup` is described in
[the ck-setup skill](../plugins/connected-knowledge/skills/ck-setup/SKILL.md).

## How capture works

After each finished turn in Claude Code or Codex, the hook writes a small queue
entry on this Mac, "this session changed", and does nothing else. It never opens
the transcript. A background sweep saves each session that has ended or been quiet
for ten minutes (`idle_minutes`). The sweep starts when a session starts or ends,
when a turn ends while another queued session is already due, and when you run
`/ck-add-session` or `ck.py sweep`. It reads the transcript once and writes:

- a conversation note in `Sources/AI Conversations/<year>/`, named
  `2026-10-06 <Title> — claude-code 8e32d2fd.md`, with the labels and a short block
  the plugin keeps up to date;
- the transcript in `Attachments/AI Transcripts/<year>/`, with links, tags and code
  from the chat shown as plain text;
- a project note in `Projects/` the first time a project appears;
- one line per conversation in `_meta/index/conversations.<machine>.jsonl`.

Sessions are in scope when they start inside one of your capture folders and not
inside an excluded folder. The project is the first folder below the capture
folder where the session started, even if it later moves elsewhere.

What stays yours: everything outside the `ck:begin`/`ck:end` block, and your
changes to title, category, classification status, review status and topics.
If you delete a conversation note, the sweep does not recreate it. If you edit a
transcript, it is no longer updated; delete it to let it be regenerated. A
shorter or different transcript never replaces a saved conversation.

Machine state lives outside the vault, in folders only you can read: the
configuration (`~/.config/connected-knowledge/config.json`), the queue, the
manifest of what this Mac saved, and one raw copy of each transcript. Two Macs can
share one synced vault: each saves only the sessions it holds, writes its own
index file, and never overwrites a note another Mac wrote.

## A new vault

`/ck-setup` creates one for you, or run the script directly. The target folder
must not exist yet.

```bash
python3 "$CORE/scripts/starter_vault.py" /path/to/New-Vault --confirmed-no-existing-vault \
  --structure full --variant no-templates --topic "AI & Agents" --topic "Health"
```

- `--structure full` creates every folder now; `minimal` creates only Home, the
  Vault Guide, the agent instructions and the profile.
- `--variant templates` adds `Templates/` with seven note templates for Obsidian's
  core Templates plugin; `no-templates` puts the same note shapes in the Vault
  Guide instead.
- `--topic` (repeatable) creates one map per main topic, linked from Home.
- `--ontology none|default|custom` and `--categories` choose the categories.
- `--preview` lists what would be created.

Nothing under `.obsidian/` is written. Point Obsidian's Templates plugin at
`Templates` yourself if you chose that variant.

## An existing vault

`/ck-setup` reads the vault without changing it and proposes how the plugin's
labels map onto the names the vault already uses: a vault that uses `type` and
`status` gets conversation notes with `type: reference` and `status: auto`, and no
second set of fields. It lists the files and folders it would add (the profile
`_meta/ck/vault.json`, a conversations folder, a transcripts folder, the index
folder), and can append a short "AI history" paragraph to your guide. Existing
notes are never moved or renamed.

For a separate read-only baseline, set `CORE` to the core skill folder and run:

```bash
python "$CORE/scripts/vault_check.py" /path/to/existing-vault --profile generic > /path/outside-vault/check.json
```

A vault set up by Connected Knowledge carries its profile, which the checker reads
automatically. `--profile auto` applies the schema only to notes declaring
`schema_version: 1`. A missing category is a warning while
`classification_status` is `provisional` and is not required on maps.

## One-time collection

Copy `config/collection.disabled.json` outside the installed plugin, set an explicit
inbox and add only selected sources as described in the Collect Research
reference. Then:

```bash
python "$CORE/scripts/collect.py" --config /path/to/collection.json --once
```

Review `inbox/runs`, `inbox/review` and provenance records. Repeat runs skip
unchanged inputs. Different bytes create versions. Feeds capture entry XML, not
article bodies. No raw source is automatically promoted to a developed note.

## Extract a selected PDF

```bash
python "$CORE/scripts/extract_pdf.py" /path/to/original.pdf --output /path/to/extractions
```

Exit 1 means some pages need review; exit 2 means failure. Physical page numbers
are kept. Scanned pages are flagged; OCR is not included.

## Import account exports

Keep the export and destination outside the repository. Preview a Claude
conversation array without creating output:

```bash
python "$CORE/scripts/chat_import.py" /private/exports/conversations.json /path/to/Vault/ChatArchive/claude --platform claude --account personal
```

Use a stable, non-secret account label. Add `--vocabulary existing` for vaults
using `type` and `status`. Notes carry `source_platform`, `source_id` and
`source_account`; ChatGPT's epoch timestamps become ISO 8601 dates; message text is
shown as plain text. See [history import](../plugins/connected-knowledge/skills/zettelkasten-obsidian/references/history-import.md)
and [export bundles](../plugins/connected-knowledge/skills/zettelkasten-obsidian/references/export-bundles.md).
After an import on the hub, run `ck.py mark-import claude` (or `openai`) so
`/ck-help` knows when the last export arrived.

## Develop the graph

The [graph workflow](../plugins/connected-knowledge/skills/zettelkasten-obsidian/references/graph-development.md)
searches imported messages and applies reviewed proposals with source citations.
The assistant supplies interpretation; the scripts check structure and evidence
references, not the truth of a claim.

## Ongoing collection later

Select sources, filters, inbox, cadence, execution computer, retention and
exclusions first. Set `ongoing_enabled` true only after that choice. An
independently configured scheduler can call `collect.py --scheduled`. No scheduler
is installed by these instructions.

## Compare and validate existing vaults

Adapt the [profile example](../plugins/connected-knowledge/skills/zettelkasten-obsidian/assets/profiles/existing-vault.json),
then ask: "Check this vault using its existing properties; report template and link
scope separately and do not change files." See
[profile rules and evidence limits](../plugins/connected-knowledge/skills/zettelkasten-obsidian/references/existing-vaults.md).

## Guided use

Run `/ck-help`, or invoke Connected Knowledge and ask "Guide me step by step."
Choose vault setup, past conversations, saving the current conversation, a
document, or exploring your notes. After each task the assistant suggests one
relevant next task and waits for your choice.
