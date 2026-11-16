"""Turn materials/study_items.json into one participant's trial list.

Design (slides: Factors, Session protocol), 24 main paragraphs:
  * The items used are chosen in study/config.py (ONESTOP_ARTICLES,
    SPECIALIST_IDS); study_items.json keeps every item. None = use all of them
    (8 articles + 16 excerpts = 48 paragraphs).
  * 4 OneStop articles x 4 paragraphs. Each reader sees half the articles in the
    Elementary version and half in the Advanced version, never both versions of
    an article. List A / list B swap which half is which (odd / even participant
    number), so across readers every article is read at both levels.
  * 8 specialist excerpts (2 each: medicine, law, philosophy, economics).
  * Paragraphs of one article stay together and in their original order (read
    out of order they would be confusing for the wrong reason). The blocks -
    articles and single excerpts - are shuffled.
  * Each half of the session (before / after the break) gets 1 Elementary
    article, 1 Advanced article and 4 excerpts (one per domain), so difficulty
    is not tied to fatigue. Which article / excerpt goes in which half is
    counterbalanced by participant number (half_swaps), balanced over every 16
    consecutive ids. Block order within a half is shuffled, seeded by the
    participant id, so the whole plan can be reproduced.
"""
import json
import os
import random
import re
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.path.join(HERE, "..", "materials", "study_items.json")

TOPICS = [  # (key used in the trial list, wording in the questionnaire)
    ("Medicine", "Medicine and the human body"),
    ("Law", "Law"),
    ("Philosophy", "Philosophy"),
    ("Economics", "Economics"),
    ("News", "News and current affairs"),
]


def load_items(path=ITEMS):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def select_items(items, articles=None, specialist_ids=None):
    """The items used in the session, in the order given (None = all, in file order)."""
    from . import config as C
    articles = C.ONESTOP_ARTICLES if articles is None else articles
    specialist_ids = C.SPECIALIST_IDS if specialist_ids is None else specialist_ids
    out = dict(items)
    if articles:
        by = {a["article"]: a for a in items["onestop_articles"]}
        missing = [a for a in articles if a not in by]
        if missing:
            raise ValueError(f"ONESTOP_ARTICLES not in study_items.json: {missing}")
        out["onestop_articles"] = [by[a] for a in articles]
    if specialist_ids:
        by = {s["id"]: s for s in items["specialist"]}
        missing = [s for s in specialist_ids if s not in by]
        if missing:
            raise ValueError(f"SPECIALIST_IDS not in study_items.json: {missing}")
        out["specialist"] = [by[s] for s in specialist_ids]
    if len(out["onestop_articles"]) % 4:
        raise ValueError("need a multiple of 4 articles (Ele/Adv x two halves)")
    counts = {}
    for s in out["specialist"]:
        counts[s["domain"]] = counts.get(s["domain"], 0) + 1
    if any(n % 2 for n in counts.values()):
        raise ValueError(f"need an even number of excerpts per domain (one half each): {counts}")
    return out


def _participant_number(pid):
    digits = re.sub(r"\D", "", pid)
    return int(digits) if digits else zlib.crc32(pid.encode())


def participant_list(pid):
    return "A" if _participant_number(pid) % 2 == 1 else "B"


def half_swaps(pid):
    """Which item of each pair goes in the first half, counterbalanced over participants.

    k = the reader's position within their list (P01, P03, P05 ... -> 0, 1, 2 ...).
    Its three lowest bits, and their XORs, give six on/off switches; each is on
    for exactly half of every 8 consecutive readers of a list, so over P01-P16
    every item is in the first half for half of the readers who see it.
    Returns (swap_ele, swap_adv, [swap per domain, in item-file order]).
    """
    k = (_participant_number(pid) - 1) // 2
    b0, b1, b2 = k & 1, (k >> 1) & 1, (k >> 2) & 1
    return bool(b0), bool(b1), [bool(x) for x in (b2, b0 ^ b1, b0 ^ b2, b1 ^ b2)]


