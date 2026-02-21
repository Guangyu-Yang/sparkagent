"""Tests for sparkagent.auth.oauth module."""

import base64
import hashlib
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sparkagent.auth.oauth import (
    ANTHROPIC_AUTH_URL,
    ANTHROPIC_CLIENT_ID,
    ANTHROPIC_REDIRECT_URI,
    ANTHROPIC_TOKEN_URL,
    OAuthError,
    OAuthTokens,
    build_authorization_url,
    compute_expires_at,
    exchange_code_for_tokens,
    generate_pkce_pair,
    is_token_expired,
    refresh_access_token,
)

# ============================================================================
# PKCE Generation
# ============================================================================


class TestGeneratePkcePair:
    """Tests for generate_pkce_pair()."""

    def test_verifier_length(self):
        verifier, _ = generate_pkce_pair()
        assert 43 <= len(verifier) <= 128

    def test_verifier_characters(self):
        """Verifier should only contain URL-safe base64 characters."""
        verifier, _ = generate_pkce_pair()
        assert re.fullmatch(r"[A-Za-z0-9_-]+", verifier)

    def test_challenge_is_base64url_no_padding(self):
        """Challenge should be base64url-encoded without = padding."""
        _, challenge = generate_pkce_pair()
        assert "=" not in challenge
        assert re.fullmatch(r"[A-Za-z0-9_-]+", challenge)

    def test_challenge_matches_verifier(self):
        """Challenge should be BASE64URL(SHA256(verifier))."""
        verifier, challenge = generate_pkce_pair()
        expected_digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected_challenge = base64.urlsafe_b64encode(expected_digest).rstrip(b"=").decode("ascii")
        assert challenge == expected_challenge

    def test_pair_uniqueness(self):
        """Two generated pairs should be different."""
        pair1 = generate_pkce_pair()
        pair2 = generate_pkce_pair()
        assert pair1[0] != pair2[0]
        assert pair1[1] != pair2[1]


# ============================================================================
# Authorization URL
# ============================================================================


class TestBuildAuthorizationUrl:
    """Tests for build_authorization_url()."""

    def test_url_starts_with_auth_endpoint(self):
        url = build_authorization_url("test_challenge", "test_verifier")
        assert url.startswith(ANTHROPIC_AUTH_URL)

    def test_url_contains_required_params(self):
        url = build_authorization_url("my_challenge", "my_verifier")
        assert "client_id=" + ANTHROPIC_CLIENT_ID in url
        assert "response_type=code" in url
        assert "code_challenge=my_challenge" in url
        assert "code_challenge_method=S256" in url
        assert "code=true" in url

    def test_state_is_code_verifier(self):
        """The state parameter should be set to the code_verifier (matching Claude Code)."""
        url = build_authorization_url("ch", "my_verifier_value")
        assert "state=my_verifier_value" in url

    def test_url_contains_redirect_uri(self):
        url = build_authorization_url("ch", "st")
        # URL-encoded redirect URI
        assert "redirect_uri=" in url

    def test_url_contains_scopes(self):
        url = build_authorization_url("ch", "st")
        assert "scope=" in url

    def test_spaces_encoded_as_percent20(self):
        """Spaces in scope should be encoded as %20 (matching JS URL.searchParams.set)."""
        url = build_authorization_url("ch", "st")
        assert "%20" in url
        assert "scope=org%3Acreate_api_key%20" in url


# ============================================================================
# Helpers
# ============================================================================


def _mock_httpx_client(response_data: dict, status_code: int = 200):
    """Create a mock httpx.AsyncClient with a canned POST response.

    Returns ``(mock_client_class, mock_client_instance)`` where
    ``mock_client_class`` is suitable for patching ``httpx.AsyncClient``.
    """
    # httpx.Response.json() is a sync method, so use MagicMock for the response
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = response_data
    mock_response.text = str(response_data)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    return mock_client


# ============================================================================
# Token Exchange
# ============================================================================


