#!/usr/bin/env python3
"""postkit: small helpers for drawing posts, ads and printed cards as exact-size PNGs.

Claude writes a short Python script per design that imports this module, then runs it.
Needs Pillow. Fonts come from ../assets/fonts (SIL Open Font License, see each *-OFL.txt).

    import sys; sys.path.insert(0, "<skill folder>/scripts")
    from postkit import Canvas, SIZES, look_parts
    bg, ink, accents, supports, faces = look_parts("look.json")   # the chosen look: every colour and typeface comes from it
    c = Canvas(*SIZES["instagram-post"], bg=bg, look="look.json")
    c.text((90, 120, 990, 520), "<the headline>", faces[0], "Regular", 120, color=ink, on=bg)
    c.image((90, 560, 990, 1180), None, slot="hero-photo")   # a placeholder until the student adds the image
    c.qr((90, 1200, 330, 1440), "https://<the page's address>?src=card")   # print pieces only; None until it is published
    c.save("post-a.png")                                      # prints a report: overflow, contrast, empty slots

Commands:  python3 postkit.py help   |   python3 postkit.py fonts   |   python3 postkit.py sizes

Part of Leverage by BCE. Designed and built by Nayan Kanaparthi, Berkley Center for Entrepreneurship, NYU Stern.
"""
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover
    Image = None

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.normpath(os.path.join(HERE, "..", "assets", "fonts"))

# Exact platform sizes in pixels. Print sizes are at 300 dots per inch.
SIZES = {
    "instagram-post": (1080, 1350),      # feed, 4:5
    "instagram-square": (1080, 1080),
    "story": (1080, 1920),               # Instagram and TikTok stories and reels covers, 9:16
    "linkedin-post": (1200, 627),        # link and image post
    "linkedin-square": (1200, 1200),
    "linkedin-banner": (1584, 396),      # profile or page header
    "card-quarter-letter": (1275, 1650), # 4.25 x 5.5 in, four to a letter sheet
    "card-4x6": (1200, 1800),            # 4 x 6 in postcard
    "flyer-letter": (2550, 3300),        # 8.5 x 11 in
}


def need_pillow():
    if Image is None:
        sys.exit("postkit needs Pillow. If this chat can't install it, deliver the design as an HTML file at the exact size instead.")


def list_fonts():
    out = {}
    for f in sorted(os.listdir(FONT_DIR)):
        if f.endswith(".ttf"):
            fam, _, style = f[:-4].partition("-")
            out.setdefault(fam, []).append(style)
    return out


def font(family, style="Regular", size=40):
    need_pillow()
    path = os.path.join(FONT_DIR, f"{family}-{style}.ttf")
    if not os.path.exists(path):
        path = os.path.join(FONT_DIR, f"{family}-Regular.ttf")
    if not os.path.exists(path):
        raise SystemExit(f"No font named {family}. Run: python3 postkit.py fonts")
    return ImageFont.truetype(path, int(size))


def _rgb(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def contrast(fg, bg):
    """WCAG contrast ratio between two hex colours."""
    def lum(c):
        vals = []
        for v in _rgb(c):
            v /= 255
            vals.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        r, g, b = vals
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def look_parts(path):
    """(background, text, [accents], [supports], [typefaces]) from look.json, in the order the look lists them,
    so a drawing script never types a colour by hand."""
    import json
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    by = {}
    for c in data.get("colours", []):
        by.setdefault(c.get("role"), []).append(c["hex"])
    return (by.get("background", ["#FFFFFF"])[0], by.get("text", ["#000000"])[0],
            by.get("accent", []), by.get("support", []), [k["family"] for k in data.get("type", [])])


# ---- QR codes ----
# Why it is built in: print pieces need a code that opens the page, and the chats students use can't count on a QR
# library being installed. This writes the standard (ISO/IEC 18004) code itself: byte mode, error correction M,
# versions 1 to 9, which holds an address of up to 180 bytes. tests/test_qr.py reads every size back with OpenCV.
QR_MAX_BYTES = 180
_QR_M = {  # version: (error-correction codewords per block, [(blocks, data codewords in each), ...])
    1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
    6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
}
_QR_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46]}
_GF_EXP, _GF_LOG = [0] * 512, [0] * 256
_v = 1
for _i in range(255):
    _GF_EXP[_i], _GF_LOG[_v] = _v, _i
    _v <<= 1
    if _v & 0x100:
        _v ^= 0x11D