def _split(xs, swap):
    """First and second half of xs; swapped when swap is True."""
    a, b = xs[:len(xs) // 2], xs[len(xs) // 2:]
    return (b, a) if swap else (a, b)


def _onestop_trial(art, para, level):
    v = para[level]
    return {"item_id": f"OS-{art['article']}-p{para['p_index']}-{level.upper()}", "kind": "onestop",
            "level": level, "article": art["article"], "article_title": art["title"], "p_index": para["p_index"],
            "topic": "News", "text": v["text"], "n_words": v["n_words"], "fk_grade": v["fk_grade"],
            "question": para["question"]}


def _specialist_trial(s):
    return {"item_id": s["id"], "kind": "specialist", "level": "Spec", "article": "", "article_title": "",
            "p_index": "", "topic": s["domain"], "text": s["text"], "n_words": s["n_words"],
            "fk_grade": s["fk_grade"], "question": None, "source": s["source"]}


def build_plan(pid, items=None, articles=None, specialist_ids=None):
    """articles / specialist_ids: override config (None = config; [] = every item)."""
    items = select_items(items or load_items(), articles, specialist_ids)
    lst = participant_list(pid)
    seed = zlib.crc32(pid.encode())
    rng = random.Random(seed)

    arts = items["onestop_articles"]
    half = len(arts) // 2
    ele_arts, adv_arts = (arts[:half], arts[half:]) if lst == "A" else (arts[half:], arts[:half])
    swap_ele, swap_adv, swap_dom = half_swaps(pid)
    ele_halves = _split(ele_arts, swap_ele)
    adv_halves = _split(adv_arts, swap_adv)
    # excerpts: half of every domain goes to each half of the session
    domains = {}
    for s in items["specialist"]:
        domains.setdefault(s["domain"], []).append(s)
    if len(domains) > len(swap_dom):
        raise ValueError(f"half_swaps() balances at most {len(swap_dom)} domains, got {len(domains)}")
    spec_halves = [[], []]
    for d, swap in zip(domains.values(), swap_dom):
        first, second = _split(d, swap)
        spec_halves[0] += first
        spec_halves[1] += second

    halves = []
    for h in range(2):
        e, a, s = ele_halves[h], adv_halves[h], spec_halves[h]
        blocks = [[_onestop_trial(art, p, "Ele") for p in art["paragraphs"]] for art in e]
        blocks += [[_onestop_trial(art, p, "Adv") for p in art["paragraphs"]] for art in a]
        blocks += [[_specialist_trial(x)] for x in s]
        rng.shuffle(blocks)
        halves.append(blocks)

    main = []
    for h, blocks in enumerate(halves, start=1):
        for b, block in enumerate(blocks, start=1):
            for tr in block:
                tr.update(phase="main", half=h, block=f"H{h}B{b:02d}")
                main.append(tr)
    for i, tr in enumerate(main, start=1):
        tr["trial"] = i
        if tr["question"]:
            order = list(range(len(tr["question"]["options"])))
            rng.shuffle(order)
            tr["option_order"] = order  # option_order[k] = index in the source list shown at position k

    practice = []
    for i, p in enumerate(items["practice"], start=1):
        tr = {"trial": f"P{i}", "phase": "practice", "half": 0, "block": "practice", "item_id": p["id"],
              "kind": p["kind"], "level": p.get("level", "Spec"), "article": "", "article_title": p.get("title", ""),
              "p_index": "", "topic": "News" if p["kind"] == "onestop" else p.get("domain", ""),
              "text": p["text"], "n_words": len(p["text"].split()), "fk_grade": "", "question": p.get("question")}
        if tr["question"]:
            order = list(range(len(tr["question"]["options"])))
            rng.shuffle(order)
            tr["option_order"] = order
        practice.append(tr)

    break_after = sum(1 for t in main if t["half"] == 1)
    return {"participant": pid, "list": lst, "seed": seed, "break_after_trial": break_after,
            "practice": practice, "main": main}
