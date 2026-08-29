"""The one data type that flows through the pipeline and into data/items.json."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Item:
    id: str  # sha1(guid or link)
    source: str  # source key
    source_name: str
    sport: str  # cricket | f1 | football | tennis | other
    sports_ok: bool  # False => hidden from the page, kept in JSON
    url: str
    title: str
    summary: str
    summary_method: str  # feed | extract | stub
    author: str | None
    published_at: str | None  # ISO-8601 UTC
    fetched_at: str  # ISO-8601 UTC — when we first saw it
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        known = {f: data.get(f) for f in cls.__dataclass_fields__}
        known["tags"] = known.get("tags") or []
        return cls(**known)
