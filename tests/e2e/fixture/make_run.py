#!/usr/bin/env python3
"""Build a self-contained browser-test run dir: config, trials.tsv, PNG images.

Images are served same-origin by fixture/serve.py because the tiles set
crossOrigin='anonymous' for canvas access, and Chromium refuses data: URIs under CORS.
Usage: make_run.py <out_dir> [rows]
"""
import json
import shutil
import struct
import sys
import zlib
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]


def png(width, height, pixel):
    """Minimal PNG encoder: pixel(x, y) -> RGB(A) tuple, alpha for masks."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw += bytes(pixel(x, y))

    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)

    colour_type = 6 if len(pixel(0, 0)) == 4 else 2
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, colour_type, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw), 6))
            + chunk(b'IEND', b''))


def write_png(images, name, width, height, pixel):
    (images / name).write_bytes(png(width, height, pixel))
    return f'/e2e-img/{name}'


def gradient(c0, c1):
    """Diagonal ramp with a corner block, so A and B are visibly different images."""
    def p(x, y):
        t = (x / 199 + y / 149) / 2
        rgb = tuple(round(a + (b - a) * t) for a, b in zip(c0, c1))
        if x < 33 and y < 25:
            return tuple(min(255, v + 60) for v in rgb)
        return rgb
    return p


def mask_pixel(regions):
    """Pure IDENTITY_COLORS rectangles on black: the mask scan matches <10 per channel."""
    def p(x, y):
        for x0, y0, x1, y1, colour in regions:
            if x0 <= x < x1 and y0 <= y < y1:
                return (*colour, 255)
        return (0, 0, 0, 255)
    return p


def identity_colors(count):
    """The app's own palette, as tuples: the fixture paints masks with the bytes the scanner matches."""
    colors = json.loads((REPO / 'frontend/src/identity-colors.json').read_text())
    if len(colors) < count:
        raise SystemExit(f'identity-colors.json has {len(colors)} colours, the fixture needs {count}')
    return [tuple(colour) for colour in colors[:count]]


def solid(colour):
    return lambda x, y: (*colour, 255) if len(colour) == 3 else colour


def main():
    out = Path(sys.argv[1]).resolve()
    rows = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    if out.exists():
        shutil.rmtree(out)
    images = out / 'images'
    images.mkdir(parents=True)

    config = yaml.safe_load((REPO / 'survey_config.yaml').read_text())
    config['survey']['pairs_per_user'] = rows
    config['tutorial']['enabled'] = False
    config['data']['file'] = 'trials.tsv'
    (out / 'survey_config.yaml').write_text(yaml.safe_dump(config, sort_keys=False, width=100))

    columns = config['data']['columns']
    palette = [(30, 90, 200), (200, 90, 30), (30, 160, 90), (150, 40, 160)]
    # Read, not mirrored: the mask scan in study-state.ts matches these exact colours, so a fixture
    # that hardcodes them keeps painting the old palette after the app moves on.
    identities = identity_colors(3)
    mask_regions = [(10, 10, 70, 70, identities[0]),
                    (80, 10, 140, 70, identities[1]),
                    (10, 80, 70, 140, identities[2])]

    lines = ['# E2E fixture trials -- tab-separated, one row per trial, no header row']
    for i in range(rows):
        # The last two rows leave mask/identity empty: the app samples trials per session, so
        # one optional-free row could be sampled out and the case would silently stop being covered.
        empty_optional = rows > 2 and i >= rows - 2
        base, other = palette[i % len(palette)], palette[(i + 1) % len(palette)]
        values = {
            'prompt': f'Trial {i + 1}: a red cube on a wooden table under soft light',
            'method_a': 'method_a',
            'method_b': 'method_b',
            'image_a_url': write_png(images, f'trial{i}_a.png', 200, 150, gradient(base, other)),
            'image_b_url': write_png(images, f'trial{i}_b.png', 200, 150, gradient(other, base)),
            'mask_url': '' if empty_optional else write_png(
                images, f'trial{i}_mask.png', 200, 150, mask_pixel(mask_regions)),
            'identity_urls': '' if empty_optional else ','.join(
                write_png(images, f'trial{i}_id{k}.png', 90, 90, solid(c))
                for k, c in enumerate(identities)),
        }
        lines.append('\t'.join(values[c] for c in columns))
    (out / 'trials.tsv').write_text('\n'.join(lines) + '\n')

    shutil.copy(REPO / 'examples' / 'tutorial_image_pair.txt', out / 'tutorial_image_pair.txt')
    print(out)


if __name__ == '__main__':
    main()
