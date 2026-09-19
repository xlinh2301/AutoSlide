"""Pydantic v2 data models for content origins, source records, research results, and provenance."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
import urllib.parse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from autoslide.planner.models import TargetReference


class ContentOrigin(BaseModel):
    """Source origin attribution for presentation content blocks and operations."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["USER", "WEB", "AI_GENERATED"]
    source_ids: list[str] = Field(default_factory=list)
    runtime_name: str | None = None


class SourceRecord(BaseModel):
    """External or research web source cited in support of presentation edits."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    url: str
    title: str
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    summary: str = ""
    claims: list[str] = Field(default_factory=list)
    approved: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Enforce strict HTTP/HTTPS protocol validation."""
        if not isinstance(v, str):
            raise ValueError(f"Invalid URL: {v}. Must be a string.")
        parsed = urllib.parse.urlparse(v.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                f"Invalid URL '{v}'. Must be a valid absolute URL using http:// or https://."
            )
        return v.strip()


class ResearchResult(BaseModel):
    """Normalized output from web research queries."""

    model_config = ConfigDict(frozen=True)

    query: str
    sources: list[SourceRecord] = Field(default_factory=list)
    summary: str = ""
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_output: str | None = None


class GeneratedContent(BaseModel):
    """AI-generated content block with explicit origin attribution."""

    model_config = ConfigDict(frozen=True)

    prompt: str
    text: str
    origin: ContentOrigin
    model_or_runtime: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvenanceRecord(BaseModel):
    """Tracks origin attribution and destination targeting for content items."""

    model_config = ConfigDict(frozen=True)

    content_ref: str
    origin: ContentOrigin
    destination: TargetReference
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContentBlock(BaseModel):
    """Arbitrary supported or typed content item for slide insertion and deck structuring."""

    model_config = ConfigDict(frozen=True)

    block_type: str = "text"
    text: str = ""
    origin: ContentOrigin | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
