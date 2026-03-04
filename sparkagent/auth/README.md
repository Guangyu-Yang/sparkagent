# auth — Authentication

OAuth 2.0 + PKCE flow for authenticating with Anthropic's API.

## Files

| File | Purpose |
|------|---------|
| `oauth.py` | PKCE key generation, authorization URL building, token exchange, and token refresh |

## Key Abstractions

### OAuthTokens (Pydantic model)

```python
class OAuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
```

### OAuthError

Custom exception with an optional `status_code` field for HTTP error context.

### Functions

| Function | Description |
|----------|-------------|
| `generate_pkce_pair()` | Returns `(code_verifier, code_challenge)` for PKCE S256 |
| `build_authorization_url(challenge, verifier)` | Builds the Anthropic OAuth URL to open in a browser |
| `exchange_code_for_tokens(code, verifier)` | Exchanges authorization code for access + refresh tokens |
| `refresh_access_token(refresh_token)` | Refreshes an expired access token |
| `compute_expires_at(expires_in)` | Returns ISO 8601 UTC expiry timestamp |
| `is_token_expired(expires_at)` | Checks expiry with a 5-minute buffer |

### Constants

| Constant | Value |
|----------|-------|
| `ANTHROPIC_CLIENT_ID` | `9d1c250a-e61b-44d9-88ed-5944d1962f5e` |
| `ANTHROPIC_AUTH_URL` | `https://claude.ai/oauth/authorize` |
| `ANTHROPIC_TOKEN_URL` | `https://console.anthropic.com/v1/oauth/token` |
| `ANTHROPIC_REDIRECT_URI` | `https://console.anthropic.com/oauth/code/callback` |
| `ANTHROPIC_SCOPES` | `org:create_api_key user:profile user:inference` |
| `TOKEN_EXPIRY_BUFFER_SECONDS` | `300` (5 minutes) |
