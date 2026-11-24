---
feature: The account's name (decision 0061): a person sets the name the site shows for them, and staff set it for someone in People (M4; the owner, 2026-11-23: "now")
status: approved
approved: 2026-11-23, as recommended ("Approve as recommended"): §8's three answers
plan: `dev plans/2026-11-21-vibrant-mindz-push-plan.md` (M4); `dev plans/2026-11-23-next-session-m4g-name-shell-session.md` §4, 1
pr: #139
---

# Contract: the account's name

## 1. Goal

Anyone signed in can give themselves a name, change it or remove it on their account pages. Staff holding `auth.user.manage` can do the same for someone in People, if they outrank that person. The name then shows wherever the site already reads `auth_user.display_name`: the session's `name` and the admin's person card (#119), People, the admin's Activity, blog's author list and bylines, media's and pages' "by", and the data export. Today nothing sets it, so a post's byline shows no one.

## 2. Interfaces

**The name's rules,** `kernel.auth.names.clean_name(text: str) -> str | None`, applied in this order:
1. Unicode NFC.
2. Every run of whitespace becomes one space (line breaks and tabs included), and the ends are trimmed.
3. Refused (`ValueError`): a control character (category Cc), or a direction override, embedding or isolate (U+202A to U+202E, U+2066 to U+2069), which could make a name read as something else in a list.
4. At most 120 characters (the column), each code point counted as one.

An empty result is no name: `display_name` becomes NULL. Names aren't unique.

**HTTP**, under `/api/auth`. Both routes take `{name: string}`, strict, at most 240 characters as sent. A refused name answers 422 `kernel.invalid_request` with "A name is up to 120 characters, on one line." A name that is the same once cleaned changes nothing and writes no audit entry.
- `PUT /account/name`: signed in, **no step-up** (a name opens nothing). It answers 200 `{"user": {...}}`, as `GET /session` does. The account row is locked and the session checked with `accounts.held`, as renaming a passkey does. Limit: `rate_limit("10/1h", key="account")`, then 429 `kernel.rate_limited`.
- `PUT /admin/users/{id}/name`: `auth.user.manage`, **step-up**, as other People writes are. It answers 200 with the person as `GET /admin/users` gives them (`Person`). It locks both rows in id order, as `set_roles` does.
  - 403 `auth.role_not_yours`, unless the caller outranks the person by decision 0013's rule, as suspension applies it: only an owner renames an owner; anyone else is renamed only by someone holding every permission they hold; `member` is no rank. Callers always outrank themselves.
  - 404 `kernel.not_found` for no such person, or a deleted one.
  - 409 `auth.account_not_active` when the caller is no longer active, or the person is being deleted. A suspended person can still be renamed, so staff can clear an offensive name.
- `GET /admin/users?q=` also finds names that contain `q`, case ignored, matched as typed and never as a pattern (`autoescape`), as it finds addresses now.
- **The guard is shared.** `moderation._outranked` moves to `kernel.auth.permissions.outranks(db, actor: uuid.UUID, person: uuid.UUID) -> bool`, and moderation calls it there.

**Audit:** `auth.name_changed`, new in `KERNEL_ACTIONS`. The actor is whoever changed the name; the subject is the account. `details` is `{"cleared": true}` when the name was removed, and otherwise empty. The entry never holds a name, just as `auth.email_changed` holds no address. A person's own Activity calls it "Changed the name", and already marks entries they didn't make. The admin's Activity lists it with auth's actions (`admin/actions.ts`).

**No event.** Every place reads the name live, and nothing keeps a copy (blog's search documents hold the title, summary and body only).

**Passkeys:** a passkey registered after this carries the name as WebAuthn's `user.displayName`, or the email when there's none. `user.name` stays the email.

**Web.**
- **Account** (§8, 1): a new page, `/account/profile`, called Profile, first in `AccountPage`'s pills, as VM Website's Account board draws them.
  - Its card, Name ("Shown to staff, and on what you publish here."), shows the name or "No name yet", and a Change button.
  - Change opens a dialog with one field, Name ("Up to 120 characters. Leave it empty for none."). Saving puts the answer in the session's cache (`SESSION_KEY`) and says "Saved your name."
  - `AccountPage` says "Signed in as {name}", or the email when there's no name, as the board has it.
- **People:**
  - Everyone on People gets Open on every row; today only those holding `auth.role.assign` do.
  - `PersonRoles` becomes `PersonDialog`. It opens with a Name field and its own "Save name" button. The roles below it show only to those holding `auth.role.assign`, and work as now.
  - The Name field is read-only, with the reason under it, when the reader doesn't outrank the person. The dialog works that out from `GET /admin/roles`, which it reads already; the server refuses regardless.
  - Renaming yourself refreshes the session (`refreshSession`), as your own roles do.
  - The search field's label becomes "Search by name or email".

## 3. Data

None. `auth_user.display_name varchar(120) NULL` is in `kernel_0002` already. No migration and no database check; `kernel_0017` stays free.

## 4. Files

- **Backend:**
  - `kernel/backend/kernel/auth/names.py`, new: `clean_name`, `NameBody`, both routes, mounted in `app.py` beside `passkeys_router`.
  - `kernel/backend/kernel/auth/permissions.py`: `outranks`.
  - `kernel/backend/kernel/moderation.py`: imports `outranks`.
  - `kernel/backend/kernel/auth/roles.py`: `q` matches names too.
  - `kernel/backend/kernel/auth/passkeys.py`: `displayName`.
  - `kernel/backend/kernel/audit.py`: the action.
- **Web:**
  - `kernel/web/src/account/Profile.tsx` and `Profile.test.tsx`, new.
  - `AccountPage.tsx`; `app/pages.ts` and `app/screens.ts`, where `/account/notifications` is declared.
  - `account/Activity.tsx`; `admin/People.tsx`, `admin/actions.ts`.
- **Generated:** `kernel/openapi.json` and the web's `schema.ts` (`python -m tools.openapi`, `npm run api:types`).
- **Docs:**
  - `SPEC.md`: 14.1 (a bullet on the name), 14.10 (name changes are audited) and 14.11 (`auth_user` lists the display name), plus the change log.
  - `docs/decisions/0061-the-accounts-name.md`, and `docs/contracts/auth-api.md`'s two new rows and the `q` change.
  - `docs/progress.json`, then `python -m tools.progress`.

## 5. Conventions this follows

`CLAUDE.md`, Rules (tests first; one logical change per PR); spec 14.13's contract tests; `PATCH /passkeys/{id}` for a name a person types, and `PUT /admin/users/{id}/roles` for a People write; decision 0013's rank rule; `kernel/web/src/account/Account.tsx`'s Email card for the card and its dialog.

## 6. Non-goals

- A name isn't asked at sign-up or by `mechframe create-owner`. VM Website's Auth board asks for none.
- No handle, photo, bio or public profile page. Those are hook 10 and the `profiles` module, where "a public name and handle" is still the owner's to decide (`dev plans/contracts/hooks.md` §8, 4). No slot for module cards on Profile yet.
- No check of a name against moderation's filters or reserved names (§8, 3), and no uniqueness.
- No past names are kept, in a table or in the audit log (§8, 2).
- No name in the kernel's mails.
- No event, and no index on the name for `q`, which scans; a site's People list is small.

## 7. Acceptance

- **`kernel/tests/auth/test_names.py`, new:**
  - `test_a_name_is_cleaned_before_it_is_kept`, parametrized: `"  Big \n  Haas "` becomes `"Big Haas"`; decomposed "é" is kept composed; 120 characters pass and 121 are refused; `"\x00"` and `"\u202e"` are refused; `""` and `"   "` become `None`.
  - `test_your_name_changes_the_session_and_is_audited`
  - `test_the_same_name_again_writes_nothing`
  - `test_removing_your_name_is_recorded_as_cleared`
  - `test_the_eleventh_change_in_an_hour_is_refused`
  - `test_staff_rename_only_those_they_outrank`: an admin renames a member; a non-owner is refused for an owner; an owner renames an owner; a role short of one of the person's permissions is refused.
  - `test_a_rename_by_staff_needs_a_recent_sign_in`
  - `test_a_deleted_person_is_not_found_and_a_departing_one_is_refused`
- **Elsewhere in the kernel's tests:**
  - `kernel/tests/auth/test_roles.py`, `test_people_search_finds_names_as_typed`: `%` and `_` are matched literally.
  - `kernel/tests/auth/test_passkeys.py`, `test_a_new_passkey_is_shown_by_the_name`.
  - `kernel/tests/test_moderation.py` stays green with `outranks` moved.
- **Contract tests:** `kernel/tests/contract/test_auth_contract.py`, `test_put_account_name`; and `test_people_roles_contract.py`, `test_put_admin_user_name`, covering each status in §2.
- **Web:**
  - `Profile.test.tsx`: the name or "No name yet"; a save updates "Signed in as"; a refusal shows its words.
  - `People.test.tsx`: Open for a reader without `auth.role.assign`, who sees no roles; Save name sends `PUT …/name`; the field is read-only for an owner when the reader isn't one.
- **End to end:** `kernel/tests/e2e/admin.spec.ts`, "A name set on Profile names you on the person card and in People", at 1440 and 390.
- **Live:** in the harness, signed in as the seed's owner, set a name on `/account/profile`. It shows on the person card, in People, and on a published post's byline. Remove it, and the byline is gone.

## 8. Open questions

None. The owner's answers, 2026-11-23, as recommended:
1. A person sets their name on a new Profile page, `/account/profile`, first in the account's pills.
2. A rename's audit entry holds no name, old or new.
3. Names aren't checked against moderation's filters or reserved names until comments or community show members' names publicly.

## Changes after approval

- 2026-11-23, as built (#139):
  - **The 409s** are tested in `test_names.py` only. The contract suite can't make a departing account over HTTP, and its other statuses are all in `test_put_admin_user_name`.
  - **The admin's Activity** lists `auth.name_changed` under "Accounts and roles", beside the other account changes, not with sign-ins.
  - **People's dialog** for a reader without `auth.role.assign` ends with Close in place of Cancel.
  - **`/account/profile`** is declared in all four places a kernel page is: `kernel.json`, `server_copy.py`, `pages.ts` and `screens.ts`.
  - **The account pages' per-theme axe check** in `sign-in.spec.ts` covers Profile too.
  - **The end-to-end test** runs at 390 for Profile, then at 1440 for People, under one sign-in.
