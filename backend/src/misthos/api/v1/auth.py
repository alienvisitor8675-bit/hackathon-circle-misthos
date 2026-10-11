"""Sign-in with a wallet (#70) and linking a GitHub account (#80)."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse

from misthos.api.guards import limit_signin
from misthos.api.session import SIGNED_IN, signed_in_address
from misthos.auth import sessions, siwe
from misthos.config import settings
from misthos.repositories import AccountConflict
from misthos.schemas import (
    Account,
    GitHubLinkStart,
    GitHubPendingOut,
    MeOut,
    NonceOut,
    RoleRequest,
    SessionOut,
    SignInRequest,
    SimulatedLink,
)
from misthos.services.github import GitHubError
from misthos.services.github.oauth import GitHubOAuth
from misthos.store import AccountExists, store

router = APIRouter(prefix="/auth", tags=["auth"])

NONCE_TTL = timedelta(minutes=10)
STATEMENT = "Sign in to Misthos. This costs nothing and moves no money."


def domain() -> str:
    return urlsplit(settings.public_url).netloc


def callback_url() -> str:
    return f"{settings.public_url.rstrip('/')}/api/v1/auth/github/callback"


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def oauth_configured() -> bool:
    """Whether a real GitHub account can be linked: the OAuth App's id and secret are
    both set. Read again on every call, so a test can configure it."""
    return bool(settings.github_oauth_client_id and settings.github_oauth_client_secret)


def oauth() -> GitHubOAuth | None:
    if not oauth_configured():
        return None
    return GitHubOAuth(settings.github_oauth_client_id, settings.github_oauth_client_secret)


def not_configured() -> HTTPException:
    """What an operator sets for linking to work, said where linking was asked for."""
    return HTTPException(
        status_code=503,
        detail="GitHub linking is not set up on this server: create a GitHub OAuth App "
        f"with the callback {callback_url()}, set MISTHOS_GITHUB_OAUTH_CLIENT_ID and "
        "MISTHOS_GITHUB_OAUTH_CLIENT_SECRET, and restart the API",
    )


@router.post("/nonce", response_model=NonceOut, dependencies=[limit_signin])
async def nonce() -> NonceOut:
    """A one-time nonce, and what the sign-in message must say around it."""
    value = secrets.token_hex(12)
    await run_in_threadpool(store.coordinator.put, f"siwe:{value}", "issued", NONCE_TTL)
    return NonceOut(
        nonce=value,
        domain=domain(),
        uri=settings.public_url,
        chain_id=settings.chain_id,
        statement=STATEMENT,
    )


@router.post("/verify", response_model=SessionOut, dependencies=[limit_signin])
async def verify(payload: SignInRequest, response: Response) -> SessionOut:
    """Check the signed message, spend its nonce, and start a session."""
    try:
        claimed = siwe.parse(payload.message)
    except siwe.SignInRefused as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    slot = f"siwe:{claimed.nonce}"
    if await run_in_threadpool(store.coordinator.get, slot) is None:
        raise HTTPException(status_code=401, detail="the nonce is unknown, used or expired")
    await run_in_threadpool(store.coordinator.delete, slot)  # one use, even if refused
    try:
        signed = siwe.verify(
            payload.message,
            payload.signature,
            domain=domain(),
            nonce=claimed.nonce,
            now=datetime.now(UTC),
        )
    except siwe.SignInRefused as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    address = signed.address.lower()
    token = sessions.issue(address)
    response.set_cookie(
        sessions.COOKIE,
        token,
        max_age=int(sessions.LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        # Sent only over HTTPS once the app is served there.
        secure=settings.public_url.startswith("https://"),
        path="/",
    )
    account = await run_in_threadpool(store.repo.get_account, address)
    return SessionOut(address=address, token=token, account=account)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> Response:
    response.delete_cookie(sessions.COOKIE, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=MeOut)
async def me(request: Request) -> MeOut:
    address = await signed_in_address(request)
    if address is None:
        raise HTTPException(status_code=401, detail="not signed in")
    account = await run_in_threadpool(store.repo.get_account, address)
    return MeOut(address=address, account=account)


@router.post("/role", response_model=Account, status_code=201)
async def choose_role(payload: RoleRequest, request: Request) -> Account:
    """The first sign-in's one choice: publisher or contributor."""
    address = await signed_in_address(request)
    if address is None:
        raise HTTPException(status_code=401, detail="sign in first")
    try:
        return await run_in_threadpool(
            lambda: store.create_account(
                address, payload.role, payload.name, budget_usdc=payload.budget_usdc
            )
        )
    except AccountExists as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


