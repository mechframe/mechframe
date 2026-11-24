---
feature: The signed-out session read (decision 0063): `GET /api/auth/session` answers 200 with no user to a signed-out visitor, so a public page logs no 401 (the owner's ask, through VM Website)
status: approved
approved: 2026-11-23, as recommended ("Yes" to approving it as recommended): §8's two answers
plan: `dev plans/2026-11-23-next-session-m4g-name-shell-session.md` §4, 3
pr: #141
---

# Contract: the signed-out session read

## 1. Goal

A signed-out visitor's browser asks who's signed in, and the answer is 200 `{"user": null}`, not 401. A public page then logs no error in the browser's console. Every route that needs a session still answers 401 `kernel.not_signed_in`.

## 2. Interfaces

**HTTP:** `GET /api/auth/session` becomes **public** (`optional_user`, which marks a route public).
- **Signed in:** 200 `{"user": {...}}`, as now.
- **Not signed in:** 200 `{"user": null}`. That covers no cookie, a cookie for no session, and a session that has expired, ended (sign-out, reset, a second factor removed) or belongs to a suspended account.
- **Both answers** carry `Cache-Control: no-store`, since the answer names who's signed in.
- **A dead cookie is left alone, not cleared** (§8, 1). A read sent with an old cookie can land after a sign-in in another tab, and clearing it would sign that tab out. The next sign-in replaces it.
- **The session's renewal** (`SessionCookies`) doesn't change.
- **Unchanged:** every other route that needs a session still answers 401. The web client's `setApiHandlers` still reads the session again after a 401 elsewhere, and now reads `user: null` as gone.

**Python:**
- `kernel.auth.answers.SessionRead(Answer)`, with `user: UserView | None`, is the read's answer model.
- `SessionAnswer`, `user: UserView`, stays for the routes that answer a signed-in person: sign-in, the name, and the rest.

**Web:**
- `readSession` in `kernel/web/src/session/session.tsx` returns `data.user`, which is `null` when signed out.
- It still reads a 401 as signed out, for a browser holding the new web against a server not yet upgraded.
- `useSession` and `Session` don't change.

**The template:** `templates/site/web/e2e/smoke.spec.ts` drops `signedOutCheck`, its allowance for the session read's 401. A signed-out visitor's pages then log no console error at all, and the smoke fails if one does.

## 3. Data

None.

## 4. Files

- **Backend:** `kernel/backend/kernel/auth/answers.py` (`SessionRead`); `kernel/backend/kernel/auth/routes.py` (the `session` route: `optional_user`, no-store).
- **Generated:** `kernel/openapi.json` and the web's `schema.ts` files (`python -m tools.openapi`, then `npm run api:types`).
- **Web:** `kernel/web/src/session/session.tsx` and `session.test.tsx`.
- **Template:** `templates/site/web/e2e/smoke.spec.ts`.
- **The contract suite:**
  - `kernel/tests/contract/conftest.py`: `Api.who() -> dict | None`. It reads the session, asserts 200 and no-store, and answers `user`.
  - `test_auth_contract.py`: its 48 session reads. Where one asserts 401 to mean "this session ended", it asserts `await api.who() is None` instead.
- **Kernel tests:** the session reads in `kernel/tests/auth/` (13 files, 9 of them asserting 401), as above.
- **Docs:**
  - `docs/contracts/auth-api.md`: the `GET /api/auth/session` row.
  - `docs/decisions/0063-the-signed-out-session-read.md` and its row in `docs/decisions/README.md`.
  - `docs/progress.json`, then `python -m tools.progress`.
  - SPEC doesn't change: it never names the read's 401.
- **Number:** 0063, not 0064 as the session prompt had it. 0063 was held for the admin shell's page order in case it changed the manifest; it didn't (#140, decision 0044 amended). That keeps the numbers without a gap.

## 5. Conventions this follows

- `CLAUDE.md`, Rules: tests first; the contract tests of spec 14.13.
- `kernel/backend/kernel/access.py`: a public route's mark.
- `passkeys.py`'s and `totp.py`'s `_NO_STORE`.

## 6. Non-goals

- No reason given for a signed-out answer ("expired" against "never signed in"), so the read tells a stranger nothing about a cookie.
- No change to any other route's 401.
- No change to VM Website's own copy of the smoke. It drops its allowance itself after upgrading the kernel; it'll be told.

## 7. Acceptance

- **Contract:** `test_auth_contract.py`, `test_get_session`, seen failing first. Signed in, the read answers 200 with the user. With no cookie, an unknown cookie, an ended session and an expired one, it answers 200 `{"user": null}` with no-store and no `Set-Cookie`.
- **The rest of the contract suite** stays green through `Api.who()`, and `test_members_and_strangers_reach_no_admin_route` is unchanged.
- **Web:** `session.test.tsx`: "is signed out on a 200 with no user", and the existing 401 test kept. The test of a 401 elsewhere reading the session again now has that read answer 200 null.
- **Template:** `python -m tools.site_smoke` (CI's E2E workflow), with no 401 allowed.
- **Live:** in the harness, signed out, open `/` and `/blog`: the console has no error, and the read answers 200 `{"user": null}`.

## 8. Open questions

None. The owner's answers, 2026-11-23, as recommended:
1. A dead session cookie (expired or ended) is left alone, not cleared in the read's answer (§2, the race with a sign-in in another tab).
2. The signed-out answer is `{"user": null}`, the same shape as signed in, so the web reads one field.

## Changes after approval

- 2026-11-23, as built (#141):
  - **The web's other tests that faked the read's 401** (`mount.test.tsx`, `Landings.test.tsx`, `StepUp.test.tsx`, and the second read in `session.test.tsx`'s "any call finds the session gone") now fake `200 {"user": null}`, as the server answers. `session.test.tsx` keeps one 401 test, for a server not yet upgraded.
  - **`client.test.tsx`'s typed read** reads `user?.email`, since `user` may be null now.
  - **The suites' "still signed in" checks** moved to `who()` too (`is not None`). A bare 200 now holds for anyone.
