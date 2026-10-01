"""Render explicitly selected Markdown templates without evaluating code or queries."""
from datetime import date
import re
import yaml


def apply_template(template, generated, identity):
    if not template.startswith('---\n') or '\n---\n' not in template[4:]:
        raise ValueError('Capture template requires YAML frontmatter')
    header, body = template[4:].split('\n---\n', 1)
    properties = yaml.safe_load(header)
    if not isinstance(properties, dict):
        raise ValueError('Capture template properties must be a mapping')
    generated_header, capture_body = generated.decode()[4:].split('\n---\n', 1)
    metadata = yaml.safe_load(generated_header)
    values = {'title': metadata['title'], 'date:YYYY-MM-DD': date.today().isoformat(),
              'date': date.today().isoformat(), 'id': identity,
              'source_file': metadata['source_file'], 'capture': capture_body.strip()}

    def expand(value):
        if isinstance(value, str):
            def replace(match):
                token = match.group(1)
                if token not in values:
                    raise ValueError('Unsupported capture template placeholder')
                return values[token]
            return re.sub(r'\{\{([^{}]+)\}\}', replace, value)
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, dict):
            return {key: expand(item) for key, item in value.items()}
        return value

    properties = expand(properties)
    if properties.get('type') not in (None, 'reference', 'review') or properties.get('note_type') not in (None, 'source'):
        raise ValueError('Choose a source or conversation-review capture template')
    if properties.get('type') == 'review' and properties.get('review_kind') not in (None, 'conversation'):
        raise ValueError('Choose a conversation-review template')
    if properties.get('decision_id'):
        raise ValueError('A source capture cannot create a decision identifier')
    if 'type' in properties and 'note_type' in properties:
        raise ValueError('Capture template has competing property vocabularies')
    if 'status' in properties and 'review_status' in properties:
        raise ValueError('Capture template has competing review properties')
    # New captures are unreviewed. Templates cannot silently certify source text.
    if 'status' in properties:
        properties['status'] = 'auto'
    if 'review_status' in properties:
        properties['review_status'] = 'draft'
    for key, value in metadata.items():
        if key in ('type', 'note_type', 'status', 'review_status') and key not in properties:
            if key in ('type', 'status') and ('note_type' in properties or 'review_status' in properties):
                continue
            if key in ('note_type', 'review_status') and ('type' in properties or 'status' in properties):
                continue
            properties.setdefault(key, value)
        elif key not in ('type', 'note_type', 'status', 'review_status'):
            properties[key] = value
    rendered = expand(body)
    if '{{capture}}' not in body:
        rendered += '\n\n## Captured source\n\n' + capture_body.strip() + '\n'
    return ('---\n' + yaml.safe_dump(properties, allow_unicode=True, sort_keys=False)
            + '---\n' + rendered).encode()
