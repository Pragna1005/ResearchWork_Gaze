"""Render every study paragraph exactly as the session will show it, to PNG files.

    python preview_materials.py            # uses this computer's screen size
    python preview_materials.py 1920x1080
    python preview_materials.py --all      # every item in study_items.json, not only those in use

By default only the items used in the session (study/config.py: ONESTOP_ARTICLES,
SPECIALIST_IDS; both versions of each article) and the practice paragraphs.
Writes previews/<item_id>.png and prints the number of lines per paragraph.
Use it before the pilot: check each excerpt reads well, nothing is cut off,
and the longest paragraph still fits on the screen.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from study import config as C  # noqa: E402
from study.layout import wrap  # noqa: E402
from study.materials import load_items, select_items  # noqa: E402


def main():
    args = sys.argv[1:]
    use_all = "--all" in args
    args = [a for a in args if a != "--all"]
    pygame.init()
    if args:
        w, h = (int(v) for v in args[0].lower().split("x"))
    else:
        w, h = pygame.display.get_desktop_sizes()[0]
    path = pygame.font.match_font(C.FONT_NAME)
    font = pygame.font.Font(path, C.FONT_SIZE) if path else pygame.font.Font(None, C.FONT_SIZE)
    pitch = int(round(C.FONT_SIZE * C.LINE_SPACING))
    left = max(40, (w - C.TEXT_WIDTH) // 2)
    width = min(C.TEXT_WIDTH, w - 2 * left)
    items = load_items() if use_all else select_items(load_items())
    paras = []
    for a in items["onestop_articles"]:
        for p in a["paragraphs"]:
            for lvl in ("Ele", "Adv"):
                paras.append((f"OS-{a['article']}-p{p['p_index']}-{lvl.upper()}", p[lvl]["text"]))
    paras += [(s["id"], s["text"]) for s in items["specialist"]]
    paras += [(p["id"], p["text"]) for p in items["practice"]]
    out = os.path.join(HERE, "previews")
    os.makedirs(out, exist_ok=True)
    worst = 0
    for pid, text in paras:
        lines = wrap(font, text, left, C.TEXT_TOP, width, pitch)
        bottom = lines[-1]["band_y1"]
        worst = max(worst, bottom)
        surf = pygame.Surface((w, h))
        surf.fill(C.BACKGROUND)
        for ln in lines:
            surf.blit(font.render(ln["text"], True, C.TEXT_COLOR), (ln["x0"], ln["y0"]))
            pygame.draw.rect(surf, (225, 225, 225), (ln["x0"] - 4, ln["band_y0"], ln["x1"] - ln["x0"] + 8, pitch), 1)
        pygame.image.save(surf, os.path.join(out, f"{pid}.png"))
        flag = "  <-- DOES NOT FIT" if bottom > h - 40 else ""
        print(f"{pid:<22} {len(lines):>2} lines, ends at y={bottom}{flag}")
    print(f"\nscreen {w}x{h}, font {path}, line pitch {pitch}px; lowest text at y={worst} "
          f"({'fits' if worst <= h - 40 else 'TOO LONG: reduce FONT_SIZE or LINE_SPACING in study/config.py'})")
    print(f"PNG files in {out} (grey boxes = the line areas used to map gaze to lines)")


if __name__ == "__main__":
    main()
