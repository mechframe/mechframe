# 0061: The account's name, set by the person or by staff who outrank them

- **Status:** Decided. The owner approved `dev plans/contracts/account-name.md` as recommended on 2026-11-23. Applied in its PR.
- **Context:** `auth_user.display_name` has been in the kernel since `kernel_0002`. The session answers it as `name` (#119), and the admin's person card, People, the admin's Activity, blog's bylines, media's and pages' "by" and the data export all read it. But nothing set it, so a post's byline named no one and the boards' "Signed in as [name]" showed an address. The owner asked for the field now, ahead of hook 10's public profiles.
- **Decision:**
  1. **The name is `display_name`, unchanged:** `varchar(120) NULL`, no migration. Every reader reads it live, and nothing keeps a copy (blog's search documents hold no author), so a rename needs no event.
  2. **Cleaning** (`kernel.auth.names.clean_name`):
     - NFC;
     - each run of whitespace one space, and the ends trimmed;
     - refused: a control character, or a direction override, embedding or isolate (U+202A to U+202E, U+2066 to U+2069), which could make a name read as something else in a list;
     - at most 120 characters.
     Empty is no name. Names aren't unique.
  3. **A person changes their own** with `PUT /api/auth/account/name`, signed in, with no step-up (a name opens nothing), ten changes an hour. It answers the session.
  4. **Staff change someone's** with `PUT /api/auth/admin/users/{id}/name`: `auth.user.manage`, step-up, and only if they outrank the person by decision 0013's rule as suspension applies it. That rule is now one function, `kernel.auth.permissions.outranks`, which moderation calls too. A suspended person can be renamed, so staff can clear an offensive name.
  5. **Audit:** `auth.name_changed`, the target the account; `{"cleared": true}` when the name was removed. The entry never holds a name, as `auth.email_changed` holds no address.
  6. **Where it shows:**
     - a new account page, Profile (`/account/profile`), first in the pills as VM Website's Account board draws them, and "Signed in as {name}";
     - People's person dialog, whose Name has its own Save, for anyone on People;
     - People's search, which finds names;
     - a new passkey's WebAuthn `user.displayName`.
- **Rejected:**
  - **A Name card on Sign-in and security:** the name isn't sign-in, and the board puts Profile first.
  - **Keeping the old and new names in the audit entry:** the log keeps no text a person typed, and staff always see the current name.
  - **Checking names against moderation's filters or reserved names now:** only staff names reach readers today, through blog's bylines. The comments or community module decides it in its own contract.
  - **A step-up for one's own name:** it guards nothing a stolen session couldn't already show.
  - **An event:** no module keeps a copy. One that copies a name adds `auth.user.renamed` in its contract.
- **Consequences:**
  - SPEC 14.1, 14.10 and 14.11 change.
  - `docs/contracts/auth-api.md` gains both routes, and `q` finds names.
  - Hook 10's public name and handle stay an open question for the `profiles` module (`dev plans/contracts/hooks.md` §8, 4). Its cards may go on Profile through a slot it adds then.
  - Sign-up and `mechframe create-owner` still ask for no name.
