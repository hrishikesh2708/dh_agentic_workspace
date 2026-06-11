"""``connector`` table — source and destination connector registry."""

from enum import Enum
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class ConnectorType(str, Enum):
    """Whether the connector is a data source or destination."""

    source = "source"
    destination = "destination"


class AuthScheme(str, Enum):
    """Authentication mechanism required by the connector."""

    oauth2 = "oauth2"
    api_key = "api_key"  # pragma: allowlist secret
    multi_key = "multi_key"


class ConnectorStatus(str, Enum):
    """Whether the connector is available for use."""

    active = "active"
    inactive = "inactive"
    disabled = "disabled"


class Connector(SQLModel, table=True):
    """A source or destination connector (including sub-connectors).

    Attributes:
        connector_slug: Stable identifier; primary key and FK target for sub-connectors.
        connector_type: ``source`` or ``destination``.
        display_name: Human-readable label shown in the UI.
        auth_scheme: Authentication mechanism (``oauth2``, ``api_key``, ``multi_key``).
        sub_connector_of: Parent connector slug for sub-destinations (e.g. ``meta``).
        status: ``active`` or ``inactive``.
    """

    __tablename__ = "connector"  # type: ignore[assignment]

    connector_slug: str = Field(primary_key=True)
    connector_type: ConnectorType
    display_name: str
    auth_scheme: AuthScheme
    sub_connector_of: Optional[str] = Field(
        default=None,
        foreign_key="connector.connector_slug",
    )
    status: ConnectorStatus = Field(default=ConnectorStatus.active)

    parent: Optional["Connector"] = Relationship(
        sa_relationship_kwargs={
            "remote_side": "Connector.connector_slug",
            "foreign_keys": "[Connector.sub_connector_of]",
        }
    )
