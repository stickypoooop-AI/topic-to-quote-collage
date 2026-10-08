"""Strict manifest validation; standard library only. No network access."""
import json
import math
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, parse_qsl


class ValidationError(ValueError):
    pass


def need(test, message):
    if not test:
        raise ValidationError(message)


def obj(value, required, optional=(), where='manifest'):
    need(isinstance(value, dict), where + ': expected object')
    need(set(required) <= set(value), where + ': missing ' + ', '.join(sorted(set(required)-set(value))))
    need(not (set(value)-set(required)-set(optional)), where + ': unknown fields ' + ', '.join(sorted(set(value)-set(required)-set(optional))))


def string(value, where, empty=False):
    need(isinstance(value, str) and (empty or bool(value.strip())), where + ': expected nonempty string')
    need(not any(ord(c) < 32 and c not in '\n\t' for c in value), where + ': control character')


def number(value, where, minimum=None, maximum=None):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    need(finite, where + ': expected finite representable number')
    need(minimum is None or value >= minimum, where + ': below minimum')
    need(maximum is None or value <= maximum, where + ': above maximum')


def boolean(value, where):
    need(type(value) is bool, where + ': expected boolean')


def sequence(value, where, minimum=1, maximum=1000):
    need(isinstance(value, list) and minimum <= len(value) <= maximum, where + ': invalid array size')


def safe_path(value, where):
    string(value, where)
    p = PurePosixPath(value)
    need(not p.is_absolute() and '..' not in p.parts and '\\' not in value and ':' not in value,
         where + ': use a relative POSIX path without traversal')
    need(value not in ('.', ''), where + ': expected filename')
    need(value == p.as_posix(), where + ': path must be normalized (no dot aliases, duplicate separators or trailing slash)')
    return p


def resolve_asset(base, value):
    safe_path(value, 'asset')
    base = Path(base).resolve()
    path = (base / value).resolve()
    need(base in path.parents, 'asset escapes manifest directory (including symlinks)')
    return path


def url(value, where, fixture=False):
    string(value, where)
    if fixture and value.startswith('fixture:'):
        return
    p = urlsplit(value)
    need(p.scheme in ('https', 'http') and bool(p.hostname) and not p.username and not p.password,
         where + ': expected public HTTP(S) reference, without credentials')
    need(not any(k.lower() in ('token', 'access_token', 'signature', 'sig', 'key', 'api_key') or k.lower().startswith(('x-amz-', 'x-goog-')) for k, _ in parse_qsl(p.query)), where + ': use a canonical source URL, not a signed or credential-bearing URL')


def frame(value, where):
    obj(value, ['image', 'transcript_time', 'crop'], where=where)
    safe_path(value['image'], where + '.image')
    need(Path(value['image']).suffix.lower() in ('.png', '.jpg', '.jpeg'), where + ': PNG/JPEG only')
    number(value['transcript_time'], where + '.transcript_time', 0)
    c = value['crop']
    sequence(c, where + '.crop', 4, 4)
    for v in c:
        number(v, where + '.crop', 0, 1)
    need(c[0] < c[2] and c[1] < c[3], where + ': crop must have positive area')


def frames(card):
    return [card['hero']] + [q['frame'] for q in card['quotes']]


def media_time(source, transcript_time):
    t = transcript_time + source['timing']['offset_seconds']
    need(t >= 0, 'calibrated media time is negative')
    need(t < source['duration_seconds'], 'calibrated media time is outside video duration')
    return t


