# Guided first-run setup

Use this flow when someone asks to get started or connect their past conversations.
Reuse choices already given. Ask the next unresolved question in plain language;
do not request personal export content just to set up paths.

1. **Where should the notes live?** Existing vault or an explicitly chosen new
   starter. For an existing vault, locate and read its shared guide before proposing
   changes. Unavailable access never means permission to create a replacement.
2. **What history is in scope?** Choose particular Claude/ChatGPT JSON/ZIP exports,
   local agent transcript folders, or skip history. Each source has a stable local
   account label. Keep originals outside the vault and plugin repository.
3. **How should notes be organized?** No classification, Admin/Personal/Work, or
   custom categories. Preserve the existing property vocabulary. Classification
   choices do not authorize reading or classifying every conversation.
4. **Should new local sessions be captured?** Off by default. If requested, choose
   host, exact project directories and transcript roots. Prepare a disabled config
   for each host; do not register hooks during setup.
5. **Review the plan.** Show source scope, destinations, category choices and disabled
   capture state. Save the setup files, then carry out only the authorized steps.
   Start with one small import preview and check its coverage before applying.

## Terminal wizard or assistant-supplied answers

Run with the plugin's Python environment and dependencies installed:

```sh
python /plugin/skills/zettelkasten-obsidian/scripts/first_run.py --wizard --output /private/knowledge-setup
```

Default is a no-write preview. Add `--apply` to save the plan and disabled capture
configs only. It does not create a vault, import anything, classify notes or enable
hooks. For a new starter the plan supplies a separate explicit creation command.
Its four templates use the selected ontology; none/custom does not force Personal
or declare the default schema. Starter notes use the default note_type/review_status
vocabulary; existing-vault imports can use type/status with `vocabulary: existing`.
Other vocabulary mappings need an adapter before import.

An assistant can prepare a private answers JSON instead of opening an interactive
terminal. Never put account credentials in it. Example paths are placeholders:

```json
{
  "vault_mode": "existing",
  "vault": "/private/Notes",
  "vocabulary": "existing",
  "ontology": "none",
  "history": [{"source": "/private/exports/history.zip", "platform": "claude",
    "account": "personal", "conversation_member": "conversations.json",
    "attachments": ["attachments/reference.pdf"]}],
  "capture": []
}
```

```sh
python /plugin/skills/zettelkasten-obsidian/scripts/first_run.py --answers /private/answers.json --output /private/knowledge-setup --apply
```

`NEXT-STEPS.md` contains individually quoted commands. `setup.json` stores choices
and argument arrays for review. Setup refuses an existing output folder, so it
cannot erase previous choices. Inspect/preserve an interrupted setup and use a new
folder if needed. Input paths and filenames can themselves be private; keep these
reports local. Planned JSON imports are preview commands; add `--apply` only when
the user authorizes the selected import. Category options constrain later explicit
annotations; they do not assign categories automatically.

The ZIP step lists members and validates the exact selection. Attachment paths are
chosen individually; the whole original ZIP is also retained as evidence. See
[export bundles](export-bundles.md) for scope and size limits. Numbered bundle
folders are preparation outputs; archive identity uses platform/account, so multiple
export batches for the same account converge on the same archive.

After import, use [graph development](graph-development.md) to prepare sourced
notes. Test [capture and recovery](session-capture.md) with synthetic events before
separately enabling any real source or host hook. None of these steps establishes
complete account coverage or cross-device synchronization.

For packaged ongoing capture, follow [bundled hooks](bundled-hooks.md). Setup writes disabled configs only; set the host-specific environment variable and explicitly enable the chosen configuration after a synthetic test. Do not add duplicate manual hooks.
