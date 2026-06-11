"""Seed destination_field_mapping table.

Revision ID: d7e8f9a0b1c2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-10

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text as sa_text

revision: str = "d7e8f9a0b1c2"  # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (destination_slug, sub_destination_slug, destination_field_path, canonical_key,
#  transform_function, is_required, is_destination_specific)
META_MAPPINGS: list[tuple[str, str, str, str, str | None, bool, bool]] = [
    ("meta", "conversion_api_for_crm", "user_data.fn", "user.pii.first_name", None, False, False),
    ("meta", "conversion_api_for_crm", "user_data.ln", "user.pii.last_name", None, False, False),
    ("meta", "conversion_api_for_crm", "user_data.ph", "user.pii.phone_hashed", None, True, False),
    ("meta", "conversion_api_for_crm", "user_data.em", "user.pii.email_hashed", None, True, False),
    ("meta", "conversion_api_for_crm", "user_data.ge", "user.pii.gender_hashed", None, False, False),
    ("meta", "conversion_api_for_crm", "user_data.db", "user.pii.date_of_birth_hashed", None, False, False),
    ("meta", "conversion_api_for_crm", "user_data.ct", "user.pii.city_hashed", None, False, False),
    ("meta", "conversion_api_for_crm", "user_data.st", "user.pii.state_hashed", None, False, False),
    ("meta", "conversion_api_for_crm", "user_data.zp", "user.pii.zipcode_hashed", None, False, False),
    ("meta", "conversion_api_for_crm", "user_data.country", "user.pii.country_hashed", None, False, False),
    ("meta", "conversion_api_for_crm", "user_data.external_id", "user.general.external_id", None, False, False),
    (
        "meta",
        "conversion_api_for_crm",
        "user_data.client_ip_address",
        "user.general.client_ip_address",
        None,
        False,
        False,
    ),
    (
        "meta",
        "conversion_api_for_crm",
        "user_data.client_user_agent",
        "user.general.client_user_agent",
        None,
        False,
        False,
    ),
    ("meta", "conversion_api_for_crm", "user_data.fbc", "user.general.fbc", None, False, True),
    ("meta", "conversion_api_for_crm", "user_data.fbp", "user.general.browser_id", None, False, False),
    ("meta", "conversion_api_for_crm", "user_data.fb_login_id", "user.general.fb_login_id", None, False, True),
    ("meta", "conversion_api_for_crm", "event_id", "event.general.event_id", None, False, False),
    ("meta", "conversion_api_for_crm", "event_name", "event.general.event_name", None, True, False),
    ("meta", "conversion_api_for_crm", "event_time", "event.general.event_time", "convert_to_timestamp", True, False),
    ("meta", "conversion_api_for_crm", "event_source_url", "event.general.event_source_url", None, False, False),
    (
        "meta",
        "conversion_api_for_crm",
        "custom_data.content_category",
        "event.general.content_category",
        None,
        False,
        False,
    ),
    ("meta", "conversion_api_for_crm", "custom_data.currency", "event.monetary.currency", None, True, False),
    (
        "meta",
        "conversion_api_for_crm",
        "custom_data.value",
        "event.general.content_value",
        "convert_to_float",
        True,
        False,
    ),
    ("meta", "conversion_api_for_crm", "custom_data.content_ids", "event.general.content_ids", None, False, False),
    ("meta", "conversion_api_for_crm", "custom_data.content_type", "event.general.content_type", None, False, False),
    ("meta", "conversion_api_for_crm", "custom_data.content_name", "event.general.content_name", None, False, False),
    (
        "meta",
        "conversion_api_for_crm",
        "custom_data.delivery_category",
        "event.general.delivery_category",
        None,
        False,
        False,
    ),
    ("meta", "conversion_api_for_crm", "custom_data.num_items", "event.general.number_items", None, False, False),
    ("meta", "conversion_api_for_crm", "custom_data.order_id", "event.general.transaction_id", None, False, False),
    ("meta", "conversion_api_for_crm", "custom_data.predicted_ltv", "event.general.predicted_ltv", None, False, False),
    ("meta", "conversion_api_for_crm", "custom_data.search_string", "event.general.search_string", None, False, False),
    ("meta", "conversion_api_for_crm", "custom_data.status", "event.general.status", None, False, False),
    ("meta", "conversion_api_for_crm", "custom_data.contents", "event.general.contents", None, False, False),
]

GOOGLE_MAPPINGS: list[tuple[str, str, str, str, str | None, bool, bool]] = [
    ("google", "enhanced_conversions", "transactionId", "event.general.event_id", "convert_to_str", True, False),
    (
        "google",
        "enhanced_conversions",
        "eventTimestamp",
        "event.general.event_time",
        "convert_to_google_format",
        True,
        False,
    ),
    ("google", "enhanced_conversions", "userData.emailAddress", "user.pii.email_hashed", None, True, False),
    ("google", "enhanced_conversions", "userData.phoneNumber", "user.pii.phone_hashed", None, True, False),
    ("google", "enhanced_conversions", "userData.address.givenName", "user.pii.first_name", None, False, False),
    ("google", "enhanced_conversions", "userData.address.familyName", "user.pii.last_name", None, False, False),
    (
        "google",
        "enhanced_conversions",
        "userData.address.postalCode",
        "user.pii.zipcode",
        "convert_to_str",
        False,
        False,
    ),
    (
        "google",
        "enhanced_conversions",
        "userData.address.regionCode",
        "user.pii.country",
        "convert_to_uppercase",
        False,
        False,
    ),
    ("google", "enhanced_conversions", "consent.adUserData", "measurement_consent", None, False, True),
    ("google", "enhanced_conversions", "consent.adPersonalization", "personalization_consent", None, False, True),
    (
        "google",
        "enhanced_conversions",
        "adIdentifiers.sessionAttributes",
        "user.pii.session_attributes",
        None,
        False,
        True,
    ),
    ("google", "enhanced_conversions", "adIdentifiers.gclid", "user.general.gclid", "convert_to_str", True, True),
    ("google", "enhanced_conversions", "adIdentifiers.gbraid", "user.general.gbraid", "convert_to_str", False, True),
    ("google", "enhanced_conversions", "adIdentifiers.wbraid", "user.general.wbraid", "convert_to_str", False, True),
    (
        "google",
        "enhanced_conversions",
        "adIdentifiers.landingPageDeviceInfo.userAgent",
        "user.general.client_user_agent",
        None,
        False,
        False,
    ),
    (
        "google",
        "enhanced_conversions",
        "adIdentifiers.landingPageDeviceInfo.ipAddress",
        "user.general.client_ip_address",
        None,
        False,
        False,
    ),
    ("google", "enhanced_conversions", "currency", "event.monetary.currency", None, True, False),
    (
        "google",
        "enhanced_conversions",
        "conversionValue",
        "event.general.content_value",
        "convert_to_float",
        True,
        False,
    ),
    (
        "google",
        "enhanced_conversions",
        "eventDeviceInfo.userAgent",
        "user.general.client_user_agent",
        None,
        False,
        False,
    ),
    (
        "google",
        "enhanced_conversions",
        "eventDeviceInfo.ipAddress",
        "user.general.client_ip_address",
        None,
        False,
        False,
    ),
    (
        "google",
        "enhanced_conversions",
        "cartData.merchantFeedLabel",
        "user.pii.merchant_feed_label",
        None,
        False,
        False,
    ),
    (
        "google",
        "enhanced_conversions",
        "cartData.merchantFeedLanguageCode",
        "user.pii.merchant_feed_language_code",
        None,
        False,
        False,
    ),
    (
        "google",
        "enhanced_conversions",
        "cartData.transactionDiscount",
        "user.pii.transaction_discount",
        None,
        False,
        False,
    ),
    ("google", "enhanced_conversions", "cartData.items", "event.general.contents", None, False, False),
]

DESTINATION_FIELD_MAPPINGS = META_MAPPINGS + GOOGLE_MAPPINGS

# Sub-slugs this seed owns (include legacy names so downgrade cleans up renames).
_META_SUB_DESTINATION_SLUGS = ("conversion_api", "conversion_api_for_crm")
_GOOGLE_SUB_DESTINATION_SLUGS = ("enhanced_conversions",)


def upgrade() -> None:
    """Seed destination_field_mapping rows."""
    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            INSERT INTO destination_field_mapping
                (
                    destination_slug,
                    sub_destination_slug,
                    destination_field_path,
                    canonical_key,
                    transform_function,
                    is_required,
                    is_destination_specific
                )
            VALUES
                (
                    :destination_slug,
                    :sub_destination_slug,
                    :destination_field_path,
                    :canonical_key,
                    :transform_function,
                    :is_required,
                    :is_destination_specific
                )
            ON CONFLICT (destination_slug, sub_destination_slug, destination_field_path)
            DO UPDATE SET
                canonical_key = EXCLUDED.canonical_key,
                transform_function = EXCLUDED.transform_function,
                is_required = EXCLUDED.is_required,
                is_destination_specific = EXCLUDED.is_destination_specific
            """
        ),
        [
            {
                "destination_slug": row[0],
                "sub_destination_slug": row[1],
                "destination_field_path": row[2],
                "canonical_key": row[3],
                "transform_function": row[4],
                "is_required": row[5],
                "is_destination_specific": row[6],
            }
            for row in DESTINATION_FIELD_MAPPINGS
        ],
    )


def downgrade() -> None:
    """Remove seeded destination_field_mapping rows."""
    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            DELETE FROM destination_field_mapping
            WHERE destination_slug = 'meta'
              AND sub_destination_slug = ANY(CAST(:meta_sub_slugs AS text[]))
            """
        ),
        {"meta_sub_slugs": list(_META_SUB_DESTINATION_SLUGS)},
    )
    conn.execute(
        sa_text(
            """
            DELETE FROM destination_field_mapping
            WHERE destination_slug = 'google'
              AND sub_destination_slug = ANY(CAST(:google_sub_slugs AS text[]))
            """
        ),
        {"google_sub_slugs": list(_GOOGLE_SUB_DESTINATION_SLUGS)},
    )
