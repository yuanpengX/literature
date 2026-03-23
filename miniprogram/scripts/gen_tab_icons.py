#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate WeChat tabBar PNGs (81x81) to align with Android AppNav.kt Material Icons:
  Home, AutoAwesome, Search, Star, Settings — filled style, inactive #49454F / active #3D5AFE.
Uses only stdlib (no Pillow). Renders high-res grid then box-downsamples for smooth edges.
"""
from __future__ import annotations

import math
import os
import struct
import zlib

# Internal resolution: 24 logical dp * SCALE
SCALE = 10
W = 24 * SCALE
H = 24 * SCALE
OUT = 81

# app.json tabBar
COLOR_INACTIVE = (0x49, 0x45, 0x4F)  # #49454F
COLOR_ACTIVE = (0x3D, 0x5A, 0xFE)  # #3D5AFE


def write_png_rgba(path: str, width: int, height: int, rows: list[bytes]) -> None:
    """rows: list of height items, each length width*4 RGBA."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b""
    for row in rows:
        raw += b"\x00" + row
    compressed = zlib.compress(raw, 9)
    with open(path, "wb") as f:
        f.write(sig)
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", compressed))
        f.write(chunk(b"IEND", b""))


def downsample(buf: list[list[tuple[float, float, float, float]]]) -> list[bytes]:
    """buf[H][W] floats 0..1 RGBA -> 81x81 PNG rows."""
    h, w = len(buf), len(buf[0])
    sx = w / OUT
    sy = h / OUT
    rows: list[bytes] = []
    for yo in range(OUT):
        row = bytearray(OUT * 4)
        for xo in range(OUT):
            r = g = b = a = 0.0
            n = 0
            y0 = int(yo * sy)
            y1 = min(int((yo + 1) * sy), h)
            x0 = int(xo * sx)
            x1 = min(int((xo + 1) * sx), w)
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    pr, pg, pb, pa = buf[yy][xx]
                    r += pr
                    g += pg
                    b += pb
                    a += pa
                    n += 1
            if n:
                r, g, b, a = r / n, g / n, b / n, a / n
            i = xo * 4
            row[i] = int(max(0, min(255, round(r * 255))))
            row[i + 1] = int(max(0, min(255, round(g * 255))))
            row[i + 2] = int(max(0, min(255, round(b * 255))))
            row[i + 3] = int(max(0, min(255, round(a * 255))))
        rows.append(bytes(row))
    return rows


def blend(dst: list[list[tuple[float, float, float, float]]], y: int, x: int, pr: float, pg: float, pb: float, pa: float) -> None:
    if not (0 <= x < W and 0 <= y < H):
        return
    br, bg, bb, ba = dst[y][x]
    if pa <= 0:
        return
    if ba <= 0:
        dst[y][x] = (pr, pg, pb, pa)
        return
    out_a = pa + ba * (1 - pa)
    if out_a <= 1e-6:
        dst[y][x] = (0.0, 0.0, 0.0, 0.0)
        return
    nr = (pr * pa + br * ba * (1 - pa)) / out_a
    ng = (pg * pa + bg * ba * (1 - pa)) / out_a
    nb = (pb * pa + bb * ba * (1 - pa)) / out_a
    dst[y][x] = (nr, ng, nb, out_a)


def fill_circle(
    dst: list[list[tuple[float, float, float, float]]],
    cx: float,
    cy: float,
    r: float,
    rgb: tuple[float, float, float],
    aa: float = 1.2,
) -> None:
    pr, pg, pb = rgb
    y0 = max(0, int(cy - r - aa - 1))
    y1 = min(H, int(cy + r + aa + 2))
    x0 = max(0, int(cx - r - aa - 1))
    x1 = min(W, int(cx + r + aa + 2))
    for y in range(y0, y1):
        for x in range(x0, x1):
            d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            alpha = max(0.0, min(1.0, (r + 0.5 - d) / aa))
            if alpha > 0:
                blend(dst, y, x, pr, pg, pb, alpha)


