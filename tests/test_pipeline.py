"""Unit tests for the fiddly pure logic: sport tagging, summary tidying, store merge.

Run:  pytest              (all)
      pytest -k classify  (one)
"""
from __future__ import annotations

from feed.models import Item
from feed.sport_tags import classify, extract_tags
from feed.store import merge, prune
from feed.summarize import summarize
from feed.textutil import (
    shorten,
    strip_html,
    summarize_text,
    tidy_summary,
    trim_to_sentence,
)


# --- sport_tags.classify ------------------------------------------------------

def test_classify_clear_winner():
    sport, ok = classify("Verstappen takes pole at the Monza Grand Prix", default="")
    assert (sport, ok) == ("f1", True)


def test_classify_no_match_uses_default():
    assert classify("A quiet news day", default="tennis") == ("tennis", True)


def test_classify_no_match_no_valid_default():
    assert classify("A quiet news day", default="") == ("", False)


def test_classify_football_not_confused_with_f1():
    sport, ok = classify("Arsenal beat Chelsea in the Premier League", default="")
    assert sport == "football" and ok


# --- sport_tags.extract_tags -------------------------------------------------

def test_extract_tags_dedups_and_caps():
    text = "Wimbledon recap: Alcaraz beats Djokovic; Alcaraz on the US Open next"
    tags = extract_tags(text, limit=3)
    assert tags == list(dict.fromkeys(tags))  # no dupes
    assert len(tags) <= 3
    assert "wimbledon" in tags


# --- textutil ---------------------------------------------------------------

def test_strip_html_unescapes_and_collapses():
    assert strip_html("<p>Hello&nbsp;&amp;   <b>world</b></p>") == "Hello & world"


def test_strip_html_spaces_block_boundaries():
    assert strip_html("<p>today's fixtures</p><p>Get in touch</p>") == "today's fixtures Get in touch"
    assert strip_html("line one<br>line two") == "line one line two"


def test_trim_to_sentence_drops_partial():
    raw = (
        "The Mercedes team rated their overall race pace as rubbish. "
        "They are still looking for answers on why it happened"
    )
    assert trim_to_sentence(raw) == "The Mercedes team rated their overall race pace as rubbish."


def test_trim_to_sentence_strips_ellipsis_marker():
    assert trim_to_sentence("A reasonably complete thought sits here.…") == "A reasonably complete thought sits here."


def test_trim_to_sentence_keeps_short_fragment():
    frag = "One long unbroken clause with no full stop anywhere in it at all"
    assert trim_to_sentence(frag) == frag


def test_trim_to_sentence_ignores_abbreviations():
    raw = (
        "The manager was pleased with his side's clinical display after the important win "
        "vs. City on Saturday which sealed a return to the top of the table"
    )
    assert trim_to_sentence(raw) == raw


def test_summarize_text_picks_two_sentences_in_order():
    body = (
        "Liverpool have agreed a fee for Bradley Barcola. "
        "The winger will join from Paris Saint-Germain. "
        "Barcola scored twelve goals last season for PSG. "
        "The weather in Merseyside was cloudy on Tuesday. "
        "Barcola is expected to sign a five-year Liverpool contract."
    )
    out = summarize_text(body, sentences=2)
    assert out.count(".") == 2
    assert "Barcola" in out
    assert out.index("Liverpool have agreed") < out.rindex("Barcola")


def test_tidy_summary_drops_trailer():
    assert tidy_summary("Real preview text here. Continue reading...") == "Real preview text here."


def test_tidy_summary_drops_photo_caption():
    raw = (
        "Aug 17, 2026; Mason, OH, USA; Arthur Fery returns a shot. "
        "Mandatory Credit: Aaron Doster-Imagn Images. He faces Buse in the final."
    )
    assert tidy_summary(raw) == "He faces Buse in the final."


def test_shorten_breaks_on_word_boundary():
    out = shorten("one two three four five", 12)
    assert out.endswith("…") and " " not in out.rstrip("…")[-1:]


# --- summarize: standfirst / promo stripping -------------------------------

def test_summarize_drops_bulleted_standfirst():
    entry = {
        "summary": (
            "<ul><li><p>News and buildup before today's games</p></li>"
            "<li><p>Get in touch: <a>mail Sarah</a> and follow us <a>on BlueSky</a></p></li></ul>"
            "<p>Liverpool have agreed a fee for Bradley Barcola from Paris Saint-Germain, sources say.</p>"
        )
    }
    summary, method = summarize(entry, "Transfer news live")
    assert method == "feed"
    assert summary.startswith("Liverpool have agreed a fee for Bradley Barcola")
    assert "BlueSky" not in summary and "Get in touch" not in summary


def test_summarize_drops_lead_paragraph_standfirst():
    entry = {
        "summary": (
            "<p>Updates from the latest round<br>"
            "<a>Day two roundup</a> | <a>Sign up for the Spin</a> | <a>Mail Tanya</a></p>"
            "<p>Despite a morning washout, play broke out at Scarborough and Yorkshire's tail wagged.</p>"
        )
    }
    summary, _ = summarize(entry, "County cricket day three – live")
    assert "Sign up for the Spin" not in summary
    assert summary.startswith("Despite a morning washout")


# --- store.merge / prune ---------------------------------------------------

def _item(id_: str, published: str) -> Item:
    return Item(
        id=id_, source="s", source_name="S", sport="f1", sports_ok=True,
        url=f"http://x/{id_}", title="t", summary="", summary_method="stub",
        author=None, published_at=published, fetched_at=published, tags=[],
    )


def test_merge_only_adds_new():
    store = {"a": _item("a", "2026-08-01T00:00:00+00:00")}
    added = merge(store, [_item("a", "2026-08-02T00:00:00+00:00"), _item("b", "2026-08-02T00:00:00+00:00")])
    assert [it.id for it in added] == ["b"]
    assert store["a"].published_at == "2026-08-01T00:00:00+00:00"  # untouched
    assert "b" in store


def test_prune_drops_old():
    store = {
        "old": _item("old", "2000-01-01T00:00:00+00:00"),
        "new": _item("new", "2026-08-29T00:00:00+00:00"),
    }
    kept = prune(store)
    assert set(kept) == {"new"}
