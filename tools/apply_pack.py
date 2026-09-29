"""Применение пакета чата «МС город» (docs/WORKFLOW.md). Замена apply.sh: только Python и git,
без unzip/bash/find — одинаково работает в Windows и Linux.

Запуск из корня репозитория mc-bot:
    python tools/apply_pack.py            — взять самый свежий mc-bot-pack-*.zip в корне
    python tools/apply_pack.py <файл.zip> — конкретный пакет
    python tools/apply_pack.py --clean    — сначала откатить незакоммиченные изменения
                                            отслеживаемых файлов и остатки прошлой попытки
    --no-push                             — без push (проверка)

Шаги: найти архив (в т.ч. «… (1).zip» от браузера) → распаковать в .pack (удалив старую) →
проверить BASE = HEAD и чистое дерево → скопировать files/ → tools/city/verify.py →
git add (явный список) → commit (COMMIT_MSG) → push → удалить .pack и архив.
При ошибке — «СТОП: …» и откат; ничего не коммитится.
"""
import glob
import os
import shutil
import subprocess
import sys
import zipfile

def _root():
    r = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = _root()                                       # корень репозитория (запуск из любой его папки)
PACK = os.path.join(ROOT, '.pack')


def say(*a): print(*a, flush=True)


def stop(msg, rollback=None):
    if rollback: rollback()
    say('СТОП:', msg); sys.exit(1)


def git(*args, check=True):
    r = subprocess.run(['git'] + list(args), cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode != 0: stop('git ' + ' '.join(args) + ': ' + (r.stderr or r.stdout).strip()[-400:])
    return r.stdout.strip()


def main():
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    clean, push = '--clean' in sys.argv, '--no-push' not in sys.argv
    if args:
        zp = os.path.abspath(args[0])
    else:
        cands = glob.glob(os.path.join(ROOT, 'mc-bot-pack-*.zip'))
        if not cands:
            stop('в корне репозитория нет mc-bot-pack-*.zip (архив остался в «Загрузках»?) — положите его в ' + ROOT)
        zp = max(cands, key=os.path.getmtime)
        if len(cands) > 1: say('Архивов несколько, беру самый свежий:', os.path.basename(zp))
    if not os.path.exists(zp): stop('нет файла ' + zp)
    say('Пакет:', os.path.basename(zp))
    if clean:
        say('--clean: откат незакоммиченных изменений:', git('status', '--short', '--untracked-files=no') or 'нет')
        git('checkout', '--', '.')
    if os.path.exists(PACK): shutil.rmtree(PACK, ignore_errors=True)
    try:
        with zipfile.ZipFile(zp) as z: z.extractall(PACK)
    except zipfile.BadZipFile:
        stop('архив повреждён или не докачан — скачайте заново')
    for need in ('BASE', 'COMMIT_MSG', 'files'):
        if not os.path.exists(os.path.join(PACK, need)): stop(f'в архиве нет {need} — это не пакет чата')
    base = open(os.path.join(PACK, 'BASE'), encoding='utf-8').read().strip()
    head = git('rev-parse', 'HEAD')
    if git('rev-parse', base, check=False) != head:
        stop(f'HEAD {head[:7]} не равен базе пакета {base[:7]} — пакет собран от другого коммита (git pull или новый пакет)')
    dirty = git('status', '--porcelain', '--untracked-files=no')
    if dirty: stop('есть незакоммиченные изменения (повторите с --clean, если это остатки прошлой попытки):\n' + dirty)
    src = os.path.join(PACK, 'files')
    files = sorted(os.path.relpath(os.path.join(d, f), src).replace('\\', '/')
                   for d, _, fs in os.walk(src) for f in fs)
    new = [f for f in files if subprocess.run(['git', 'ls-files', '--error-unmatch', f], cwd=ROOT,
                                              capture_output=True).returncode != 0]
    say(f'Файлов в пакете: {len(files)} (новых {len(new)})')
    for f in files:
        dst = os.path.join(ROOT, f); os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(src, f), dst)

    def rollback():
        git('checkout', '--', '.', check=False)
        for f in new:
            try: os.remove(os.path.join(ROOT, f))
            except OSError: pass
        say('Изменения откачены.')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    if not os.path.isdir(os.path.join(ROOT, 'node_modules')): say('ВНИМАНИЕ: нет node_modules — генераторам нужен npm install')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'city', 'verify.py')], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    say(r.stdout.strip())
    if r.returncode != 0: stop('verify FAIL — ничего не закоммичено' + ('\n' + r.stderr.strip()[-400:] if r.stderr.strip() else ''), rollback)
    for f in files: git('add', '--', f)
    staged = git('diff', '--cached', '--name-only')
    if not staged: stop('после git add нечего коммитить (файлы пакета совпадают с репозиторием?)', rollback)
    git('commit', '-q', '-F', os.path.join(PACK, 'COMMIT_MSG'))
    if push: git('push', '-q', 'origin', 'HEAD:master')
    else: say('(push пропущен: --no-push)')
    say('Готово: коммит', git('rev-parse', '--short', 'HEAD'))
    shutil.rmtree(PACK, ignore_errors=True)
    try: os.remove(zp)
    except OSError: pass


if __name__ == '__main__':
    main()
