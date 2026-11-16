"""Rebuild materials/study_items.json from the original sources.

You do NOT need to run this to collect data: study_items.json is already built.
It documents exactly where every paragraph came from, so the selection can be
checked or changed. Needs: OneStopQA (github.com/berzak/onestop-qa,
annotations/onestop_qa.zip -> onestop_qa.json) and sparse clones of the four
OpenStax book repositories (github.com/openstax/osbooks-*), plus `wordfreq`.

    python build_materials.py ONESTOP_JSON OPENSTAX_DIR
"""
import json, os, re, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from readability import fk_grade

try:
    from wordfreq import zipf_frequency
except ImportError:
    zipf_frequency = None

# --- OneStop: 8 study articles (first 4 paragraphs each) + 1 practice article
STUDY_ARTICLES = [0, 1, 5, 8, 10, 11, 12, 27]
PARAGRAPHS_PER_ARTICLE = 4
PRACTICE_ARTICLE = 25          # Vienna Named World's Top City... (Intermediate level)
PRACTICE_PARAGRAPHS = [0, 1]
QUESTION_INDEX = 0             # first of the 3 OneStopQA questions, same for everyone

# --- OpenStax: (repo, module id, first words of the paragraph)
OPENSTAX_BOOKS = {
    "anatomy-physiology": ("Medicine", "Anatomy and Physiology 2e", "https://openstax.org/details/books/anatomy-and-physiology-2e"),
    "business-law": ("Law", "Business Law I Essentials", "https://openstax.org/details/books/business-law-i-essentials"),
    "introduction-philosophy": ("Philosophy", "Introduction to Philosophy", "https://openstax.org/details/books/introduction-philosophy"),
    "principles-economics-bundle": ("Economics", "Principles of Economics 3e", "https://openstax.org/details/books/principles-economics-3e"),
}
SPECIALIST = [
    ("SP-MED-1", "anatomy-physiology", "m46667", "Amine hormones are synthesized"),
    ("SP-MED-2", "anatomy-physiology", "m46496", "The liver has three main components"),
    ("SP-MED-3", "anatomy-physiology", "m46553", "Three of the cranial nerves"),
    ("SP-MED-4", "anatomy-physiology", "m46548", "Continuous with the laryngopharynx"),
    ("SP-LAW-1", "business-law", "m78877", "The Constitution empowers federal law making"),
    ("SP-LAW-2", "business-law", "m78897", "Contracts must be created for the exchange"),
    ("SP-LAW-3", "business-law", "m78896", "The promissory estoppel doctrine"),
    ("SP-LAW-4", "business-law", "m78900", "With globalization, there has been"),
    ("SP-PHI-1", "introduction-philosophy", "m00015", "Western readers should take care"),
    ("SP-PHI-2", "introduction-philosophy", "m00027", "Whatever follows"),
    ("SP-PHI-3", "introduction-philosophy", "m00033", "Today, some might think that atomism"),
    ("SP-PHI-4", "introduction-philosophy", "m00048", "The British philosopher Gertrude"),
    ("SP-ECO-1", "principles-economics-bundle", "m63942", "Monopolists are not productively efficient"),
    ("SP-ECO-2", "principles-economics-bundle", "m63610", "A production possibilities frontier defines"),
    ("SP-ECO-3", "principles-economics-bundle", "m64121", "The government need not balance"),
    ("SP-ECO-4", "principles-economics-bundle", "m63804", "The Keynesian perspective considers"),
]
PRACTICE_SPECIALIST = ("PR-PHI", "introduction-philosophy", "m00029", "Inferences can be deductive")

NS = "{http://cnx.rice.edu/cnxml}"


def stats(text):
    toks = re.findall(r"[A-Za-z][A-Za-z\-']+", text)
    rare = (sum(zipf_frequency(t.lower(), "en") < 3.2 for t in toks) / len(toks)) if zipf_frequency else None
    return {"n_words": len(text.split()), "fk_grade": fk_grade(text),
            "rare_word_share": round(rare, 3) if rare is not None else None}


def openstax_para(osdir, repo, module, start):
    root = ET.parse(os.path.join(osdir, repo, "modules", module, "index.cnxml")).getroot()
    title = root.find(f"{NS}title").text
    for p in root.iter(f"{NS}para"):
        t = " ".join("".join(p.itertext()).split())
        if t.startswith(start) or t.lstrip("“\"").startswith(start):
            return t, title
    raise SystemExit(f"not found: {repo} {module} {start!r}")


def main(onestop_json, osdir):
    data = json.load(open(onestop_json, encoding="utf-8"))["data"]
    out = {"note": "Built by build_materials.py. Texts are unmodified. OneStop answer options are "
                   "stored with the correct answer first; the app shuffles them on screen.",
           "onestop_articles": [], "specialist": [], "practice": []}
    for ai in STUDY_ARTICLES:
        art = data[ai]
        paras = []
        for pi in range(PARAGRAPHS_PER_ARTICLE):
            p = art["paragraphs"][pi]
            q = p["qas"][QUESTION_INDEX]
            paras.append({
                "p_index": pi,
                "Adv": {"text": p["Adv"]["context"], **stats(p["Adv"]["context"])},
                "Ele": {"text": p["Ele"]["context"], **stats(p["Ele"]["context"])},
                "question": {"q_index": QUESTION_INDEX, "text": q["question"], "options": q["answers"], "correct": 0},
            })
        out["onestop_articles"].append({"article": f"A{ai:02d}", "title": art["title"], "paragraphs": paras})
    for sid, repo, module, start in SPECIALIST:
        text, mtitle = openstax_para(osdir, repo, module, start)
        domain, book, url = OPENSTAX_BOOKS[repo]
        out["specialist"].append({"id": sid, "domain": domain, "text": text, **stats(text),
                                  "source": f"OpenStax, {book}, section '{mtitle}' ({module})",
                                  "url": url, "licence": "CC BY-NC-SA 4.0"})
    art = data[PRACTICE_ARTICLE]
    for pi in PRACTICE_PARAGRAPHS:
        p = art["paragraphs"][pi]
        q = p["qas"][QUESTION_INDEX]
        out["practice"].append({"id": f"PR-A{PRACTICE_ARTICLE:02d}-p{pi}", "kind": "onestop", "level": "Int",
                                "title": art["title"], "text": p["Int"]["context"],
                                "question": {"q_index": QUESTION_INDEX, "text": q["question"],
                                             "options": q["answers"], "correct": 0}})
    # typo in the OneStopQA source (practice item only): option "2n" should read "2nd"
    for pr in out["practice"]:
        if pr.get("question"):
            pr["question"]["options"] = ["2nd" if o == "2n" else o for o in pr["question"]["options"]]
    sid, repo, module, start = PRACTICE_SPECIALIST
    text, mtitle = openstax_para(osdir, repo, module, start)
    domain, book, url = OPENSTAX_BOOKS[repo]
    out["practice"].append({"id": sid, "kind": "specialist", "domain": domain, "text": text,
                            "source": f"OpenStax, {book}, section '{mtitle}' ({module})", "licence": "CC BY-NC-SA 4.0"})
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "study_items.json")
    json.dump(out, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("wrote", path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
