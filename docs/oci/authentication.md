# Authentication

The registry implements the [Docker Registry v2 Token Authentication](https://docs.docker.com/registry/spec/auth/token/) specification.

## How it works

```
┌──────────┐   GET /v2/            ┌──────────────┐
│  Docker  │ ─────────────────────▶│   Registry   │
│  Client  │ ◀─────────────────────│              │
└──────────┘  401 WWW-Authenticate └──────────────┘
     │         Bearer realm="…"
     │
     │        GET /auth/token              ┌──────────────┐
     └──────────────────────────────────▶  │ Token Service│
              (optional Basic Auth)        │  /auth/token │
     ┌──────────────────────────────────── │              │
     │        200 {"token": "<JWT>"}       └──────────────┘
     ▼
GET /v2/ (Authorization: Bearer <JWT>)
     ──────────────────────────────▶  200 OK
```

1. Docker hits `GET /v2/` → gets `401` with `WWW-Authenticate: Bearer realm="…"`.
2. Docker fetches a JWT from the realm URL (`/auth/token`), optionally with `Authorization: Basic`.
3. Docker retries the original request using `Authorization: Bearer <JWT>`.

**Anonymous access:** if no credentials are sent to `/auth/token`, a token for the `anonymous` user is returned. Docker push/pull works without `docker login` — callers just receive the anonymous identity.

---

## Configuration

Settings are loaded via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) from environment variables or a `.env` file.

| Environment Variable    | Type   | Default                                  | Description |
|-------------------------|--------|------------------------------------------|-------------|
| `AUTH_SECRET_KEY`       | `str`  | random (changes on restart)              | HMAC secret used to sign JWTs. **Set a stable value in production.** Generate one with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `AUTH_TOKEN_EXPIRATION` | `int`  | `300`                                    | Token lifetime in seconds. |
| `AUTH_REALM`            | `str`  | `http://localhost:5000/auth/token`       | Token endpoint URL advertised in `WWW-Authenticate` challenges. Must be reachable by Docker clients. |
| `AUTH_SERVICE`          | `str`  | `registry`                               | Service name embedded in the JWT `aud` (audience) claim. |
| `AUTH_ISSUER`           | `str`  | `registry-token-service`                 | Issuer label embedded in the JWT `iss` claim (informational). |
| `REGISTRY_USERS`        | `str`  | _(empty)_                                | Comma-separated `username:password` pairs loaded on startup. Example: `alice:supersecret,bob:hunter2` |

---

## Setting up users

Copy `.env.dist` to `.env` and populate `REGISTRY_USERS`:

```env
AUTH_SECRET_KEY=<output of secrets.token_hex(32)>
REGISTRY_USERS=alice:supersecret,bob:hunter2
```

Restart the registry for the new users to take effect.

---

## docker login

```bash
docker login -u alice localhost:5000
# Password: <enter alice's password>
```

Docker will:
1. Probe `GET /v2/` to discover the token realm.
2. Exchange credentials at `GET /auth/token` for a JWT.
3. Store the token in `~/.docker/config.json`.

---

## Token endpoint reference

`GET /auth/token`

| Query parameter | Description |
|-----------------|-------------|
| `service`       | Registry service name (sent automatically by Docker, must match `AUTH_SERVICE`). |
| `scope`         | Resource scope — e.g. `repository:alpine:pull,push`. Embedded in the JWT `access` claim. |
| `account`       | Username hint used as the JWT subject when no `Authorization` header is present. |

**Request headers**

| Header          | Description |
|-----------------|-------------|
| `Authorization` | Optional `Basic <base64(user:pass)>`. Omit for anonymous access. |

**Response (200 OK)**

```json
{
  "token": "<JWT>",
  "access_token": "<JWT>",
  "expires_in": 300,
  "issued_at": null
}
```

**Error (401)**

```json
{
  "errors": [
    {"code": "UNAUTHORIZED", "message": "invalid credentials"}
  ]
}
```

---

## Getting a token with curl

**Anonymous**

```bash
curl http://localhost:5000/auth/token
```

**Authenticated**

```bash
curl -u alice:supersecret http://localhost:5000/auth/token
```

**With scope**

```bash
curl "http://localhost:5000/auth/token?scope=repository:alpine:pull"
```
