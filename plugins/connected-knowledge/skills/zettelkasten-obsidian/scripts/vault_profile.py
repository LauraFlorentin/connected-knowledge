"""Local conventions and read-only inventory shared by the vault tools."""
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re

TYPE_NAMES = {'string', 'integer', 'number', 'boolean', 'date', 'list', 'string_list'}


def property_value(value):
    """Serialize vocabulary values without dropping typed YAML mapping keys."""
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except TypeError:
        # JSON cannot represent date keys or sort mixed string/numeric keys.
        # Retain those values as explicit YAML rather than coercing keys, which
        # could silently merge distinct keys such as 1 and "1".
        import yaml
        return json.dumps({'yaml': yaml.safe_dump(value, sort_keys=True)})


def validate_config(cfg):
    if not isinstance(cfg, dict):
        raise ValueError('Profile config must be an object')
    for key in ('fields', 'enums', 'types', 'roles'):
        if not isinstance(cfg.get(key, {}), dict):
            raise ValueError(f'{key} must be an object')
    if any(not isinstance(k, str) or not isinstance(v, str) or not v
           for k, v in cfg.get('fields', {}).items()):
        raise ValueError('fields must map names to nonempty field names')
    for key in ('required', 'references', 'exclude_dirs', 'template_folders'):
        value = cfg.get(key, [])
        if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
            raise ValueError(f'{key} must be a list of nonempty strings')
    for key in ('guide',):
        if key in cfg and (not isinstance(cfg[key], str) or not cfg[key]):
            raise ValueError(f'{key} must be a nonempty relative path')
    for key in ('template_folders',):
        for name in cfg.get(key, []):
            if Path(name).is_absolute() or '..' in Path(name).parts or name == '.':
                raise ValueError(f'{key} must contain vault-relative subdirectories')
    if 'guide' in cfg and (Path(cfg['guide']).is_absolute() or '..' in Path(cfg['guide']).parts):
        raise ValueError('guide must stay inside the vault')
    for field, allowed in cfg.get('enums', {}).items():
        if not isinstance(allowed, list) or not allowed:
            raise ValueError(f'enums.{field} must be a nonempty list')
    for field, names in cfg.get('types', {}).items():
        names = names if isinstance(names, list) else [names]
        if not names or any(not isinstance(n, str) or n not in TYPE_NAMES for n in names):
            raise ValueError(f'Unknown type rule for {field}')
    for role, rule in cfg.get('roles', {}).items():
        if not isinstance(rule, dict):
            raise ValueError(f'roles.{role} must be an object')
        validate_config(rule)
        if 'identity' in rule and (not isinstance(rule['identity'], str) or not rule['identity']):
            raise ValueError(f'roles.{role}.identity must be a field name')
        fields = cfg.get('fields', {})
        identity = fields.get(rule.get('identity'), rule.get('identity'))
        references = [fields.get(k, k) for k in rule.get('references', []) + cfg.get('references', [])]
        if identity and identity in references:
            raise ValueError(f'roles.{role}: identity cannot also be a reference')


def matches_type(value, name):
    if name == 'string': return isinstance(value, str)
    if name == 'integer': return type(value) is int
    if name == 'number': return type(value) in (int, float)
    if name == 'boolean': return type(value) is bool
    if name == 'date': return isinstance(value, date) and not isinstance(value, datetime)
    if name == 'list': return isinstance(value, list)
    if name == 'string_list': return isinstance(value, list) and all(isinstance(x, str) for x in value)
    return False


def local_rules(meta, cfg, add, path):
    fields = cfg.get('fields', {})
    role = meta.get(fields.get('note_type', 'note_type'))
    rule = cfg.get('roles', {}).get(role, {}) if isinstance(role, str) else {}
    for source in (cfg, rule):
        for field in source.get('required', []):
            actual = fields.get(field, field)
            if actual not in meta or meta[actual] in (None, ''):
                add('required', path, f'Missing {actual}')
        for field, allowed in source.get('enums', {}).items():
            actual = fields.get(field, field)
            if actual in meta and meta[actual] not in allowed:
                add('enum', path, f'Invalid {actual}: {meta[actual]!r}')
        for field, names in source.get('types', {}).items():
            actual = fields.get(field, field)
            if actual not in meta or meta[actual] is None: continue
            names = names if isinstance(names, list) else [names]
            if not any(matches_type(meta[actual], n) for n in names):
                add('property-type', path, f'{actual} must have type {names}')
    return role, rule


