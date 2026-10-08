"""Check local references, obvious private identifiers and package inventory; optionally build a deterministic ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile
from media import atomic_write

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {'__pycache__', '.git', '.venv', 'build', '.DS_Store'}
ALLOWED = {'.py', '.md', '.json', '.yaml', '.txt', '.png'}


def files(root):
    result = []
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root)
        if any(x in EXCLUDE or x.startswith('output') for x in rel.parts):
            continue
        if p.is_symlink():
            raise ValueError('Package symlink: ' + str(rel))
        if p.is_file():
            if p.suffix not in ALLOWED and p.name not in ('LICENSE', '.gitignore'):
                raise ValueError('Unexpected distributable file: ' + str(rel))
            result.append(p)
    return result


def audit(root=ROOT):
    candidates = files(root)
    issues = []
    patterns = [r'libfile_[0-9a-f]{16,}', r'file_[0-9a-f]{16,}',
                r'/Users/[A-Za-z0-9_.-]+/', r'/home/[A-Za-z0-9_.-]+/',
                r'(?i)(?:api[_-]?key|access_token)\s*[=:]\s*["\x27][A-Za-z0-9_-]{20,}',
                r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                r'https?://[^\s]+[?&](?:X-Amz-Signature|sig|token)=',
                r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}']
    for p in candidates:
        if p.suffix == '.png':
            from PIL import Image
            with Image.open(p) as im:
                im.load()
                if im.format != 'PNG' or im.mode != 'RGB':
                    issues.append(str(p.relative_to(root)) + ': expected RGB PNG fixture')
            continue
        text = p.read_text(encoding='utf-8')
        for pat in patterns:
            if re.search(pat, text):
                issues.append(str(p.relative_to(root)) + ': potential private data; review locally')
        if p.suffix == '.md':
            for link in re.findall(r'\]\(([^)]+)\)', text):
                if re.match(r'https?://|#|mailto:', link):
                    continue
                target = link.split('#')[0]
                if target and not (p.parent/target).exists():
                    issues.append(str(p.relative_to(root))+': broken local link '+target)
    skill=(root/'SKILL.md').read_text(encoding='utf-8')
    if not skill.startswith('---\nname: topic-to-quote-collage\ndescription: '):
        issues.append('SKILL.md frontmatter invalid')
    if len(skill.split('---', 2)) != 3:
        issues.append('SKILL.md frontmatter not closed')
    return candidates, issues


def package(destination, root=ROOT):
    paths, issues=audit(root)
    if issues:
        raise ValueError('\n'.join(issues))
    import io
    stream=io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in paths:
            info=zipfile.ZipInfo(root.name+'/'+p.relative_to(root).as_posix(), (1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            z.writestr(info,p.read_bytes())
    data=stream.getvalue()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP CRC failed')
    atomic_write(destination,data)
    return {'file_count':len(paths),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zip', dest='zip_path')
    a=p.parse_args()
    try:
        paths, issues=audit()
        result={'files':len(paths),'issues':issues,'scope':'heuristic text/inventory checks; media ownership and meaning still require review'}
        if issues:
            print(json.dumps(result,ensure_ascii=False));raise SystemExit(2)
        if a.zip_path:
            result['archive']=package(a.zip_path)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError) as e:
        p.exit(2,str(e)+'\n')
