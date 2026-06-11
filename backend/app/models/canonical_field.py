"""``canonical_field`` table — Datahash canonical schema registry."""

from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class FieldCategory(str, Enum):
    """Semantic grouping for a canonical field."""

    identity = "identity"
    monetary = "monetary"
    ad_identifier = "ad_identifier"
    consent = "consent"
    cart = "cart"
    event = "event"
    product = "product"


class CanonicalField(SQLModel, table=True):
    """One field in the Datahash canonical schema.

    ``canonical_key`` is the stable identifier (e.g. ``user.pii.email_hashed``)
    and serves as the primary key — other tables FK to it directly.

    Attributes:
        canonical_key: Dot-notation stable identifier; primary key and FK target.
        field_label: Human-readable label (e.g. 'Email Address').
        field_hint: Optional guidance for mappers and reviewers.
        field_category: Semantic grouping (identity, monetary, etc.).
        is_pii: Whether the field carries personally identifiable information.
    """

    __tablename__ = "canonical_field"  # type: ignore[assignment]

    canonical_key: str = Field(primary_key=True)
    field_label: str
    field_hint: Optional[str] = Field(default=None)
    field_category: FieldCategory = Field(
        description="One of: identity, monetary, ad_identifier, consent, cart, event"
    )
    is_pii: bool = Field(default=False)
