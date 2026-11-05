from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Place(Strict):
    name: str = Field(min_length=1, max_length=160)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    basis: Literal["stated", "gps", "sample"] = "stated"

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be supplied together")
        return self


class Source(Strict):
    id: str
    author: str
    text: str
    captured_at: str
    date_basis: Literal["captured", "posted"] = "captured"
    asset_ids: list[str] = Field(default_factory=list)
    location: Place | None = None


class Chapter(Strict):
    day: int = Field(ge=1, le=365)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=5000)
    quote: str
    quote_source_id: str
    source_ids: list[str] = Field(min_length=1)
    asset_ids: list[str]


class Album(Strict):
    design: Literal["classic", "quiet", "editorial", "urban", "coastal"] | None = None
    title: str = Field(min_length=1, max_length=160)
    subtitle: str = Field(max_length=600)
    location: str
    date_label: str
    cover_asset_id: str
    chapters: list[Chapter] = Field(min_length=1, max_length=50)


class Editorial(Strict):
    album: Album
    approved: bool
    notes: list[str]


def validate_evidence(album: Album, sources: list[dict], assets: set[str]):
    """Check referential integrity and verbatim quotes, not semantic truth."""
    index = {s["id"]: s for s in sources}
    if album.cover_asset_id not in assets:
        raise ValueError("Cover is not an available source photograph")
    for chapter in album.chapters:
        datetime.fromisoformat(chapter.date)
        if not set(chapter.source_ids).issubset(index):
            raise ValueError("Unknown evidence citation")
        if not set(chapter.asset_ids).issubset(assets):
            raise ValueError("Unknown source photograph")
        if chapter.quote and (chapter.quote_source_id not in chapter.source_ids or chapter.quote not in index[chapter.quote_source_id]["text"]):
            raise ValueError("Quoted words must occur verbatim in the cited source")
        cited_assets = {a for sid in chapter.source_ids for a in index[sid]["asset_ids"]}
        if not set(chapter.asset_ids).issubset(cited_assets):
            raise ValueError("Photographs must belong to cited source posts")
