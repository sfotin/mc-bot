"""
decor_check.py - находит в docs/DECOR.md все блоки ```json, парсит каждый
как схему (см. decor_lib.entries_to_schema) и прогоняет check_supports с
terrain="below" (и check_water, если в блоке есть вода). Печатает отчёт по
каждому элементу (подписан ближайшим заголовком выше). Ошибки в JSON из
DECOR.md не исправляются - только сообщаются (см. BOT.md/задание).

Запуск:
    python3 tools/decor/decor_check.py [--file docs/DECOR.md]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decor_lib as dl  # noqa: E402

# консоль Windows по умолчанию не в UTF-8 (cp1251/cp866) - без этого падает
# на кириллице/типографских символах (например "×" в заголовках DECOR.md)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DEFAULT_DECOR_MD = os.path.join('docs', 'DECOR.md')

HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$', re.M)
JSON_FENCE_RE = re.compile(r'```json\s*\n(.*?)\n```', re.S)


def find_elements(text):
    """Возвращает список (heading, json_text, start_pos) для каждого ```json блока -
    heading - ближайший заголовок (### / ##) ВЫШЕ блока в тексте."""
    headings = [(m.start(), m.group(2).strip()) for m in HEADING_RE.finditer(text)]

    def heading_for(pos):
        current = '(без заголовка)'
        for hpos, htext in headings:
            if hpos > pos:
                break
            current = htext
        return current

    elements = []
    for m in JSON_FENCE_RE.finditer(text):
        elements.append((heading_for(m.start()), m.group(1), m.start()))
    return elements


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--file', default=DEFAULT_DECOR_MD)
    return p.parse_args()


def main():
    args = parse_args()
    with open(args.file, encoding='utf-8') as f:
        text = f.read()

    elements = find_elements(text)
    print(f'Найдено блоков ```json в {args.file}: {len(elements)}\n')

    terrain = dl.make_terrain('below')
    total_errors = 0
    total_warnings = 0
    parse_failures = []

    for i, (heading, json_text, _pos) in enumerate(elements, 1):
        label = f'{i}. {heading}'
        try:
            entries = json.loads(json_text)
        except json.JSONDecodeError as e:
            print(f'=== {label} ===')
            print(f'ОШИБКА РАЗБОРА JSON: {e}')
            print()
            parse_failures.append(label)
            total_errors += 1
            continue

        schema, order = dl.entries_to_schema(entries)
        has_water = any(dl.parse_block(b)[0] == 'water' for b in schema.values())
        errors = dl.check_water(schema, terrain) if has_water else []
        support_errors, warnings = dl.check_supports(schema, order, terrain)
        errors = errors + support_errors

        err_count = dl.report(schema, order, errors, warnings, label=label)
        print()
        total_errors += err_count
        total_warnings += len(warnings)

    print('=== ИТОГО ===')
    print(f'элементов: {len(elements)}, ошибок разбора JSON: {len(parse_failures)}, '
          f'ошибок проверок: {total_errors - len(parse_failures)}, предупреждений: {total_warnings}')
    if parse_failures:
        print('Не разобрался JSON (сообщено, не исправлено):', ', '.join(parse_failures))

    sys.exit(1 if total_errors else 0)


if __name__ == '__main__':
    main()
