"""Read-only localization gate, independent of the mockup's menu arrangement.

Run ``python scripts/toolbox/localization_audit.py --inventory menu_inventory.json``.
The inventory is a JSON array (or {"items": [...]}) of {id, label_key,
tooltip_key?}; path/parent/order are optional descriptive data. Every command
keeps its id when the mockup moves it. This tool never creates ids from labels
or menu position, and never edits the inventory, catalogs, settings or project.

``--scan`` lists Greek string *candidates* still in Python source, excluding
docstrings. These include internal values and are not a verified UI inventory.
``--json`` emits machine-readable results for the next migration step.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from archforge.localization import Translator, validate_catalogs, validate_inventory


def check_inventory(items, translator):
    return validate_inventory(items, translator)


def scan(root=ROOT / 'archforge'):
    """Candidate source locations, not an assertion that every literal is a label."""
    out = []
    for path in sorted(Path(root).rglob('*.py')):
        if 'scenarios' in path.parts or 'localization' in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding='utf8'))
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.body and isinstance(node.body[0], ast.Expr):
                    docs.add(id(node.body[0].value))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docs and re.search('[Α-Ωα-ω]', node.value)):
                out.append({'path': str(path.relative_to(ROOT)), 'line': node.lineno,
                            'candidate': node.value[:240], 'status': 'requires_context_review'})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--scan', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    errors = validate_catalogs()
    items = []
    if args.inventory:
        try:
            loaded = json.loads(args.inventory.read_text(encoding='utf8'))
            items = loaded.get('items') if isinstance(loaded, dict) else loaded
            errors.extend(check_inventory(items, Translator(language='en')))
        except (OSError, ValueError) as exc:
            errors.append(f'inventory: {exc}')
    candidates = scan() if args.scan else []
    result = {'catalog_errors': errors, 'inventory_items': len(items) if isinstance(items, list) else 0,
              'inventory_supplied': args.inventory is not None,
              'legacy_candidates': candidates,
              'complete_interface_translation_verified': False}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f'Catalog errors: {len(errors)}')
        print(f'Inventory: {result["inventory_items"]} items' if args.inventory else
              'Inventory not supplied; menu coverage is NOT verified.')
        if args.scan:
            print(f'Legacy source candidates: {len(candidates)} (context review required)')
        for error in errors:
            print(error)
        print('This gate does not certify complete interface translation or Windows usability.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
