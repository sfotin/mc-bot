"""Единая проверка генераторов: python3 tools/city/verify.py [--district oldtown]

Для каждого генератора из реестра: запуск во временную папку (никогда не в schemas/),
сравнение выхода со схемами в schemas/ (как множество записей), разбор вывода
проверок генератора (ошибки опор/воды/порядка, проходимость, перепады, висящие,
негативные прогоны). Печатает по строке на генератор: OK или FAIL с причиной;
последняя строка — «verify: все OK» или «verify: FAIL n».
Новый генератор района добавляется в REGISTRY (docs/WORKFLOW.md).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SCH = os.path.join(REPO, 'schemas')

# (генератор, аргументы, {выход: схема в schemas/}); {T} — временная папка, {S} — schemas/
REGISTRY = {
    'oldtown': [
        ('gen_oldtown_1.py', ['--out', '{T}/a.json', '--preview', ''], {'a.json': 'oldtown-1-earthworks.json'}),
        ('gen_oldtown_1_fix1.py', ['--out', '{T}/a.json', '--preview', ''], {'a.json': 'oldtown-1-fix-1.json'}),
        ('gen_oldtown_2.py', ['--out', '{T}/a.json', '--preview', ''], {'a.json': 'oldtown-2-streets.json'}),
        ('gen_oldtown_3.py', ['--out', '{T}/a.json', '--preview', '', '--fix-from', '{S}/oldtown-3-build.json',
                              '--fix-out', '{T}/f.json'], {'f.json': 'oldtown-3-fix-2.json'}),
        ('gen_oldtown_4.py', ['--out', '{T}/a.json', '--preview', ''], {'a.json': 'oldtown-4-market.json'}),
        ('gen_oldtown_5.py', ['--out', '{T}/a.json', '--preview', ''], {'a.json': 'oldtown-5-tavern.json'}),
        ('gen_oldtown_6.py', ['--out', '{T}/a.json', '--preview', '', '--fix-from', '{S}/oldtown-6-library.json',
                              '--fix-out', '{T}/f.json'], {'f.json': 'oldtown-6-fix-1.json'}),
        ('gen_oldtown_7.py', ['--out', '{T}/a.json', '--preview', '', '--fix-from', '{S}/oldtown-7-gallery.json',
                              '--fix-out', '{T}/f.json'], {'f.json': 'oldtown-7-fix-1.json'}),
        ('gen_oldtown_8.py', ['--outdir', '{T}', '--preview', '', '--fix-from-dir', '{S}', '--fix-out', '{T}/f.json'],
         {'oldtown-8-k1.json': 'oldtown-8-k1.json', 'oldtown-8-k2.json': 'oldtown-8-k2.json',
          'oldtown-8-k5.json': 'oldtown-8-k5.json', 'f.json': 'oldtown-8-fix-1.json'}),
    ],
    'city': [
        ('gen_city_1.py', ['--outdir', '{T}', '--preview', '', '--fix-fountain', '{T}/f.json'],
         {'city-1-streets.json': 'city-1-streets.json', 'city-1-parks.json': 'city-1-parks.json',
          'f.json': 'city-1-fix-1.json'}),
        ('gen_city_4.py', ['--out', '{T}/a.json', '--preview', ''], {'a.json': 'city-4-opener.json'}),
        ('gen_city_5.py', ['--outdir', '{T}', '--preview', ''],
         {n: n for n in ('city-5-gate.json', 'city-5-bridge.json', 'city-6-sail.json', 'city-7-spiral.json',
                         'city-7-decks.json', 'city-7-ring.json')}),
        ('gen_city_6.py', ['--outdir', '{T}', '--preview', ''],
         {'city-6-pebbles.json': 'city-6-pebbles.json', 'city-6-summit.json': 'city-6-summit.json'}),
        ('gen_city_8.py', ['--outdir', '{T}', '--preview', ''],
         {'city-8-fix-1.json': 'city-8-fix-1.json', 'city-8-balloons.json': 'city-8-balloons.json'}),
    ],
    'park': [
        ('gen_park_1.py', ['--outdir', '{T}', '--preview', ''],
         {'park-1-ground.json': 'park-1-ground.json', 'park-1-build.json': 'park-1-build.json'}),
        ('gen_park_2.py', ['--out', '{T}/a.json', '--preview', ''], {'a.json': 'park-2-zoo.json'}),
    ],
    'hill': [
        ('gen_hill_1.py', ['--outdir', '{T}', '--preview', ''],
         {'hill-1-ground.json': 'hill-1-ground.json', 'hill-1-tower.json': 'hill-1-tower.json'}),
        ('gen_hill_1.py', ['--v2', '--outdir', '{T}', '--preview', ''], {'hill-1-fix-1.json': 'hill-1-fix-1.json'}),
    ],
    'mount': [
        ('gen_mount_1.py', ['--outdir', '{T}', '--preview', ''],
         {'mount-1-ground.json': 'mount-1-ground.json', 'mount-1-tower.json': 'mount-1-tower.json', 'mount-1-build.json': 'mount-1-build.json'}),
        ('gen_mount_2.py', ['--outdir', '{T}', '--preview', ''],
         {'mount-2-demolish.json': 'mount-2-demolish.json', 'mount-2-track.json': 'mount-2-track.json', 'mount-2-start.json': 'mount-2-start.json'}),
    ],
}

ZERO = [r'опоры/вода/порядок[^:]*: ошибок (\d+)', r'опоры/вода/порядок: ошибок (\d+)', r'предупреждений (\d+)',
        r'перепад[^—]*— (\d+)', r'со стыком[^—]*— (\d+)', r'висящие[^:]*: (\d+)', r'без стоянки[^:]*: (\d+)',
        r'в резерве трасс ниже Y 60 — (\d+)', r'вода рельефа, открытая в воздух[^:]*: (\d+)', r'ИТОГО недостижимых точек: (\d+)',
        r'скамейки[^:]*: ошибок (\d+)', r'у выходов с лестниц[^:]*: (\d+)', r'щели\): ошибок (\d+)', r'вода, открытая в воздух[^:]*: (\d+)', r'предметы на стекле[^:]*: (\d+)',
        r'обрыв[^—]*— (\d+)', r'вне района[^:]*: (\d+)', r'слой снега[^:]*: (\d+)', r'задеты[^:]*: (\d+)',
        r'обычного льда[^:]*: (\d+)', r'разрывов дорожки (\d+)', r'выходов для лодки[^:]*: (\d+)', r'у выходов лестницы[^:]*: (\d+)',
        r'без света[^:]*: (\d+)', r'осталось вне Горной площади — (\d+)', r'не свободно 3 бл\.: (\d+)',
        r'опоры в вольерах зоопарка: (\d+)', r'касается зоны вылета без поребрика: (\d+)', r'забор лам выше Y 89 — блоков (\d+)', r'подходы к наружным дверям: \d+, ошибок (\d+)']


def problems(out):
    bad = []
    for line in out.splitlines():
        s = line.strip()
        if 'НЕГАТИВ' in s:
            if s.endswith('False') or re.search(r'ошибок 0 \(ждём > 0\)', s): bad.append(s)
            continue
        if ('проходимость' in s or 'маршрут' in s or 'текущий проект' in s or 'построенное + исправление' in s) and s.endswith('False'): bad.append(s)
        for rx in ZERO:
            m = re.search(rx, s)
            if m and int(m.group(1)) > 0: bad.append(s); break
    return bad


def records(path):
    return {(e['x'], e['y'], e['z'], e['block']) for e in json.load(open(path))}


ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')   # Windows: вывод генераторов — в UTF-8


def run(argv):
    return subprocess.run([sys.executable] + argv, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', cwd=REPO, env=ENV)


def main():
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--district', default=None, help='район из REGISTRY (по умолчанию — все)')
    a = ap.parse_args()
    fails = 0
    r = run([os.path.join(HERE, 'world_model.py')])
    ok = r.returncode == 0
    print(('OK  ' if ok else 'FAIL') + ' world_model.py  ' + (r.stdout.splitlines() or [''])[0] + ('' if ok else ' ' + r.stderr[-300:]))
    fails += 0 if ok else 1
    for dist, items in REGISTRY.items():
        if a.district and dist != a.district: continue
        for gen, args, cmp in items:
            with tempfile.TemporaryDirectory() as T:
                argv = [x.replace('{T}', T).replace('{S}', SCH) for x in args]
                r = run([os.path.join(HERE, gen)] + argv)
                why = []
                if r.returncode != 0:
                    err = [l for l in r.stderr.strip().splitlines() if l.strip() and not l.startswith('Node.js v')]
                    why.append('ошибка запуска: ' + (' / '.join(err[-2:]) if err else 'код ' + str(r.returncode)))
                else:
                    for got, want in cmp.items():
                        gp = os.path.join(T, got); wp = os.path.join(SCH, want)
                        if not os.path.exists(gp): why.append(f'{got} не создан')
                        elif not os.path.exists(wp): why.append(f'нет schemas/{want}')
                        elif records(gp) != records(wp): why.append(f'{want} не совпадает')
                    why += problems(r.stdout)
            names = ', '.join(cmp.values())
            if why:
                fails += 1
                print(f'FAIL {gen}  ' + ' | '.join(why[:4]))
            else:
                print(f'OK   {gen}  (совпадают: {names}; проверки чистые)')
    print('verify: все OK' if not fails else f'verify: FAIL {fails}')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
