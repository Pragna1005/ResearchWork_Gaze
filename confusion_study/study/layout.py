"""Word wrapping that records where every line and word is drawn.

Each line dict:
  text, x0, x1                 horizontal extent of the drawn text
  y0, y1                       the glyph box (what you see)
  band_y0, band_y1             the full line pitch around it - the AOI used to
                               decide which line a gaze point is on
  words: [(word, x0, x1), ...]
"""


def wrap(font, text, left, top, width, pitch):
    words = text.split()
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and font.size(trial)[0] > width:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    glyph_h = font.get_height()
    out = []
    for i, ws in enumerate(lines):
        band_y0 = top + i * pitch
        y0 = band_y0 + (pitch - glyph_h) // 2
        line_text = " ".join(ws)
        word_boxes = []
        for j, w in enumerate(ws):
            start = font.size(" ".join(ws[:j]) + (" " if j else ""))[0] if j else 0
            word_boxes.append((w, left + start, left + start + font.size(w)[0]))
        out.append({"index": i, "text": line_text, "x0": left, "x1": left + font.size(line_text)[0],
                    "y0": y0, "y1": y0 + glyph_h, "band_y0": band_y0, "band_y1": band_y0 + pitch,
                    "words": word_boxes})
    return out


def line_at(lines, x, y, x_margin=60):
    """Index of the line whose band contains (x, y), or None."""
    if x is None or y is None:
        return None
    for ln in lines:
        if ln["band_y0"] <= y < ln["band_y1"] and ln["x0"] - x_margin <= x <= ln["x1"] + x_margin:
            return ln["index"]
    return None


def word_at(lines, x, y):
    li = line_at(lines, x, y, x_margin=0)
    if li is None:
        return None
    for j, (w, x0, x1) in enumerate(lines[li]["words"]):
        if x0 - 6 <= x <= x1 + 6:
            return j
    return None