def stroke_circle(
    dst: list[list[tuple[float, float, float, float]]],
    cx: float,
    cy: float,
    r: float,
    stroke: float,
    rgb: tuple[float, float, float],
    aa: float = 1.15,
) -> None:
    """Circular ring: distance from stroke centerline r, half-width stroke/2."""
    pr, pg, pb = rgb
    y0 = max(0, int(cy - r - stroke - aa))
    y1 = min(H, int(cy + r + stroke + aa + 1))
    x0 = max(0, int(cx - r - stroke - aa))
    x1 = min(W, int(cx + r + stroke + aa + 1))
    half = stroke / 2
    for y in range(y0, y1):
        for x in range(x0, x1):
            d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            dist_ring = abs(d - r) - half
            alpha = max(0.0, min(1.0, 1.0 - dist_ring / aa))
            if alpha > 0:
                blend(dst, y, x, pr, pg, pb, alpha)


def fill_poly(
    dst: list[list[tuple[float, float, float, float]]],
    pts: list[tuple[float, float]],
    rgb: tuple[float, float, float],
) -> None:
    """Even-odd-ish fill using scanline intersections (convex-friendly)."""
    pr, pg, pb = rgb
    ys = [p[1] for p in pts]
    y_min, y_max = int(max(0, min(ys))), int(min(H - 1, max(ys)))
    n = len(pts)
    for y in range(y_min, y_max + 1):
        yy = y + 0.5
        xs: list[float] = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            if y1 == y2:
                continue
            if yy < min(y1, y2) or yy >= max(y1, y2):
                continue
            t = (yy - y1) / (y2 - y1)
            xi = x1 + t * (x2 - x1)
            xs.append(xi)
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa, xb = xs[k], xs[k + 1]
            x_start = max(0, int(math.floor(xa)))
            x_end = min(W, int(math.ceil(xb)))
            for x in range(x_start, x_end):
                blend(dst, y, x, pr, pg, pb, 1.0)


def stroke_line(
    dst: list[list[tuple[float, float, float, float]]],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    stroke: float,
    rgb: tuple[float, float, float],
) -> None:
    pr, pg, pb = rgb
    length = math.hypot(x1 - x0, y1 - y0)
    if length < 1e-6:
        return
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    px, py = -uy, ux
    half = stroke / 2
    # parallelogram as quad
    p1 = (x0 + px * half, y0 + py * half)
    p2 = (x0 - px * half, y0 - py * half)
    p3 = (x1 - px * half, y1 - py * half)
    p4 = (x1 + px * half, y1 + py * half)
    fill_poly(dst, [p1, p2, p3, p4], rgb)
    fill_circle(dst, x0, y0, half, rgb)
    fill_circle(dst, x1, y1, half, rgb)


def draw_home(dst: list[list[tuple[float, float, float, float]]], rgb: tuple[float, float, float]) -> None:
    # Material Home filled: wide roof + body (24dp grid, ~Material baseline proportions)
    k = SCALE
    fill_poly(
        dst,
        [
            (9 * k, 12 * k),
            (15 * k, 12 * k),
            (15 * k, 21 * k),
            (9 * k, 21 * k),
        ],
        rgb,
    )
    fill_poly(
        dst,
        [
            (5 * k, 12 * k),
            (12 * k, 4.5 * k),
            (19 * k, 12 * k),
        ],
        rgb,
    )


def draw_auto_awesome(dst: list[list[tuple[float, float, float, float]]], rgb: tuple[float, float, float]) -> None:
    k = SCALE
    # Four sparkles (Material auto_awesome layout, simplified crosses/diamonds as small quads)
    def sparkle(cx: float, cy: float, s: float) -> None:
        fill_poly(dst, [(cx, cy - s), (cx + s * 0.45, cy), (cx, cy + s), (cx - s * 0.45, cy)], rgb)
        fill_poly(dst, [(cx - s, cy), (cx, cy - s * 0.45), (cx + s, cy), (cx, cy + s * 0.45)], rgb)

    sparkle(6.5 * k, 6.5 * k, 2.8 * k)
    sparkle(17.5 * k, 7 * k, 2.2 * k)
    sparkle(8 * k, 17 * k, 2.5 * k)
    sparkle(17 * k, 16 * k, 3.0 * k)


