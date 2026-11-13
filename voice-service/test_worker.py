# Тести воркера без звуку і без справжнього Supabase: локальний мок-сервер на 127.0.0.1.
# Запуск: python -m unittest -v test_worker   (VOICE_SKIP_MODELS=1 пропускає тест із моделями)
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import re
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import soundfile as sf

import worker

VOICE_DIR = worker.default_home().parent / 'voice'
SECRET = '0123456789abcdef0123456789abcdef-test-secret'
TTS_PHRASE = 'Зараз на рахунках сорок дві тисячі гривень.'


def make_ogg_opus(a: np.ndarray, sr: int) -> bytes:
    """OGG/Opus 48 кГц моно через libopus (PyAV), як голосові Telegram. Лише в памʼять."""
    import av
    a = worker._resample(np.asarray(a, dtype=np.float32), sr, 48000)
    buf = io.BytesIO()
    with av.open(buf, 'w', format='ogg') as c:
        s = c.add_stream('libopus', rate=48000)
        s.layout = 'mono'
        s.bit_rate = 32000
        n = s.codec_context.frame_size or 960
        pts = 0
        for i in range(0, len(a), n):
            part = a[i:i + n]
            if len(part) < n:
                part = np.pad(part, (0, n - len(part)))
            fr = av.AudioFrame.from_ndarray(part.reshape(1, -1), format='flt', layout='mono')
            fr.sample_rate = 48000
            fr.pts = pts
            pts += n
            for p in s.encode(fr):
                c.mux(p)
        for p in s.encode(None):
            c.mux(p)
    return buf.getvalue()


def wav_to_ogg(path) -> bytes:
    a, sr = sf.read(str(path), dtype='float32', always_2d=True)
    return make_ogg_opus(a.mean(axis=1), sr)