def template_locations(root, cfg):
    folders = list(cfg.get('template_folders', []))
    setting = root / '.obsidian/templates.json'
    if setting.is_file():
        data = json.loads(setting.read_text())
        folder = data.get('folder')
        if isinstance(folder, str) and folder:
            folders.append(folder)
    result = []
    for folder in folders:
        p = (root / folder).resolve()
        if not p.is_relative_to(root) or p == root:
            raise ValueError('Template folder must be a subdirectory inside the vault')
        if not p.is_dir():
            raise ValueError(f'Template folder is missing or not a directory: {folder}')
        if p not in result: result.append(p)
    return result


def is_template(path, folders):
    return any(path.is_relative_to(folder) for folder in folders)


def file_inventory(root):
    """Do not follow symlinks or collect repository internals."""
    files = {}
    for p in sorted(root.rglob('*')):
        if '.git' in p.relative_to(root).parts or p.is_symlink() or not p.is_file(): continue
        if any(parent.is_symlink() for parent in p.parents if parent != root and root in parent.parents): continue
        files[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return files


def inspect_templates(root, folders, loader, cfg):
    import yaml
    results = []
    seen = set()
    for folder in folders:
        for p in sorted(folder.rglob('*.md')):
            if p.is_symlink() or p in seen: continue
            seen.add(p)
            text = p.read_text(encoding='utf-8-sig')
            issues = []
            # Bounded core substitution; arbitrary Moment formats are deliberately unverified.
            supported = {'title': 'Template trial', 'date': '2000-01-02',
                         'date:YYYY-MM-DD': '2000-01-02', 'time': '03:04', 'time:HH:mm': '03:04'}
            def expand(match):
                token = match.group(1)
                if token.startswith('date:') and re.fullmatch(r'[YMDHms\-:T Z]+', token[5:]):
                    # Moment-style date formats used by Obsidian's core Templates plugin.
                    sample = {'YYYY': '2000', 'MM': '01', 'DD': '02', 'HH': '03', 'mm': '04', 'ss': '05', 'Z': '+00:00'}
                    return re.sub(r'YYYY|MM|DD|HH|mm|ss|Z', lambda m: sample[m.group(0)], token[5:])
                if token not in supported:
                    issues.append({'severity':'warning', 'code':'template-variable',
                                   'message':f'Unsupported expansion: {match.group(0)}'})
                    return match.group(0)
                return supported[token]
            expanded = re.sub(r'{{([^{}]+)}}', expand, text)
            fm = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', expanded, re.S)
            meta = {}
            try:
                if expanded.startswith('---') and not fm: raise ValueError('Unterminated YAML frontmatter')
                if fm:
                    meta = yaml.load(fm.group(1), Loader=loader)
                    if meta is None: meta = {}
                    if not isinstance(meta, dict): raise ValueError('Frontmatter must be a mapping')
            except Exception as exc:
                issues.append({'severity':'error', 'code':'template-yaml', 'message':str(exc)})
            # Blank template placeholders are intentional, so validate only nonblank values.
            values = {k:v for k,v in meta.items() if v not in (None, '')} if isinstance(meta, dict) else {}
            template_cfg = dict(cfg, required=[])
            template_cfg['roles'] = {k:dict(v, required=[]) for k,v in cfg.get('roles', {}).items()}
            local_rules(values, template_cfg,
                        lambda code, path, message: issues.append({'severity':'error','code':code,'message':message}), p)
            results.append({'path':p.relative_to(root).as_posix(),
                            'sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'findings':issues,
                            'expansion':'bounded_synthetic_check', 'ui_trial':'not_performed'})
    return results
