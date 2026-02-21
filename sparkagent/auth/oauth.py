"""Anthropic OAuth 2.0 Authorization Code flow with PKCE.

Implements the same OAuth flow used by Claude Code to authenticate
with Anthropic using a Claude Max (or Pro/Free) subscription.

Flow:
    1. Generate PKCE pair (code_verifier + code_challenge)
    2. Open browser to authorization URL
    3. User authorizes → callback page shows authorization code
    4. Exchange code for access_token + refresh_token
    5. Auto-refresh when token expires
"""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import httpx
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ANTHROPIC_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
ANTHROPIC_AUTH_URL = "https://claude.ai/oauth/authorize"
ANTHROPIC_TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
ANTHROPIC_REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
ANTHROPIC_SCOPES = "org:create_api_key user:profile user:inference"

TOKEN_EXPIRY_BUFFER_SECONDS = 300  # Refresh 5 minutes before actual expiry

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class OAuthTokens(BaseModel):
    """Tokens returned from the Anthropic OAuth token endpoint."""

    access_token: str
    refresh_token: str
    expires_in: int  # seconds until access_token expires


class OAuthError(Exception):
    """Raised when an OAuth operation fails."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge pair.

    Returns:
        A tuple of ``(code_verifier, code_challenge)``.
        The verifier is a 43-character URL-safe random string.
        The challenge is ``BASE64URL(SHA256(verifier))`` without padding.
    """
    code_verifier = secrets.token_urlsafe(32)  # 43 chars

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    return code_verifier, code_challenge


# ---------------------------------------------------------------------------
# Authorization URL
# ---------------------------------------------------------------------------


def build_authorization_url(code_challenge: str, code_verifier: str) -> str:
    """Build the full Anthropic OAuth authorization URL.

    Matches the URL format used by Claude Code's ``setup-token`` command.
    The ``state`` parameter is set to the PKCE ``code_verifier`` (same as
    Claude Code and opencode-anthropic-auth).

    Args:
        code_challenge: The PKCE code challenge (S256).
        code_verifier: The PKCE code verifier (also used as the ``state``
            parameter, matching Claude Code's behavior).

    Returns:
        The complete authorization URL to open in a browser.
    """
    params = {
        "code": "true",
        "client_id": ANTHROPIC_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": ANTHROPIC_REDIRECT_URI,
        "scope": ANTHROPIC_SCOPES,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": code_verifier,
    }
    # Use quote_via=quote so spaces encode as %20 (matching JS
    # URL.searchParams.set behaviour used by Claude Code).
    return f"{ANTHROPIC_AUTH_URL}?{urlencode(params, quote_via=quote)}"


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


async def exchange_code_for_tokens(
    code: str,
    code_verifier: str,
) -> OAuthTokens:
    """Exchange an authorization code for access and refresh tokens.

    The callback page returns the code in the format ``<code>#<state>``.
    This function splits on ``#`` and sends both parts to the token
    endpoint (matching Claude Code's behaviour).

    Args:
        code: The authorization code from the callback page.  May include
            a ``#<state>`` suffix which will be stripped automatically.
        code_verifier: The original PKCE code verifier.

    Returns:
        An :class:`OAuthTokens` instance with the new tokens.

    Raises:
        OAuthError: If the token exchange fails.
    """
    # The callback returns "code#state" — split them apart.
    parts = code.split("#", 1)
    auth_code = parts[0]
    state = parts[1] if len(parts) > 1 else code_verifier

    payload = {
        "code": auth_code,
        "state": state,
        "grant_type": "authorization_code",
        "client_id": ANTHROPIC_CLIENT_ID,
        "redirect_uri": ANTHROPIC_REDIRECT_URI,
        "code_verifier": code_verifier,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            ANTHROPIC_TOKEN_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    if response.status_code != 200:
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise OAuthError(
            f"Token exchange failed ({response.status_code}): {detail}",
            status_code=response.status_code,
        )

    data = response.json()
    return OAuthTokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data.get("expires_in", 28800),
    )


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


async def refresh_access_token(refresh_token: str) -> OAuthTokens:
    """Refresh an expired access token using a refresh token.

    Args:
        refresh_token: The stored refresh token.

    Returns:
        An :class:`OAuthTokens` instance with the new tokens.

    Raises:
        OAuthError: If the refresh fails (e.g. refresh token expired).
    """
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": ANTHROPIC_CLIENT_ID,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            ANTHROPIC_TOKEN_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    if response.status_code != 200:
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise OAuthError(
            f"Token refresh failed ({response.status_code}): {detail}. "
            "Run `sparkagent login` to re-authenticate.",
            status_code=response.status_code,
        )

    data = response.json()
    return OAuthTokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", refresh_token),
        expires_in=data.get("expires_in", 28800),
    )


# ---------------------------------------------------------------------------
# Expiry helpers
# ---------------------------------------------------------------------------


def compute_expires_at(expires_in: int) -> str:
    """Compute an ISO 8601 expiry timestamp from a duration in seconds.

    Args:
        expires_in: Number of seconds until the token expires.

    Returns:
        An ISO 8601 UTC timestamp string.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return expires_at.isoformat()


def is_token_expired(expires_at: str | None) -> bool:
    """Check whether an access token has expired (or is about to).

    Includes a 5-minute buffer so we refresh *before* the actual expiry.

    Args:
        expires_at: ISO 8601 UTC timestamp, or None/empty if unknown.

    Returns:
        True if the token is expired or the expiry is unknown.
    """
    if not expires_at:
        return True

    try:
        expiry = datetime.fromisoformat(expires_at)
        # Ensure timezone-aware
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        buffer = timedelta(seconds=TOKEN_EXPIRY_BUFFER_SECONDS)
        return datetime.now(timezone.utc) >= (expiry - buffer)
    except (ValueError, TypeError):
        return True
