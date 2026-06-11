"""Seed connector table.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-06-10

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text as sa_text

revision: str = "e8f9a0b1c2d3"  # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Each row: connector_slug, connector_type, display_name, auth_scheme, sub_connector_of, status
CONNECTORS = [
    # ── Sources ─────────────────────────────────────────────────────────────
    ("salesforce", "source", "Salesforce", "oauth2", None, "active"),
    ("hubspot", "source", "HubSpot", "oauth2", None, "disabled"),
    ("zoho_crm", "source", "Zoho CRM", "oauth2", None, "inactive"),
    ("leadsquared", "source", "LeadSquared", "api_key", None, "inactive"),
    ("mysql", "source", "MySQL", "multi_key", None, "inactive"),
    ("postgresql", "source", "PostgreSQL", "multi_key", None, "inactive"),
    ("bigquery", "source", "BigQuery", "multi_key", None, "inactive"),
    ("s3", "source", "Amazon S3", "multi_key", None, "inactive"),
    ("gcs", "source", "Google Cloud Storage", "multi_key", None, "inactive"),
    ("sftp", "source", "SFTP", "multi_key", None, "inactive"),
    # ── Destinations — top-level ─────────────────────────────────────────────
    ("meta", "destination", "Meta", "api_key", None, "inactive"),
    ("google", "destination", "Google", "oauth2", None, "inactive"),
    ("tiktok", "destination", "TikTok", "api_key", None, "inactive"),
    ("snapchat", "destination", "Snapchat", "api_key", None, "inactive"),
    ("linkedin", "destination", "LinkedIn", "oauth2", None, "inactive"),
    ("pinterest", "destination", "Pinterest", "oauth2", None, "inactive"),
    ("microsoft", "destination", "Microsoft", "oauth2", None, "inactive"),
    ("reddit", "destination", "Reddit", "oauth2", None, "inactive"),
    ("x", "destination", "X (Twitter)", "oauth2", None, "inactive"),
    # ── Meta sub-destinations ────────────────────────────────────────────────
    ("meta_conversions_api", "destination", "Conversions API", "api_key", "meta", "disabled"),
    ("meta_conversions_api_crm", "destination", "Conversions API for CRM", "api_key", "meta", "active"),
    ("meta_custom_audience", "destination", "Custom Audience", "api_key", "meta", "inactive"),
    ("meta_offline_conversions", "destination", "Offline Conversions API", "api_key", "meta", "inactive"),
    ("meta_app_conversions", "destination", "App Conversions API", "api_key", "meta", "inactive"),
    ("meta_instagram_conversions", "destination", "Instagram Conversions API", "api_key", "meta", "inactive"),
    ("meta_whatsapp_conversions", "destination", "WhatsApp Conversions API", "api_key", "meta", "inactive"),
    ("meta_messenger_conversions", "destination", "Messenger Conversions API", "api_key", "meta", "inactive"),
    # ── Google sub-destinations ──────────────────────────────────────────────
    ("google_enhanced_conversions", "destination", "Enhanced Conversions", "oauth2", "google", "active"),
    ("google_customer_match", "destination", "Customer Match", "oauth2", "google", "inactive"),
    ("google_analytics_4", "destination", "Google Analytics 4", "oauth2", "google", "inactive"),
    ("google_bigquery", "destination", "BigQuery", "oauth2", "google", "inactive"),
    ("google_offline_conversions", "destination", "Offline Conversions", "oauth2", "google", "disabled"),
    ("google_store_sales", "destination", "Store Sales Conversions", "oauth2", "google", "inactive"),
    (
        "google_enhanced_conversions_leads",
        "destination",
        "Enhanced Conversions for Leads",
        "oauth2",
        "google",
        "inactive",
    ),
    ("google_local_product_inventory", "destination", "Local Product Inventory", "oauth2", "google", "inactive"),
    ("google_product_catalog", "destination", "Product Catalog", "oauth2", "google", "inactive"),
    ("google_dm", "destination", "Display & Video 360", "oauth2", "google", "inactive"),
]


def upgrade() -> None:
    """Seed connector rows."""
    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            INSERT INTO connector
                (connector_slug, connector_type, display_name, auth_scheme, sub_connector_of, status)
            VALUES
                (:connector_slug, :connector_type, :display_name, :auth_scheme, :sub_connector_of, :status)
            ON CONFLICT (connector_slug) DO NOTHING
            """
        ),
        [
            {
                "connector_slug": row[0],
                "connector_type": row[1],
                "display_name": row[2],
                "auth_scheme": row[3],
                "sub_connector_of": row[4],
                "status": row[5],
            }
            for row in CONNECTORS
        ],
    )


def downgrade() -> None:
    """Remove seeded connector rows."""
    conn = op.get_bind()
    slugs = [row[0] for row in CONNECTORS]
    conn.execute(
        sa_text("DELETE FROM connector WHERE connector_slug = ANY(:slugs)"),
        {"slugs": slugs},
    )
