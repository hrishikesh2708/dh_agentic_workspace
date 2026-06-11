"""Salesforce REST API client + protocol.

Merges the two files from ``crawler_agent/src/integrations/salesforce/`` into
one module. ``SourceClient`` is the Protocol the agent depends on; future
adapters (HubSpot, etc.) will satisfy the same interface.
"""

from __future__ import annotations

from typing import (
    Any,
    Protocol,
    runtime_checkable,
)

import httpx

from app.agents.core.agent_config import _AgentSettingsProxy
from app.core.logging import logger
from app.schemas.agent.types import (
    SourceField,
    SourceSchema,
)

# Dev/demo fallback when Salesforce OAuth is unavailable (mirrors intent_worker's
# hard-coded object list when list_eligible_objects fails).
_FALLBACK_OBJECT_NAMES = [
    "Lead",
    "Contact",
    "Account",
    "Opportunity",
    "Campaign",
    "CampaignMember",
]

_FALLBACK_FIELDS_BY_OBJECT: dict[str, list[SourceField]] = {
    "Lead": [
        SourceField(name="Id", label="Lead ID", type="id"),
        SourceField(name="FirstName", label="First Name", type="string"),
        SourceField(name="LastName", label="Last Name", type="string"),
        SourceField(name="Email", label="Email", type="email"),
        SourceField(name="Company", label="Company", type="string"),
        SourceField(name="Phone", label="Phone", type="phone"),
        SourceField(name="Status", label="Status", type="picklist"),
        SourceField(name="LeadSource", label="Lead Source", type="picklist"),
        SourceField(name="City", label="City", type="string"),
        SourceField(name="State", label="State/Province", type="string"),
        SourceField(name="Country", label="Country", type="string"),
    ],
    "Contact": [
        SourceField(name="Id", label="Contact ID", type="id"),
        SourceField(name="FirstName", label="First Name", type="string"),
        SourceField(name="LastName", label="Last Name", type="string"),
        SourceField(name="Email", label="Email", type="email"),
        SourceField(name="Phone", label="Phone", type="phone"),
        SourceField(name="AccountId", label="Account ID", type="reference"),
    ],
    "Account": [
        SourceField(name="Id", label="Account ID", type="id"),
        SourceField(name="Name", label="Account Name", type="string"),
        SourceField(name="Industry", label="Industry", type="picklist"),
        SourceField(name="Website", label="Website", type="url"),
    ],
}


@runtime_checkable
class SourceClient(Protocol):
    """Common interface every source integration must implement."""

    async def load_source_schema(self, object_name: str) -> SourceSchema:
        """Return the schema for one source object."""
        ...

    async def list_eligible_objects(
        self,
        *,
        include_standard: bool = True,
        include_custom: bool = True,
    ) -> list[str]:
        """Return source-side object names eligible for mapping."""
        ...


