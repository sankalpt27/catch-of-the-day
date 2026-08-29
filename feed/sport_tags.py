"""Rule-based sport classification and keyword tagging.

Used to (a) classify items from `sport: multi` sources and (b) attach keyword tags
that the v2 client-side ranker will lean on. Single-sport sources skip classify().
"""
from __future__ import annotations

import re

from .config import SPORTS

# keyword -> sport. Keep these reasonably distinctive; generic words ("goal",
# "match") are avoided where they collide across sports.
KEYWORDS: dict[str, list[str]] = {
    "cricket": [
        "cricket", "test match", "the ashes", "odi", "t20", "ipl", "big bash",
        "county championship", "wicket", "batsman", "batter", "bowler", "innings",
        "bcci", "icc", "ranji", "kohli", "rohit sharma", "bumrah", "joe root",
        "ben stokes", "steve smith", "pat cummins", "babar azam", "rashid khan",
    ],
    "f1": [
        "formula 1", "formula one", "grand prix", "pole position", "qualifying",
        "verstappen", "hamilton", "leclerc", "lando norris", "piastri",
        "george russell", "fernando alonso", "red bull racing", "scuderia ferrari",
        "mclaren", "fia", "pit stop", "drs", "pit lane", "constructors' championship",
    ],
    "football": [
        "football", "soccer", "premier league", "la liga", "serie a", "bundesliga",
        "ligue 1", "champions league", "europa league", "uefa", "midfielder",
        "striker", "arsenal", "liverpool", "manchester united", "manchester city",
        "chelsea", "tottenham", "real madrid", "barcelona", "bayern munich",
        "lionel messi", "cristiano ronaldo", "mbappe", "erling haaland",
    ],
    "tennis": [
        "tennis", "atp tour", "wta tour", "grand slam", "wimbledon", "roland garros",
        "french open", "us open", "australian open", "novak djokovic", "alcaraz",
        "jannik sinner", "medvedev", "zverev", "swiatek", "sabalenka", "coco gauff",
        "rafael nadal", "roger federer", "break point", "tie-break",
    ],
}

_PATTERNS: dict[str, list[re.Pattern]] = {
    sport: [re.compile(r"\b" + re.escape(k) + r"\b", re.IGNORECASE) for k in kws]
    for sport, kws in KEYWORDS.items()
}


def score_sports(text: str) -> dict[str, int]:
    return {sport: sum(1 for p in pats if p.search(text)) for sport, pats in _PATTERNS.items()}


def classify(text: str, default: str = "") -> tuple[str, bool]:
    """Return (sport, sports_ok).

    A clear single winner wins. A tie resolves to `default` when it is one of the
    tied sports. No matches at all -> (default, default in SPORTS).
    """
    scores = score_sports(text)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_sport, top_score = ranked[0]

    if top_score == 0:
        return default, default in SPORTS

    if len(ranked) > 1 and ranked[1][1] == top_score:
        if default in SPORTS and scores.get(default) == top_score:
            return default, True
        return default or top_sport, (default in SPORTS) or True

    return top_sport, True


def extract_tags(text: str, limit: int = 6) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for kws in KEYWORDS.values():
        for k in kws:
            if len(k) < 5 or k in seen:
                continue
            if re.search(r"\b" + re.escape(k) + r"\b", text, re.IGNORECASE):
                seen.add(k)
                out.append(k)
    return out[:limit]
