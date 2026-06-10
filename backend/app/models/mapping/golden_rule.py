"""``golden_rule`` table — learned high-confidence mapping patterns."""

from typing import Optional

from sqlmodel import Field

from app.models.base import BaseModel


class GoldenRule(BaseModel, table=True):
    """A learned rule: ``(source_pattern, destination_type) → destination_field``.

    ``occurrence_count`` is incremented every time a human approves the same
    pair; once it hits :attr:`Settings.GOLDEN_RULE_MIN_OCCURRENCES` (default 3)
    the rule is surfaced as a high-priority example in future mapper runs.

    Attributes:
        id: Auto-increment primary key.
        source_pattern: Lowercased source field name (or pattern).
        destination_field: The destination field this pattern maps to.
        destination_type: Which destination schema this rule applies to.
        occurrence_count: Number of times the pair has been confirmed.
    """

    __tablename__ = "golden_rule"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    source_pattern: str = Field(max_length=255, index=True)
    destination_field: str = Field(max_length=255)
    destination_type: str = Field(max_length=255, index=True)
    occurrence_count: int = Field(default=1)
