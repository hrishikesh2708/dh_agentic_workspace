"""All Pydantic schemas in one place.

Sections:
  - Base
  - Auth
  - Project
  - Agent types (mapping pipeline domain models)
"""

# ruff: noqa: D101, D102

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from asgi_correlation_id import correlation_id
from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


def _get_request_id() -> UUID:
    value = correlation_id.get()
    return UUID(value) if value else uuid4()


class BaseResponse(BaseModel):
    request_id: UUID = Field(default_factory=_get_request_id)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class TokenResponse(BaseResponse):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: SecretStr = Field(..., min_length=8, max_length=64)
    username: str | None = Field(default=None, max_length=50)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: SecretStr) -> SecretStr:
        p = v.get_secret_value()
        if len(p) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", p):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", p):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", p):
            raise ValueError("Password must contain at least one number")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', p):
            raise ValueError("Password must contain at least one special character")
        return v


class UserResponse(BaseResponse):
    id: int
    email: str
    username: str | None = None
    token: Token


class SessionResponse(BaseResponse):
    session_id: str
    name: str = Field(default="", max_length=100)
    token: Token

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return re.sub(r'[<>{}[\]()\'"`]', "", v)


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectRead(BaseModel):
    id: UUID
    user_id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: list[ProjectRead]
    total: int


# ---------------------------------------------------------------------------
# Agent / mapping pipeline domain types
# ---------------------------------------------------------------------------


class MappingStatus(str, Enum):
    auto_approved = "auto_approved"
    needs_review = "needs_review"
    unmatched = "unmatched"
    not_proposed = "not_proposed"
    human_approved = "human_approved"
    human_corrected = "human_corrected"


class MappingKind(str, Enum):
    canonical = "canonical"
    projection = "projection"


class Sources(BaseModel):
    connector_id: str
    connector_type: str
    display_name: str
    sub_connector_of: str | None = None
    parent_connector_id: str | None = None
    parent_connector_name: str | None = None


class Destinations(BaseModel):
    connector_id: str
    connector_type: str
    display_name: str
    sub_connector_of: str | None = None
    parent_connector_id: str | None = None
    parent_connector_name: str | None = None


class ValidationStatus(str, Enum):
    pass_status = "pass"
    warn = "warn"
    fail = "fail"


class SourceField(BaseModel):
    name: str
    label: str
    type: str
    description: str | None = None
    picklist_values: list[str] = Field(default_factory=list)
    sample_values: list[str] = Field(default_factory=list)
    is_custom: bool = False


class SourceSchema(BaseModel):
    object_name: str
    fields: list[SourceField]


class DestinationField(BaseModel):
    name: str
    type: str
    canonical_key: str
    required: bool = False
    transform_function: str | None = None
    description: str | None = None
    enum_values: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class DestinationSchema(BaseModel):
    destination: str
    label: str
    description: str | None = None
    status: str
    fields: list[DestinationField]


class CanonicalSchemaField(BaseModel):
    canonical_key: str
    field_label: str
    field_hint: str | None = None
    field_category: str
    is_pii: bool = False


class CanonicalSchema(BaseModel):
    canonical: str = "canonical"
    label: str = "Datahash Canonical"
    description: str | None = "Internal canonical schema"
    fields: list[CanonicalSchemaField]


class ProposedMapping(BaseModel):
    source_field: str
    destination_field: str | None = None
    confidence: float = 0.0
    reasoning: str = ""
    transformation_needed: str | None = None
    validation_status: ValidationStatus = ValidationStatus.pass_status
    validation_notes: list[str] = Field(default_factory=list)
    status: MappingStatus = MappingStatus.needs_review

    @field_validator("transformation_needed", mode="before")
    @classmethod
    def _coerce_transformation_needed(cls, value: Any) -> Any:
        if isinstance(value, bool):
            return "required" if value else None
        return value