for _i in range(255, 512):
    _GF_EXP[_i] = _GF_EXP[_i - 255]


def _gf_mul(a, b):
    return 0 if a == 0 or b == 0 else _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_ec(data, n):
    """The n Reed-Solomon error-correction codewords for a block of data codewords."""
    gen = [1]
    for i in range(n):
        nxt = [0] * (len(gen) + 1)
        for j, c in enumerate(gen):
            nxt[j] ^= c
            nxt[j + 1] ^= _gf_mul(c, _GF_EXP[i])
        gen = nxt
    rem = [0] * n
    for d in data:
        f = d ^ rem[0]
        rem = rem[1:] + [0]
        for j in range(n):
            rem[j] ^= _gf_mul(gen[j + 1], f)
    return rem


def _qr_format_bits(mask):
    data = mask                       # error correction M is 00, so the five data bits are just the mask number
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    return ((data << 10) | rem) ^ 0x5412


def _qr_version_bits(version):
    rem = version
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
    return (version << 12) | rem


_QR_MASKS = [
    lambda i, j: (i + j) % 2 == 0, lambda i, j: i % 2 == 0, lambda i, j: j % 3 == 0, lambda i, j: (i + j) % 3 == 0,
    lambda i, j: (i // 2 + j // 3) % 2 == 0, lambda i, j: (i * j) % 2 + (i * j) % 3 == 0,
    lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0, lambda i, j: ((i + j) % 2 + (i * j) % 3) % 2 == 0,
]


def _qr_penalty(m):
    size, score = len(m), 0
    lines = [row for row in m] + [[m[r][c] for r in range(size)] for c in range(size)]
    for line in lines:
        run = 1
        for k in range(1, size):
            if line[k] == line[k - 1]:
                run += 1
            else:
                if run >= 5:
                    score += run - 2
                run = 1
        if run >= 5:
            score += run - 2
        bits = "".join("1" if b else "0" for b in line)
        score += 40 * (bits.count("10111010000") + bits.count("00001011101"))
    for r in range(size - 1):
        for c in range(size - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    dark = sum(sum(1 for b in row if b) for row in m)
    score += 10 * int(abs(dark * 100 / (size * size) - 50) // 5)
    return score


def qr_matrix(text):
    """The QR code for text as rows of True (dark) and False (light), without the quiet zone around it."""
    data = text.encode("utf-8")
    if len(data) > QR_MAX_BYTES:
        raise ValueError(f"too long for the QR code: {len(data)} bytes, {QR_MAX_BYTES} at most")
    version = next(v for v in sorted(_QR_M) if sum(n * d for n, d in _QR_M[v][1]) - 2 >= len(data))
    ec_len, groups = _QR_M[version]
    total = sum(n * d for n, d in groups)
    bits = [0, 1, 0, 0] + [(len(data) >> k) & 1 for k in range(7, -1, -1)]
    for byte in data:
        bits += [(byte >> k) & 1 for k in range(7, -1, -1)]
    bits += [0] * min(4, total * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    words = [int("".join(map(str, bits[k:k + 8])), 2) for k in range(0, len(bits), 8)]
    pad = 0
    while len(words) < total:
        words.append((0xEC, 0x11)[pad % 2])
        pad += 1
    blocks, at = [], 0
    for n, d in groups:
        for _ in range(n):
            blocks.append(words[at:at + d])
            at += d
    ecs = [_rs_ec(b, ec_len) for b in blocks]
    stream = [b[k] for k in range(max(len(b) for b in blocks)) for b in blocks if k < len(b)]
    stream += [e[k] for k in range(ec_len) for e in ecs]
    stream_bits = [(w >> k) & 1 for w in stream for k in range(7, -1, -1)]

    size = 17 + 4 * version
    m = [[False] * size for _ in range(size)]
    fixed = [[False] * size for _ in range(size)]

    def put(row, col, dark):
        if 0 <= row < size and 0 <= col < size:
            m[row][col], fixed[row][col] = bool(dark), True

    for k in range(size):                                   # timing lines
        put(6, k, k % 2 == 0)
        put(k, 6, k % 2 == 0)
    for cr, cc in ((3, 3), (3, size - 4), (size - 4, 3)):    # the three corner squares, with their light border
        for dr in range(-4, 5):
            for dc in range(-4, 5):
                put(cr + dr, cc + dc, max(abs(dr), abs(dc)) not in (2, 4))
    centres = _QR_ALIGN[version]
    for a in centres:                                        # the small alignment squares
        for b in centres:
            if (a, b) in ((6, 6), (6, centres[-1]), (centres[-1], 6)):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    put(a + dr, b + dc, max(abs(dr), abs(dc)) != 1)

    def format_cells(mask):
        """Where the 15 format bits go (two copies), as (row, col, dark), plus the one module that is always dark."""
        f = _qr_format_bits(mask)
        bit = lambda k: (f >> k) & 1
        out = [(k, 8, bit(k)) for k in range(6)] + [(7, 8, bit(6)), (8, 8, bit(7)), (8, 7, bit(8))]
        out += [(8, 14 - k, bit(k)) for k in range(9, 15)]
        out += [(8, size - 1 - k, bit(k)) for k in range(8)]
        out += [(size - 15 + k, 8, bit(k)) for k in range(8, 15)]
        return out + [(size - 8, 8, 1)]

    for row, c, dark in format_cells(0):                     # reserves the format cells; the real bits go in below
        put(row, c, dark)
    if version >= 7:
        vb = _qr_version_bits(version)
        for k in range(18):
            a, b = size - 11 + k % 3, k // 3
            put(b, a, (vb >> k) & 1)
            put(a, b, (vb >> k) & 1)

    cells, col, upward = [], size - 1, True                  # the data path: two columns at a time, zigzag from bottom right
    while col > 0:
        if col == 6:
            col -= 1
        for row in (range(size - 1, -1, -1) if upward else range(size)):
            for c in (col, col - 1):
                if not fixed[row][c]:
                    cells.append((row, c))
        upward = not upward
        col -= 2
    for k, (row, c) in enumerate(cells):
        m[row][c] = bool(stream_bits[k]) if k < len(stream_bits) else False

    best = None
    for mask, rule in enumerate(_QR_MASKS):
        trial = [row[:] for row in m]
        for row, c in cells:
            if rule(row, c):
                trial[row][c] = not trial[row][c]
        for row, c, dark in format_cells(mask):
            trial[row][c] = bool(dark)
        score = _qr_penalty(trial)
        if best is None or score < best[0]:
            best = (score, trial)
    return best[1]


class Canvas:
    def __init__(self, width, height, bg="#FFFFFF", margin=None, look=None):
        need_pillow()
        self.w, self.h = int(width), int(height)
        self.bg = bg
        # look: the path to look.json. With it, every colour and typeface used is checked against the chosen look,
        # so the page, the posts and the print pieces can't drift apart (OFF LOOK in the report).
        self.look_colours, self.look_fonts, self.off_look = None, None, []
        self.look_bg, self.look_ink, self.look_label_font = None, None, None
        if look:
            import json
            with open(look, encoding="utf-8") as f:
                data = json.load(f)
            self.look_colours = {self._norm(c["hex"]) for c in data.get("colours", [])}
            self.look_fonts = {k["family"] for k in data.get("type", [])}
            self.look_label_font = data["type"][-1]["family"] if data.get("type") else None
            roles = {c.get("role"): c["hex"] for c in data.get("colours", [])}
            self.look_bg, self.look_ink = roles.get("background"), roles.get("text")
            self._see(bg)
        self.img = Image.new("RGB", (self.w, self.h), _rgb(bg))
        self.draw = ImageDraw.Draw(self.img)
        self.margin = int(margin if margin is not None else round(min(self.w, self.h) * 0.06))
        self.notes = []
        self.text_boxes = []
        self.slots = []

    # ---- the chosen look ----
    @staticmethod
    def _norm(c):
        c = c.strip().lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        return "#" + c.upper()

    def _see(self, colour):
        if self.look_colours is not None and colour:
            c = self._norm(colour)
            if c not in self.look_colours and ("colour " + c) not in self.off_look:
                self.off_look.append("colour " + c)

    def _see_font(self, family):
        if self.look_fonts is not None and family not in self.look_fonts and ("typeface " + family) not in self.off_look:
            self.off_look.append("typeface " + family)

    def colour(self, c):
        """A colour for shapes drawn through .draw: checked against the look, returned as an RGB tuple."""
        self._see(c)
        return _rgb(c)

    # ---- shapes ----
    def rect(self, box, fill=None, radius=0, outline=None, width=0):
        self._see(fill)
        self._see(outline)
        fill = _rgb(fill) if fill else None
        outline = _rgb(outline) if outline else None
        if radius:
            self.draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
        else:
            self.draw.rectangle(box, fill=fill, outline=outline, width=width)

    def line(self, xy, color="#000000", width=2):
        self._see(color)
        self.draw.line(xy, fill=_rgb(color), width=width)

    # ---- text ----
    def _wrap(self, text, fnt, max_w, tracking):
        lines = []
        for para in text.split("\n"):
            words, cur = para.split(), ""
            for w in words:
                trial = (cur + " " + w).strip()
                if self._width(trial, fnt, tracking) <= max_w or not cur:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
        return lines

    def _width(self, s, fnt, tracking):
        return self.draw.textlength(s, font=fnt) + tracking * max(len(s) - 1, 0)

    def text(self, box, text, family, style="Regular", size=60, color="#000000", on=None, min_size=None,
             align="left", valign="top", line_height=1.15, tracking=0):
        """Fit text into box (x0, y0, x1, y1), shrinking from size down to min_size. `on` is the colour behind it,
        for the contrast check. Returns the size used."""
        self._see(color)
        self._see(on)
        self._see_font(family)
        x0, y0, x1, y1 = box
        max_w, max_h = x1 - x0, y1 - y0
        min_size = min_size or max(12, int(size * 0.55))
        s = int(size)
        while True:
            fnt = font(family, style, s)
            lines = self._wrap(text, fnt, max_w, tracking)
            asc, desc = fnt.getmetrics()
            lh = int((asc + desc) * line_height)
            total = lh * len(lines)
            widest = max(self._width(l, fnt, tracking) for l in lines) if lines else 0
            if (total <= max_h and widest <= max_w) or s <= min_size:
                break
            s -= 2
        if total > max_h or widest > max_w:
            self.notes.append(f"OVERFLOW: '{text[:40]}' does not fit its box even at {s}px. Shorten it or enlarge the box.")
        y = y0 if valign == "top" else (y0 + (max_h - total) // 2 if valign == "middle" else y1 - total)
        for l in lines:
            lw = self._width(l, fnt, tracking)
            x = x0 if align == "left" else (x0 + (max_w - lw) / 2 if align == "center" else x1 - lw)
            if tracking:
                cx = x
                for ch in l:
                    self.draw.text((cx, y), ch, font=fnt, fill=_rgb(color))
                    cx += self.draw.textlength(ch, font=fnt) + tracking
            else:
                self.draw.text((x, y), l, font=fnt, fill=_rgb(color))
            y += lh
        if on:
            ratio = contrast(color, on)
            need = 3.0 if s >= 48 else 4.5
            if ratio < need:
                self.notes.append(f"LOW CONTRAST: '{text[:40]}' is {ratio:.1f}:1 on {on}, needs {need}:1.")
        if s < 0.022 * self.w and self.w >= 1000:
            self.notes.append(f"SMALL TEXT: '{text[:40]}' is {s}px on a {self.w}px canvas. It will be hard to read on a phone.")
        self.text_boxes.append((x0, y0, x1, y0 + total, text[:30]))
        return s

    # ---- images ----
    def image(self, box, path=None, slot="image", radius=0, fit="cover", placeholder_bg=None, placeholder_ink=None):
        """Place an image cropped to fill the box. With no image yet, draw a quiet placeholder naming the slot,
        so the layout is real and the student knows exactly what to add."""
        self._see(placeholder_bg)
        self._see(placeholder_ink)
        x0, y0, x1, y1 = [int(v) for v in box]
        w, h = x1 - x0, y1 - y0
        if path and os.path.exists(path):
            im = Image.open(path).convert("RGB")
            im = ImageOps.fit(im, (w, h), method=Image.LANCZOS) if fit == "cover" else ImageOps.contain(im, (w, h))
            if radius:
                mask = Image.new("L", (w, h), 0)
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
                self.img.paste(im, (x0, y0), mask)
            else:
                self.img.paste(im, (x0 + (w - im.width) // 2, y0 + (h - im.height) // 2))
            self.slots.append((slot, True))
            return
        if not placeholder_bg and self.look_bg and self.look_ink:
            # a placeholder in the look's own tones: the background shifted a little toward the text colour
            b, k = _rgb(self.look_bg), _rgb(self.look_ink)
            bg = tuple(round(b[i] + (k[i] - b[i]) * 0.14) for i in range(3))
            ink = _rgb(placeholder_ink or self.look_ink)
        else:
            bg = _rgb(placeholder_bg or "#D9D6CF")
            ink = _rgb(placeholder_ink or "#5A5750")
        hatch = tuple(int(b + (i - b) * 0.12) for b, i in zip(bg, ink))
        tile = Image.new("RGB", (w, h), bg)
        td = ImageDraw.Draw(tile)
        step = max(18, w // 30)
        for k in range(0, w + h, step):
            td.line((k, 0, k - h, h), fill=hatch, width=2)
        fnt = font(self.look_label_font or "WorkSans", "Regular", max(18, w // 26))
        label = f"Your image: {slot}"
        tw = td.textlength(label, font=fnt)
        asc, desc = fnt.getmetrics()
        pad = 16
        td.rectangle(((w - tw) / 2 - pad, h / 2 - asc / 2 - pad, (w + tw) / 2 + pad, h / 2 + asc / 2 + desc + pad), fill=bg)
        td.text(((w - tw) / 2, h / 2 - asc / 2), label, font=fnt, fill=ink)
        if radius:
            mask = Image.new("L", (w, h), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
            self.img.paste(tile, (x0, y0), mask)
        else:
            self.img.paste(tile, (x0, y0))
        self.slots.append((slot, False))

    # ---- QR code (print pieces) ----
    def qr(self, box, address=None, slot="qr-code"):
        """A QR code that opens `address`, fitted in the box, in the look's own dark and light colours.
        With no address yet (the page isn't published), draws a placeholder and lists it as an empty slot."""
        x0, y0, x1, y1 = [int(v) for v in box]
        side = min(x1 - x0, y1 - y0)
        dark, light = "#000000", "#FFFFFF"
        if self.look_bg and self.look_ink:
            dark, light = sorted((self.look_bg, self.look_ink), key=lambda c: contrast(c, "#FFFFFF"), reverse=True)
        problem = None
        if address:
            if not address.lower().startswith(("https://", "http://")):
                problem = "the address must start with https://"
            elif len(address.encode("utf-8")) > QR_MAX_BYTES:
                problem = f"the address is {len(address.encode('utf-8'))} characters; a QR code here holds {QR_MAX_BYTES}. Use a shorter address"
        if not address or problem:
            if problem:
                self.notes.append(f"QR CODE: {problem}.")
            self.draw.rectangle((x0, y0, x0 + side, y0 + side), fill=_rgb(light), outline=_rgb(dark), width=max(2, side // 60))
            fnt = font(self.look_label_font or "WorkSans", "Regular", max(14, side // 11))
            words = ["QR code", "goes here", "once the page", "is published"]
            asc, desc = fnt.getmetrics()
            lh = int((asc + desc) * 1.1)
            ty = y0 + (side - lh * len(words)) // 2
            for w in words:
                tw = self.draw.textlength(w, font=fnt)
                self.draw.text((x0 + (side - tw) / 2, ty), w, font=fnt, fill=_rgb(dark))
                ty += lh
            self.slots.append((slot, False))
            return False
        grid = qr_matrix(address)
        n = len(grid) + 8                                    # four quiet squares on every side
        px = side // n
        if px < 6:
            self.notes.append(f"QR CODE: too small to scan reliably ({px}px a square). Make its box at least {n * 6}px wide.")
            px = max(px, 1)
        off = (side - px * n) // 2
        self.draw.rectangle((x0, y0, x0 + side, y0 + side), fill=_rgb(light))
        for r, row in enumerate(grid):
            for c, on in enumerate(row):
                if on:
                    gx, gy = x0 + off + (c + 4) * px, y0 + off + (r + 4) * px
                    self.draw.rectangle((gx, gy, gx + px - 1, gy + px - 1), fill=_rgb(dark))
        self.slots.append((slot, True))
        return True

    # ---- output ----
    def _checks(self):
        for item in self.off_look:
            self.notes.append(f"OFF LOOK: {item} isn't in the chosen look (look.json). Use the look's, or change the look first.")
        m = self.margin
        for (x0, y0, x1, y1, t) in self.text_boxes:
            if x0 < m or y0 < m or x1 > self.w - m or y1 > self.h - m:
                self.notes.append(f"MARGIN: '{t}' sits inside the {m}px safe margin.")
        boxes = self.text_boxes
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    self.notes.append(f"OVERLAP: '{a[4]}' overlaps '{b[4]}'.")

    def save(self, path, pdf=False, dpi=300):
        self._checks()
        self.img.save(path, dpi=(dpi, dpi))
        if pdf:
            self.img.save(os.path.splitext(path)[0] + ".pdf", "PDF", resolution=dpi)
        empty = [s for s, filled in self.slots if not filled]
        print(f"Saved {path} at {self.w}x{self.h}.")
        for n in self.notes:
            print("  " + n)
        if empty:
            print("  EMPTY IMAGE SLOTS: " + ", ".join(empty) + " (placeholders until the student adds their images"
                  + (", or gives the published page's address for the QR code" if any(e.startswith("qr") for e in empty) else "") + ").")
        if not self.notes:
            print("  No overflow, overlap, margin, contrast or off-look problems found.")
        return not self.notes


API = """postkit API
Canvas(width, height, bg="#FFFFFF", margin=None, look="look.json")   margin defaults to 6% of the short side;
        always pass look= once the student has picked a look, so every piece is checked against it
  .rect(box, fill=None, radius=0, outline=None, width=0)
  .line(xy, color="#000000", width=2)
  .text(box, text, family, style="Regular", size=60, color="#000000", on=<colour behind it>,
        min_size=None, align="left|center|right", valign="top|middle|bottom", line_height=1.15, tracking=0)
        shrinks from size to min_size (default 55% of size) until the text fits; returns the size used.
        One line needs a box about 1.6 times its size in height (two lines, about 3.2 times), or it shrinks
  .image(box, path_or_None, slot="name", radius=0, fit="cover|contain", placeholder_bg=None, placeholder_ink=None)
        crops the image to fill the box; with no file yet, draws a placeholder naming the slot
  .qr(box, "https://<the page's address>?src=card")   a QR code in the look's dark and light colours, for print pieces;
        with None (the page isn't published yet) it draws a placeholder. Up to 180 characters; at least 6px a square
  .draw   the underlying Pillow ImageDraw, for shapes the helpers don't cover
  .colour("#RRGGBB")   use this for every colour you pass to .draw, so it is checked against the look too
  .save(path, pdf=False, dpi=300)   prints a report and returns True when there are no problems
look_parts("look.json")   (background, text, [accents], [supports], [typefaces]): take every colour and typeface from here
font(family, style, size)   a Pillow font from the bundled fonts;  contrast(fg, bg)   WCAG ratio
SIZES   exact platform sizes (python3 postkit.py sizes)
Checks in the report:
  OVERFLOW     text that doesn't fit its box even at min_size
  LOW CONTRAST under 4.5:1, or under 3:1 for text 48px and over (needs on=)
  SMALL TEXT   under 2.2% of the canvas width on canvases 1000px wide or more
  MARGIN       a text box inside the safe margin
  OVERLAP      two text boxes overlapping
  EMPTY IMAGE SLOTS   placeholders still waiting for the student's images, or a QR code waiting for the page's address
  QR CODE      an address that is too long or doesn't start with https://, or a code too small to scan
  OFF LOOK     a colour or typeface that isn't in look.json (only when look= is given)
"""


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "fonts":
        for fam, styles in list_fonts().items():
            print(f"{fam}: {', '.join(styles)}")
    elif len(sys.argv) > 1 and sys.argv[1] == "help":
        print(API)
    elif len(sys.argv) > 1 and sys.argv[1] == "sizes":
        for k, (w, h) in SIZES.items():
            print(f"{k}: {w} x {h}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
