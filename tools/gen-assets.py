#!/usr/bin/env python3
"""生成站点图标（favicon / PWA / iOS）与社交预览图。

设计基调「纸墨·青」：青绿底 #0f766e 上的白色衬线字母 D，配一条纸色短线；
社交预览图沿用首页 hero 的版式（竖强调条 + 衬线站名 + 点阵纹理 + 「记」水印）。

用法：python3 tools/gen-assets.py      （需要 Pillow，字体用系统的 Noto Serif/Sans CJK）
产物：
  assets/img/favicons/favicon.svg
  assets/img/favicons/favicon.ico           16/32/48
  assets/img/favicons/favicon-96x96.png
  assets/img/favicons/apple-touch-icon.png  180
  assets/img/favicons/web-app-manifest-192x192.png
  assets/img/favicons/web-app-manifest-512x512.png  （maskable，满幅不留圆角）
  assets/img/social-preview.png             1200×630
"""
from PIL import Image, ImageDraw, ImageFont
import pathlib

REPO = pathlib.Path("/home/dasein/blog")
OUT = REPO / "assets" / "img"
FAV = OUT / "favicons"
FAV.mkdir(parents=True, exist_ok=True)

SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
TEAL = (15, 118, 110)
TEAL_DARK = (10, 92, 86)
PAPER = (252, 251, 248)
INK = (31, 29, 26)
MUTED = (114, 109, 99)


def serif(size, weight=2):
    return ImageFont.truetype(SERIF, size, index=2)


def sans(size, index=2):
    return ImageFont.truetype(SANS, size, index=index)


def rounded(size, radius_ratio=0.22, bg=TEAL, glyph="D", glyph_ratio=0.60):
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 竖向渐变：上浅下深
    grad = Image.new("RGBA", (1, s))
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        t = y / (s - 1)
        gd.point((0, y), fill=(
            round(TEAL[0] * (1 - t) + TEAL_DARK[0] * t),
            round(TEAL[1] * (1 - t) + TEAL_DARK[1] * t),
            round(TEAL[2] * (1 - t) + TEAL_DARK[2] * t),
            255,
        ))
    grad = grad.resize((s, s))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, s - 1, s - 1), radius=int(s * radius_ratio), fill=255
    )
    img.paste(grad, (0, 0), mask)

    f = serif(int(s * glyph_ratio))
    bbox = d.textbbox((0, 0), glyph, font=f)
    gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(
        ((s - gw) / 2 - bbox[0], (s - gh) / 2 - bbox[1] - s * 0.012),
        glyph,
        font=f,
        fill=(255, 255, 255, 255),
    )
    # 字下的纸色短线，呼应站名下的强调条
    bar_w, bar_h = int(s * 0.20), max(2, int(s * 0.022))
    bx = (s - bar_w) / 2
    by = (s - gh) / 2 + gh * 0.98
    d.rounded_rectangle((bx, by, bx + bar_w, by + bar_h), radius=bar_h / 2, fill=(252, 251, 248, 235))
    return img.resize((size, size), Image.LANCZOS)


def maskable(size):
    s = size * 4
    img = Image.new("RGB", (s, s), TEAL)
    d = ImageDraw.Draw(img)
    f = serif(int(s * 0.52))
    bbox = d.textbbox((0, 0), "D", font=f)
    gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((s - gw) / 2 - bbox[0], (s - gh) / 2 - bbox[1]), "D", font=f, fill=(255, 255, 255))
    return img.resize((size, size), Image.LANCZOS)


rounded(96).save(FAV / "favicon-96x96.png")
rounded(192).save(FAV / "web-app-manifest-192x192.png")
rounded(180).save(FAV / "apple-touch-icon.png")
maskable(512).save(FAV / "web-app-manifest-512x512.png")

ico = rounded(256)
ico.save(FAV / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="我的技术博客">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#128a80"/>
      <stop offset="1" stop-color="#0a5c56"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="112" fill="url(#g)"/>
  <text x="256" y="352" text-anchor="middle"
        font-family="Georgia, 'Noto Serif SC', 'Times New Roman', serif"
        font-weight="700" font-size="300" fill="#ffffff">D</text>
  <rect x="204" y="368" width="104" height="11" rx="5.5" fill="#fcfbf8" opacity="0.92"/>
</svg>
"""
(FAV / "favicon.svg").write_text(svg)

# ---------- 社交预览图 1200×630 ----------
W, H = 1200, 630
card = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(card, "RGBA")

# 右上角青色光晕
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
for r in range(520, 0, -12):
    a = int(9 * (1 - r / 520))
    gd.ellipse((W - 260 - r, -140 - r, W - 260 + r, -140 + r), fill=(15, 118, 110, a))
card = Image.alpha_composite(card.convert("RGBA"), glow)

# 点阵纹理（右下）
dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
dd = ImageDraw.Draw(dots)
for x in range(720, W, 26):
    for y in range(200, H, 26):
        dd.ellipse((x, y, x + 3, y + 3), fill=(47, 45, 41, 26))
card = Image.alpha_composite(card, dots)

d = ImageDraw.Draw(card, "RGBA")

# 左侧强调竖条
d.rounded_rectangle((88, 132, 96, 470), radius=4, fill=TEAL)

# eyebrow
f_eye = sans(23)
d.text((132, 148), "PERSONAL  BLOG  ·  技术笔记", font=f_eye, fill=TEAL)

# 标题
f_title = serif(96)
d.text((128, 196), "我的技术博客", font=f_title, fill=INK)

# 分隔线
d.line((132, 350, 700, 350), fill=(236, 231, 221), width=2)

# 标语
f_tag = sans(34)
d.text((132, 380), "记录学习与折腾", font=f_tag, fill=MUTED)

# 站点地址
f_url = sans(26)
d.text((132, 470), "onedasein.github.io", font=f_url, fill=(15, 118, 110))

# 右侧巨大的“记”水印（单独图层做半透明叠加）
mark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
md = ImageDraw.Draw(mark)
f_mark = serif(360)
md.text((830, 200), "记", font=f_mark, fill=(15, 118, 110, 20))
card = Image.alpha_composite(card, mark)

card.convert("RGB").save(OUT / "social-preview.png", optimize=True)
print("done")
