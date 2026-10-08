"""Local media helpers. No downloads, shell interpolation, or installations."""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from manifest import ValidationError, need


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_write(path, data, overwrite=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.quote-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        if overwrite:
            os.replace(temp, path)
        else:
            # Hard-link creation fails atomically if destination already exists.
            os.link(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path, value, overwrite=False):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode(), overwrite)


def image_bytes(image, suffix='.png'):
    b = io.BytesIO()
    fmt = 'JPEG' if suffix.lower() in ('.jpg', '.jpeg') else 'PNG'
    image.convert('RGB').save(b, fmt, **({'quality': 95, 'subsampling': 0} if fmt == 'JPEG' else {}))
    return b.getvalue()


def executable(name, explicit=None):
    selected = explicit or os.environ.get('QUOTE_' + name.upper()) or shutil.which(name)
    need(bool(selected), name + ' not found; supply --' + name + ' or QUOTE_' + name.upper())
    p = Path(selected).expanduser()
    if not p.is_file():
        found = shutil.which(str(p))
        need(bool(found), 'executable not found: ' + name)
        p = Path(found)
    return str(p.resolve())


def run(args, timeout=120):
    try:
        r = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ValidationError('media command failed: ' + type(e).__name__) from e
    need(r.returncode == 0, 'media command failed: ' + r.stderr.decode('utf-8', 'replace')[-1000:])
    return r.stdout


def duration(video, ffprobe):
    raw = run([ffprobe, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-select_streams', 'v:0', '-show_entries', 'format=duration:stream=codec_type', '-of', 'json', str(video)])
    try:
        info = json.loads(raw)
        need(bool(info.get('streams')), 'input has no video stream')
        value = float(info['format']['duration'])
        need(math.isfinite(value) and value > 0, 'video duration must be positive and finite')
        return value
    except (ValueError, KeyError) as e:
        raise ValidationError('cannot determine finite video duration') from e


def binding(source, frame, video_hash):
    return {'source_id': source['id'], 'source_url': source['url'], 'video_sha256': video_hash,
            'transcript_time': frame['transcript_time'], 'offset_seconds': source['timing']['offset_seconds'],
            'media_time': frame['transcript_time'] + source['timing']['offset_seconds']}


def choose_font(explicit=None):
    from PIL import ImageFont
    selected = explicit or os.environ.get('QUOTE_FONT')
    candidates = [selected] if selected else [
        '/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc',
        str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc'),
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc']
    for path in candidates:
        if path and Path(path).is_file():
            try:
                ImageFont.truetype(str(path), 24)
                return str(path)
            except OSError:
                pass
    raise ValidationError('CJK font not found; supply --font or QUOTE_FONT. No fonts are bundled.')
