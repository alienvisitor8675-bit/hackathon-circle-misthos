"""The core's side of the paid API: only the edge may call it (#200).

An agent buys a call from the edge over x402. The edge verifies the payment, asks the
core here to do the work, and settles only if the core answered. These routes are
therefore internal: every request must carry the edge's `X-Misthos-Core-Token`, and one
that does not is answered 404, as if nothing were here. They are not in the API schema.

Every route here reads; none moves money, changes an issue, or touches a session,
wallet, statement or policy. The edge's catalog is the allowlist of what is sold, and
each entry names one route under this prefix.

- `POST /access` says whether a signed-in caller may use a paid route free.
- `POST /calls` writes down a settlement once the edge has settled it.
- `GET /calls` reads the books of paid calls back, to reconcile with Circle Gateway.
"""

from __future__ import annotations

import hmac
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool

from misthos.auth import sessions
from misthos.config import settings
from misthos.domain.money import Usdc
from misthos.domain.paid import PaidCall, totals
from misthos.schemas import (
    PaidAccess,
    PaidAccessAsked,
    PaidCallIn,
    PaidCallOut,
    PaidCallsOut,
    PaidRouteTotal,
    money,
)
from misthos.services.paid import PaidCaller, is_free, who
from misthos.store import store

PREFIX = "/internal/paid"


async def edge_only(request: Request) -> None:
    """Refuse anyone but the edge, and say nothing about why."""
    expected = settings.edge_core_token
    given = request.headers.get("x-misthos-core-token", "")
    if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(status_code=404, detail="Not Found")


def paid_caller(request: Request) -> PaidCaller:
    """Who the edge says this call is for. Trusted because only the edge gets here."""
    return PaidCaller(
        route=request.headers.get("x-misthos-paid-route", ""),
        payer=request.headers.get("x-misthos-payer") or None,
        free_caller=request.headers.get("x-misthos-free-caller") or None,
    )


PAID_CALLER = Depends(paid_caller)

router = APIRouter(prefix=PREFIX, tags=["paid"], dependencies=[Depends(edge_only)])


@router.post("/access", response_model=PaidAccess)
async def access(asked: PaidAccessAsked, request: Request) -> PaidAccess:
    """Whether the caller the edge is holding may use `route` free.

    The edge passes on the caller's own `Authorization` in
    `X-Misthos-Caller-Authorization`; a session it names is looked up here and checked
    against the route's free-tier rule. Anything else is not free.
    """
    header = request.headers.get("x-misthos-caller-authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    address = sessions.address_in(token) if token else None
    account = await run_in_threadpool(store.repo.get_account, address) if address else None
    if account is None or not is_free(asked.route, account, asked.params):
        return PaidAccess(free=False)
    return PaidAccess(free=True, who=who(account))


def _call_out(call: PaidCall) -> PaidCallOut:
    return PaidCallOut(
        id=call.id,
        route=call.route,
        request_digest=call.request_digest,
        payer=call.payer,
        amount=money(call.amount),
        network=call.network,
        asset=call.asset,
        transaction=call.transaction,
        ref=call.ref,
        settled_at=call.settled_at,
    )


@router.post("/calls", response_model=PaidCallOut, status_code=201)
async def record_call(body: PaidCallIn, response: Response) -> PaidCallOut:
    """Write down a settlement. The same settlement twice is recorded once (200)."""
    call, new = await run_in_threadpool(
        lambda: store.record_paid_call(
            route=body.route,
            request_digest=body.request_digest,
            payer=body.payer,
            amount=Usdc(body.amount_base_units),
            network=body.network,
            asset=body.asset,
            transaction=body.transaction,
            ref=body.ref,
        )
    )
    if not new:
        response.status_code = 200
    return _call_out(call)


@router.get("/calls", response_model=PaidCallsOut)
async def list_calls(
    since: Annotated[datetime | None, Query()] = None,
    route: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> PaidCallsOut:
    """The books: settled calls, newest first, and what each route earned per network."""
    calls = await run_in_threadpool(
        lambda: store.list_paid_calls(since=since, route=route, limit=limit)
    )
    return PaidCallsOut(
        calls=[_call_out(c) for c in calls],
        totals=[
            PaidRouteTotal(route=t.route, network=t.network, calls=t.calls, amount=money(t.amount))
            for t in totals(calls)
        ],
        total=money(Usdc(sum(c.amount.base_units for c in calls))),
    )
