"""Spotify-powered track discovery utilities."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List

import requests
from requests import HTTPError

from set_weaver.schemas.track_data import TrackData, TrackFilter

SPOTIFY_API_BASE = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"

_GENRE_ALIASES = {
    "deep house": "deep-house",
    "progressive house": "progressive-house",
    "tech house": "tech-house",
    "melodic techno": "melodic-techno",
    "electronic": "electronic",
    "house": "house",
    "techno": "techno",
    "trance": "trance",
    "drum & bass": "drum-and-bass",
    "drum and bass": "drum-and-bass",
}

_FALLBACK_GENRES = [
    "house",
    "electronic",
    "dance",
    "techno",
]

_MAJOR_CAMELOT = [
    "8B",
    "3B",
    "10B",
    "5B",
    "12B",
    "7B",
    "2B",
    "9B",
    "4B",
    "11B",
    "6B",
    "1B",
]
_MINOR_CAMELOT = [
    "5A",
    "12A",
    "7A",
    "2A",
    "9A",
    "4A",
    "11A",
    "6A",
    "1A",
    "8A",
    "3A",
    "10A",
]


def _normalize_genre_seed(name: str) -> str:
    lookup = name.strip().lower()
    return _GENRE_ALIASES.get(lookup, lookup.replace(" ", "-"))


def _energy_to_level(value: float | None) -> int:
    if value is None:
        return 5
    scaled = int(round(max(0.0, min(1.0, value)) * 9)) + 1
    return max(1, min(10, scaled))


def _normalize_energy(value: int, *, upper: bool = False) -> float:
    normalized = max(0.0, min(1.0, value / 10))
    if upper:
        return min(0.99, max(normalized, 0.1))
    return max(0.01, min(0.9, normalized - 0.05))


def _camelot_from_audio_features(key_index: int | None, mode: int | None) -> str | None:
    if key_index is None or key_index < 0 or key_index > 11:
        return None
    if mode == 1:
        return _MAJOR_CAMELOT[key_index]
    if mode == 0:
        return _MINOR_CAMELOT[key_index]
    return None


@dataclass
class SpotifyToken:
    access_token: str
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 30


class SpotifyRecommendationClient:
    """Minimal Spotify client using the Client Credentials flow."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: SpotifyToken | None = None

    @classmethod
    def from_env(cls) -> SpotifyRecommendationClient:
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            msg = "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are required for Spotify search"
            raise RuntimeError(msg)
        return cls(client_id, client_secret)

    def query(self, track_filter: TrackFilter, *, limit: int = 10) -> List[TrackData]:
        tracks = self._fetch_via_search(track_filter, limit=limit)
        if not tracks:
            return []
        results: List[TrackData] = []
        for track in tracks:
            # Estimate BPM from filter midpoint since audio-features requires extra scopes
            estimated_bpm = (track_filter.bpm_min + track_filter.bpm_max) // 2
            # Assign random Camelot key or use filter if provided
            camelot = track_filter.key_camelot or "8A"
            # Estimate energy from track popularity (0-100) scaled to 1-10
            popularity = track.get("popularity", 50)
            estimated_energy = max(1, min(10, (popularity // 10) + 1))
            
            duration_ms = track.get("duration_ms", 0) or 0
            artists = ", ".join(artist.get("name", "") for artist in track.get("artists", [])) or "Unknown Artist"
            results.append(
                TrackData(
                    id=track["id"],
                    artist=artists,
                    title=track.get("name", "Unknown Track"),
                    genre=track_filter.genre,
                    bpm=estimated_bpm,
                    key_camelot=camelot,
                    energy_level=estimated_energy,
                    duration_sec=max(1, duration_ms // 1000),
                )
            )
        return results

    def _fetch_via_search(self, track_filter: TrackFilter, *, limit: int) -> List[Dict]:
        """Use Spotify search (client credentials compatible, no audio-features needed)."""
        query_variants = self._build_search_queries(track_filter)
        for query in query_variants:
            params = {
                "q": query,
                "type": "track",
                "limit": min(limit, 50),
            }
            response = self._get("/search", params)
            items = response.get("tracks", {}).get("items", [])
            if items:
                return items[:limit]
        return []

    def _build_search_queries(self, track_filter: TrackFilter) -> list[str]:
        normalized = _normalize_genre_seed(track_filter.genre)
        fallback_queries: list[str] = []
        if normalized:
            fallback_queries.append(f"genre:{normalized}")
        if track_filter.genre:
            fallback_queries.append(track_filter.genre.strip())
        if normalized:
            fallback_queries.append(normalized.replace("-", " "))
        for genre in _FALLBACK_GENRES:
            fallback_queries.append(f"genre:{genre}")
        seen: set[str] = set()
        ordered: list[str] = []
        for term in fallback_queries:
            candidate = term.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            ordered.append(candidate)
        return ordered

    def _get(self, path: str, params: Dict[str, str | float | int]) -> Dict:
        token = self._ensure_token()
        url = f"{SPOTIFY_API_BASE}{path}"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if response.status_code == 401:
            self._token = None
            token = self._ensure_token()
            headers["Authorization"] = f"Bearer {token}"
            response = requests.get(url, headers=headers, params=params, timeout=20)
        self._ensure_success(response)
        return response.json()

    @staticmethod
    def _ensure_success(response: requests.Response) -> None:
        try:
            response.raise_for_status()
        except HTTPError as exc:  # pragma: no cover - passthrough logging
            detail = response.text
            raise RuntimeError(
                "Spotify API request failed. Double-check the genre seed, tempo bounds, and that your app has access to recommendations. "
                f"Status {response.status_code}: {detail}",
            ) from exc

    def _ensure_token(self) -> str:
        if self._token and not self._token.is_expired:
            return self._token.access_token
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        response = requests.post(TOKEN_URL, data=data, timeout=15)
        if response.status_code != 200:
            detail = response.text
            raise RuntimeError(
                "Spotify client credentials request failed. Verify SPOTIFY_CLIENT_ID/SECRET and that the app allows the client credentials flow. "
                f"Status {response.status_code}: {detail}",
            )
        payload = response.json()
        access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        self._token = SpotifyToken(access_token=access_token, expires_at=time.time() + expires_in)
        return access_token


_SPOTIFY_CLIENT: SpotifyRecommendationClient | None = None


def get_spotify_client() -> SpotifyRecommendationClient:
    global _SPOTIFY_CLIENT
    if _SPOTIFY_CLIENT is None:
        _SPOTIFY_CLIENT = SpotifyRecommendationClient.from_env()
    return _SPOTIFY_CLIENT


def spotify_enabled() -> bool:
    return bool(os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET"))


def query_spotify_library(filters: TrackFilter, *, limit: int = 10) -> List[TrackData]:
    client = get_spotify_client()
    return client.query(filters, limit=limit)