class MockServer:
    """Імітація voice-jobs: перевіряє підпис і мітку часу, роздає завдання, збирає результати."""

    def __init__(self, secret, jobs=(), fail_first=0):
        self.secret, self.jobs, self.fail_first = secret, list(jobs), fail_first
        self.results, self.infos = {}, []
        self.claims = self.unauth = self.failed = 0
        self.lock = threading.Lock()
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def reply(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                if self.path != '/functions/v1/voice-jobs':
                    return self.reply(404, {'error': 'not found'})
                ts = self.headers.get('X-Voice-Ts', '')
                sig = self.headers.get('X-Voice-Sig', '')
                good = hmac.new(mock.secret.encode(), f'{ts}\n'.encode() + body, hashlib.sha256).hexdigest()
                if not ts.isdigit() or abs(time.time() - int(ts)) > 120 or not hmac.compare_digest(sig, good):
                    with mock.lock:
                        mock.unauth += 1
                    return self.reply(401, {'error': 'unauthorized'})
                req = json.loads(body)
                if req.get('op') == 'claim':
                    with mock.lock:
                        mock.claims += 1
                        mock.infos.append(req.get('info'))
                        if mock.failed < mock.fail_first:
                            mock.failed += 1
                            return self.reply(503, {'error': 'busy'})
                        job = mock.jobs.pop(0) if mock.jobs else None
                    if job is None:
                        time.sleep(min(float(req.get('wait', 0)), 0.2))
                    return self.reply(200, {'job': job})
                if req.get('op') == 'done':
                    with mock.lock:
                        mock.results[req['id']] = req
                    return self.reply(200, {'accepted': True})
                return self.reply(400, {'error': 'bad op'})

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.url = f'http://127.0.0.1:{self.httpd.server_address[1]}'
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(5)


class FakeStt:
    label = 'fake'

    def transcribe(self, audio):
        return 'тест'


class FakeTts:
    def synth(self, text):
        return b'OggS', 1.0


def start_worker(api, stt, tts, **kw):
    stop = threading.Event()
    t = threading.Thread(target=worker.run, args=(api, stt, tts, stop), kwargs=kw, daemon=True)
    t.start()
    return stop, t


def wait_until(cond, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


class TestProtocol(unittest.TestCase):
    def test_hmac_vector(self):
        self.assertEqual(worker.sign(SECRET, '1794600000', b'{"op":"claim","wait":50}'),
                         'adbf98413f862dbc6a3cc4990d70ad696f1df493b3c4ad440d25a0e10cd7341c')

    def test_401_keeps_running(self):
        with MockServer(SECRET) as m, self.assertLogs('voice', 'INFO') as logs:
            api = worker.Api(m.url, 'x' * 40)  # не той секрет
            stop, t = start_worker(api, FakeStt(), FakeTts(), auth_wait=0.05, wait=1)
            self.assertTrue(wait_until(lambda: m.unauth >= 3, 10))
            self.assertTrue(t.is_alive())
            stop.set()
            t.join(10)
        self.assertFalse(t.is_alive())
        self.assertEqual(m.claims, 0)
        self.assertTrue(any('voice_secret' in r for r in logs.output))

    def test_5xx_retry_then_job(self):
        job = {'id': 7, 'kind': 'tts', 'input': {'text': 'Привіт.'}}
        with MockServer(SECRET, [job], fail_first=2) as m:
            api = worker.Api(m.url, SECRET)
            stop, t = start_worker(api, FakeStt(), FakeTts(), sleep=lambda s: time.sleep(0.01), wait=1)
            self.assertTrue(wait_until(lambda: 7 in m.results, 10))
            stop.set()
            t.join(10)
        self.assertTrue(m.results[7]['ok'])
        self.assertEqual(m.failed, 2)

    def test_bad_input_reports_error(self):
        out = worker.handle_job({'id': 1, 'kind': 'stt', 'input': {'audio_b64': '@@@'}}, FakeStt(), FakeTts())
        self.assertEqual(out, {'op': 'done', 'id': 1, 'ok': False, 'error': 'пошкоджений base64'})


class TestAudio(unittest.TestCase):
    def test_split_text(self):
        long = ', '.join(['слово'] * 120) + '. Друге речення! Третє?'
        parts = worker.split_text(long)
        self.assertTrue(all(0 < len(p) <= worker.CHUNK_MAX for p in parts))
        self.assertEqual(' '.join(parts).split(), long.split())
        self.assertEqual(parts[-2:], ['Друге речення!', 'Третє?'])

    def test_libopus_ogg_decodes(self):
        raw = wav_to_ogg(VOICE_DIR / 'q01.wav')
        info = sf.info(io.BytesIO(raw))
        self.assertEqual((info.samplerate, info.channels, info.subtype), (48000, 1, 'OPUS'))
        a = worker.decode_to_16k(raw)
        self.assertEqual(a.dtype, np.float32)
        self.assertAlmostEqual(len(a) / 16000, info.duration, delta=0.1)

    def test_too_long_audio(self):
        raw = make_ogg_opus(np.zeros(16000 * 121, dtype=np.float32), 16000)
        with self.assertRaisesRegex(worker.JobError, 'задовге'):
            worker.decode_to_16k(raw)

    def test_long_ogg_write(self):
        t = np.arange(48000 * 150) / 48000
        a = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        raw = worker.encode_ogg_opus(a)
        info = sf.info(io.BytesIO(raw))
        self.assertAlmostEqual(info.duration, 150, delta=0.1)
        b, sr = sf.read(io.BytesIO(raw), dtype='float32')
        self.assertEqual(sr, 48000)
        self.assertAlmostEqual(len(b) / sr, 150, delta=0.1)


@unittest.skipIf(os.environ.get('VOICE_SKIP_MODELS'), 'VOICE_SKIP_MODELS')
class TestEndToEnd(unittest.TestCase):
    """Справжні моделі, мок-сервер, обидва типи завдань через цикл воркера."""

    @classmethod
    def setUpClass(cls):
        logging.getLogger('voice').setLevel(logging.INFO)
        t0 = time.time()
        cls.stt = worker.Stt(os.environ.get('VOICE_DEVICE', 'auto'))
        cls.tts = worker.Tts(str(VOICE_DIR / 'voice.npy'))
        print(f'\n[e2e] models ready in {time.time() - t0:.1f}s, stt={cls.stt.label}')

    def test_stt_and_tts_jobs(self):
        ogg = wav_to_ogg(VOICE_DIR / 'q01.wav')
        jobs = [
            {'id': 123, 'kind': 'stt', 'input': {'audio_b64': base64.b64encode(ogg).decode(), 'mime': 'audio/ogg'}},
            {'id': 124, 'kind': 'tts', 'input': {'text': TTS_PHRASE}},
        ]
        with MockServer(SECRET, jobs) as m:
            api = worker.Api(m.url, SECRET)
            stop, t = start_worker(api, self.stt, self.tts, wait=1)
            done = wait_until(lambda: len(m.results) == 2, 180)
            stop.set()
            t.join(15)
        self.assertTrue(done, m.results)
        self.assertFalse(t.is_alive())
        self.assertEqual(m.infos[0]['version'], '1')

        stt = m.results[123]
        self.assertTrue(stt['ok'], stt)
        text = stt['output']['text']
        self.assertEqual(text, text.strip())
        words = re.findall(r"[а-щьюяєіїґʼ']{2,}", text.lower())
        self.assertGreaterEqual(len(words), 2, text)
        print(f'[e2e] stt q01: {text}')

        tts = m.results[124]
        self.assertTrue(tts['ok'], tts)
        self.assertEqual(tts['output']['mime'], 'audio/ogg')
        raw = base64.b64decode(tts['output']['audio_b64'])
        info = sf.info(io.BytesIO(raw))
        a, sr = sf.read(io.BytesIO(raw), dtype='float32')
        self.assertEqual((info.format, info.subtype, sr, info.channels), ('OGG', 'OPUS', 48000, 1))
        dur = len(a) / sr
        self.assertTrue(1 <= dur <= 15, dur)
        self.assertAlmostEqual(tts['output']['duration'], dur, delta=0.1)
        peak = float(np.max(np.abs(a)))
        rms = float(np.sqrt(np.mean(a ** 2)))
        self.assertTrue(0.5 < peak <= 1.0 and rms > 0.01, (peak, rms))
        print(f'[e2e] tts: {dur:.2f}s 48k mono, peak {peak:.2f}, rms {rms:.3f}')


if __name__ == '__main__':
    unittest.main()
