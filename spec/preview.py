# Превʼю index.html без Supabase: копія в spec/.out/preview/ і локальний http.server.
# Рецепт: прибрати тег supabase-js (sb лишається null, застосунок іде на демо-даних),
# вимкнути реєстрацію service worker, прибрати sb&& біля кнопок, які без БД сховані.
import functools
import http.server
import shutil
import socket
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'spec' / '.out' / 'preview'

# (що шукаємо, на що міняємо); кожен шаблон мусить знайтися рівно раз
SWAPS = [
    ('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"></script>', ''),
    ("sb&&h('button',{onClick:openSettings", "h('button',{onClick:openSettings"),
    ("sb&&h('button',{className:'side-item',onClick:openSettings,", "h('button',{className:'side-item',onClick:openSettings,"),
    ("tab!=='overview'&&sb&&h('button',{onClick:fabAct", "tab!=='overview'&&h('button',{onClick:fabAct"),
    ("sb&&h('button',{className:'dact'", "h('button',{className:'dact'"),
    ("if('serviceWorker' in navigator){", "if(false){"),
]
COPY = ['manifest.json', 'icon-192.svg', 'icon-512.svg']


def build():
    """Збирає копію для превʼю; падає, якщо шаблон рецепта зник з index.html."""
    src = (ROOT / 'index.html').read_text(encoding='utf-8')
    for old, new in SWAPS:
        n = src.count(old)
        if n != 1:
            raise RuntimeError(f'превʼю: шаблон знайдено {n} раз(и): {old[:60]}')
        src = src.replace(old, new)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'index.html').write_text(src, encoding='utf-8')
    for name in COPY:
        if (ROOT / name).exists():
            shutil.copy2(ROOT / name, OUT / name)
    return OUT


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Server:
    """http.server в окремому потоці; stop() звільняє порт."""

    def __init__(self, directory=None, port=None):
        self.port = port or _free_port()
        handler = functools.partial(_Quiet, directory=str(directory or OUT))
        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}/index.html'

    def start(self):
        self.thread.start()
        return self.url

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


def start():
    """Збирає превʼю і піднімає сервер; повертає обʼєкт Server (url у .url)."""
    out = build()
    srv = Server(out)
    srv.start()
    return srv


if __name__ == '__main__':
    import time
    s = start()
    print('Превʼю:', s.url, '(Ctrl+C зупиняє)')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        s.stop()
