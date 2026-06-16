"""Salesforce REST API client + protocol.

Auth strategy (priority order):
1. DB tokens — load access_token + instance_url from ProjectConnectionSecret
   for the given project_id. Refresh automatically on 401.
2. Env-var fallback — username-password flow using SALESFORCE_* env vars.
   Used in dev/test when no project_id is available.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable
from uuid import UUID

import httpx

from app.agents.core.agent_config import _AgentSettingsProxy
from app.core.logging import logger
from app.schemas import SourceField, SourceSchema


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
    """Salesforce REST client.

    Tries DB-stored OAuth tokens first (project-scoped). Falls back to the
    username-password env-var flow when no project_id is set.
    """

    def __init__(self, settings: _AgentSettingsProxy, project_id: Optional[UUID] = None) -> None:
        """Initialize client with optional project-scoped OAuth credentials."""
        self.settings = settings
        self.project_id = project_id
        self._token: str | None = None
        self._instance_url: str | None = None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Ensure _token + _instance_url are set. Prefer DB tokens."""
        if self._token and self._instance_url:
            return
        if self.project_id:
            await self._load_from_db()
        else:
            await self._authenticate_via_env()

    async def _load_from_db(self) -> None:
        """Load access_token + instance_url from ProjectConnectionSecret."""
        from sqlmodel import Session, select

        from app.models import ProjectConnection, ProjectConnectionStatus
        from app.models import ProjectConnectionSecret
        from app.services.database import database_service

        with Session(database_service.engine) as db:
            conn_stmt = select(ProjectConnection).where(
                ProjectConnection.project_id == self.project_id,
                ProjectConnection.connector_slug == "salesforce",
                ProjectConnection.status == ProjectConnectionStatus.active,
            )
            conn = db.exec(conn_stmt).first()
            if not conn:
                raise RuntimeError(f"No active Salesforce connection for project {self.project_id}")

            secrets_stmt = select(ProjectConnectionSecret).where(
                ProjectConnectionSecret.project_connection_id == conn.id
            )
            secrets = {s.secret_key: s.secret_value for s in db.exec(secrets_stmt).all()}

        self._token = secrets.get("access_token")
        self._instance_url = (conn.connection_metadata or {}).get("instance_url")
        self._refresh_token = secrets.get("refresh_token")

        if not self._token or not self._instance_url:
            raise RuntimeError("Salesforce DB connection is missing access_token or instance_url")

        logger.info("salesforce_auth_from_db", project_id=str(self.project_id))

    async def _authenticate_via_env(self) -> None:
        """Fallback: username-password OAuth flow from env vars."""
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
        self._refresh_token = data.get("refresh_token")
        logger.info("salesforce_auth_via_env")

    async def _refresh_access_token(self) -> None:
        """Use stored refresh_token to get a new access_token; update DB row."""
        refresh_token = getattr(self, "_refresh_token", None)
        if not refresh_token:
            raise RuntimeError("No refresh_token available; re-authentication required")

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.settings.salesforce_client_id,
            "client_secret": self.settings.salesforce_client_secret,
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.settings.salesforce_auth_url}/services/oauth2/token",
                data=payload,
            )
            response.raise_for_status()
            data = response.json()

        new_token = data["access_token"]
        self._token = new_token

        # Persist updated token to DB if project-scoped
        if self.project_id:
            from sqlmodel import Session, select

            from app.models import ProjectConnection, ProjectConnectionStatus
            from app.models import ProjectConnectionSecret
            from app.services.database import database_service

            with Session(database_service.engine) as db:
                conn_stmt = select(ProjectConnection).where(
                    ProjectConnection.project_id == self.project_id,
                    ProjectConnection.connector_slug == "salesforce",
                    ProjectConnection.status == ProjectConnectionStatus.active,
                )
                conn = db.exec(conn_stmt).first()
                if conn:
                    secret_stmt = select(ProjectConnectionSecret).where(
                        ProjectConnectionSecret.project_connection_id == conn.id,
                        ProjectConnectionSecret.secret_key == "access_token",  # pragma: allowlist secret
                    )
                    secret = db.exec(secret_stmt).first()
                    if secret:
                        secret.secret_value = new_token
                        db.add(secret)
                        db.commit()

        logger.info("salesforce_token_refreshed", project_id=str(self.project_id) if self.project_id else "env")

    # ------------------------------------------------------------------
    # API calls (with lazy token refresh on 401)
    # ------------------------------------------------------------------

    async def _get(self, url: str) -> dict[str, Any]:
        """Authenticated GET with automatic token refresh on 401."""
        await self.authenticate()
        headers = {"Authorization": f"Bearer {self._token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 401:
                logger.info("salesforce_token_expired_refreshing")
                await self._refresh_access_token()
                headers = {"Authorization": f"Bearer {self._token}"}
                response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def describe_object(self, object_name: str) -> dict[str, Any]:
        """Call ``/sobjects/{object}/describe`` for raw schema metadata."""
        url = f"{self._instance_url}/services/data/v61.0/sobjects/{object_name}/describe"
        return await self._get(url)

    async def list_sobjects(self) -> list[dict[str, Any]]:
        """List all sObjects accessible to the authenticated user."""
        url = f"{self._instance_url}/services/data/v61.0/sobjects/"
        return (await self._get(url)).get("sobjects", [])

    async def list_eligible_objects(
        self,
        *,
        include_standard: bool = True,
        include_custom: bool = True,
    ) -> list[str]:
        """Filter ``list_sobjects()`` to mappable objects (queryable, non-hidden)."""
        sobjects = await self.list_sobjects()
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
        raw = await self.describe_object(object_name)
        fields = [self._normalize_field(f) for f in raw.get("fields", [])]
        return SourceSchema(object_name=object_name, fields=fields)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
