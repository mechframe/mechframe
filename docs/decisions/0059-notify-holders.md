# 0059: A notice to everyone who holds a permission, `notifications.notify_holders`

- **Status:** Decided; applied in `contact`'s PR. The owner chose it on 2026-11-22 (`dev plans/contracts/contact.md`, §8, 1, as recommended): everyone who may read the Inbox is told of a new message, rather than VybeSite's one address in Settings.
- **Context:** `notifications.notify(db, user_id, key, context, link=)` tells one person. A module that must tell the site's people about something new (a contact message, a comment to approve, an order) had no way to find them: who holds a permission is the kernel's to answer (`kernel.auth.permissions`), and a module may reach only the kernel's public surface (SPEC 6). The attention items of hook 8 show to holders, but only on the Dashboard, and only while someone looks.
- **Decision:**
  1. `notifications.notify_holders(db, permission, key, context, *, link=None) -> list[uuid.UUID]` calls `notify` once for each active account that holds `permission`: one with the owner's role, or with a role that grants it. Each person gets the notice as they chose for `key`, and the answer is the people it reached, in the site or by email, in id order.
  2. Holding is by role. Overrides are per resource (SPEC 14.8), so they play no part in a notice about the site as a whole.
  3. A permission not shaped `<id>.<resource>.<action>`, and a key nobody declares, are a caller's bug: `ValueError`, before anyone is read or anything is written.
- **Rejected:**
  - An address in the module's settings that gets every message (VybeSite's `notify_email`): it bypasses each person's choices and the one-click unsubscribe, and copies people's messages into a mailbox the site doesn't manage.
  - A public `holders(db, permission)` answering the ids, for each module to loop over: every caller would write the same loop, and the kernel would hand out who its staff are.
- **Consequences:** `contact` is the first caller. Comments to approve (step 3), campaigns and the shop can tell their staff the same way. A site with many holders sends many notices, each in the caller's transaction, so a caller keeps to events that are rare per minute, such as a public form behind `rate_limit`.