class TestExchangeCodeForTokens:
    """Tests for exchange_code_for_tokens()."""

    @pytest.mark.asyncio
    async def test_successful_exchange(self):
        mock_client = _mock_httpx_client({
            "access_token": "sk-ant-oat01-access-123",
            "refresh_token": "refresh-456",
            "expires_in": 28800,
        })

        with patch("sparkagent.auth.oauth.httpx.AsyncClient", return_value=mock_client):
            tokens = await exchange_code_for_tokens("auth_code_123", "verifier_abc")

        assert isinstance(tokens, OAuthTokens)
        assert tokens.access_token == "sk-ant-oat01-access-123"
        assert tokens.refresh_token == "refresh-456"
        assert tokens.expires_in == 28800

    @pytest.mark.asyncio
    async def test_exchange_splits_code_hash_state(self):
        """The callback returns 'code#state' — we must split on '#'."""
        mock_client = _mock_httpx_client({
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 100,
        })

        with patch("sparkagent.auth.oauth.httpx.AsyncClient", return_value=mock_client):
            await exchange_code_for_tokens("my_code#my_state", "my_verifier")

        payload = mock_client.post.call_args[1]["json"]
        assert payload["code"] == "my_code"
        assert payload["state"] == "my_state"

    @pytest.mark.asyncio
    async def test_exchange_sends_correct_payload(self):
        mock_client = _mock_httpx_client({
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 100,
        })

        with patch("sparkagent.auth.oauth.httpx.AsyncClient", return_value=mock_client):
            await exchange_code_for_tokens("my_code#my_state", "my_verifier")

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == ANTHROPIC_TOKEN_URL
        payload = call_kwargs[1]["json"]
        assert payload["code"] == "my_code"
        assert payload["state"] == "my_state"
        assert payload["code_verifier"] == "my_verifier"
        assert payload["grant_type"] == "authorization_code"
        assert payload["client_id"] == ANTHROPIC_CLIENT_ID
        assert payload["redirect_uri"] == ANTHROPIC_REDIRECT_URI

    @pytest.mark.asyncio
    async def test_exchange_without_hash_uses_verifier_as_state(self):
        """If no '#' in code, state defaults to the code_verifier."""
        mock_client = _mock_httpx_client({
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 100,
        })

        with patch("sparkagent.auth.oauth.httpx.AsyncClient", return_value=mock_client):
            await exchange_code_for_tokens("plain_code", "my_verifier")

        payload = mock_client.post.call_args[1]["json"]
        assert payload["code"] == "plain_code"
        assert payload["state"] == "my_verifier"

    @pytest.mark.asyncio
    async def test_exchange_failure_raises_oauth_error(self):
        mock_client = _mock_httpx_client(
            {"error": "invalid_grant"}, status_code=400
        )

        with patch("sparkagent.auth.oauth.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(OAuthError) as exc_info:
                await exchange_code_for_tokens("bad_code", "verifier")

        assert exc_info.value.status_code == 400
        assert "400" in str(exc_info.value)


# ============================================================================
# Token Refresh
# ============================================================================


class TestRefreshAccessToken:
    """Tests for refresh_access_token()."""

    @pytest.mark.asyncio
    async def test_successful_refresh(self):
        mock_client = _mock_httpx_client({
            "access_token": "sk-ant-oat01-new-access",
            "refresh_token": "new-refresh",
            "expires_in": 28800,
        })

        with patch("sparkagent.auth.oauth.httpx.AsyncClient", return_value=mock_client):
            tokens = await refresh_access_token("old-refresh-token")

        assert tokens.access_token == "sk-ant-oat01-new-access"
        assert tokens.refresh_token == "new-refresh"
        assert tokens.expires_in == 28800

    @pytest.mark.asyncio
    async def test_refresh_sends_correct_payload(self):
        mock_client = _mock_httpx_client({
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 100,
        })

        with patch("sparkagent.auth.oauth.httpx.AsyncClient", return_value=mock_client):
            await refresh_access_token("my_refresh_token")

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == ANTHROPIC_TOKEN_URL
        payload = call_kwargs[1]["json"]
        assert payload["grant_type"] == "refresh_token"
        assert payload["refresh_token"] == "my_refresh_token"
        assert payload["client_id"] == ANTHROPIC_CLIENT_ID

    @pytest.mark.asyncio
    async def test_refresh_failure_raises_oauth_error(self):
        mock_client = _mock_httpx_client(
            {"error": "invalid_refresh_token"}, status_code=401
        )

        with patch("sparkagent.auth.oauth.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(OAuthError) as exc_info:
                await refresh_access_token("bad_refresh")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_preserves_refresh_token_if_not_returned(self):
        """If the server doesn't return a new refresh_token, keep the old one."""
        mock_client = _mock_httpx_client({
            "access_token": "new-access",
            "expires_in": 28800,
            # No refresh_token in response
        })

        with patch("sparkagent.auth.oauth.httpx.AsyncClient", return_value=mock_client):
            tokens = await refresh_access_token("original-refresh")

        assert tokens.refresh_token == "original-refresh"


# ============================================================================
# Expiry Helpers
# ============================================================================


class TestIsTokenExpired:
    """Tests for is_token_expired()."""

    def test_none_is_expired(self):
        assert is_token_expired(None) is True

    def test_empty_string_is_expired(self):
        assert is_token_expired("") is True

    def test_future_timestamp_not_expired(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        assert is_token_expired(future) is False

    def test_past_timestamp_is_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert is_token_expired(past) is True

    def test_within_buffer_is_expired(self):
        """A token expiring in 3 minutes should be considered expired (5-min buffer)."""
        almost_expired = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()
        assert is_token_expired(almost_expired) is True

    def test_outside_buffer_not_expired(self):
        """A token expiring in 10 minutes should NOT be expired (5-min buffer)."""
        still_valid = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        assert is_token_expired(still_valid) is False

    def test_invalid_string_is_expired(self):
        assert is_token_expired("not-a-date") is True


class TestComputeExpiresAt:
    """Tests for compute_expires_at()."""

    def test_returns_iso_string(self):
        result = compute_expires_at(28800)
        # Should be parseable
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None

    def test_future_timestamp(self):
        result = compute_expires_at(3600)
        dt = datetime.fromisoformat(result)
        assert dt > datetime.now(timezone.utc)

    def test_respects_duration(self):
        """The computed expiry should be roughly expires_in seconds from now."""
        before = datetime.now(timezone.utc)
        result = compute_expires_at(7200)
        after = datetime.now(timezone.utc)

        dt = datetime.fromisoformat(result)
        # Should be within a small window of 2 hours from now
        expected_min = before + timedelta(seconds=7199)
        expected_max = after + timedelta(seconds=7201)
        assert expected_min <= dt <= expected_max


# ============================================================================
# OAuthTokens model
# ============================================================================


class TestOAuthTokens:
    """Tests for OAuthTokens model."""

    def test_creation(self):
        tokens = OAuthTokens(
            access_token="access-123",
            refresh_token="refresh-456",
            expires_in=28800,
        )
        assert tokens.access_token == "access-123"
        assert tokens.refresh_token == "refresh-456"
        assert tokens.expires_in == 28800


# ============================================================================
# OAuthError
# ============================================================================


class TestOAuthError:
    """Tests for OAuthError exception."""

    def test_with_status_code(self):
        err = OAuthError("bad request", status_code=400)
        assert str(err) == "bad request"
        assert err.status_code == 400

    def test_without_status_code(self):
        err = OAuthError("unknown error")
        assert str(err) == "unknown error"
        assert err.status_code is None
