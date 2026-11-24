# 0063: The session read answers a signed-out visitor 200 with no user

- **Status:** Decided. The owner approved `dev plans/contracts/signed-out-session.md` as recommended on 2026-11-23. Applied in its PR.
- **Context:**
  - Every page the web app draws asks `GET /api/auth/session` who's signed in. To a signed-out visitor it answered 401 `kernel.not_signed_in`, and the browser logs every 401 as an error in the console.
  - So every public page of every site logged one error, by design, and the template's smoke had to allow it.
  - VM Website asked, for the owner, for a public page with a clean console.
  - The session prompt held 0064 for this and 0063 for the admin shell's page order, in case that changed the manifest. It didn't (#140, decision 0044 amended), so this takes 0063 and the numbers stay without a gap.
- **Decision:**
  1. **The read is public** (`optional_user`). Signed in, it answers 200 `{"user": {...}}` as before. With no session that counts it answers 200 `{"user": null}`: no cookie, a cookie for no session, or a session that expired or ended.
  2. **It's never cached:** both answers carry `Cache-Control: no-store`, since the answer names the person.
  3. **A dead cookie is left where it is** (the owner's answer 1). The read can land after a sign-in in another tab, and clearing the cookie then would sign that tab out. The next sign-in replaces it.
  4. **The signed-out answer has the signed-in shape** (the owner's answer 2), so the web reads one field. The model is `kernel.auth.answers.SessionRead`, with `user: UserView | None`. `SessionAnswer` stays non-null for the routes that answer a signed-in person.
  5. **Every other route that needs a session still answers 401.** The web client still reads the session again after one, and now reads `user: null` as gone. It also still reads a 401 from the session read as signed out, for a server not yet upgraded.
  6. **The template's smoke allows no console error**, a 401 included.
- **Rejected:**
  - **204 with no body:** a second shape for the web to read.
  - **Clearing a dead cookie:** the race in 3.
  - **Saying why there's no user** ("expired" against "never signed in"): the read would tell a stranger something about a cookie it holds.
- **Consequences:**
  - `docs/contracts/auth-api.md`'s row changes; SPEC doesn't, since it never named the read's 401.
  - **The contract suite** reads "this session ended" through `Api.who()`. It asserts 200 and no-store, and answers the user or None. The kernel's auth tests read `json()["user"]` the same way.
  - A site that copied the template's smoke drops its own allowance after upgrading the kernel.
