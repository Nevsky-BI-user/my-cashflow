# Заміри швидкості без звуку: прогрів моделей, stt на q01..q10 (через OGG/Opus, як із Telegram), tts на 3 фрази.
# Запуск: python bench.py
import io
import time

import soundfile as sf

import worker
from test_worker import VOICE_DIR, wav_to_ogg

PHRASES = [
    'Зараз на рахунках сорок дві тисячі гривень.',
    'Борг по кредитці десять тисяч, погасити до двадцять пʼятого листопада.',
    'На продукти за жовтень витратили дванадцять тисяч триста сорок пʼять гривень, '
    'це на дві тисячі більше, ніж у вересні. До зарплати лишилось одинадцять днів.',
]

t = time.time()
stt = worker.Stt('auto')
print(f'warmup stt {stt.label}: {time.time() - t:.1f}s (load+warmup)')
t = time.time()
tts = worker.Tts(str(VOICE_DIR / 'voice.npy'))
print(f'warmup tts: {time.time() - t:.1f}s (load+warmup)')

total = 0.0
for f in sorted(VOICE_DIR.glob('q*.wav')):
    ogg = wav_to_ogg(f)
    t = time.time()
    audio = worker.decode_to_16k(ogg)
    text = stt.transcribe(audio)
    dt = time.time() - t
    total += dt
    print(f'stt {f.name} audio {len(audio) / 16000:4.1f}s took {dt:5.2f}s | {text}')
print(f'stt total {total:.2f}s')

for i, p in enumerate(PHRASES, 1):
    t = time.time()
    ogg, dur = tts.synth(p)
    dt = time.time() - t
    info = sf.info(io.BytesIO(ogg))
    print(f'tts #{i} chars {len(p)} took {dt:.2f}s audio {dur:.2f}s RTF {dt / dur:.3f} '
          f'ogg {len(ogg)} B {info.samplerate} Hz ch {info.channels}')
