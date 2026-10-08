import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from PIL import Image
from manifest import load, validate, resolve_asset, media_time, ValidationError
from media import atomic_write, sha256, binding, write_json
from render_collage import render, card_image, verify_receipts
from make_fixture import build
from media import choose_font
from extract_frames import extract


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.m = json.loads((ROOT/'examples/fixture/manifest.json').read_text())

    def bad(self, change):
        change(self.m)
        with self.assertRaises((ValidationError, TypeError)):
            validate(self.m)

    def test_valid(self):
        validate(self.m)

    def test_huge_integer_clean_error(self):
        self.m['layout']['width'] = 10**1000
        with self.assertRaises(ValidationError):
            validate(self.m)

    def test_huge_offset_with_float_anchor_clean_error(self):
        timing = self.m['sources'][0]['timing']
        timing['anchors'][0]['media_seconds'] = 0.0
        timing['offset_seconds'] = 10**1000
        with self.assertRaisesRegex(ValidationError, 'offset_seconds: expected finite representable number'):
            validate(self.m)

    def test_huge_frame_time_with_float_offset_clean_error(self):
        timing = self.m['sources'][0]['timing']
        timing['offset_seconds'] = .25
        for anchor in timing['anchors']:
            anchor['media_seconds'] += .25
        self.m['cards'][0]['hero']['transcript_time'] = 10**1000
        with self.assertRaisesRegex(ValidationError, 'hero.transcript_time: expected finite representable number'):
            validate(self.m)

    def test_dot_path_alias(self):
        self.bad(lambda m: m['cards'][0]['quotes'][0]['frame'].update({'image': 'frames/./frame-0.png'}))

    def test_duplicate_separator_alias(self):
        self.bad(lambda m: m['cards'][0]['quotes'][0]['frame'].update({'image': 'frames//frame-0.png'}))

    def test_valid_youtube_query(self):
        self.m['sources'][0]['url'] = 'https://www.youtube.com/watch?v=illustrative-id'
        validate(self.m)

    def test_signed_source_rejected(self):
        self.bad(lambda m: m['sources'][0].update({'url': 'https://example.org/video?' + 'token=test-value'}))

    def test_non_utf8_clean_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'broken.json';p.write_bytes(bytes([255,254]))
            with self.assertRaises(ValidationError):
                load(p)

    def test_unknown_field(self):
        self.bad(lambda m: m.update({'quotes_typo': []}))

    def test_missing_field(self):
        self.bad(lambda m: m.pop('sources'))

    def test_wrong_type(self):
        self.bad(lambda m: m.update({'cards': 'wrong'}))

    def test_unsupported_version(self):
        self.bad(lambda m: m.update({'schema_version': 2}))

    def test_unconfirmed_angle(self):
        self.bad(lambda m: m['editorial'].update({'status': 'draft'}))

    def test_non_finite_time(self):
        self.bad(lambda m: m['cards'][0]['hero'].update({'transcript_time': float('nan')}))

    def test_bool_is_not_number(self):
        self.bad(lambda m: m['layout'].update({'width': True}))

    def test_crop_bounds(self):
        self.bad(lambda m: m['cards'][0]['hero'].update({'crop': [0, -.1, 1, 1]}))

    def test_reversed_crop(self):
        self.bad(lambda m: m['cards'][0]['hero'].update({'crop': [.9, 0, .2, 1]}))

    def test_native_horizontal_crop(self):
        self.m['cards'][0]['mode'] = 'native_burned_in'
        self.m['layout']['fit'] = 'contain'
        self.bad(lambda m: m['cards'][0]['quotes'][0]['frame'].update({'crop': [.1, .5, 1, 1]}))

    def test_unsupported_image(self):
        self.bad(lambda m: m['cards'][0]['hero'].update({'image': 'bad.svg'}))

    def test_unsupported_video(self):
        self.bad(lambda m: m['sources'][0].update({'video': 'bad.m3u8'}))

    def test_traversal(self):
        self.bad(lambda m: m['cards'][0]['hero'].update({'image': '../private.png'}))

    def test_windows_absolute_path(self):
        self.bad(lambda m: m['cards'][0]['hero'].update({'image': 'C:/private.png'}))

    def test_quote_order(self):
        self.bad(lambda m: m['cards'][0]['quotes'].reverse())

    def test_unreviewed_translation(self):
        self.bad(lambda m: m['cards'][0]['quotes'][0].update({'reviewed': False}))

    def test_excerpts_need_note(self):
        self.bad(lambda m: m['cards'][0]['quotes'][0].update({'excerpted': True}))

    def test_context_required(self):
        self.bad(lambda m: m['cards'][0]['quotes'][0].update({'context_before': ''}))

    def test_frame_must_belong_to_quote(self):
        self.bad(lambda m: m['cards'][0]['quotes'][0]['frame'].update({'transcript_time': 4}))

    def test_duplicate_ids(self):
        self.bad(lambda m: m['cards'].append(copy.deepcopy(m['cards'][0])))

    def test_same_path_different_timestamp(self):
        self.bad(lambda m: m['cards'][0]['quotes'][0]['frame'].update({'image': 'frames/frame-0.png'}))

    def test_two_distinct_anchors(self):
        self.bad(lambda m: m['sources'][0]['timing'].update({'anchors': [m['sources'][0]['timing']['anchors'][0]]*2}))

    def test_nonconstant_offset_rejected(self):
        self.bad(lambda m: m['sources'][0]['timing']['anchors'][1].update({'media_seconds': 4.8}))

    def test_intro_offset_sign(self):
        s = self.m['sources'][0]
        s['duration_seconds'] = 20
        s['timing']['offset_seconds'] = 5.25
        for a in s['timing']['anchors']:
            a['media_seconds'] += 5.25
        validate(self.m)
        self.assertAlmostEqual(media_time(s, 1.4), 6.65)

    def test_negative_media_time(self):
        s = self.m['sources'][0]
        s['timing']['offset_seconds'] = -2
        with self.assertRaises(ValidationError):
            media_time(s, 1)

    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'manifest.json'
            p.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaisesRegex(ValidationError, 'duplicate JSON key'):
                load(p)

    def test_malformed_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'manifest.json'; p.write_text('{broken')
            with self.assertRaises(ValidationError):
                load(p)

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)/'base';base.mkdir()
            (base/'link').symlink_to(Path(td), target_is_directory=True)
            with self.assertRaises(ValidationError):
                resolve_asset(base, 'link/secret.png')


class RenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = choose_font()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.manifest = build(self.base/'fixture', self.font)
        self.m = load(self.manifest)

    def save(self):
        self.manifest.write_text(json.dumps(self.m, ensure_ascii=False), encoding='utf-8')

    def test_dimensions_rgb_preview_deterministic(self):
        render(self.manifest, self.base/'a', self.font, preview=True)
        render(self.manifest, self.base/'b', self.font, preview=True)
        for p in (self.base/'a').glob('*.png'):
            with Image.open(p) as im:
                self.assertEqual(im.mode, 'RGB')
                self.assertEqual(im.size, (720, 960) if '.preview.' in p.name else (1080, 1440))
            self.assertEqual(sha256(p), sha256(self.base/'b'/p.name))

    def test_no_overwrite(self):
        render(self.manifest, self.base/'a', self.font)
        p = self.base/'a/illustrative-demo.png'; before = p.read_bytes()
        with self.assertRaisesRegex(ValidationError, 'exists'):
            render(self.manifest, self.base/'a', self.font)
        self.assertEqual(before, p.read_bytes())

    def test_explicit_overwrite(self):
        render(self.manifest, self.base/'a', self.font)
        render(self.manifest, self.base/'a', self.font, overwrite=True)

    def test_atomic_write_no_clobber(self):
        p = self.base/'one.txt';atomic_write(p, b'first')
        with self.assertRaises(FileExistsError):
            atomic_write(p, b'second')
        self.assertEqual(p.read_bytes(), b'first')

    def test_long_chinese_fails_without_output(self):
        self.m['cards'][0]['quotes'][0]['translation_zh'] = '保留限定词，不把不确定说成确定。'*40
        self.save()
        with self.assertRaisesRegex(ValidationError, 'overflow'):
            render(self.manifest, self.base/'long', self.font)
        self.assertFalse((self.base/'long').exists())

    def test_long_heading_fails(self):
        self.m['cards'][0]['heading'] = '不要把标题塞进小区域'*40
        self.save()
        with self.assertRaisesRegex(ValidationError, 'overflow'):
            render(self.manifest, self.base/'long', self.font)

    def test_jpeg_decodes_and_preserves_original_with_preview(self):
        render(self.manifest, self.base/'jpg', self.font, preview=True, output_format='jpg')
        with Image.open(self.base/'jpg/illustrative-demo.jpg') as im:
            im.load();self.assertEqual(im.format, 'JPEG');self.assertEqual(im.size, (1080,1440))
        self.assertTrue((self.base/'jpg/illustrative-demo.preview.png').is_file())

    def test_native_crop_pixels_not_redrawn(self):
        self.m['cards'][0]['mode'] = 'native_burned_in'
        self.m['layout']['fit'] = 'contain'
        self.save()
        render(self.manifest, self.base/'native', self.font)
        # Every source frame remains byte-identical; output differs from translation mode.
        hashes = [sha256(self.manifest.parent/f['image']) for f in [self.m['cards'][0]['hero']]+[q['frame'] for q in self.m['cards'][0]['quotes']]]
        self.m['cards'][0]['quotes'][0]['translation_zh'] = '这段文字不应画入原生模式'
        self.save();render(self.manifest, self.base/'native2', self.font)
        self.assertEqual(sha256(self.base/'native/illustrative-demo.png'),sha256(self.base/'native2/illustrative-demo.png'))
        self.assertEqual(hashes, [sha256(self.manifest.parent/f['image']) for f in [self.m['cards'][0]['hero']]+[q['frame'] for q in self.m['cards'][0]['quotes']]])

    def test_same_file_via_internal_symlink(self):
        alias = self.manifest.parent/'frames/alias.png'
        alias.symlink_to('frame-0.png')
        self.m['cards'][0]['quotes'][0]['frame']['image'] = 'frames/alias.png'
        self.save()
        with self.assertRaisesRegex(ValidationError, 'same image path'):
            load(self.manifest)

    def test_missing_frame(self):
        (self.manifest.parent/'frames/frame-0.png').unlink()
        with self.assertRaisesRegex(ValidationError, 'missing frame'):
            render(self.manifest, self.base/'missing', self.font)

    def test_disguised_unsupported_image(self):
        p=self.manifest.parent/'frames/frame-0.png'
        Image.new('RGB',(10,10)).save(p,format='GIF')
        with self.assertRaisesRegex(ValidationError,'unsupported image'):
            load(self.manifest,check_images=True)

    def test_tiny_crop_zero_pixels(self):
        self.m['cards'][0]['hero']['crop'] = [0,0,.000001,.000001]
        self.save()
        with self.assertRaisesRegex(ValidationError,'zero pixels'):
            load(self.manifest,check_images=True)

    def test_stale_frame_receipt(self):
        s=self.m['sources'][0];s['url']='https://example.org/fixture';s['transcript']['kind']='manual'
        self.m['kind']='real_video'
        video=self.manifest.parent/s['video'];video.write_bytes(b'self-authored receipt binding test; not a playable video')
        for f in [self.m['cards'][0]['hero']]+[q['frame'] for q in self.m['cards'][0]['quotes']]:
            p=self.manifest.parent/f['image'];r=binding(s,f,sha256(video));r['image_sha256']=sha256(p)
            write_json(p.with_suffix(p.suffix+'.frame.json'),r)
        verify_receipts(self.m,self.manifest.parent)
        self.m['cards'][0]['hero']['transcript_time'] += .1
        with self.assertRaisesRegex(ValidationError,'stale frame'):
            verify_receipts(self.m,self.manifest.parent)

    def test_mutated_video_invalidates_receipt(self):
        # Different media content cannot reuse a receipt even with the same filename.
        self.test_stale_frame_receipt()
        self.m['cards'][0]['hero']['transcript_time'] -= .1
        (self.manifest.parent/self.m['sources'][0]['video']).write_bytes(b'changed content')
        with self.assertRaisesRegex(ValidationError,'stale frame'):
            verify_receipts(self.m,self.manifest.parent)

    def test_three_strips(self):
        q=copy.deepcopy(self.m['cards'][0]['quotes'][-1]);q.update(start=3,end=3.8,translation_zh='这是第三条示例。')
        q['frame'].update(image='frames/frame-3.png',transcript_time=3.4)
        shutil.copy(self.manifest.parent/'frames/frame-2.png',self.manifest.parent/'frames/frame-3.png')
        self.m['cards'][0]['quotes'].append(q);self.m['layout']['font_size']=34
        self.m['layout']['hero_fraction']=.56;self.save()
        render(self.manifest,self.base/'three',self.font)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg/ffprobe absent; actual extraction integration not run')
