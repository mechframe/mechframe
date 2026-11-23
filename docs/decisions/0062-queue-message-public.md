# 0062: A module may queue a message it rendered itself, `email.queue_message`

- **Status:** Decided; applied in `campaigns`' PR. The owner approved `dev plans/contracts/campaigns.md` on 2026-11-22, with this addition to the kernel (§2, "The kernel's addition").
- **Context:** A module sends mail through `email.send` and `email.queue`, which render a template it declares in `emails.py`: `string.Template` placeholders, each value escaped. A newsletter is written by a person in Markdown, made HTML by `kernel.markdown.render`, framed in an email's single column with the site's colours as values, and given each subscriber's own unsubscribe link and RFC 8058's one-click headers. None of that is a template's placeholder: the body is the module's own HTML, already cleaned. `email.queue_message`, which `kernel.notifications` and the kernel's auth mails already use, takes exactly that, but it wasn't on the public surface (SPEC 6), so a module couldn't call it.
- **Decision:**
  1. `email.queue_message(db, to, subject, text, html=None, headers=None)` joins SPEC 6's table, unchanged: the message as rendered, queued in the caller's transaction as a sealed `kernel.send_mail` job, sent through the site's adapter by the worker and retried as `email.queue`'s are.
  2. `headers` may be only RFC 8058's two, `List-Unsubscribe` and `List-Unsubscribe-Post`, each one line of at most 900 characters. Another header, a line break or a message past the kernel's bounds is `ValueError` before anything is queued (`email.check`, as for every message).
  3. The From stays the site's `MAIL_FROM`: a module can't set it, nor a Reply-To.
- **Rejected:**
  - A template per newsletter, made at send time: templates are declared when the app starts, so a site can reword them, and a person's email isn't one to reword.
  - A newsletter adapter in `campaigns` that sends around the queue: it would skip `Checked`, the retries and the sealing, and `test_no_kernel_code_sends_mail_around_the_queue` holds the kernel to the queue for good reason.
  - Letting a module add any header: a Bcc or a second recipient through a header is the injection `check` exists to stop.
- **Consequences:**
  - `campaigns` is the first caller; a shop's receipts or a digest can render their own the same way.
  - The function's signature and its refusals are now under semver.
