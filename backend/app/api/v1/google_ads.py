"""Google Ads account and conversion action picker endpoints.

Called by the frontend after Google OAuth to let the user pick which
Google Ads account and conversion action to use for the integration.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

GOOGLE_ADS_API_VERSION = "v17"
GOOGLE_ADS_BASE = "https://googleads.googleapis.com"


async def _refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Get a fresh Google access token."""
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
    resp.raise_for_status()
    return resp.json()["access_token"]


@router.get("/google/accounts")
async def list_google_ads_accounts(
    project_id: UUID = Query(..., description="Project ID to load Google credentials for"),
):
    """List accessible Google Ads customer accounts.

    Returns: {accounts: [{value: customerId, label: name}]}
    """
    import httpx
    from app.config import settings

    # Mock mode for development
    if getattr(settings, "MOCK_GOOGLE_ADS", False):
        return {
            "accounts": [
                {"value": "123-456-7890", "label": "Mock Account (test)"},
            ]
        }

    developer_token = getattr(settings, "GOOGLE_ADS_DEVELOPER_TOKEN", None)
    if not developer_token:
        return {"accounts": [], "warning": "Google Ads developer token not configured."}

    client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "")
    refresh_token = getattr(settings, "GOOGLE_REFRESH_TOKEN", "")

    try:
        access_token = await _refresh_access_token(client_id, client_secret, refresh_token)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GOOGLE_ADS_BASE}/{GOOGLE_ADS_API_VERSION}/customers:listAccessibleCustomers",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "developer-token": developer_token,
                },
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        data = resp.json()
        resource_names = data.get("resourceNames", [])
        accounts = [{"value": rn.split("/")[-1], "label": rn} for rn in resource_names]
        return {"accounts": accounts}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/google/conversion-actions")
async def list_google_conversion_actions(
    project_id: UUID = Query(...),
    customer_id: str = Query(..., description="Google Ads customer ID (without dashes)"),
):
    """List available conversion actions for a Google Ads customer account.

    Returns: {conversionActions: [{value: resourceName, label: name + status}]}
    """
    import httpx
    from app.config import settings

    # Mock mode
    if getattr(settings, "MOCK_GOOGLE_ADS", False):
        return {
            "conversionActions": [
                {"value": "customers/123/conversionActions/456", "label": "Purchase (ENABLED)"},
                {"value": "customers/123/conversionActions/789", "label": "Lead (ENABLED)"},
            ]
        }

    developer_token = getattr(settings, "GOOGLE_ADS_DEVELOPER_TOKEN", None)
    if not developer_token:
        return {"conversionActions": [], "warning": "Developer token not configured."}

    client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "")
    refresh_token = getattr(settings, "GOOGLE_REFRESH_TOKEN", "")

    try:
        access_token = await _refresh_access_token(client_id, client_secret, refresh_token)
        cid = customer_id.replace("-", "")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GOOGLE_ADS_BASE}/{GOOGLE_ADS_API_VERSION}/customers/{cid}/googleAds:searchStream",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "developer-token": developer_token,
                },
                json={
                    "query": (
                        "SELECT conversion_action.id, conversion_action.name, "
                        "conversion_action.status FROM conversion_action"
                    )
                },
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        actions = []
        for batch in resp.json():
            for row in batch.get("results", []):
                ca = row.get("conversionAction", {})
                name = ca.get("name", "Unknown")
                status = ca.get("status", "")
                resource = ca.get("resourceName", "")
                actions.append(
                    {
                        "value": resource,
                        "label": f"{name} ({status})" if status else name,
                    }
                )
        return {"conversionActions": actions}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
