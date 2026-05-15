"""Tests for authentication endpoints and middleware."""

import base64

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.auth.token_service import create_token, decode_token, get_subject
from src.auth.user import UserStore, _hash_password, _verify_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _basic(username: str, password: str) -> str:
    """Return an HTTP Basic Authorization header value."""
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {creds}"


def _bearer(token: str) -> str:
    return f"Bearer {token}"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def authed_client():
    """TestClient pre-loaded with a valid Bearer token for 'alice'."""
    token = create_token("alice")
    return TestClient(app, headers={"Authorization": _bearer(token)})


@pytest.fixture
def user_store_with_alice(monkeypatch):
    """Return a fresh UserStore with alice:password123 registered."""
    store = UserStore.__new__(UserStore)
    store._users = {}
    store.add_user("alice", "password123")
    import src.routes.auth.routes as auth_module
    monkeypatch.setattr(auth_module, "user_store", store)
    return store


# ---------------------------------------------------------------------------
# Token service unit tests
# ---------------------------------------------------------------------------


class TestTokenService:
    def test_create_and_decode_token(self):
        """Round-trip: created token can be decoded back to its subject."""
        # Arrange / Act
        token = create_token("alice")
        payload = decode_token(token)

        # Assert
        assert payload["sub"] == "alice"

    def test_token_contains_access_claim(self):
        """Access list is embedded in the JWT."""
        # Arrange
        access = [{"type": "repository", "name": "alpine", "actions": ["pull"]}]

        # Act
        token = create_token("alice", access=access)
        payload = decode_token(token)

        # Assert
        assert payload["access"] == access

    def test_get_subject_valid_token(self):
        # Arrange / Act
        token = create_token("bob")
        subject = get_subject(token)

        # Assert
        assert subject == "bob"

    def test_get_subject_invalid_token(self):
        # Act
        subject = get_subject("not.a.valid.jwt")

        # Assert
        assert subject is None

    def test_get_subject_empty_string(self):
        # Act
        subject = get_subject("")

        # Assert
        assert subject is None

    @pytest.mark.parametrize("username", ["alice", "anonymous", "user123", "org/team"])
    def test_create_token_various_subjects(self, username):
        """create_token works for arbitrary subject strings."""
        # Act
        token = create_token(username)

        # Assert
        assert get_subject(token) == username


# ---------------------------------------------------------------------------
# User store unit tests
# ---------------------------------------------------------------------------


class TestUserStore:
    def test_add_and_authenticate_user(self):
        # Arrange
        store = UserStore.__new__(UserStore)
        store._users = {}

        # Act
        store.add_user("alice", "secret")

        # Assert
        assert store.authenticate("alice", "secret") is True

    def test_wrong_password_rejected(self):
        # Arrange
        store = UserStore.__new__(UserStore)
        store._users = {}
        store.add_user("alice", "correct")

        # Act / Assert
        assert store.authenticate("alice", "wrong") is False

    def test_unknown_user_rejected(self):
        # Arrange
        store = UserStore.__new__(UserStore)
        store._users = {}

        # Act / Assert
        assert store.authenticate("nobody", "pass") is False

    def test_exists_after_add(self):
        # Arrange
        store = UserStore.__new__(UserStore)
        store._users = {}

        # Act
        store.add_user("bob", "pass")

        # Assert
        assert store.exists("bob") is True
        assert store.exists("unknown") is False

    def test_load_from_env(self, monkeypatch):
        """Users listed in registry_users setting are loaded on init."""
        # Arrange
        import src.settings as settings_module
        monkeypatch.setattr(settings_module.settings, "registry_users", "eve:pass1,mallory:pass2")

        # Act
        store = UserStore()

        # Assert
        assert store.authenticate("eve", "pass1") is True
        assert store.authenticate("mallory", "pass2") is True

    def test_load_from_env_ignores_malformed_entries(self, monkeypatch):
        """Entries without ':' are silently skipped."""
        # Arrange
        import src.settings as settings_module
        monkeypatch.setattr(settings_module.settings, "registry_users", "validuser:pass,badentry,,  ")

        # Act
        store = UserStore()

        # Assert
        assert store.authenticate("validuser", "pass") is True

    def test_hash_and_verify_password(self):
        # Arrange
        raw = "mysecret"

        # Act
        stored = _hash_password(raw)

        # Assert
        assert _verify_password(raw, stored) is True
        assert _verify_password("wrong", stored) is False


# ---------------------------------------------------------------------------
# /auth/token endpoint tests
# ---------------------------------------------------------------------------


