"""Локальне превʼю без БД; сервер завершується сам або через Ctrl+C."""
import argparse
import sys
import threading
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'spec'))
import preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['app', 'concepts', 'minimal'], default='app')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--seconds', type=int, default=1200, help='Час роботи, 1–3600 секунд')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 3600 or not 0 <= args.port <= 65535:
        parser.error('Некоректний порт або час роботи')
    directory = preview.build() if args.target == 'app' else ROOT / 'docs' / 'redesign'
    entry = {'app': 'index.html', 'concepts': 'concepts.html', 'minimal': 'minimal-concepts.html'}[args.target]
    if not (directory / entry).is_file():
        parser.error(f'Немає файла {directory / entry}')
    server = preview.Server(directory, args.port)
    try:
        server.start()
        print(f'http://127.0.0.1:{server.port}/{entry}', flush=True)
        print(f'Автоматична зупинка через {args.seconds} с. Ctrl+C — завершити зараз.', flush=True)
        threading.Event().wait(args.seconds)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        print('Превʼю зупинено.', flush=True)


if __name__ == '__main__':
    main()
