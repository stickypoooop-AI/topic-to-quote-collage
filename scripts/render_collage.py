"""Render labeled Chinese quote collages from reviewed actual frames (or marked fixtures)."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from manifest import load, need, frames, resolve_asset, ValidationError
from media import choose_font, image_bytes, atomic_write, write_json, sha256, binding

BG = (16, 23, 30)
TEXT = (247, 244, 232)
ACCENT = (239, 194, 116)
MUTED = (170, 186, 196)


def wrap(text, font, width):
    need(width > 0, 'text box has no width')
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for char in paragraph:
            need(font.getlength(char) <= width, 'single character exceeds text width')
            if font.getlength(line + char) > width and line:
                lines.append(line)
                line = char
            else:
                line += char
        lines.append(line)
    return lines


def text_box(draw, text, box, font, fill=TEXT, max_lines=None):
    x, y, w, h = box
    lines = wrap(text, font, w)
    ascent, descent = font.getmetrics()
    step = round((ascent + descent) * 1.12)
    need(not max_lines or len(lines) <= max_lines, 'text overflow: split the excerpt or enlarge the layout; text was not truncated')
    need(len(lines)*step <= h, 'text height overflow: split the excerpt or enlarge the layout; text was not truncated')
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill, anchor='lt')
        y += step
    return y


def crop_frame(base, spec):
    with Image.open(resolve_asset(base, spec['image'])) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        c = spec['crop']
        box = tuple(round(v*d) for v, d in zip(c, (im.width, im.height, im.width, im.height)))
        need(box[2] > box[0] and box[3] > box[1], 'empty crop')
        return im.crop(box)


def fit(image, size, mode):
    if mode == 'cover':
        return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
    out = Image.new('RGB', size, BG)
    thumb = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
    out.paste(thumb, ((size[0]-thumb.width)//2, (size[1]-thumb.height)//2))
    return out


def verify_receipts(m, base):
    if m['kind'] == 'synthetic_fixture':
        return
    sources = {s['id']: s for s in m['sources']}
    hashes = {}
    for c in m['cards']:
        s = sources[c['source_id']]
        if s['id'] not in hashes:
            video = resolve_asset(base, s['video'])
            need(video.is_file(), 'source video required to verify frame hashes')
            hashes[s['id']] = sha256(video)
        for f in frames(c):
            p = resolve_asset(base, f['image'])
            r = p.with_suffix(p.suffix + '.frame.json')
            need(r.is_file(), 'missing extraction receipt: run extract_frames.py')
            try:
                record = json.loads(r.read_text(encoding='utf-8'))
            except (OSError, ValueError) as e:
                raise ValidationError('unreadable extraction receipt') from e
            expected = binding(s, f, hashes[s['id']])
            need(all(record.get(k) == v for k, v in expected.items()), 'stale frame: source/time/offset changed; re-extract')
            need(record.get('image_sha256') == sha256(p), 'frame pixels changed; re-extract')


def card_image(m, card, base, font_path):
    la = m['layout']
    w, h = la['width'], la['height']
    margin = round(w*.045)
    font = ImageFont.truetype(font_path, la['font_size'])
    heading_font = ImageFont.truetype(font_path, round(w*.054))
    small = ImageFont.truetype(font_path, max(16, round(w*.022)))
    label_font = ImageFont.truetype(font_path, max(16, round(w*.02)))
    image = Image.new('RGB', (w, h), BG)
    draw = ImageDraw.Draw(image)
    fixture = m['kind'] == 'synthetic_fixture'
    label = '演示素材 · 编辑标题 · 非真实引语' if fixture else '编辑标题 · 非讲者原话'
    draw.rectangle((margin, margin, margin+round(w*.06), margin+3), fill=ACCENT)
    label_y = margin+round(w*.017)
    text_box(draw, label, (margin, label_y, w-2*margin, h*.05), label_font, ACCENT, 1)
    heading_y = label_y + round(w*.04)
    title_bottom = text_box(draw, card['heading'], (margin, heading_y, w-2*margin, h*.13), heading_font, TEXT, 2)
    top = title_bottom + round(w*.022)
    footer_h = round(w*.115)
    content_h = h-top-footer_h
    need(content_h >= h*.5, 'heading leaves insufficient image space')
    source = next(s for s in m['sources'] if s['id'] == card['source_id'])
    if card['mode'] == 'native_burned_in':
        native = [crop_frame(base, f) for f in frames(card)]
        need(len({i.width for i in native}) == 1, 'native frames/crops must share width for uniform subtitle scale')
        joined = Image.new('RGB', (native[0].width, sum(i.height for i in native)), BG)
        y = 0
        for i in native:
            joined.paste(i, (0, y)); y += i.height
        image.paste(fit(joined, (w, content_h), 'contain'), (0, top))
    else:
        hero_h = round(content_h * la['hero_fraction'])
        image.paste(fit(crop_frame(base, card['hero']), (w, hero_h), la['fit']), (0, top))
        y = top+hero_h
        strip_total = content_h-hero_h
        for index, q in enumerate(card['quotes']):
            band_h = (strip_total*(index+1)//len(card['quotes']))-(strip_total*index//len(card['quotes']))
            band = fit(crop_frame(base, q['frame']), (w, band_h), la['fit']).convert('RGBA')
            band = Image.alpha_composite(band, Image.new('RGBA', band.size, (0, 0, 0, 157))).convert('RGB')
            image.paste(band, (0, y))
            draw = ImageDraw.Draw(image)
            pad = round(w*.021)
            label = '中文翻译 · ' + q['speaker'] + (' · 节选' if q['excerpted'] else '')
            text_box(draw, label, (margin, y+pad, w-2*margin, band_h), label_font, ACCENT, 1)
            qy = y+pad+round(w*.039)
            text_box(draw, q['translation_zh'], (margin, qy, w-2*margin, band_h-(qy-y)-pad), font, TEXT, 3)
            y += band_h
    draw = ImageDraw.Draw(image)
    ftop = h-footer_h
    draw.line((margin, ftop+round(w*.018), w-margin, ftop+round(w*.018)), fill=(66, 80, 89), width=1)
    native_label = '原生烧录字幕 · 像素未重绘' if card['mode'] == 'native_burned_in' else '中文为后期翻译字幕'
    first, last = card['quotes'][0], card['quotes'][-1]
    origin = '{} · {}–{}s'.format(source['title'], format(first['start'], '.2f'), format(last['end'], '.2f'))
    text_box(draw, origin, (margin, ftop+round(w*.029), w-2*margin, footer_h), small, TEXT, 1)
    text_box(draw, native_label+' · 完整来源与上下文见附带清单', (margin, ftop+round(w*.065), w-2*margin, footer_h), label_font, MUTED, 1)
    return image


def render(manifest_path, out_dir, font=None, preview=False, overwrite=False, output_format='png'):
    m = load(manifest_path, check_images=True)
    base, out = Path(manifest_path).parent, Path(out_dir)
    need(output_format in ('png', 'jpg'), 'unsupported output format')
    font_path = choose_font(font)
    verify_receipts(m, base)
    paths = [out/(c['id']+'.'+output_format) for c in m['cards']]
    if preview:
        paths += [out/(c['id']+'.preview.png') for c in m['cards']]
    paths += [out/'provenance.json', out/'render-report.json']
    need(len(set(paths)) == len(paths), 'output path collision')
    for path in paths:
        need(overwrite or not path.exists(), 'output exists; choose a new directory or explicit --overwrite: '+path.name)
    # Pre-render everything before committing; overflow does not leave half a set.
    results = [(c, card_image(m, c, base, font_path)) for c in m['cards']]
    outputs = []
    for c, im in results:
        p = out/(c['id']+'.'+output_format)
        data = image_bytes(im, p.suffix)
        outputs.append((p, data))
        if preview:
            # 720x960 RGB canvas, aspect preserved; originals remain untouched.
            outputs.append((out/(c['id']+'.preview.png'), image_bytes(fit(im, (720, 960), 'contain'))))
    report = {'kind': m['kind'], 'font_file': Path(font_path).name, 'mode': 'RGB',
              'outputs': [{'name': p.name, 'bytes': len(b)} for p, b in outputs],
              'visual_qa': 'pending actual pixel inspection',
              'semantic_qa': 'manifest declarations only; source/translation review is a host-agent responsibility'}
    for p, data in outputs:
        atomic_write(p, data, overwrite)
    write_json(out/'provenance.json', m, overwrite)
    write_json(out/'render-report.json', report, overwrite)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest')
    p.add_argument('--out', required=True)
    p.add_argument('--font')
    p.add_argument('--preview', action='store_true')
    p.add_argument('--format', choices=['png', 'jpg'], default='png')
    p.add_argument('--overwrite', action='store_true')
    a = p.parse_args()
    try:
        print(json.dumps(render(a.manifest, a.out, a.font, a.preview, a.overwrite, a.format), ensure_ascii=False))
    except (ValidationError, OSError, ValueError, KeyError, TypeError) as e:
        p.exit(2, str(e)+'\n')
