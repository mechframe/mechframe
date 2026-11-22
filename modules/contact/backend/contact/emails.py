"""contact: its email templates (kernel.email, decision 0033).

`contact.message_received` is the notice to the Inbox's readers (decision
0059): its subject is the notice's title in the site, its text and HTML the
email. It names the topic and the sender and links to the message; the
message itself stays on the site.
"""

from kernel import email

EMAILS: dict[str, email.Template] = {
    "contact.message_received": email.Template(
        subject="New message: $topic",
        text="$name wrote through the contact form on $site_name about $topic.\n\nRead it: $link\n",
        html=(
            "<p>$name wrote through the contact form on $site_name about $topic.</p>"
            '<p><a href="$link">Read it</a></p>'
        ),
    ),
}
