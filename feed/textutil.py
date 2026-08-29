"""HTML-to-text, length trimming, and a dependency-free extractive summarizer."""
from __future__ import annotations

import html
import re
from collections import Counter
from html.parser import HTMLParser

# Tags whose boundaries are a space in the plain-text rendering — otherwise
# "<p>fixtures</p><p>Get in touch" collapses to "fixturesGet in touch".
_BLOCK_TAGS = frozenset({
    "p", "div", "br", "li", "ul", "ol", "dl", "dd", "dt", "tr", "td", "th",
    "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "aside", "header",
    "footer", "figure", "figcaption", "blockquote", "pre", "hr", "table", "nav",
})


class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _BLOCK_TAGS:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    @property
    def text(self) -> str:
        return "".join(self._parts)


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    stripper = _Stripper()
    try:
        stripper.feed(raw)
        text = stripper.text
    except Exception:  # malformed markup — fall back to a blunt regex
        text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


_TRAILER = re.compile(
    r"\s*(?:"
    r"\[\s*[.…]+\s*\]"  # "[...]" / "[…]"
    r"|(?:continue|keep)\s+reading\b.*"
    r"|read\s+(?:more|the\s+full\s+(?:story|article))\b.*"
    r"|the\s+post\s+.+?\s+appeared\s+first\s+on\s+.+"
    r")\s*$",
    re.IGNORECASE | re.DOTALL,
)

# Sentences that are photo-agency caption boilerplate, not article text.
_CAPTION = re.compile(
    r"mandatory credit|imagn images|getty images|\|\s*source:|^\w{3}\s+\d{1,2},\s+\d{4};",
    re.IGNORECASE,
)

# Newsletter / contact boilerplate some publishers prepend to the description.
_PROMO_PREFIX = re.compile(
    r"^\s*(?:"
    r"sign up (?:for|to)[^.]*?(?:newsletter|inbox|here)\b[.!?]?\s*"
    r"|get in touch[:.].*?(?:blue ?sky|twitter|\bx\b|e-?mail|\bmail\b)[^.]*?[.!?]?\s+"
    r"|follow (?:us|the .+?)\s+on [^.]*?[.!?]?\s+"
    r"|subscribe to [^.]*?(?:newsletter|here)\b[.!?]?\s*"
    r")+",
    re.IGNORECASE,
)


def tidy_summary(text: str) -> str:
    """Strip promo prefixes, photo-credit caption sentences, and trailing cruft."""
    text = _PROMO_PREFIX.sub("", text).strip()

    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = [s for s in sentences if s and not _CAPTION.search(s)]
    text = " ".join(kept).strip()

    prev = None
    while prev != text:
        prev = text
        text = _TRAILER.sub("", text).strip().strip("|–—- ").strip()
    return text


def shorten(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:—-")
    return cut + "…"


_ENDS_CLEAN = re.compile(r'[.!?]["”’\')\]]?\s*$')
_ABBREV = frozenset({"mr", "mrs", "ms", "dr", "st", "no", "vs", "sr", "jr", "co", "capt"})
_BOUNDARY = re.compile(r'([.!?])(["”’\')\]]?)(?=\s)')


def trim_to_sentence(text: str, floor: int = 40) -> str:
    """Drop a dangling partial sentence left by a feed's own truncation.

    Removes a trailing '…' / '...' marker, then, if the text no longer ends on
    sentence punctuation, cuts back to the last real sentence boundary — unless
    that would leave less than `floor` characters, in which case the fragment is
    kept (better a fragment than nothing).
    """
    text = re.sub(r"\s*(?:\.\.\.|…)\s*$", "", text.strip()).strip()
    if not text or _ENDS_CLEAN.search(text):
        return text

    last_end = 0
    for m in _BOUNDARY.finditer(text):
        word = re.search(r"([A-Za-z.]+)$", text[: m.start()])
        if word and word.group(1).lower().strip(".") in _ABBREV:
            continue
        last_end = m.end()
    if last_end >= floor:
        return text[:last_end].strip()
    return text


# --- extractive summary (frequency-scored, no dependencies) ------------------

_STOPWORDS = frozenset(
    "the a an and or but if then else than that this these those of to in on for "
    "with as at by from is are was were be been being it its he she they them his "
    "her their we you i not no do does did have has had will would can could should "
    "may might must about into over after before their there here what which who "
    "when where why how all any both each more most other some such only own same "
    "so up out off down also just".split()
)
_WORD = re.compile(r"[A-Za-z']+")


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"“\'])', text)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def summarize_text(body: str, sentences: int = 2) -> str:
    """Pick the most representative sentences by keyword frequency, keeping their
    original order. Biased slightly toward the opening (news leads matter)."""
    sents = _split_sentences(body)
    if len(sents) <= sentences:
        return " ".join(sents)

    freq: Counter[str] = Counter()
    for s in sents:
        for w in _WORD.findall(s.lower()):
            if len(w) > 2 and w not in _STOPWORDS:
                freq[w] += 1
    if not freq:
        return " ".join(sents[:sentences])

    scored: list[tuple[float, int]] = []
    for i, s in enumerate(sents):
        toks = [w for w in _WORD.findall(s.lower()) if len(w) > 2 and w not in _STOPWORDS]
        if not toks:
            continue
        score = sum(freq[w] for w in toks) / (len(toks) ** 0.5)
        score *= 1.0 + max(0, 5 - i) * 0.04
        scored.append((score, i))

    top = sorted(scored, reverse=True)[:sentences]
    chosen = sorted(idx for _, idx in top)
    return " ".join(sents[i] for i in chosen)
