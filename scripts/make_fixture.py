"""Generate self-authored geometric fixture art and illustrative (not real) quotes."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from media import atomic_write, image_bytes, write_json, choose_font


def build(out_dir, font=None, overwrite=False):
    out = Path(out_dir)
    font_path = choose_font(font)
    targets = [out/'manifest.json'] + [out/'frames'/('frame-%d.png' % i) for i in range(3)]
    if not overwrite and any(p.exists() for p in targets):
        raise ValueError('fixture exists; use another directory or --overwrite')
    for i in range(3):
        im = Image.new('RGB', (1080, 900), (22, 43, 54))
        d = ImageDraw.Draw(im)
        for x in range(0, 1080, 45):
            d.line((x, 0, x-280, 900), fill=(27, 51, 63), width=2)
        d.ellipse((620, -220, 1340, 500), fill=(35, 68, 76))
        d.rounded_rectangle((75, 105, 380, 330), 15, fill=(232, 183, 102))
        big = ImageFont.truetype(font_path, 43)
        d.text((105, 136), '自制测试画面', font=big, fill=(22, 43, 54))
        d.text((105, 203), '不是视频截图', font=big, fill=(22, 43, 54))
        # Deliberately schematic bust: no real likeness or borrowed media.
        d.ellipse((552, 146, 806, 413), fill=(218, 172, 140))
        d.pieslice((552, 112, 806, 382), 180, 360, fill=(44, 37, 39))
        d.rounded_rectangle((475, 403, 930, 880), 110, fill=(87, 118, 130))
        d.line((580, 516, 380+i*28, 640-i*24), fill=(218, 172, 140), width=55)
        d.ellipse((355+i*28, 615-i*24, 410+i*28, 670-i*24), fill=(218, 172, 140))
        d.rectangle((0, 768, 1080, 900), fill=(33+i*9, 62+i*5, 71))
        d.text((45, 790), 'ILLUSTRATIVE FRAME %02d' % i, font=ImageFont.truetype(font_path, 32), fill=(189, 210, 215))
        atomic_write(targets[i+1], image_bytes(im), overwrite)
    def frame(i, t, crop):
        return {'image': 'frames/frame-%d.png'%i, 'transcript_time': t, 'crop': crop}
    quotes = []
    texts = [
        ('A useful example should state what it can and cannot show.', '好示例应讲清：能展示什么、不能展示什么。'),
        ('When evidence is missing, leave the conclusion open.', '证据不足的时候，先让结论保持开放。')]
    for i, (en, zh) in enumerate(texts, 1):
        quotes.append({'speaker': '虚构讲者', 'start': float(i), 'end': float(i)+.8,
          'original_text': en, 'translation_zh': zh,
          'context_before': 'Self-authored illustrative text; no real event or speaker.',
          'context_after': 'Only tests layout and provenance fields.',
          'excerpted': False, 'omissions_note': '', 'reviewed': True,
          'frame': frame(i, i+.4, [0, .64, 1, 1])})
    m = {'schema_version': 1, 'kind': 'synthetic_fixture',
      'editorial': {'topic': '示例的边界', 'angle': '先说明证据能支持什么', 'status': 'exact_brief', 'confirmation': 'Self-authored fixture brief; illustrative only.'},
      'sources': [{'id': 'fixture-talk', 'title': '自制版式演示', 'url': 'fixture:geometric-speaker', 'language': 'en',
        'video': 'fixture.mp4', 'duration_seconds': 5, 'rights_note': 'Original procedural art and illustrative text; no real quotation.',
        'transcript': {'kind': 'synthetic', 'reference': 'scripts/make_fixture.py', 'verification_note': 'Self-authored fixture, not a factual statement about a person.'},
        'timing': {'offset_seconds': 0, 'tolerance_seconds': .04,
          'anchors': [{'transcript_seconds': 0, 'media_seconds': 0, 'evidence': 'Synthetic start.'},
                      {'transcript_seconds': 4, 'media_seconds': 4, 'evidence': 'Synthetic endpoint.'}]}}],
      'cards': [{'id': 'illustrative-demo', 'source_id': 'fixture-talk', 'heading': '先看证据，再做判断', 'mode': 'translated_script',
        'hero': frame(0, .4, [0, 0, 1, .86]), 'quotes': quotes}],
      'layout': {'width': 1080, 'height': 1440, 'hero_fraction': .61, 'font_size': 43, 'fit': 'cover'}}
    write_json(targets[0], m, overwrite)
    return targets[0]


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True)
    p.add_argument('--font')
    p.add_argument('--overwrite', action='store_true')
    a = p.parse_args()
    try:
        print(build(a.out, a.font, a.overwrite))
    except (OSError, ValueError) as e:
        p.exit(2, str(e)+'\n')
