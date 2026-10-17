/**
 * Every route an agent can pay for, and its default price (#200).
 *
 * This list is the allowlist. The edge serves a paid route only if it is here, and
 * every one lives under `/paid/` and runs in the core under `/api/v1/internal/paid/`.
 * Nothing here may reach an auth, wallet, statement, policy or lifecycle route: the
 * catalog test walks every entry and checks.
 *
 * Prices are USDC, decimal text. `EDGE_PRICES` overrides any of them by id.
 */

import type { PaidRoute } from './paid.js'

export const CATALOG: PaidRoute[] = []
