"""``destination_field_mapping`` table — canonical → destination field projections."""

from typing import (
    TYPE_CHECKING,
    Optional,
)

from sqlmodel import (
    Field,
    Relationship,
    SQLModel,
    UniqueConstraint,
)

if TYPE_CHECKING:
    from app.models.canonical_field import CanonicalField


class DestinationFieldMapping(SQLModel, table=True):
    """Maps a destination field path to a canonical field.

    Attributes:
        id: Auto-increment primary key.
        destination_slug: Top-level destination (e.g. ``meta``, ``google``).
        sub_destination_slug: Sub-destination API (e.g. ``conversions_api``).
        destination_field_path: Field path in the destination schema (e.g. ``user_data.em``).
        canonical_key: FK to ``canonical_field.canonical_key``.
        transform_function: Optional transform applied before send (e.g. ``convert_to_str``).
        is_required: Whether the destination requires this field.
        is_destination_specific: True for fields that only apply to one destination (e.g. gclid).
    """

    __tablename__ = "destination_field_mapping"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint(
            "destination_slug",
            "sub_destination_slug",
            "destination_field_path",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    destination_slug: str
    sub_destination_slug: str
    destination_field_path: str
    canonical_key: str = Field(foreign_key="canonical_field.canonical_key", index=True)
    transform_function: Optional[str] = Field(default=None)
    is_required: bool = Field(default=False)
    is_destination_specific: bool = Field(default=False)

    canonical_field: "CanonicalField" = Relationship()
