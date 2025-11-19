"""Entry point for running the Set Weaver orchestration pipeline."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, List

from set_weaver.agents.library_agent import LibraryAgent
from set_weaver.agents.strategist_agent import StrategistAgent
from set_weaver.agents.transition_agent import TransitionAgent
from set_weaver.schemas.track_data import SetlistReport
from set_weaver.tools.spotify_oauth import (
    OAuthToken,
    build_authorize_url,
    exchange_code_for_token,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)
from dotenv import load_dotenv


def _load_env() -> None:
    env_path = Path(os.getenv("SET_WEAVER_ENV", ".env"))
    if env_path.is_file():
        load_dotenv(env_path)
    else:
        load_dotenv()

COMMANDS = {"plan", "spotify-auth-url", "spotify-exchange-code"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Set Weaver workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Generate a DJ set plan")
    plan_parser.add_argument("prompt", help="User description of the desired DJ set.")
    plan_parser.add_argument(
        "--override-title",
        help="Optional title to overwrite the Strategist's chosen set title.",
    )
    plan_parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit JSON without indentation for downstream piping.",
    )

    auth_parser = subparsers.add_parser(
        "spotify-auth-url",
        help="Generate a Spotify authorization URL using PKCE.",
    )
    auth_parser.add_argument(
        "--client-id",
        help="Spotify application client ID. Defaults to SPOTIFY_CLIENT_ID env var.",
    )
    auth_parser.add_argument(
        "--redirect-uri",
        required=True,
        help="Redirect URI registered with the Spotify application.",
    )
    auth_parser.add_argument(
        "--scope",
        action="append",
        help="OAuth scope to request. Repeat for multiple scopes.",
    )
    auth_parser.add_argument(
        "--state",
        help="Optional state to include in the authorization URL.",
    )
    auth_parser.add_argument(
        "--include-dialog",
        action="store_true",
        help="Force Spotify to display the consent dialog even if previously approved.",
    )

    token_parser = subparsers.add_parser(
        "spotify-exchange-code",
        help="Exchange an authorization code for access and refresh tokens.",
    )
    token_parser.add_argument(
        "--client-id",
        help="Spotify application client ID. Defaults to SPOTIFY_CLIENT_ID env var.",
    )
    token_parser.add_argument(
        "--client-secret",
        help="Optional client secret. Provide only when using the non-PKCE flow.",
    )
    token_parser.add_argument(
        "--redirect-uri",
        required=True,
        help="Redirect URI registered with the Spotify application.",
    )
    token_parser.add_argument("--code", required=True, help="Authorization code returned by Spotify.")
    token_parser.add_argument(
        "--code-verifier",
        required=True,
        help="Original code verifier used when generating the authorization URL.",
    )

    return parser


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = _build_parser()
    return parser.parse_args(argv)


def _serialize_report(report: SetlistReport, *, compact: bool) -> str:
    payload: dict[str, Any] = report.model_dump()
    indent = None if compact else 2
    return json.dumps(payload, indent=indent, sort_keys=not compact)


def _ensure_client_id(value: str | None) -> str:
    if value:
        return value
    env_value = os.getenv("SPOTIFY_CLIENT_ID")
    if not env_value:
        raise RuntimeError("Spotify client ID is required. Set SPOTIFY_CLIENT_ID or pass --client-id.")
    return env_value


def _handle_plan(args: argparse.Namespace) -> int:
    library_agent = LibraryAgent()
    transition_agent = TransitionAgent()
    strategist = StrategistAgent(library_agent, transition_agent)

    report = strategist.plan_set(args.prompt)
    if getattr(args, "override_title", None):
        report = report.model_copy(update={"set_title": args.override_title})

    print(_serialize_report(report, compact=args.compact))
    return 0


def _handle_auth_url(args: argparse.Namespace) -> int:
    client_id = _ensure_client_id(args.client_id)
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    state = args.state or generate_state()
    scopes: Iterable[str] | None = args.scope
    url = build_authorize_url(
        client_id=client_id,
        redirect_uri=args.redirect_uri,
        scopes=scopes,
        state=state,
        code_challenge=challenge,
        include_dialog=args.include_dialog,
    )
    payload = {
        "authorization_url": url,
        "code_verifier": verifier,
        "state": state,
        "scopes": list(scopes) if scopes else None,
    }
    print(json.dumps(payload, indent=2))
    return 0


def _token_to_payload(token: OAuthToken) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "access_token": token.access_token,
        "token_type": token.token_type,
        "expires_in": token.expires_in,
        "expires_at": token.expires_at,
    }
    if token.refresh_token:
        payload["refresh_token"] = token.refresh_token
    if token.scope:
        payload["scope"] = token.scope
    return payload


def _handle_exchange(args: argparse.Namespace) -> int:
    client_id = _ensure_client_id(args.client_id)
    token = exchange_code_for_token(
        client_id=client_id,
        code=args.code,
        redirect_uri=args.redirect_uri,
        code_verifier=args.code_verifier,
        client_secret=args.client_secret,
    )
    print(json.dumps(_token_to_payload(token), indent=2))
    return 0


def main(argv: List[str] | None = None) -> int:
    _load_env()
    raw_args = list(argv or sys.argv[1:])
    if raw_args and raw_args[0] not in COMMANDS and not raw_args[0].startswith("-"):
        raw_args = ["plan", *raw_args]
    parsed = _parse_args(raw_args)
    if parsed.command == "plan":
        return _handle_plan(parsed)
    if parsed.command == "spotify-auth-url":
        return _handle_auth_url(parsed)
    if parsed.command == "spotify-exchange-code":
        return _handle_exchange(parsed)
    raise RuntimeError(f"Unhandled command {parsed.command}")


if __name__ == "__main__":
    raise SystemExit(main())
