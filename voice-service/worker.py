# Мовний сервіс ноутбука: бере в Supabase голосові завдання бота і виконує їх.
# stt: голосове з Telegram (OGG/Opus) у текст, faster-whisper.
# tts: текст відповіді в голос власника, HolosTTS ONNX, результат OGG/Opus.
# Нічого не відтворює: аудіо лише декодується й кодується в памʼяті.
import argparse
import base64
import hashlib
import hmac
import io
import json
import logging
import logging.handlers
import os
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from math import gcd
from pathlib import Path

VERSION = '1'
STT_MODEL = 'large-v3-turbo'
STT_PROMPT = 'Питання про сімейний бюджет: баланс, витрати, гривні, кредитка, аванс, зарплата.'
MAX_AUDIO_SEC = 120.0
MAX_TEXT = 2000
CHUNK_MAX = 250
PAUSE_SEC = 0.2
PEAK = 0.9
OUT_SR = 48000
CLAIM_WAIT = 50
BACKOFF_MIN, BACKOFF_MAX = 2.0, 30.0
AUTH_WAIT = 60.0

log = logging.getLogger('voice')


# ---------- Шляхи і конфіг ----------

def default_home() -> Path:
    """Тека .local/voice-service головного клону.

    Йдемо вгору від цього файла до першої теки з каталогом .git (у робочій
    копії гілки .git лише файл, тож її пропускаємо і виходимо на головний клон).
    """
    env = os.environ.get('VOICE_HOME')
    if env:
        return Path(env)
    for p in Path(__file__).resolve().parents:
        if (p / '.git').is_dir():
            return p / '.local' / 'voice-service'
    raise SystemExit('не знайшов корінь репозиторію, задайте --home або VOICE_HOME')


def load_config(home: Path) -> dict:
    # utf-8-sig: PowerShell 5.1 пише файли з BOM
    cfg = json.loads((home / 'config.json').read_text(encoding='utf-8-sig'))
    for key in ('supabase_url', 'voice_secret', 'voice_npy'):
        if not cfg.get(key):
            raise SystemExit(f'у config.json немає {key}')
    if len(cfg['voice_secret']) < 32:
        raise SystemExit('voice_secret коротший за 32 символи')
    cfg.setdefault('device', 'auto')
    return cfg


def setup_logging(home: Path) -> None:
    logs = home / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(logs / 'worker.log', maxBytes=1_000_000,
                                             backupCount=3, encoding='utf-8')
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    log.addHandler(h)
    log.setLevel(logging.INFO)


def err_brief(e: BaseException) -> str:
    """Тип помилки і місце, без тексту повідомлення: там може бути вміст запиту."""
    tb = traceback.extract_tb(e.__traceback__)
    where = f' at {Path(tb[-1].filename).name}:{tb[-1].lineno}' if tb else ''
    return f'{type(e).__name__}{where}'


# ---------- Протокол ----------

class AuthError(Exception):
    pass


class TransientError(Exception):
    pass


def sign(secret: str, ts: str, body: bytes) -> str:
    return hmac.new(secret.encode(), f'{ts}\n'.encode() + body, hashlib.sha256).hexdigest()