def validate(data, base=None, check_images=False, check_videos=False):
    obj(data, ['schema_version', 'kind', 'editorial', 'sources', 'cards', 'layout'])
    need(type(data['schema_version']) is int and data['schema_version'] == 1, 'unsupported schema_version')
    need(data['kind'] in ('real_video', 'synthetic_fixture'), 'unsupported kind')
    fixture = data['kind'] == 'synthetic_fixture'
    ed = data['editorial']
    obj(ed, ['topic', 'angle', 'status', 'confirmation'])
    for k in ('topic', 'angle', 'confirmation'):
        string(ed[k], 'editorial.' + k)
    need(ed['status'] in ('confirmed', 'exact_brief'), 'editorial angle must be confirmed or already explicit in exact brief')
    sequence(data['sources'], 'sources')
    sources = {}
    for s in data['sources']:
        obj(s, ['id', 'title', 'url', 'language', 'video', 'duration_seconds', 'rights_note', 'transcript', 'timing'])
        for k in ('id', 'title', 'language', 'rights_note'):
            string(s[k], 'source.' + k)
        need(s['id'] not in sources, 'duplicate source id')
        sources[s['id']] = s
        url(s['url'], 'source.url', fixture)
        safe_path(s['video'], 'source.video')
        need(Path(s['video']).suffix.lower() in ('.mp4', '.mov', '.mkv', '.webm', '.m4v'), 'unsupported video extension')
        number(s['duration_seconds'], 'duration_seconds', 0.001)
        tr = s['transcript']
        obj(tr, ['kind', 'reference', 'verification_note'])
        need(tr['kind'] in ('official', 'manual', 'asr_reviewed', 'synthetic'), 'unsupported transcript kind')
        need(fixture or tr['kind'] != 'synthetic', 'real video cannot use synthetic transcript')
        for k in ('reference', 'verification_note'):
            string(tr[k], 'transcript.' + k)
        ti = s['timing']
        obj(ti, ['offset_seconds', 'tolerance_seconds', 'anchors'])
        number(ti['offset_seconds'], 'offset_seconds')
        number(ti['tolerance_seconds'], 'tolerance_seconds', 0, 0.5)
        sequence(ti['anchors'], 'timing.anchors', 2)
        distinct = set()
        for a in ti['anchors']:
            obj(a, ['transcript_seconds', 'media_seconds', 'evidence'])
            number(a['transcript_seconds'], 'anchor transcript_seconds', 0)
            number(a['media_seconds'], 'anchor media_seconds', 0)
            string(a['evidence'], 'anchor evidence')
            need(a['media_seconds'] < s['duration_seconds'], 'anchor beyond media duration')
            distinct.add(a['transcript_seconds'])
            need(abs(a['media_seconds'] - a['transcript_seconds'] - ti['offset_seconds']) <= ti['tolerance_seconds'] + 1e-8,
                 'timing anchors disagree: constant offset invalid; split edited sources and recalibrate')
        need(len(distinct) >= 2, 'need two distinct calibration anchors')
        if check_videos:
            need(resolve_asset(base, s['video']).is_file(), 'missing video: ' + s['video'])
    la = data['layout']
    obj(la, ['width', 'height', 'hero_fraction', 'font_size', 'fit'])
    for k in ('width', 'height', 'font_size'):
        need(type(la[k]) is int, 'layout.' + k + ': expected integer')
    number(la['width'], 'width', 480, 4096)
    number(la['height'], 'height', 640, 6144)
    number(la['font_size'], 'font_size', 18, 160)
    number(la['hero_fraction'], 'hero_fraction', 0.35, 0.78)
    need(la['fit'] in ('contain', 'cover'), 'fit must be contain or cover')
    sequence(data['cards'], 'cards')
    ids, image_bindings = set(), {}
    for c in data['cards']:
        obj(c, ['id', 'source_id', 'heading', 'mode', 'hero', 'quotes'])
        string(c['id'], 'card.id')
        need(bool(re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', c['id'])), 'card id must be a safe lowercase filename')
        need(c['id'] not in ids, 'duplicate card id')
        ids.add(c['id'])
        need(c['source_id'] in sources, 'unknown source_id')
        s = sources[c['source_id']]
        string(c['heading'], 'heading')
        need(c['mode'] in ('translated_script', 'native_burned_in'), 'unsupported subtitle mode')
        frame(c['hero'], 'hero')
        sequence(c['quotes'], 'quotes', 1, 6)
        prev = -1
        for q in c['quotes']:
            obj(q, ['speaker', 'start', 'end', 'original_text', 'translation_zh', 'context_before', 'context_after', 'excerpted', 'omissions_note', 'reviewed', 'frame'])
            for k in ('speaker', 'original_text', 'context_before', 'context_after'):
                string(q[k], 'quote.' + k)
            string(q['translation_zh'], 'translation_zh', empty=c['mode'] == 'native_burned_in')
            string(q['omissions_note'], 'omissions_note', empty=True)
            for k in ('excerpted', 'reviewed'):
                boolean(q[k], k)
            need(q['reviewed'], 'unreviewed quote/translation cannot render')
            need(not q['excerpted'] or bool(q['omissions_note'].strip()), 'excerpted quote requires omissions_note')
            number(q['start'], 'quote.start', 0)
            number(q['end'], 'quote.end', 0)
            need(prev <= q['start'] < q['end'], 'quote segments must be ordered and non-overlapping')
            prev = q['end']
            media_time(s, q['start'])
            need(q['end'] + s['timing']['offset_seconds'] <= s['duration_seconds'], 'quote end beyond video')
            frame(q['frame'], 'quote.frame')
            need(q['start'] <= q['frame']['transcript_time'] <= q['end'], 'quote frame outside its excerpt')
            if c['mode'] == 'native_burned_in':
                need(q['frame']['crop'][0] == 0 and q['frame']['crop'][2] == 1, 'native band must preserve full width')
        if c['mode'] == 'native_burned_in':
            need(la['fit'] == 'contain', 'native mode requires contain; never crop subtitle ends')
        for f in frames(c):
            media_time(s, f['transcript_time'])
            binding = (s['id'], f['transcript_time'])
            asset = resolve_asset(base, f['image']) if base is not None else Path(f['image'])
            key = str(asset)
            if base is not None and asset.is_file():
                stat = asset.stat()
                key = (stat.st_dev, stat.st_ino)
            need(key not in image_bindings or image_bindings[key] == binding, 'same image path assigned different source/time')
            image_bindings[key] = binding
            if check_images:
                from PIL import Image
                p = resolve_asset(base, f['image'])
                need(p.is_file(), 'missing frame: ' + f['image'])
                try:
                    with Image.open(p) as im:
                        need(im.format in ('PNG', 'JPEG') and getattr(im, 'n_frames', 1) == 1, 'unsupported image content')
                        im.load()
                        x0, y0, x1, y1 = f['crop']
                        need(round(x1*im.width) > round(x0*im.width) and round(y1*im.height) > round(y0*im.height), 'crop rounds to zero pixels')
                except OSError as e:
                    raise ValidationError('unreadable image: ' + f['image']) from e
    return data


def load(path, **kwargs):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate JSON key: ' + k)
            out[k] = v
        return out
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as e:
        raise ValidationError(str(e)) from e
    return validate(data, Path(path).parent, **kwargs)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest')
    p.add_argument('--check-images', action='store_true')
    p.add_argument('--check-videos', action='store_true')
    a = p.parse_args()
    try:
        m = load(a.manifest, check_images=a.check_images, check_videos=a.check_videos)
        print(json.dumps({'valid': True, 'cards': len(m['cards']), 'kind': m['kind']}))
    except (ValidationError, TypeError, KeyError) as e:
        p.exit(2, 'Invalid manifest: ' + str(e) + '\n')