class TestAuthTokenEndpoint:
    def test_anonymous_token_no_credentials(self, client):
        """Token endpoint returns a token when called with no credentials."""
        # Act
        response = client.get("/auth/token")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "access_token" in data
        assert "expires_in" in data

    def test_anonymous_token_subject_is_anonymous(self, client):
        """Subject of a no-credential token is 'anonymous'."""
        # Act
        response = client.get("/auth/token")
        token = response.json()["token"]

        # Assert
        assert get_subject(token) == "anonymous"

    def test_valid_credentials_return_token(self, client, user_store_with_alice):
        """Valid Basic Auth credentials yield a token for the user."""
        # Act
        response = client.get(
            "/auth/token",
            headers={"Authorization": _basic("alice", "password123")},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert get_subject(data["token"]) == "alice"

    def test_invalid_password_returns_401(self, client, user_store_with_alice):
        """Wrong password yields 401."""
        # Act
        response = client.get(
            "/auth/token",
            headers={"Authorization": _basic("alice", "wrong")},
        )

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["errors"][0]["code"] == "UNAUTHORIZED"

    def test_unknown_user_returns_401(self, client):
        """Unknown user yields 401."""
        # Act
        response = client.get(
            "/auth/token",
            headers={"Authorization": _basic("nobody", "pass")},
        )

        # Assert
        assert response.status_code == 401

    def test_scope_embedded_in_token(self, client):
        """scope query param is parsed into access claim."""
        # Act
        response = client.get("/auth/token?scope=repository:alpine:pull,push")
        token = response.json()["token"]
        payload = decode_token(token)

        # Assert
        assert len(payload["access"]) == 1
        access_entry = payload["access"][0]
        assert access_entry["type"] == "repository"
        assert access_entry["name"] == "alpine"
        assert "pull" in access_entry["actions"]
        assert "push" in access_entry["actions"]

    def test_account_param_sets_subject(self, client):
        """account query param sets the subject for anonymous requests."""
        # Act
        response = client.get("/auth/token?account=mybot")
        token = response.json()["token"]

        # Assert
        assert get_subject(token) == "mybot"

    def test_malformed_basic_auth_returns_400(self, client):
        """A non-base64 Basic header returns 400."""
        # Act
        response = client.get(
            "/auth/token",
            headers={"Authorization": "Basic !!!not-base64!!!"},
        )

        # Assert
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# /v2/ authentication challenge
# ---------------------------------------------------------------------------


class TestV2AuthChallenge:
    def test_v2_without_token_returns_401(self, client):
        """GET /v2/ without a Bearer token returns 401."""
        # Act
        response = client.get("/v2/")

        # Assert
        assert response.status_code == 401

    def test_v2_without_token_www_authenticate_header(self, client):
        """The 401 response includes a WWW-Authenticate Bearer challenge."""
        # Act
        response = client.get("/v2/")

        # Assert
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"].startswith("Bearer realm=")

    def test_v2_with_valid_token_returns_200(self, authed_client):
        """GET /v2/ with a valid Bearer token returns 200."""
        # Act
        response = authed_client.get("/v2/")

        # Assert
        assert response.status_code == 200

    def test_v2_with_anonymous_token_returns_200(self, client):
        """A token issued for 'anonymous' from /auth/token is accepted by /v2/."""
        # Arrange – get an anonymous token
        token_resp = client.get("/auth/token")
        token = token_resp.json()["token"]

        # Act
        response = client.get("/v2/", headers={"Authorization": _bearer(token)})

        # Assert
        assert response.status_code == 200

    def test_v2_response_has_distribution_header(self, authed_client):
        """Successful /v2/ response carries the registry version header."""
        # Act
        response = authed_client.get("/v2/")

        # Assert
        assert response.headers.get("Docker-Distribution-API-Version") == "registry/2.0"


# ---------------------------------------------------------------------------
# Full docker login flow simulation
# ---------------------------------------------------------------------------


class TestDockerLoginFlow:
    def test_full_login_flow(self, client, user_store_with_alice):
        """
        Simulate docker login:
          1. GET /v2/  →  401 with WWW-Authenticate
          2. GET /auth/token with Basic creds  →  200 + JWT
          3. GET /v2/ with Bearer  →  200
        """
        # Step 1 – discovery
        r1 = client.get("/v2/")
        assert r1.status_code == 401
        www_auth = r1.headers["WWW-Authenticate"]
        assert "realm=" in www_auth

        # Step 2 – authenticate
        r2 = client.get(
            "/auth/token",
            headers={"Authorization": _basic("alice", "password123")},
        )
        assert r2.status_code == 200
        token = r2.json()["token"]
        assert get_subject(token) == "alice"

        # Step 3 – use token
        r3 = client.get("/v2/", headers={"Authorization": _bearer(token)})
        assert r3.status_code == 200

    @pytest.mark.parametrize("username,password,expected_status", [
        ("alice", "password123", 200),
        ("alice", "wrongpass", 401),
        ("unknown", "any", 401),
    ])
    def test_token_endpoint_parametrized(
        self, client, user_store_with_alice, username, password, expected_status
    ):
        """Token endpoint responds correctly across credential scenarios."""
        # Act
        response = client.get(
            "/auth/token",
            headers={"Authorization": _basic(username, password)},
        )

        # Assert
        assert response.status_code == expected_status
