"""campaigns: its email template (kernel.email, decision 0033).

`campaigns.confirm` asks a new sign-up to confirm (double opt-in, §8, 2):
nobody is mailed the news until they click its link. It's a message about
their own request, so it carries no unsubscribe: an address that never
confirms gets nothing more, and its row goes after 30 days. The newsletter
itself is rendered by `render.py` and queued through `email.queue_message`.
"""

from kernel import email

EMAILS: dict[str, email.Template] = {
    "campaigns.confirm": email.Template(
        subject="Confirm your subscription to $site_name",
        text=(
            "Someone, hopefully you, asked for news from $site_name at this address.\n\n"
            "Confirm it: $link\n\n"
            "If it wasn't you, ignore this email and nothing more will be sent.\n"
        ),
        html=(
            "<p>Someone, hopefully you, asked for news from $site_name at this address.</p>"
            '<p><a href="$link">Confirm your subscription</a></p>'
            "<p>If it wasn't you, ignore this email and nothing more will be sent.</p>"
        ),
    ),
}
