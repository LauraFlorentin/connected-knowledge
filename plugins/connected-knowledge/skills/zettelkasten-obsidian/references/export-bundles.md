# ZIP exports and selected attachments

`export_bundle.py` prepares a private staging bundle. It does not download URLs,
execute files, recursively unpack archives, run OCR or infer which message owns an
attachment. Keep the input export and output outside the plugin repository.

First inventory names without extracting or reading conversation text into the chat:

```sh
python /plugin/skills/zettelkasten-obsidian/scripts/export_bundle.py /private/export.zip
```

Select the exact conversation JSON and each attachment to preserve. Preview first:

```sh
python /plugin/skills/zettelkasten-obsidian/scripts/export_bundle.py /private/export.zip --platform claude --conversation-member data/conversations.json --attachment attachments/reference.pdf --destination /private/prepared-bundle
```

Add `--apply` after reviewing selection. A bundle contains:

- `original.zip`: the complete supplied ZIP, byte-for-byte, including unselected
  members. Select an appropriately scoped export; this is not a data-minimization filter.
- `conversations.json`: the selected array for the existing chat importer.
- `files/`: selected attachment bytes, preserving their relative archive paths.
- `ATTACHMENTS.md`: clickable relative links, without invented message associations.
- `bundle.json`: selected scope and SHA-256 inventory.

Then preview/import `conversations.json` with `chat_import.py` into a separate
managed archive. Keep the prepared bundle: the importer preserves conversation
JSON but does not copy the attachments into its Markdown archive. The index is
usable locally; move/copy an attachment into a vault only as a separately selected
operation, preserving its provenance. File contents require their own supported
reader (for example PDF extraction); retention does not mean searchable extraction.
Provider attachment references remain in original JSON; unrecognized references,
remote-only files and missing bytes are not silently resolved. The tool never uses
export download tokens or fetches a URL found in messages.

## Safety and recovery

Only relative portable paths are accepted. Traversal, absolute/drive paths,
backslashes, controls, symlinks/special files, encrypted entries, duplicate paths,
case/Unicode collisions and file/directory collisions are rejected. Limits are
10,000 members, 512 MiB compressed input/total uncompressed payload, 128 MiB per
member, and 1,000:1 compression ratio. Larger exports need separately prepared,
reviewed batches; the tool does not silently skip members to fit the limit.

Apply uses a private staging directory and sibling exclusive lock, then renames
completed output into a previously absent destination. Ordinary exceptions clean
up owned staging files. A process kill may leave a staging directory/lock: establish
that no writer is active before preserving/removing that incomplete staging state.
Do not clear a live lock. No stale-lock auto-removal is performed.

An identical selection verifies every inventoried output hash and becomes a no-op.
Changed/missing output files fail closed, preserving edits. Choose a new destination
for another ZIP or selection. No full multi-process adversarial filesystem security
is claimed; run in trusted single-user private storage.