class SalesforceClient:
    """Salesforce REST client using the username-password OAuth flow.

    The access token + instance URL are cached in-memory after the first
    successful auth and reused for subsequent calls in the same process.
    """

    def __init__(self, settings: _AgentSettingsProxy) -> None:
        """Initialise without authenticating.

        Args:
            settings: Agent settings proxy with Salesforce credentials.
        """
        self.settings = settings
        self._token: str | None = None
        self._instance_url: str | None = None

    def _credentials_configured(self) -> bool:
        return bool(
            self.settings.salesforce_client_id
            and self.settings.salesforce_client_secret
            and self.settings.salesforce_username
            and self.settings.salesforce_password
        )

    @staticmethod
    def _fallback_object_names() -> list[str]:
        return list(_FALLBACK_OBJECT_NAMES)

    @staticmethod
    def _fallback_source_schema(object_name: str) -> SourceSchema:
        fields = _FALLBACK_FIELDS_BY_OBJECT.get(object_name)
        if not fields:
            fields = [
                SourceField(name="Id", label=f"{object_name} ID", type="id"),
                SourceField(name="Name", label="Name", type="string"),
            ]
        logger.warning(
            "salesforce_fallback_schema",
            object_name=object_name,
            field_count=len(fields),
        )
        return SourceSchema(object_name=object_name, fields=fields)

    async def authenticate(self) -> None:
        """Fetch + cache an OAuth access token. No-op if already authenticated."""
        if self._token and self._instance_url:
            return

        payload = {
            "grant_type": "password",
            "client_id": self.settings.salesforce_client_id,
            "client_secret": self.settings.salesforce_client_secret,
            "username": self.settings.salesforce_username,
            "password": f"{self.settings.salesforce_password}{self.settings.salesforce_security_token}",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.settings.salesforce_auth_url}/services/oauth2/token",
                data=payload,
            )
            response.raise_for_status()
            data = response.json()
        self._token = data["access_token"]
        self._instance_url = data["instance_url"]

    async def describe_object(self, object_name: str) -> dict[str, Any]:
        """Call ``/sobjects/{object}/describe`` for raw schema metadata."""
        await self.authenticate()
        url = f"{self._instance_url}/services/data/v61.0/sobjects/{object_name}/describe"
        headers = {"Authorization": f"Bearer {self._token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def list_sobjects(self) -> list[dict[str, Any]]:
        """List all sObjects accessible to the authenticated user."""
        await self.authenticate()
        url = f"{self._instance_url}/services/data/v61.0/sobjects/"
        headers = {"Authorization": f"Bearer {self._token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("sobjects", [])

    async def list_eligible_objects(
        self,
        *,
        include_standard: bool = True,
        include_custom: bool = True,
    ) -> list[str]:
        """Filter ``list_sobjects()`` to mappable objects (queryable, non-hidden)."""
        if not self._credentials_configured():
            return self._fallback_object_names()
        try:
            sobjects = await self.list_sobjects()
        except Exception as exc:
            logger.warning("salesforce_list_objects_failed", error=str(exc))
            return self._fallback_object_names()
        standard_set = self._standard_object_set()
        eligible = [
            item.get("name", "")
            for item in sobjects
            if self._is_eligible_sobject(
                item,
                standard_set,
                include_standard=include_standard,
                include_custom=include_custom,
            )
        ]
        return sorted({name for name in eligible if name})

    async def load_source_schema(self, object_name: str) -> SourceSchema:
        """Fetch + normalise an object's schema into a :class:`SourceSchema`."""
        if not self._credentials_configured():
            return self._fallback_source_schema(object_name)
        try:
            raw = await self.describe_object(object_name)
            fields = [self._normalize_field(f) for f in raw.get("fields", [])]
            return SourceSchema(object_name=object_name, fields=fields)
        except Exception as exc:
            logger.warning(
                "salesforce_load_schema_failed",
                object_name=object_name,
                error=str(exc),
            )
            return self._fallback_source_schema(object_name)

    def _standard_object_set(self) -> set[str]:
        return {s.strip() for s in self.settings.salesforce_standard_objects.split(",") if s.strip()}

    @staticmethod
    def _is_eligible_sobject(
        item: dict[str, Any],
        standard_set: set[str],
        include_standard: bool,
        include_custom: bool,
    ) -> bool:
        name = item.get("name", "")
        if not name or not item.get("queryable", False) or item.get("deprecatedAndHidden", False):
            return False
        is_custom = name.endswith("__c")
        is_standard = name in standard_set
        return (include_custom and is_custom) or (include_standard and is_standard)

    @staticmethod
    def _normalize_field(raw_field: dict[str, Any]) -> SourceField:
        picklist_values = [item.get("value", "") for item in raw_field.get("picklistValues", []) if item.get("value")]
        sample_values = []
        if raw_field.get("defaultValue") is not None:
            sample_values.append(str(raw_field["defaultValue"]))

        return SourceField(
            name=raw_field.get("name", ""),
            label=raw_field.get("label", raw_field.get("name", "")),
            type=raw_field.get("type", "string"),
            description=raw_field.get("inlineHelpText"),
            picklist_values=picklist_values,
            sample_values=sample_values,
            is_custom=bool(raw_field.get("custom")),
        )
