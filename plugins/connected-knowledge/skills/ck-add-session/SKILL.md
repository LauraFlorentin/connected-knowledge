---
name: ck-add-session
description: Save a chat or coding session to the Obsidian vault now, as a short labelled conversation note plus its full transcript. Use when the user runs /ck-add-session or $ck-add-session, or asks to save, capture or add this conversation or session to their notes.
argument-hint: "[current | latest | all | <session-id> | <path>] [--title …] [--category …] [--topic …] [--project …] [--device …]"
---

# Add a session to the vault

Arguments: $ARGUMENTS

The script is `../zettelkasten-obsidian/scripts/ck.py`, relative to this skill's
folder. Run `python3 <path to ck.py> add-session <target> [options]`; it needs no
packages. The target defaults to `current`.

1. **Preview.** Run the command without `--apply`. For the current Claude Code
   session add `--session-id ${CLAUDE_SESSION_ID}`; if that still reads as a
   placeholder, leave it out and the newest session started in this folder is used.
2. **Fill the gaps** from what you know of the conversation, each shown to the
   person as a proposal:
   - a title of at most five words (`--title`) if the preview's title is weak;
   - a category from the vault's categories (`--category`), by purpose, not by
     keywords; leave it out when unsure;
   - one to three topics from `ck.py topics` (`--topic`, repeatable). Never invent
     a topic; offer `ck.py topic-add "<name>" --parent "<topic>"` instead;
   - a two- or three-sentence summary (`--summary`), which the note marks as yours
     to review;
   - the device the person typed on (`--device iphone`), if they say.
3. **Apply.** If the person already said "save it", run the same command with
   `--apply`; otherwise ask once.
4. **Check.** Read the note back (`note` in the result is relative to the vault)
   and give one Obsidian link to it.

`all` previews every local session in the capture folders that is not saved yet.
Show the count and a few examples, and apply only after the person agrees.

In a chat app without local files (Claude chat, a phone, ChatGPT web) you cannot
run the script. Prepare the conversation note yourself in the vault's shape, with
`source_coverage: visible_context`, from the visible conversation only. Save it
through the private selected-save tool if it is connected; otherwise hand over
the Markdown and say "prepared, not saved".

## Finish

1. Run `ck.py doctor --next`.
2. Say in one line what was done, give the one link, and name any limit.
3. Offer `next.suggestion` as the next step (typically "develop this conversation
   into notes"), `next.alternative` as one alternative, and "stop here".
4. Wait for the choice. Do not start the next task unasked.
