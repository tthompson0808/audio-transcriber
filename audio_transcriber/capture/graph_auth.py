"""One-shot delegated OAuth flow for Microsoft Graph.

Run during install: opens a browser, CEO signs in, refresh token is
persisted to Windows Credential Manager. Subsequent polls use that token.
"""
import os

try:
    import msal
except ImportError:
    msal = None

from audio_transcriber.auth import credentials


def run_device_code_flow(client_id: str, tenant_id: str, scopes: list[str]) -> dict:
    """Interactive device-code flow. Returns the token dict and persists refresh_token.

    Caller prints the user_code + verification_uri so the CEO can complete sign-in.
    """
    if msal is None:
        raise RuntimeError("msal not installed. pip install msal")

    app = msal.PublicClientApplication(
        client_id, authority=f"https://login.microsoftonline.com/{tenant_id}"
    )
    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        raise RuntimeError(f"Failed to start device flow: {flow}")

    print("\n" + "=" * 60)
    print(flow["message"])
    print("=" * 60 + "\n")

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Authentication failed: {result.get('error_description')}")

    if result.get("refresh_token"):
        credentials.set_secret("graph_refresh_token", result["refresh_token"])
    credentials.set_secret("graph_client_id", client_id)
    credentials.set_secret("graph_tenant_id", tenant_id)

    return result