LINK_SLOT = "gh-link"
"""Where a link's state is kept between starting it and GitHub returning it."""

INSTALL_SLOT = "gh-install"
"""That a wallet was handed the install link.

The install link carries a link state, but GitHub is not documented to return it, so a
callback from an install may arrive with no state at all. This is what tells such a
callback apart from one nobody started here: only a wallet that was shown the install
link has it.
"""

PENDING_SLOT = "gh-pending"
"""A login GitHub reported, kept until the wallet that asked to install confirms it."""


async def mint_link_state(address: str) -> str:
    """A single-use state for a GitHub link, whichever flow finishes it.

    Two flows end at the same callback, and both need the state to prove the person
    finishing the link is the one who started it: the OAuth button, which authorizes
    and links in one trip, and the install link, which can authorize the same way
    while installing (see `repositories` in `publishers`). GitHub hands the state back,
    so one guard covers both and neither can be finished by another wallet.
    """
    state = secrets.token_urlsafe(24)
    await run_in_threadpool(store.coordinator.put, f"{LINK_SLOT}:{state}", address, NONCE_TTL)
    return state


async def record_install_intent(address: str) -> None:
    """Remember that this wallet was offered the install link."""
    await run_in_threadpool(store.coordinator.put, f"{INSTALL_SLOT}:{address}", "1", NONCE_TTL)


async def _pending_login(pending_id: str, address: str) -> dict[str, str]:
    """What GitHub reported, if this wallet is the one that asked to install."""
    held = await run_in_threadpool(store.coordinator.get, f"{PENDING_SLOT}:{pending_id}")
    if held is None:
        raise HTTPException(status_code=404, detail="this link is unknown or expired")
    found = json.loads(str(held))
    if found.get("address") != address:
        raise HTTPException(status_code=403, detail="this link belongs to another wallet")
    return found


@router.post(
    "/github/start",
    response_model=GitHubLinkStart,
    responses={
        409: {"description": "The browser is on another address than GitHub returns to"},
        503: {"description": "No GitHub OAuth App is configured; the detail says what to set"},
    },
)
async def start_github_link(
    request: Request, account: Account | None = SIGNED_IN
) -> GitHubLinkStart:
    """Where to send the user to approve linking their GitHub account."""
    if account is None:
        raise HTTPException(status_code=401, detail="sign in and choose a role first")
    client = oauth()
    if client is None:
        raise not_configured()
    # GitHub returns to the public URL, and the session cookie belongs to the address
    # the browser is on. Opened at 127.0.0.1:5173 with the public URL on localhost, the
    # callback would arrive without the session and be refused, after the user had
    # approved on GitHub. Said now instead, while it can still be put right.
    public = _origin(settings.public_url)
    origin = request.headers.get("origin")
    if origin and _origin(origin) != public:
        raise HTTPException(
            status_code=409,
            detail=f"GitHub sends you back to {public}, and this browser is on {origin}; "
            f"open the app at {public} and link from there",
        )
    state = await mint_link_state(account.address)
    return GitHubLinkStart(authorize_url=client.authorize_url(state, callback_url()))


