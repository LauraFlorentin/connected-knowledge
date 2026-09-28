# Practical use

Set `CORE` to the extracted package's core directory:

```bash
CORE=/absolute/path/to/connected-knowledge/plugins/connected-knowledge/skills/zettelkasten-obsidian
```

Use a Python environment with `CORE/scripts/requirements.txt` installed. Scripts work without Claude, ChatGPT or Obsidian running.

## Existing vault

First supply the vault path or a representative sample. Inspect the conventions, map properties if necessary, and produce a read-only baseline:

```bash
python "$CORE/scripts/vault_check.py" /path/to/existing-vault --profile generic > /path/outside-vault/check.json
```

Do not rename folders, migrate notes, or change `.obsidian` configuration to satisfy this package. The core's `references/onboarding.md` describes the adaptive workflow. Default `auto` checking validates our schema only on notes declaring `schema_version: 1`.

## Optional new vault

Only after explicitly choosing not to use an existing vault:

```bash
python "$CORE/scripts/starter_vault.py" /path/to/new-vault --confirmed-no-existing-vault
```

The target must be absent. It creates a starting guide, an adaptable `VAULT-GUIDE.md` and four manual note templates; no app settings. Add folders as needed. This command is not a migration tool.

## One-time collection

Copy `config/collection.disabled.json` outside the installed plugin, set an explicit inbox and add only selected sources as described in the Collect Research reference. Then:

```bash
python "$CORE/scripts/collect.py" --config /path/to/collection.json --once
```

Review `inbox/runs`, `inbox/review` and provenance records. Repeat runs skip unchanged inputs. Different bytes create versions. Feeds capture entry XML, not article bodies. No raw source is automatically promoted to a developed note. Errors and incomplete captures produce a nonzero exit. Select a specific enabled source with `--source source-id`.

## Extract a selected PDF

```bash
python "$CORE/scripts/extract_pdf.py" /path/to/original.pdf --output /path/to/extractions
```

Read metadata before relying on text. Exit 1 means some pages need review; exit 2 means failure. Physical PDF page numbers are retained. Scanned/low-text pages are flagged; OCR is not included. Inspect figures and tables visually. Preserve the original separately; capture already does this in its raw archive.

## Develop notes and check them

Prompt: “Develop the selected source into the smallest useful set of source and idea notes. Keep provenance, distinguish inference, explain useful links, and follow my existing vault conventions.”

Use source, idea, map and decision templates only where useful. Examples are marked fictional. Adopted decisions need actual evidence; source summaries are not independent corroboration. For an AI-banking draft, use Synthesize mode to connect claims, address objections and expose missing evidence.

```bash
python "$CORE/scripts/vault_check.py" /path/to/vault --profile auto
```

The checker prints JSON and never rewrites notes. Exit 1 signals errors (or warnings with `--strict`); exit 2 signals a failure to run. A clean structural check does not validate truth. See core `references/research-tools.md` for scope and optional field mappings.

## Ongoing collection later

Select sources, filters, inbox, cadence/timezone, execution computer/service, retention and exclusions first. Set `ongoing_enabled` true only after that choice. An independently configured scheduler can call:

```bash
python "$CORE/scripts/collect.py" --config /path/to/collection.json --scheduled
```

No scheduler is installed by these instructions. A sleeping/offline local computer cannot provide dependable unattended collection. Phone use requires a reachable remote runtime/destination or selected manual upload. Available email or cloud connectors require separately authorized access; this package does not fetch all consumer chat histories.
