"""Small reproducible WenetSpeech meeting pilot; never changes deployed ASR.

Source data and reports belong in ignored data/ and runs/. The public test split
is used for exploratory research, not as a model-independent benchmark.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import random
import time

import numpy as np
import requests
import soundfile as sf

from robustness import (FrontendEngine, Settings, engine_arguments, read_entries,
                        assert_disjoint, paired_interval, score_result, summarize_results,
                        decode_wav_pcm16_mono, artifact_fingerprint, _resample, noise_controls)
from scripts.evaluate_asr import EvaluationEntry

DATASET = 'TwinkStart/WenetSpeech'
REVISION = 'ec930f771e48837e9ec246b1e128a1662ab9ce87'
API = 'https://datasets-server.huggingface.co/rows'


def fetch(output: Path, offset: int, count: int):
    if output.exists():
        raise ValueError('output already exists; refusing to overwrite')
    if offset < 0 or not 1 <= count <= 100:
        raise ValueError('offset must be nonnegative and count between 1 and 100')
    response = None
    for attempt in range(4):
        try:
            response = requests.get(API, params={'dataset': DATASET, 'config': 'default',
                                    'split': 'test_meeting', 'offset': offset, 'length': count}, timeout=30)
            response.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    rows = response.json()['rows']
    if len(rows) != count or [r['row_idx'] for r in rows] != list(range(offset, offset + count)):
        raise ValueError('unexpected dataset rows')
    for r in rows:
        url = r['row']['audio'][0]['src']
        if f'/{REVISION}/' not in url:
            raise ValueError('dataset revision differs from pinned revision')
    output.mkdir(parents=True)

    def download(item):
        index, row = item['row_idx'], item['row']
        for attempt in range(3):
            try:
                response = requests.get(row['audio'][0]['src'], timeout=25)
                response.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
        audio, rate = sf.read(io.BytesIO(response.content), dtype='float32', always_2d=True)
        if rate <= 0 or audio.shape[1] != 1 or not np.isfinite(audio).all():
            raise ValueError(f'unexpected audio format at row {index}')
        if not row['text'].strip() or not 0 < len(audio) <= 60 * rate:
            raise ValueError(f'unexpected transcription or duration at row {index}')
        samples = _resample(audio[:, 0].tolist(), rate, 16000) if rate != 16000 else audio[:, 0]
        name = f'{index:06d}.wav'
        sf.write(output / name, samples, 16000, subtype='PCM_16')
        return {'audio': name, 'text': row['text'], 'source_id': row['sid'],
                'source_sample_rate': rate, 'source_sha256': hashlib.sha256(response.content).hexdigest()}

    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(download, rows))
    (output / 'manifest.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
    (output / 'provenance.json').write_text(json.dumps({
        'dataset': DATASET, 'revision': REVISION, 'split': 'test_meeting',
        'offset': offset, 'count': count, 'sample_selection': 'contiguous rows, fixed before inference',
        'license': 'See upstream WenetSpeech and underlying audio rights',
        'conversion': 'server-provided Opus decoded, native sherpa resampling to 16kHz if needed, PCM16 WAV',
        'caveat': 'meeting and speaker independence cannot be established from exposed metadata'
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(manifest: Path, output: Path, candidate: Path, prior: Path | None = None,
        noise_manifest: Path | None = None):
    if output.exists():
        raise ValueError('report exists; refusing to overwrite')
    entries, hashes = read_entries(manifest)
    prior_report = None
    if prior:
        prior_report = json.loads(prior.read_text(encoding='utf-8'))
        assert_disjoint(hashes, prior_report['fingerprints'])
    defaults = {name: field.default for name, field in Settings.model_fields.items() if name.startswith('asr_')}
    settings = Settings(_env_file=None, **defaults)
    models = {'baseline': artifact_fingerprint(settings.asr_model_file),
              'trained_head': artifact_fingerprint(candidate)}
    if prior_report and any(models[name]['sha256'] != prior_report['models'][name]['sha256']
                            for name in models):
        raise ValueError('Model differs from the earlier experiment')
    engines = {}
    for name, path, front in [('baseline', settings.asr_model_file, 'baseline'),
                               ('trim', settings.asr_model_file, 'padded_trim'),
                               ('vad_02', settings.asr_model_file, 'baseline'),
                               ('trained_head', candidate, 'baseline')]:
        args = engine_arguments(settings)
        args['model_path'] = path
        if name == 'vad_02':
            args['vad_threshold'] = 0.2
        engine = FrontendEngine(**args, candidate=front)
        engine.ensure_available()
        engine._ensure_recognizer()
        engines[name] = engine
    warm, rate = decode_wav_pcm16_mono(entries[0].audio.read_bytes())
    for engine in engines.values():
        engine.transcribe(warm, rate)
    rows = {name: [] for name in engines}
    for idx, entry in enumerate(entries):
        samples, rate = decode_wav_pcm16_mono(entry.audio.read_bytes())
        order = list(engines)
        random.Random(73029 + idx).shuffle(order)
        for name in order:
            start = time.perf_counter()
            result = engines[name].transcribe(samples, rate)
            elapsed = time.perf_counter() - start
            row = score_result(entry, result, len(samples) / rate, elapsed)
            row.update(group=hashes[idx]['audio_sha256'], condition='original')
            rows[name].append(row)
        if (idx + 1) % 10 == 0:
            print(f'{idx + 1}/{len(entries)}', flush=True)
    # Noise controls are regression probes only, not a real-world false-positive rate.
    controls = list(noise_controls())
    if noise_manifest:
        noise_entries, _ = read_entries(noise_manifest)
        for entry in noise_entries:
            if entry.reference.strip():
                raise ValueError('Noise control must have an empty reference')
            audio, rate = decode_wav_pcm16_mono(entry.audio.read_bytes())
            controls.append((entry.audio.name, _resample(audio, rate, 16000)))
    for control, samples in controls:
        entry = EvaluationEntry(Path(control), '', 0)
        for name, engine in engines.items():
            start = time.perf_counter()
            result = engine.transcribe(samples, 16000)
            row = score_result(entry, result, len(samples) / 16000, time.perf_counter() - start)
            row.update(group=control, condition='noise_control')
            rows[name].append(row)
    report = {'fingerprints': hashes, 'models': models,
              'protocol': {'vad_threshold_baseline': settings.asr_vad_threshold,
                           'vad_threshold_candidate': 0.2, 'noise_controls': len(controls),
                           'noise_manifest': str(noise_manifest) if noise_manifest else None,
                           'source_revision': REVISION, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                           'iteration_order': 'seeded per sample', 'warmup': 'one utterance per engine'},
              'summaries': {name: summarize_results(value) for name, value in rows.items()},
              'paired_cer_delta_95ci': {name: paired_interval(rows['baseline'], rows[name])
                                        for name in ('trim', 'vad_02', 'trained_head')},
              'scope': 'Exploratory source segments; meeting/speaker disjointness and model pretraining overlap unverified; not target robot',
              'rows': rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'summaries': report['summaries'], 'paired_cer_delta_95ci': report['paired_cer_delta_95ci']}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('fetch')
    a.add_argument('--output', type=Path, required=True)
    a.add_argument('--offset', type=int, required=True)
    a.add_argument('--count', type=int, required=True)
    b = sub.add_parser('run')
    b.add_argument('--manifest', type=Path, required=True)
    b.add_argument('--output', type=Path, required=True)
    b.add_argument('--candidate', type=Path, required=True)
    b.add_argument('--prior', type=Path)
    b.add_argument('--noise-manifest', type=Path)
    args = parser.parse_args()
    if args.command == 'fetch':
        fetch(args.output, args.offset, args.count)
    else:
        run(args.manifest, args.output, args.candidate, args.prior, args.noise_manifest)


if __name__ == '__main__':
    main()
