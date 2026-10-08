"""Read-only environment checks; never installs dependencies or downloads assets."""
import argparse
import json
import platform
from media import choose_font, executable, run


def check(font=None, ffmpeg=None, ffprobe=None, render_only=False):
    result = {'python': platform.python_version(), 'pillow': None, 'font': None, 'ffmpeg': None, 'ffprobe': None, 'errors': []}
    if tuple(map(int, platform.python_version_tuple()[:2])) < (3, 9):
        result['errors'].append('Python 3.9+ required')
    try:
        import PIL
        result['pillow'] = PIL.__version__
        if tuple(map(int, PIL.__version__.split('.')[:2])) < (10, 4):
            result['errors'].append('Pillow 10.4+ required')
        result['font'] = choose_font(font)
    except (ImportError, ValueError) as e:
        result['errors'].append(str(e))
    if not render_only:
        for name, explicit in [('ffmpeg', ffmpeg), ('ffprobe', ffprobe)]:
            try:
                path = executable(name, explicit)
                result[name] = run([path, '-version']).decode().splitlines()[0]
            except ValueError as e:
                result['errors'].append(str(e))
    result['ok'] = not result['errors']
    result['capabilities'] = 'local validation/rendering; local video extraction when FFmpeg+ffprobe available; no search/transcription/download'
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font')
    p.add_argument('--ffmpeg')
    p.add_argument('--ffprobe')
    p.add_argument('--render-only', action='store_true')
    a = p.parse_args()
    r = check(a.font, a.ffmpeg, a.ffprobe, a.render_only)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    raise SystemExit(0 if r['ok'] else 2)