def draw_search(dst: list[list[tuple[float, float, float, float]]], rgb: tuple[float, float, float]) -> None:
    k = SCALE
    cx, cy = 10.5 * k, 10.5 * k
    r = 3.8 * k
    stroke = 1.35 * k
    stroke_circle(dst, cx, cy, r, stroke, rgb, aa=1.0)
    # handle down-right
    ang = math.pi / 4
    x0 = cx + (r - stroke * 0.3) * math.cos(ang)
    y0 = cy + (r - stroke * 0.3) * math.sin(ang)
    x1 = cx + (r + 3.2 * k) * math.cos(ang)
    y1 = cy + (r + 3.2 * k) * math.sin(ang)
    stroke_line(dst, x0, y0, x1, y1, stroke, rgb)


def draw_star(dst: list[list[tuple[float, float, float, float]]], rgb: tuple[float, float, float]) -> None:
    """Filled 5-point star (Material Star): 5 triangles from center to outer arc."""
    k = SCALE
    cx, cy = 12 * k, 12 * k
    outer = 5.0 * k
    for i in range(5):
        a1 = -math.pi / 2 + i * (2 * math.pi / 5)
        a2 = -math.pi / 2 + (i + 1) * (2 * math.pi / 5)
        p1 = (cx + outer * math.cos(a1), cy + outer * math.sin(a1))
        p2 = (cx + outer * math.cos(a2), cy + outer * math.sin(a2))
        fill_poly(dst, [(cx, cy), p1, p2], rgb)


def draw_settings(dst: list[list[tuple[float, float, float, float]]], rgb: tuple[float, float, float]) -> None:
    """Gear approximating Material Settings (filled)."""
    k = SCALE
    cx, cy = 12 * k, 12 * k
    body_r = 5.0 * k
    hole_r = 2.0 * k
    fill_circle(dst, cx, cy, body_r, rgb)
    # punch center hole
    for y in range(H):
        for x in range(W):
            if math.hypot(x + 0.5 - cx, y + 0.5 - cy) < hole_r:
                dst[y][x] = (0.0, 0.0, 0.0, 0.0)
    # six teeth — short outward trapezoids
    inner_r = body_r * 0.88
    outer_r = body_r + 1.35 * k
    teeth = 6
    for i in range(teeth):
        a0 = (i - 0.22) * (2 * math.pi / teeth) - math.pi / 2
        a1 = (i + 0.22) * (2 * math.pi / teeth) - math.pi / 2
        fill_poly(
            dst,
            [
                (cx + inner_r * math.cos(a0), cy + inner_r * math.sin(a0)),
                (cx + outer_r * math.cos(a0), cy + outer_r * math.sin(a0)),
                (cx + outer_r * math.cos(a1), cy + outer_r * math.sin(a1)),
                (cx + inner_r * math.cos(a1), cy + inner_r * math.sin(a1)),
            ],
            rgb,
        )


def norm_rgb(t: tuple[int, int, int]) -> tuple[float, float, float]:
    return t[0] / 255.0, t[1] / 255.0, t[2] / 255.0


def render_pair(
    name: str,
    draw_fn,
    out_dir: str,
) -> None:
    for suffix, color in (("", COLOR_INACTIVE), ("-active", COLOR_ACTIVE)):
        buf = [[(0.0, 0.0, 0.0, 0.0) for _ in range(W)] for _ in range(H)]
        rgb = norm_rgb(color)
        draw_fn(buf, rgb)
        rows = downsample(buf)
        path = os.path.join(out_dir, f"tab-{name}{suffix}.png")
        write_png_rgba(path, OUT, OUT, rows)
        print("wrote", path)


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    img_dir = os.path.join(root, "images")
    os.makedirs(img_dir, exist_ok=True)
    pairs = [
        ("home", draw_home),
        ("daily", draw_auto_awesome),
        ("search", draw_search),
        ("saved", draw_star),
        ("settings", draw_settings),
    ]
    for name, fn in pairs:
        render_pair(name, fn, img_dir)


if __name__ == "__main__":
    main()
