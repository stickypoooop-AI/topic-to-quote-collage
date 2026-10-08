"""Extract reviewed manifest frames from local videos with calibrated timestamps."""
import argparse
from pathlib import Path
import tempfile
from PIL import Image
from manifest import load, need, frames, resolve_asset, media_time, ValidationError
from media import executable, duration, run, sha256, binding, atomic_write, write_json


def extract(manifest_path, ffmpeg=None, ffprobe=None, overwrite=False):
    m = load(manifest_path, check_videos=True)
    base = Path(manifest_path).parent
    ffmpeg, ffprobe = executable('ffmpeg', ffmpeg), executable('ffprobe', ffprobe)
    sources = {s['id']: s for s in m['sources']}
    pending, hashes, seen = [], {}, set()
    for s in m['sources']:
        video = resolve_asset(base, s['video'])
        actual = duration(video, ffprobe)
        need(abs(actual - s['duration_seconds']) <= 0.25, 'manifest/video duration mismatch; inspect source and recalibrate')
        hashes[s['id']] = sha256(video)
    for c in m['cards']:
        s = sources[c['source_id']]
        for f in frames(c):
            p = resolve_asset(base, f['image'])
            if p in seen:
                continue
            seen.add(p)
            need(overwrite or not p.exists(), 'frame exists; use a new path or explicit --overwrite: ' + f['image'])
            receipt = p.with_suffix(p.suffix + '.frame.json')
            need(overwrite or not receipt.exists(), 'frame receipt exists')
            pending.append((s, f, p, receipt))
    # Decode all frames first; a failure leaves no partial batch.
    with tempfile.TemporaryDirectory(prefix='quote-extract-') as temp:
        outputs = []
        for index, (s, f, p, receipt) in enumerate(pending):
            out = Path(temp) / (str(index) + p.suffix)
            # Output-side seek decodes from the start; slower, avoids fast-seek intro/keyframe assumptions.
            run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-protocol_whitelist', 'file,pipe',
                 '-i', str(resolve_asset(base, s['video'])), '-ss', format(media_time(s, f['transcript_time']), '.9f'),
                 '-map', '0:v:0', '-frames:v', '1', '-an', '-sn', '-n', str(out)])
            need(out.is_file(), 'no decoded frame; timestamp may be outside available media')
            with Image.open(out) as im:
                im.load()
                need(im.width > 0 and im.height > 0, 'empty decoded frame')
            record = binding(s, f, hashes[s['id']])
            record['image_sha256'] = sha256(out)
            record['method'] = 'ffmpeg_output_seek'
            outputs.append((p, receipt, out.read_bytes(), record))
        for p, receipt, pixels, record in outputs:
            atomic_write(p, pixels, overwrite)
            write_json(receipt, record, overwrite)
    return len(outputs)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest')
    p.add_argument('--ffmpeg')
    p.add_argument('--ffprobe')
    p.add_argument('--overwrite', action='store_true')
    a = p.parse_args()
    try:
        print('Extracted frames:', extract(a.manifest, a.ffmpeg, a.ffprobe, a.overwrite))
    except (ValidationError, OSError, ValueError, KeyError, TypeError) as e:
        p.exit(2, str(e) + '\n')