@router.get("/github/callback", include_in_schema=False)
async def github_callback(
    request: Request, code: str, state: str | None = None
) -> RedirectResponse:
    """Finish a link, from either of the two ways one can start.

    The state is server-side, so it proves the flow began here; it does not prove who
    is finishing it. Without the session check any caller could start a link with
    their own wallet, send the authorize URL to someone else, and have that person's
    GitHub login bound to the attacker's account -- and `github_login` is what gates
    publishing, claiming and submitting, so the attacker would then be paid for work
    the victim opened. The account is therefore taken from the session and must match
    the address the state was issued to.

    A callback with no state at all is the install flow: with "Request user
    authorization (OAuth) during installation" on, GitHub sends the person here as
    part of installing, and it is not documented to return the state our install link
    carries. Linking on that would be the same hole, so the login is put aside and the
    wallet that was offered the install link confirms it instead.
    """
    address = await signed_in_address(request)
    if address is None:
        raise HTTPException(status_code=401, detail="sign in to finish linking GitHub")
    if state is None:
        return await _hold_for_confirmation(code, address)
    slot = f"{LINK_SLOT}:{state}"
    started_by = await run_in_threadpool(store.coordinator.get, slot)
    if started_by is None:
        raise HTTPException(status_code=400, detail="the link request is unknown or expired")
    if started_by != address:
        # Spend the state either way: it is single-use, and a mismatch is not a
        # request to leave it lying around for a second attempt.
        await run_in_threadpool(store.coordinator.delete, slot)
        raise HTTPException(status_code=403, detail="this link was started by another wallet")
    await run_in_threadpool(store.coordinator.delete, slot)
    client = oauth()
    if client is None:
        raise not_configured()
    try:
        login = await run_in_threadpool(client.login_for, code, callback_url())
        await run_in_threadpool(store.link_github, address, login)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AccountConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RedirectResponse(f"{settings.public_url.rstrip('/')}/account?linked=github", 303)


async def _hold_for_confirmation(code: str, address: str) -> RedirectResponse:
    """Put the reported login aside for the wallet that was offered the install."""
    offered = await run_in_threadpool(store.coordinator.get, f"{INSTALL_SLOT}:{address}")
    if offered is None:
        raise HTTPException(
            status_code=400,
            detail="this link was not started here: install the App from your account page",
        )
    client = oauth()
    if client is None:
        raise not_configured()
    try:
        login = await run_in_threadpool(client.login_for, code, callback_url())
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    pending_id = secrets.token_urlsafe(18)
    await run_in_threadpool(
        store.coordinator.put,
        f"{PENDING_SLOT}:{pending_id}",
        json.dumps({"address": address, "login": login}),
        NONCE_TTL,
    )
    return RedirectResponse(
        f"{settings.public_url.rstrip('/')}/account?github=pending&id={pending_id}", 303
    )


@router.get("/github/pending/{pending_id}", response_model=GitHubPendingOut)
async def github_pending(
    pending_id: str, account: Account | None = SIGNED_IN
) -> GitHubPendingOut:
    """What GitHub said, for the wallet that asked to install, so it can be shown."""
    if account is None:
        raise HTTPException(status_code=401, detail="sign in first")
    held = await _pending_login(pending_id, account.address)
    return GitHubPendingOut(login=held["login"])


@router.post("/github/confirm/{pending_id}", response_model=Account)
async def github_confirm(
    pending_id: str, account: Account | None = SIGNED_IN
) -> Account:
    """Bind the login GitHub reported to the wallet that asked to install.

    A person confirming the login they can see is what stands in for the state the
    install flow does not return; without it, anyone could hand a signed-in wallet a
    callback URL carrying their own code and be linked to it.
    """
    if account is None:
        raise HTTPException(status_code=401, detail="sign in first")
    held = await _pending_login(pending_id, account.address)
    try:
        linked = await run_in_threadpool(store.link_github, account.address, held["login"])
    except AccountConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await run_in_threadpool(store.coordinator.delete, f"{PENDING_SLOT}:{pending_id}")
    return linked


@router.post("/github/simulate", response_model=Account)
async def simulate_github_link(
    payload: SimulatedLink, account: Account | None = SIGNED_IN
) -> Account:
    """Link a GitHub login without OAuth, for the simulation's demo only."""
    if not settings.simulated:
        raise HTTPException(status_code=403, detail="link through GitHub")
    if account is None:
        raise HTTPException(status_code=401, detail="sign in and choose a role first")
    try:
        return await run_in_threadpool(store.link_github, account.address, payload.login)
    except AccountConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
