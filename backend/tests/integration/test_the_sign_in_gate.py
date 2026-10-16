"""The sign-in gate (#181): a wallet, a GitHub account, then a side.

The gate links GitHub before the side is chosen, and choosing the side is what creates
the account. So a login is held against the wallet in between, takes the
one-login-one-wallet slot while it is held, and is adopted onto the account when it is
created. The first step has two doors: a wallet extension such as MetaMask, and a Circle
wallet, which signs the same message and is verified the same way.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from siwe_wallet import Wallet

from misthos.api.v1 import auth as auth_routes
from misthos.auth.siwe import checksum
from misthos.config import Settings, settings
from misthos.main import app
from misthos.services.github.oauth import GitHubOAuth
from misthos.services.wallets import Wallets, simulated_sign_in_address
from misthos.store import store

API = "/api/v1"
SIGN_IN_ID = "browser-7f3a9c2e5b1d4e8f"


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()
    yield


def sign_in(client: TestClient, wallet: Wallet) -> dict:
    nonce = client.post(f"{API}/auth/nonce").json()["nonce"]
    message = wallet.message(nonce)
    r = client.post(
        f"{API}/auth/verify", json={"message": message, "signature": wallet.sign(message)}
    )
    assert r.status_code == 200, r.text
    return r.json()


def me(client: TestClient) -> dict:
    r = client.get(f"{API}/auth/me")
    assert r.status_code == 200, r.text
    return r.json()


def link(client: TestClient, login: str) -> httpx.Response:
    return client.post(f"{API}/auth/github/simulate", json={"login": login})


def choose(client: TestClient, role: str, name: str, **extra: str) -> httpx.Response:
    return client.post(f"{API}/auth/role", json={"role": role, "name": name, **extra})


def oauth_answering(monkeypatch: pytest.MonkeyPatch, login: str) -> None:
    """A configured OAuth App, with GitHub answering that the approver is `login`."""

    def github(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "gho_once"})
        return httpx.Response(200, json={"login": login})

    client = GitHubOAuth("c", "s", transport=httpx.MockTransport(github))
    monkeypatch.setattr(auth_routes, "oauth", lambda: client)


def through_github(client: TestClient) -> httpx.Response:
    """Start a link, and come back from GitHub with the state it was given."""
    start = client.post(f"{API}/auth/github/start")
    assert start.status_code == 200, start.text
    state = parse_qs(urlsplit(start.json()["authorize_url"]).query)["state"][0]
    return client.get(
        f"{API}/auth/github/callback",
        params={"code": "c0de", "state": state},
        follow_redirects=False,
    )


class TestLinkingBeforeASide:
    def test_a_signed_in_wallet_with_no_account_links_a_typed_login(self) -> None:
        client = TestClient(app)
        wallet = Wallet(101)
        sign_in(client, wallet)

        r = link(client, "Ada-Dev")

        assert r.status_code == 200, r.text
        assert r.json() == {
            "address": wallet.address.lower(),
            "account": None,
            "pending_github_login": "Ada-Dev",
        }
        assert me(client)["pending_github_login"] == "Ada-Dev"
        # Linking created nothing: the side is still to choose.
        assert store.repo.get_account(wallet.address) is None

    def test_github_itself_links_before_a_side_and_returns_to_the_gate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        oauth_answering(monkeypatch, "ada-real")
        client = TestClient(app)
        sign_in(client, Wallet(102))

        back = through_github(client)

        # The refusal "sign in and choose a role first" is gone.
        assert back.status_code == 303, back.text
        assert back.headers["location"] == "http://localhost:5173/?signin=continue"
        assert me(client) | {"address": None} == {
            "address": None,
            "account": None,
            "pending_github_login": "ada-real",
        }

    def test_starting_a_link_still_needs_a_signed_in_wallet(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        oauth_answering(monkeypatch, "anyone")
        anonymous = TestClient(app)
        assert anonymous.post(f"{API}/auth/github/start").status_code == 401
        assert link(anonymous, "anyone").status_code == 401

    def test_a_wallet_can_change_the_login_it_holds_until_it_chooses_a_side(self) -> None:
        client = TestClient(app)
        sign_in(client, Wallet(103))
        link(client, "first-try")
        assert link(client, "second-try").status_code == 200
        assert me(client)["pending_github_login"] == "second-try"
        # And the login it let go of is free for another wallet.
        other = TestClient(app)
        sign_in(other, Wallet(104))
        assert link(other, "first-try").status_code == 200


class TestComingBackFromGitHub:
    def test_saying_no_on_github_comes_back_to_the_gate_with_nothing_linked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        oauth_answering(monkeypatch, "never-asked")
        client = TestClient(app)
        sign_in(client, Wallet(105))
        start = client.post(f"{API}/auth/github/start").json()["authorize_url"]
        state = parse_qs(urlsplit(start).query)["state"][0]

        # What GitHub sends back when the account holder cancels: an error, no code.
        back = client.get(
            f"{API}/auth/github/callback",
            params={"error": "access_denied", "state": state},
            follow_redirects=False,
        )

        assert back.status_code == 303
        assert back.headers["location"] == "http://localhost:5173/?signin=continue&github=cancelled"
        assert me(client)["pending_github_login"] is None


class TestOneLoginOneWallet:
    """The rule stays as it was; only its reach grows to links that are still pending."""

    def test_a_login_another_wallet_holds_is_refused_and_named(self) -> None:
        first, second = TestClient(app), TestClient(app)
        sign_in(first, Wallet(111))
        assert link(first, "same-login").status_code == 200

        sign_in(second, Wallet(112))
        r = link(second, "SAME-login")

        assert r.status_code == 409
        assert r.json()["detail"] == "SAME-login is being linked by another wallet"
        assert me(second)["pending_github_login"] is None

    def test_a_login_on_another_wallets_account_is_refused_and_named(self) -> None:
        first, second = TestClient(app), TestClient(app)
        sign_in(first, Wallet(113))
        link(first, "taken-login")
        assert choose(first, "contributor", "taken-login").status_code == 201

        sign_in(second, Wallet(114))
        r = link(second, "taken-login")

        assert r.status_code == 409
        assert r.json()["detail"] == "taken-login is linked to another wallet"

    def test_an_account_cannot_link_a_login_another_wallet_holds(self) -> None:
        """The older order, a side first and GitHub after, meets the same rule."""
        holder, legacy = TestClient(app), TestClient(app)
        sign_in(holder, Wallet(115))
        link(holder, "held-login")
        sign_in(legacy, Wallet(116))
        choose(legacy, "publisher", "Legacy Ltd")

        r = link(legacy, "held-login")

        assert r.status_code == 409
        assert me(legacy)["account"]["github_login"] is None

    def test_github_returning_a_login_another_wallet_holds_links_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = TestClient(app)
        sign_in(first, Wallet(117))
        link(first, "octo-held")

        oauth_answering(monkeypatch, "octo-held")
        second = TestClient(app)
        sign_in(second, Wallet(118))
        back = through_github(second)

        # Back to the gate, which says the login is another wallet's.
        assert back.status_code == 303
        assert back.headers["location"] == "http://localhost:5173/?signin=continue&github=taken"
        assert me(second)["pending_github_login"] is None
        assert me(first)["pending_github_login"] == "octo-held"


class TestChoosingTheSide:
    def test_the_side_creates_one_account_carrying_the_login(self) -> None:
        client = TestClient(app)
        wallet = Wallet(121)
        sign_in(client, wallet)
        link(client, "acme-maint")

        r = choose(client, "publisher", "Acme Widgets", budget_usdc="1200")

        assert r.status_code == 201, r.text
        account = r.json()
        assert account["github_login"] == "acme-maint"
        assert account["party_id"].startswith("PUB-")
        publisher = store.get_publisher(account["party_id"])
        assert publisher is not None and publisher.name == "Acme Widgets"
        assert publisher.wallet.address == wallet.address.lower()
        # The hold is spent: the account carries the login now.
        assert me(client)["pending_github_login"] is None
        assert me(client)["account"]["github_login"] == "acme-maint"

    def test_a_second_side_is_refused_with_the_conflict_named(self) -> None:
        client = TestClient(app)
        wallet = Wallet(122)
        sign_in(client, wallet)
        link(client, "once-only")
        assert choose(client, "contributor", "once-only").status_code == 201

        again = choose(client, "publisher", "Twice Inc")

        assert again.status_code == 409
        assert again.json()["detail"] == f"{wallet.address.lower()} already has a role"
        assert me(client)["account"]["role"] == "contributor"

    def test_a_contributors_handle_is_the_login_it_linked(self) -> None:
        client = TestClient(app)
        sign_in(client, Wallet(123))
        link(client, "hal-dev")

        account = choose(client, "contributor", "hal-dev").json()

        contributor = store.get_contributor(account["party_id"])
        assert contributor is not None and contributor.handle == "hal-dev"

    def test_a_publisher_may_leave_the_budget_to_the_default(self) -> None:
        client = TestClient(app)
        sign_in(client, Wallet(124))
        link(client, "no-budget")

        account = choose(client, "publisher", "No Budget Co").json()

        publisher = store.get_publisher(account["party_id"])
        assert publisher is not None and publisher.budget_remaining_usdc == "5,000.00"


class TestLeavingEarly:
    def test_leaving_after_any_step_leaves_no_account_behind(self) -> None:
        before = len(store.list_publishers()), len(store.list_contributors())
        client = TestClient(app)
        wallet = Wallet(131)
        sign_in(client, wallet)
        link(client, "came-and-went")

        assert store.repo.get_account(wallet.address) is None
        assert (len(store.list_publishers()), len(store.list_contributors())) == before

    def test_coming_back_finds_every_step_already_done_where_it_was_left(self) -> None:
        wallet = Wallet(132)
        first_visit = TestClient(app)
        sign_in(first_visit, wallet)
        link(first_visit, "came-back")

        # A new session for the same wallet: the gate resumes at the side.
        later = TestClient(app)
        sign_in(later, wallet)
        assert me(later) == {
            "address": wallet.address.lower(),
            "account": None,
            "pending_github_login": "came-back",
        }
        assert choose(later, "contributor", "came-back").json()["github_login"] == "came-back"


class TestTheTwoWalletDoors:
    """MetaMask and a Circle wallet are two doors to the same session."""

    def test_a_wallet_extension_signs_in_as_the_address_it_shares(self) -> None:
        wallet = Wallet(141)
        session = sign_in(TestClient(app), wallet)
        assert session["address"] == wallet.address.lower()
        assert session["account"] is None

    def circle_signs_in(self, client: TestClient) -> tuple[str, dict]:
        """The Circle door as the gate walks it, in the simulation: no frame opens."""
        started = client.post(f"{API}/auth/circle/session", json={"sign_in_id": SIGN_IN_ID})
        assert started.status_code == 200, started.text
        address = started.json()["address"]
        assert started.json()["challenge_id"] is None and started.json()["simulated"] is True

        nonce = client.post(f"{API}/auth/nonce").json()["nonce"]
        message = Wallet().message(nonce, address=checksum(address))
        signed = client.post(
            f"{API}/auth/circle/sign", json={"sign_in_id": SIGN_IN_ID, "message": message}
        )
        assert signed.status_code == 200, signed.text
        signature = signed.json()["signature"]
        verified = client.post(
            f"{API}/auth/verify", json={"message": message, "signature": signature}
        )
        assert verified.status_code == 200, verified.text
        return address, verified.json()

    def test_a_circle_wallet_signs_in_as_the_address_it_names(self) -> None:
        client = TestClient(app)
        address, session = self.circle_signs_in(client)

        assert address == simulated_sign_in_address(SIGN_IN_ID)
        assert session["address"] == address.lower()
        assert me(client)["address"] == address.lower()

    def test_a_circle_wallet_is_the_same_wallet_every_time(self) -> None:
        first, _ = self.circle_signs_in(TestClient(app))
        again, _ = self.circle_signs_in(TestClient(app))
        assert first == again

    def test_the_circle_wallet_goes_through_the_rest_of_the_gate(self) -> None:
        client = TestClient(app)
        address, _ = self.circle_signs_in(client)
        link(client, "circle-user")

        account = choose(client, "contributor", "circle-user").json()

        contributor = store.get_contributor(account["party_id"])
        assert contributor is not None
        # The wallet signed in with is the wallet the money moves through.
        assert contributor.wallet.address == address.lower()

    @pytest.mark.parametrize(
        ("what", "change"),
        [
            ("another site", {"domain": "evil.example"}),
            ("another wallet", {"address": Wallet(142).address}),
        ],
    )
    def test_circle_signs_only_this_sites_message_for_this_wallet(
        self, what: str, change: dict
    ) -> None:
        client = TestClient(app)
        address = client.post(f"{API}/auth/circle/session", json={"sign_in_id": SIGN_IN_ID}).json()[
            "address"
        ]
        nonce = client.post(f"{API}/auth/nonce").json()["nonce"]
        message = Wallet().message(nonce, **({"address": checksum(address)} | change))

        r = client.post(
            f"{API}/auth/circle/sign", json={"sign_in_id": SIGN_IN_ID, "message": message}
        )

        assert r.status_code == 400, what

    def test_circle_signs_nothing_for_a_nonce_nobody_issued_or_one_already_spent(self) -> None:
        client = TestClient(app)
        address = client.post(f"{API}/auth/circle/session", json={"sign_in_id": SIGN_IN_ID}).json()[
            "address"
        ]
        made_up = Wallet().message("0" * 24, address=checksum(address))
        body = {"sign_in_id": SIGN_IN_ID, "message": made_up}
        assert client.post(f"{API}/auth/circle/sign", json=body).status_code == 400

        nonce = client.post(f"{API}/auth/nonce").json()["nonce"]
        message = Wallet().message(nonce, address=checksum(address))
        body = {"sign_in_id": SIGN_IN_ID, "message": message}
        signature = client.post(f"{API}/auth/circle/sign", json=body).json()["signature"]
        verified = client.post(
            f"{API}/auth/verify", json={"message": message, "signature": signature}
        )
        assert verified.status_code == 200
        assert client.post(f"{API}/auth/circle/sign", json=body).status_code == 400

    def test_a_circle_signature_over_another_message_is_refused_as_today(self) -> None:
        """No path around `/auth/verify`: it recovers the address from the signature and
        the message together, so a Circle signature is no use for any other message."""
        client = TestClient(app)
        address = client.post(f"{API}/auth/circle/session", json={"sign_in_id": SIGN_IN_ID}).json()[
            "address"
        ]
        nonce = client.post(f"{API}/auth/nonce").json()["nonce"]
        signed = Wallet().message(nonce, address=checksum(address))
        signature = client.post(
            f"{API}/auth/circle/sign", json={"sign_in_id": SIGN_IN_ID, "message": signed}
        ).json()["signature"]

        other_nonce = client.post(f"{API}/auth/nonce").json()["nonce"]
        swapped = Wallet().message(other_nonce, address=checksum(address))
        r = client.post(f"{API}/auth/verify", json={"message": swapped, "signature": signature})

        assert r.status_code == 401
        assert client.get(f"{API}/auth/me").status_code == 401

    def test_a_sign_in_id_too_short_to_be_random_is_refused(self) -> None:
        r = TestClient(app).post(f"{API}/auth/circle/session", json={"sign_in_id": "abc"})
        assert r.status_code == 422


class TestTheCircleDoorLive:
    """Live, Circle's frame signs: the API hands it the challenge and never the key."""

    CIRCLE_WALLET = Wallet(151)
    """Stands in for the EOA Circle keeps half of; the test signs as the frame would."""

    @pytest.fixture
    def edge(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict | None]]:
        monkeypatch.setattr(settings, "simulated", False)
        monkeypatch.setattr(settings, "edge_core_token", "secret")
        calls: list[tuple[str, dict | None]] = []

        def answer(request: httpx.Request) -> httpx.Response:
            assert request.headers["X-Misthos-Core-Token"] == "secret"
            body = json.loads(request.content) if request.content else None
            calls.append((request.url.path, body))
            common = {
                "circleUserId": f"misthos-signin-{SIGN_IN_ID}",
                "appId": "app-1",
                "userToken": "ut",
                "encryptionKey": "ek",
                "blockchain": "ARC-TESTNET",
                "simulated": False,
            }
            calls[-1] = (f"{request.method} {request.url.path}", body)
            address = self.CIRCLE_WALLET.address.lower()
            if request.url.path.endswith("/session"):
                return httpx.Response(200, json=common | {"challengeId": None, "address": address})
            if request.method == "GET":
                return httpx.Response(200, json=common | {"address": address})
            return httpx.Response(200, json=common | {"challengeId": "sign-challenge-1"})

        transport = httpx.MockTransport(answer)

        def wallets(cfg: Settings) -> Wallets:
            return Wallets(cfg, httpx.AsyncClient(transport=transport))

        monkeypatch.setattr(auth_routes, "Wallets", wallets)
        return calls

    def test_the_frame_signs_and_verify_recovers_the_circle_wallet(
        self, edge: list[tuple[str, dict | None]]
    ) -> None:
        client = TestClient(app)
        started = client.post(f"{API}/auth/circle/session", json={"sign_in_id": SIGN_IN_ID})
        address = started.json()["address"]
        nonce = client.post(f"{API}/auth/nonce").json()["nonce"]
        message = self.CIRCLE_WALLET.message(nonce, address=checksum(address))

        signed = client.post(
            f"{API}/auth/circle/sign", json={"sign_in_id": SIGN_IN_ID, "message": message}
        )

        assert signed.status_code == 200, signed.text
        assert signed.json() | {"user_token": None} == {
            "app_id": "app-1",
            "user_token": None,
            "encryption_key": "ek",
            "challenge_id": "sign-challenge-1",
            "signature": None,
            "simulated": False,
        }
        # The address was read back, not a second session started, then the message sent.
        assert edge[-2:] == [
            (f"GET /wallets/sign-in/{SIGN_IN_ID}", None),
            (f"POST /wallets/sign-in/{SIGN_IN_ID}/sign", {"message": message}),
        ]
        # What Circle's frame hands back once the PIN is entered.
        signature = self.CIRCLE_WALLET.sign(message)
        session = client.post(
            f"{API}/auth/verify", json={"message": message, "signature": signature}
        ).json()
        assert session["address"] == self.CIRCLE_WALLET.address.lower()

    def test_reading_the_wallet_back_starts_nothing_at_circle(
        self, edge: list[tuple[str, dict | None]]
    ) -> None:
        r = TestClient(app).post(f"{API}/auth/circle/wallet", json={"sign_in_id": SIGN_IN_ID})

        assert r.status_code == 200, r.text
        assert r.json() == {"address": self.CIRCLE_WALLET.address.lower(), "simulated": False}
        assert edge == [(f"GET /wallets/sign-in/{SIGN_IN_ID}", None)]

    def test_without_an_edge_the_circle_door_says_what_to_set_up(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "simulated", False)
        monkeypatch.setattr(settings, "edge_core_token", "")
        client = TestClient(app)
        assert client.get(f"{API}/health").json()["circle_sign_in"] is False

        r = client.post(f"{API}/auth/circle/session", json={"sign_in_id": SIGN_IN_ID})

        assert r.status_code == 503
        for needed in ("MISTHOS_EDGE_CORE_TOKEN", "CIRCLE_API_KEY"):
            assert needed in r.json()["detail"]

    def test_the_simulation_offers_the_circle_door(self) -> None:
        assert TestClient(app).get(f"{API}/health").json()["circle_sign_in"] is True

    def test_outside_the_simulation_a_login_is_linked_only_through_github(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = TestClient(app)
        sign_in(client, Wallet(152))
        monkeypatch.setattr(settings, "simulated", False)
        assert link(client, "typed-login").status_code == 403
        assert me(client)["pending_github_login"] is None
