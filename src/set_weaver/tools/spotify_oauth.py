"""Utilities for handling Spotify OAuth 2.0 flows with PKCE support."""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from typing import Iterable, Mapping, MutableMapping

import requests

SPOTIFY_ACCOUNTS_BASE = "https://accounts.spotify.com"
SPOTIFY_AUTHORIZE_URL = f"{SPOTIFY_ACCOUNTS_BASE}/authorize"
SPOTIFY_TOKEN_URL = f"{SPOTIFY_ACCOUNTS_BASE}/api/token"

_DEFAULT_SCOPE = "user-read-private"


@dataclass
class OAuthToken:
    """Container for Spotify access and refresh tokens."""

    access_token: str
    token_type: str
    expires_in: int
    expires_at: int
    refresh_token: str | None = None
    scope: str | None = None

    @property
    def is_expired(self) -> bool:
        return int(time.time()) >= self.expires_at


def generate_code_verifier(length: int = 64) -> str:
    verifier = secrets.token_urlsafe(length)
    return verifier[:128]


def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_state(length: int = 16) -> str:
    return secrets.token_urlsafe(length)


def build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    scopes: Iterable[str] | None = None,
    state: str | None = None,
    code_challenge: str,
    code_challenge_method: str = "S256",
    include_dialog: bool = False,
) -> str:
    scope_param = " ".join(scopes or [_DEFAULT_SCOPE])
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope_param,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    }
    if state:
        params["state"] = state
    if include_dialog:
        params["show_dialog"] = "true"
    query = "&".join(f"{key}={requests.utils.quote(str(value))}" for key, value in params.items())
    return f"{SPOTIFY_AUTHORIZE_URL}?{query}"


def _post_token(data: MutableMapping[str, str], *, client_id: str, client_secret: str | None) -> Mapping[str, str]:
    headers: dict[str, str]
    if client_secret:
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode("ascii")).decode("ascii")
        headers = {"Authorization": f"Basic {basic}"}
    else:
        data["client_id"] = client_id
        headers = {}
    response = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers, timeout=15)
    if response.status_code != 200:
        raise RuntimeError(f"Spotify token request failed: {response.status_code} {response.text}")
    return response.json()


def exchange_code_for_token(
    *,
    client_id: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    client_secret: str | None = None,
) -> OAuthToken:
    payload: MutableMapping[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    token_json = _post_token(payload, client_id=client_id, client_secret=client_secret)
    return _parse_token_response(token_json)


def refresh_access_token(
    *,
    client_id: str,
    refresh_token: str,
    client_secret: str | None = None,
) -> OAuthToken:
    payload: MutableMapping[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    token_json = _post_token(payload, client_id=client_id, client_secret=client_secret)
    if "refresh_token" not in token_json:
        token_json["refresh_token"] = refresh_token
    return _parse_token_response(token_json)


def _parse_token_response(payload: Mapping[str, str]) -> OAuthToken:
    expires_in = int(payload.get("expires_in", 3600))
    expires_at = int(time.time()) + expires_in
    return OAuthToken(
        access_token=payload["access_token"],
        token_type=payload.get("token_type", "Bearer"),
        expires_in=expires_in,
        expires_at=expires_at,
        refresh_token=payload.get("refresh_token"),
        scope=payload.get("scope"),
    )
