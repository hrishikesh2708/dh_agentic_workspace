"""Dashboard schemas — request/response models for the dashboard REST API.

Re-exports the public schemas used by ``app/api/v1/dashboard.py`` so callers
can import from a single module path.
"""

from app.schemas.dashboard.golden_rule import (
    GoldenRuleCreate,
    GoldenRuleListResponse,
    GoldenRuleRead,
)
from app.schemas.dashboard.integrations import (
    SalesforceOAuthCallback,
    SalesforceStatus,
)
from app.schemas.dashboard.mapping import (
    FieldMappingRead,
    MappingSessionDetail,
    MappingSessionListResponse,
    MappingSessionRead,
)

__all__ = [
    "FieldMappingRead",
    "GoldenRuleCreate",
    "GoldenRuleListResponse",
    "GoldenRuleRead",
    "MappingSessionDetail",
    "MappingSessionListResponse",
    "MappingSessionRead",
    "SalesforceOAuthCallback",
    "SalesforceStatus",
]