class Api:
    def __init__(self, supabase_url: str, secret: str):
        self.url = supabase_url.rstrip('/') + '/functions/v1/voice-jobs'
        self.secret = secret

    def call(self, payload: dict, timeout: float) -> dict:
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        ts = str(int(time.time()))
        req = urllib.request.Request(self.url, data=body, method='POST', headers={
            'Content-Type': 'application/json',
            'X-Voice-Ts': ts,
            'X-Voice-Sig': sign(self.secret, ts, body),
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise AuthError() from None
            raise TransientError(f'HTTP {e.code}') from None
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise TransientError(type(e).__name__) from None


# ---------- Розпізнавання ----------

class JobError(Exception):
    """Помилка завдання з короткою причиною для сервера."""


def _add_cuda_dlls(keep: list) -> None:
    # Колеса nvidia-cublas-cu12 і nvidia-cudnn-cu12 кладуть DLL у nvidia/<назва>/bin
    try:
        import nvidia
    except ImportError:
        return
    for root in list(getattr(nvidia, '__path__', [])):
        for sub in ('cublas', 'cudnn', 'cuda_nvrtc'):
            d = os.path.join(root, sub, 'bin')
            if os.path.isdir(d):
                keep.append(os.add_dll_directory(d))
                os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')


def _resample(a, sr_from: int, sr_to: int):
    import numpy as np
    from scipy.signal import resample_poly
    if sr_from == sr_to:
        return a.astype(np.float32)
    g = gcd(sr_to, sr_from)
    return resample_poly(a, sr_to // g, sr_from // g).astype(np.float32)


def decode_to_16k(data: bytes, max_sec: float = MAX_AUDIO_SEC):
    """OGG/Opus (або інший формат libsndfile) у float32 моно 16 кГц."""
    import numpy as np
    import soundfile as sf
    try:
        info = sf.info(io.BytesIO(data))
        if info.duration > max_sec:
            raise JobError(f'задовге аудіо (понад {int(max_sec)} с)')
        a, sr = sf.read(io.BytesIO(data), dtype='float32', always_2d=True)
        a = a.mean(axis=1)
    except JobError:
        raise
    except Exception:
        a, sr = _decode_av(data)
        if len(a) / sr > max_sec:
            raise JobError(f'задовге аудіо (понад {int(max_sec)} с)')
    if len(a) == 0:
        raise JobError('порожнє аудіо')
    return _resample(np.asarray(a, dtype=np.float32), sr, 16000)


def _decode_av(data: bytes):
    """Запасний шлях через PyAV, якщо libsndfile не впорався."""
    import av
    import numpy as np
    try:
        with av.open(io.BytesIO(data)) as c:
            rs = av.AudioResampler(format='flt', layout='mono', rate=16000)
            parts = []
            for frame in c.decode(audio=0):
                for f in rs.resample(frame):
                    parts.append(f.to_ndarray().reshape(-1))
                if sum(len(p) for p in parts) > (MAX_AUDIO_SEC + 1) * 16000:
                    break
            for f in rs.resample(None):
                parts.append(f.to_ndarray().reshape(-1))
    except Exception:
        raise JobError('не вдалося декодувати аудіо') from None
    if not parts:
        raise JobError('не вдалося декодувати аудіо')
    return np.concatenate(parts).astype(np.float32), 16000


class Stt:
    def __init__(self, device: str = 'auto'):
        self._dll = []
        from faster_whisper import WhisperModel
        self.WhisperModel = WhisperModel
        self.model = None
        if device in ('auto', 'cuda'):
            try:
                _add_cuda_dlls(self._dll)
                self.model = WhisperModel(STT_MODEL, device='cuda', compute_type='float16')
                self.label = 'cuda-float16'
                self.warmup()
            except Exception as e:
                if device == 'cuda':
                    raise
                log.warning('CUDA недоступна (%s), розпізнавання на процесорі', err_brief(e))
                self.model = None
        if self.model is None:
            self.model = WhisperModel(STT_MODEL, device='cpu', compute_type='int8')
            self.label = 'cpu-int8'
            self.warmup()

    def warmup(self) -> None:
        import numpy as np
        noise = (np.random.default_rng(0).standard_normal(16000) * 0.01).astype(np.float32)
        segs, _ = self.model.transcribe(noise, language='uk', beam_size=1, vad_filter=False)
        list(segs)

    def transcribe(self, audio16k) -> str:
        segs, _ = self.model.transcribe(audio16k, language='uk', beam_size=5, vad_filter=True,
                                        initial_prompt=STT_PROMPT)
        return ' '.join(s.text.strip() for s in segs).strip()


# ---------- Озвучення ----------

def split_text(text: str, limit: int = CHUNK_MAX) -> list:
    """Речення, а задовгі ще й по комах, далі по пробілах; кожен шматок до limit."""
    text = re.sub(r'\s+', ' ', text).strip()
    out = []
    for sent in re.split(r'(?<=[.!?…])\s+', text):
        if not sent:
            continue
        if len(sent) <= limit:
            out.append(sent)
            continue
        cur = ''
        for piece in re.split(r'(?<=[,;:])\s+|\s+', sent):
            if len(piece) > limit:  # одне довжелезне «слово»
                if cur:
                    out.append(cur)
                    cur = ''
                out.extend(piece[i:i + limit] for i in range(0, len(piece), limit))
                continue
            cand = f'{cur} {piece}' if cur else piece
            if len(cand) <= limit:
                cur = cand
            else:
                out.append(cur)
                cur = piece
        if cur:
            out.append(cur)
    return out


def encode_ogg_opus(a, sr: int = OUT_SR) -> bytes:
    import soundfile as sf
    buf = io.BytesIO()
    with sf.SoundFile(buf, 'w', samplerate=sr, channels=1, format='OGG', subtype='OPUS') as f:
        for i in range(0, len(a), sr * 5):  # блоками по 5 с
            f.write(a[i:i + sr * 5])
    return buf.getvalue()


class Tts:
    def __init__(self, voice_npy: str):
        import numpy as np
        from holos_onnx import HolosTTS
        from ipa_uk import ipa
        from ukrainian_word_stress import Stressifier
        self.np = np
        self.ipa = ipa
        self.stress = Stressifier()
        self.model = HolosTTS('patriotyk/HolosTTS/onnx', providers=['CPUExecutionProvider'])
        self.sr = self.model.sample_rate
        self.voice = np.load(voice_npy).astype(np.float32)
        self.warmup()

    def warmup(self) -> None:
        self.model.generate(self.ipa(self.stress('Привіт, усе працює.')), voice=self.voice)

    def synth(self, text: str):
        np = self.np
        text = (text or '').strip()
        if not text:
            raise JobError('порожній текст')
        if len(text) > MAX_TEXT:
            raise JobError(f'задовгий текст (понад {MAX_TEXT} символів)')
        pause = np.zeros(int(self.sr * PAUSE_SEC), dtype=np.float32)
        parts = []
        for chunk in split_text(text):
            a = np.asarray(self.model.generate(self.ipa(self.stress(chunk)), voice=self.voice),
                           dtype=np.float32).reshape(-1)
            if parts:
                parts.append(pause)
            parts.append(a)
        a = np.concatenate(parts) if parts else pause
        peak = float(np.max(np.abs(a))) if len(a) else 0.0
        if peak > 1e-6:
            a = a * (PEAK / peak)
        a = np.clip(_resample(a, self.sr, OUT_SR), -1.0, 1.0)
        return encode_ogg_opus(a), round(len(a) / OUT_SR, 2)


# ---------- Цикл ----------

def handle_job(job: dict, stt, tts) -> dict:
    jid, kind, inp = job.get('id'), job.get('kind'), job.get('input') or {}
    t0 = time.time()
    try:
        if kind == 'stt':
            try:
                raw = base64.b64decode(inp.get('audio_b64') or '', validate=True)
            except Exception:
                raise JobError('пошкоджений base64') from None
            audio = decode_to_16k(raw)
            dur = len(audio) / 16000
            text = stt.transcribe(audio)
            if not text:
                raise JobError('мову не розпізнано')
            out = {'op': 'done', 'id': jid, 'ok': True, 'output': {'text': text}}
        elif kind == 'tts':
            ogg, dur = tts.synth(inp.get('text') or '')
            out = {'op': 'done', 'id': jid, 'ok': True,
                   'output': {'audio_b64': base64.b64encode(ogg).decode('ascii'),
                              'mime': 'audio/ogg', 'duration': dur}}
        else:
            raise JobError('невідомий тип завдання')
        log.info('job %s %s ok audio=%.1fs took=%.2fs', jid, kind, dur, time.time() - t0)
        return out
    except JobError as e:
        log.info('job %s %s fail "%s" took=%.2fs', jid, kind, e, time.time() - t0)
        return {'op': 'done', 'id': jid, 'ok': False, 'error': str(e)}
    except Exception as e:
        log.error('job %s %s error %s took=%.2fs', jid, kind, err_brief(e), time.time() - t0)
        return {'op': 'done', 'id': jid, 'ok': False, 'error': f'внутрішня помилка: {type(e).__name__}'}


def submit(api: Api, result: dict, stop: threading.Event, sleep) -> None:
    """Здати результат; мережеві збої повторюємо до хвилини, далі завдання вважаємо втраченим."""
    deadline = time.time() + 60
    delay = BACKOFF_MIN
    while not stop.is_set():
        try:
            r = api.call(result, timeout=30)
            if not r.get('accepted'):
                log.info('job %s not accepted (expired)', result.get('id'))
            return
        except AuthError:
            log.error('401 on done: перевірте voice_secret і годинник')
            return
        except TransientError as e:
            if time.time() + delay > deadline:
                log.error('job %s done lost: %s', result.get('id'), e)
                return
            log.warning('done retry in %.0fs: %s', delay, e)
            sleep(delay)
            delay = min(delay * 2, BACKOFF_MAX)


def run(api: Api, stt, tts, stop: threading.Event, sleep=None, auth_wait: float = AUTH_WAIT,
        wait: int = CLAIM_WAIT) -> None:
    sleep = sleep or (lambda s: stop.wait(s))
    info = {'version': VERSION, 'stt': f'{STT_MODEL}/{getattr(stt, "label", "?")}',
            'tts': 'holos-onnx-cpu'}
    delay = BACKOFF_MIN
    log.info('claim loop start, stt=%s', info['stt'])
    while not stop.is_set():
        try:
            resp = api.call({'op': 'claim', 'wait': wait, 'info': info}, timeout=wait + 20)
        except AuthError:
            log.error('401: перевірте voice_secret і годинник; пауза %.0fs', auth_wait)
            sleep(auth_wait)
            continue
        except TransientError as e:
            log.warning('claim failed (%s), retry in %.0fs', e, delay)
            sleep(delay)
            delay = min(delay * 2, BACKOFF_MAX)
            continue
        delay = BACKOFF_MIN
        job = resp.get('job') if isinstance(resp, dict) else None
        if job:
            submit(api, handle_job(job, stt, tts), stop, sleep)
    log.info('claim loop stop')


# ---------- Запуск ----------

class SingleInstance:
    """Замок на файл: другий екземпляр не стартує, навіть якщо pid-файл застарів."""

    def __init__(self, home: Path):
        import msvcrt
        self.f = open(home / 'worker.lock', 'a+')
        try:
            msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.f.close()
            raise SystemExit('воркер уже запущено')
        self.pid = home / 'worker.pid'
        self.pid.write_text(str(os.getpid()), encoding='ascii')

    def release(self) -> None:
        try:
            if self.pid.read_text(encoding='ascii').strip() == str(os.getpid()):
                self.pid.unlink()
        except OSError:
            pass


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description='Мовний сервіс бота')
    p.add_argument('--home', help='тека з config.json, логами і pid (типово .local/voice-service)')
    args = p.parse_args(argv)
    home = Path(args.home) if args.home else default_home()
    home.mkdir(parents=True, exist_ok=True)
    # pythonw не має консолі: stdout і stderr бібліотек пишемо у файл
    if sys.stdout is None or sys.stderr is None:
        (home / 'logs').mkdir(parents=True, exist_ok=True)
        stream = open(home / 'logs' / 'stderr.log', 'a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream
    setup_logging(home)
    cfg = load_config(home)
    lock = SingleInstance(home)
    try:
        log.info('start pid=%s version=%s', os.getpid(), VERSION)
        t0 = time.time()
        stt = Stt(cfg['device'])
        t1 = time.time()
        log.info('stt ready %s in %.1fs (load+warmup)', stt.label, t1 - t0)
        tts = Tts(cfg['voice_npy'])
        log.info('tts ready in %.1fs (load+warmup)', time.time() - t1)
        run(Api(cfg['supabase_url'], cfg['voice_secret']), stt, tts, threading.Event())
    except Exception as e:
        log.error('fatal %s', err_brief(e))
        raise
    finally:
        lock.release()


if __name__ == '__main__':
    main()
