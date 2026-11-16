"""Check the trial-list design rules (no screen, no tracker, a few seconds).

    python tests/test_plan.py          # checks, then prints half-assignment counts over P01-P16
    python -m pytest tests/test_plan.py

Rules (see study/materials.py): 24 main paragraphs = 4 articles (2 Ele + 2 Adv per
reader, never both versions) + 8 excerpts (2 per domain); each half has 1 Ele
article, 1 Adv article and one excerpt per domain; lists A / B swap the levels;
article paragraphs stay together and in order; the plan is reproducible; which
item goes in the first half is balanced over P01-P16.
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from study import config as C  # noqa: E402
from study.materials import build_plan, load_items  # noqa: E402

PIDS = [f"P{i:02d}" for i in range(1, 41)]
BALANCE_PIDS = [f"P{i:02d}" for i in range(1, 17)]
DOMAINS = ("Medicine", "Law", "Philosophy", "Economics")


def check_plan(plan, n_articles, n_spec_per_domain):
    main = plan["main"]
    n_paras = 4 * n_articles + n_spec_per_domain * len(DOMAINS)
    assert len(main) == n_paras, (plan["participant"], len(main))
    assert [t["trial"] for t in main] == list(range(1, n_paras + 1))
    assert plan["break_after_trial"] == sum(t["half"] == 1 for t in main)

    levels = {}
    for t in main:
        if t["kind"] == "onestop":
            levels.setdefault(t["article"], set()).add(t["level"])
    assert len(levels) == n_articles
    assert all(len(v) == 1 for v in levels.values()), "an article was read at both levels"
    lv = Counter(next(iter(v)) for v in levels.values())
    assert lv == {"Ele": n_articles // 2, "Adv": n_articles // 2}, lv

    for h in (1, 2):
        ts = [t for t in main if t["half"] == h]
        arts = {(t["article"], t["level"]) for t in ts if t["kind"] == "onestop"}
        assert Counter(l for _, l in arts) == {"Ele": n_articles // 4, "Adv": n_articles // 4}, (h, arts)
        dom = Counter(t["topic"] for t in ts if t["kind"] == "specialist")
        assert dom == {d: n_spec_per_domain // 2 for d in DOMAINS}, (h, dom)

    # paragraphs of one article: consecutive, in order, one block
    for art in levels:
        idx = [i for i, t in enumerate(main) if t["article"] == art]
        assert idx == list(range(idx[0], idx[0] + len(idx))), art
        assert [main[i]["p_index"] for i in idx] == sorted(main[i]["p_index"] for i in idx), art
        assert len({main[i]["block"] for i in idx}) == 1, art
    assert all(t["question"] for t in main if t["kind"] == "onestop")
    assert len(plan["practice"]) == len(load_items()["practice"])


def test_24_paragraph_design():
    for pid in PIDS:
        check_plan(build_plan(pid), n_articles=4, n_spec_per_domain=2)


def test_kept_items_match_config():
    plan = build_plan("P01")
    assert {t["article"] for t in plan["main"] if t["kind"] == "onestop"} == set(C.ONESTOP_ARTICLES)
    assert {t["item_id"] for t in plan["main"] if t["kind"] == "specialist"} == set(C.SPECIALIST_IDS)


def test_lists_swap_levels():
    a, b = build_plan("P01"), build_plan("P02")
    assert (a["list"], b["list"]) == ("A", "B")
    lev = lambda p: {t["article"]: t["level"] for t in p["main"] if t["kind"] == "onestop"}  # noqa: E731
    la, lb = lev(a), lev(b)
    assert la.keys() == lb.keys()
    assert all({la[k], lb[k]} == {"Ele", "Adv"} for k in la)
    half = len(C.ONESTOP_ARTICLES) // 2
    assert all(la[k] == "Ele" for k in C.ONESTOP_ARTICLES[:half])


def test_reproducible_and_varies():
    assert build_plan("P07") == build_plan("P07")
    orders = {tuple(t["item_id"] for t in build_plan(p)["main"]) for p in PIDS}
    assert len(orders) == len(PIDS)


def test_full_48_still_works():
    for pid in PIDS[:16]:
        check_plan(build_plan(pid, articles=[], specialist_ids=[]), n_articles=8, n_spec_per_domain=4)


def first_half_counts(pids=BALANCE_PIDS):
    """(level, item) -> [readers who see it, readers who see it in the first half]."""
    counts = {}
    for pid in pids:
        plan = build_plan(pid)
        for t in plan["main"]:
            if t["kind"] == "onestop" and t["p_index"] != 0:
                continue
            key = (t["level"], t["article"] or t["item_id"])
            c = counts.setdefault(key, [0, 0])
            c[0] += 1
            c[1] += t["half"] == 1
    return counts


def test_half_assignment_balanced():
    for key, (seen, first) in first_half_counts().items():
        assert seen == 8 if key[0] != "Spec" else seen == 16, (key, seen)
        assert first * 2 == seen, f"{key}: first half for {first} of {seen} readers"
    # every (first Ele article, first Adv article) combination occurs within each list
    for lst in ("A", "B"):
        combos = Counter()
        for pid in BALANCE_PIDS:
            plan = build_plan(pid)
            if plan["list"] != lst:
                continue
            h1 = {t["level"]: t["article"] for t in plan["main"] if t["half"] == 1 and t["kind"] == "onestop"}
            combos[(h1["Ele"], h1["Adv"])] += 1
        assert len(combos) == 4 and set(combos.values()) == {2}, (lst, combos)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok   {t.__name__}")
    print(f"\nFirst-half assignment over {BALANCE_PIDS[0]}-{BALANCE_PIDS[-1]}:")
    print(f"  {'level':<5} {'item':<10} {'readers':>7} {'1st half':>8} {'2nd half':>8}")
    for (lvl, item), (seen, first) in sorted(first_half_counts().items()):
        print(f"  {lvl:<5} {item:<10} {seen:>7} {first:>8} {seen - first:>8}")
    print("\nall tests passed")