class FFmpegIntegrationTests(unittest.TestCase):
    def test_synthetic_video_offset_receipt_and_seek(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);font=choose_font();mp=build(p/'fixture',font)
            m=load(mp);s=m['sources'][0]
            # All generated in test temp, never third-party footage. One-second blocks.
            ff=shutil.which('ffmpeg')
            for i,color in enumerate(['red','green','blue','yellow','purple']):
                Image.new('RGB',(320,240),color).save(mp.parent/('%02d.png'%i))
            subprocess.run([ff,'-v','error','-framerate','1','-i',str(mp.parent/'%02d.png'),'-c:v','ffv1',str(mp.parent/'fixture.mkv')],check=True)
            s['video']='fixture.mkv'
            s['timing']['offset_seconds']=1
            s['timing']['anchors']=[{'transcript_seconds':0,'media_seconds':1,'evidence':'color one'}, {'transcript_seconds':3,'media_seconds':4,'evidence':'color four'}]
            for f in [m['cards'][0]['hero']]+[q['frame'] for q in m['cards'][0]['quotes']]:
                (mp.parent/f['image']).unlink()
            mp.write_text(json.dumps(m))
            self.assertEqual(extract(mp),3)
            with Image.open(mp.parent/m['cards'][0]['hero']['image']) as im:
                # Output-side seek to media 1.4 selects first video frame >=1.4, i.e. blue at 2.
                r,g,b=im.getpixel((20,20));self.assertGreater(b,200);self.assertLess(r,20)
            self.assertTrue((mp.parent/'frames/frame-0.png.frame.json').is_file())
            with self.assertRaisesRegex(ValidationError,'exists'):
                extract(mp)


if __name__ == '__main__':
    unittest.main()
