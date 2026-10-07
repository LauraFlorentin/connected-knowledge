---
name: ck-setup
description: Set up Connected Knowledge on this machine — choose an existing Obsidian vault or create a new one, label this Mac, and switch capture of AI sessions on. Use when the user runs /ck-setup or $ck-setup, or asks to install, set up or reconfigure Connected Knowledge. Not for ordinary note requests.
argument-hint: "[resume | status | capture | vault <path>]"
---

# Set up Connected Knowledge

Arguments: $ARGUMENTS

The script is `../zettelkasten-obsidian/scripts/ck.py`, relative to this skill's
folder. Run it with the system Python; it needs no packages:
`python3 <path to ck.py> <command>`. It prints JSON. Everything previews first.
Add `--apply` only after the person has seen the preview and agreed.

If this host cannot run local commands (Claude chat, a phone, ChatGPT web), say so,
explain the steps below in plain words, and offer to prepare the answers file for
the person to run on the Mac that holds the vault.

## Steps

Ask one question at a time, in plain language. Reuse answers already given.

1. **Check.** Run `ck.py doctor`. Report in one line: Python version, whether this
   Mac is set up, and the vault. If `python_ok.capture` is false, stop and explain
   how to install Python 3.
2. **Vault.** Ask: use an existing Obsidian vault, or start a new one?
   - **New:** ask for a folder that does not exist yet. Offer the full structure
     (all folders, Home, Vault Guide, topic maps) or a minimal start (folders
     appear when needed); default full. Ask whether they want a `Templates/`
     folder for Obsidian's Templates plugin, or the note shapes inside the Vault
     Guide instead; default no templates folder. Ask for 5–10 main topics (they
     may skip). Categories are Admin, Personal and Work unless they want others.
   - **Existing:** ask for the path. The preview reads the vault without changing
     it and proposes how the plugin's labels map onto the property names the vault
     already uses. Show that mapping and the exact folders and files that would be
     added. Offer to add a short "AI history" paragraph to their guide.
3. **This Mac.** A short lowercase label such as `mac-mini` or `macbook-air`, and
   its role: `hub` (the one Mac that imports account exports) or `satellite`.
4. **Accounts.** A label per vendor they use, such as `personal` or `work`. Never
   an email address.
5. **Capture folders.** Which folders hold the projects whose AI sessions should
   be saved (for example `~/REPO`), any subfolders to leave out, and, if they drive
   this Mac remotely, the label of the device they usually type on.
6. **Preview, then apply.** Write the answers (shape below) to a temporary file
   outside the vault and run `ck.py setup --answers <file>`. Explain the preview in
   plain words. With their OK, run the same command with `--apply`.
7. **Trial.** Save this session with `ck.py add-session current` (preview, then
   `--apply`). Give the Obsidian link to the new conversation note and ask the
   person to open it.
8. **Capture switch.** Explain: after each finished turn the hook only notes that
   the session changed; a background step saves it after 10 quiet minutes, or at
   once when the session ends. Ask whether to switch it on for this Mac:
   `ck.py capture on` (preview), then `--apply`. In Codex the person must also
   review and trust the hook in `/hooks`.
9. **Older history.** Offer `/ck-add-session all` to save the local sessions this
   Mac already holds (preview first). Claude Code deletes old transcripts after a
   while, so sooner is better. Account exports (Claude: Settings → Privacy →
   Export data; ChatGPT: Settings → Data controls → Export data) are a separate,
   monthly step on the hub. If an earlier version saved conversations into a
   `ChatArchive/` folder, offer `ck.py migrate <that folder>` (preview first; it
   needs the plugin's Python packages and leaves the old folder untouched).

Arguments: `status` runs step 1 and summarises. `capture` jumps to step 8.
`vault <path>` starts step 2 with that path. `resume` runs `ck.py doctor` and
continues from the first unfinished step.

## Answers file

```json
{"machine": "mac-mini", "role": "hub", "vault_mode": "new",
 "vault": "/Users/me/Vaults/My Vault",
 "new_vault": {"structure": "full", "variant": "no-templates", "ontology": "default",
               "topics": ["AI & Agents", "Health"]},
 "accounts": {"claude": "personal", "openai": "personal"},
 "capture": {"roots": ["/Users/me/REPO"], "exclude": [], "default_remote_device": "macbook-air"},
 "update_guide": false}
```

For an existing vault use `"vault_mode": "existing"` and leave out `new_vault`.
Add `"adopt": {...}` only to correct the proposed mapping, and
`"update_guide": true` only if they agreed to the guide paragraph.

## Rules

- Never edit `.obsidian/`, and never move or rename existing notes.
- Nothing is captured until the person switches capture on for this Mac.
- Machine state stays outside the vault; the vault receives only notes,
  transcripts and the index.

## Finish

1. Run `ck.py doctor --next`.
2. Say in one line what was done, give one starting link, and name any limit.
3. Offer `next.suggestion` as the next step, `next.alternative` as one
   alternative, and "stop here".
4. Wait for the choice. Do not start the next task unasked.
