"""contact: the event it owns (kernel.events, SPEC.md section 11).

`contact.news.requested` goes once for a message whose sender ticked "Send me
news and releases too", when the message first counts as a real one: as it
arrives, or as it's let out of spam. `campaigns` hears it and asks the address
to confirm. Its payload carries the address and the name, since no module may
read another's tables; the message's id makes a second delivery harmless.
"""

from __future__ import annotations

import uuid

from pydantic import Field

from kernel import events

NEWS_REQUESTED = "contact.news.requested"


@events.payload(NEWS_REQUESTED, v=1)
class NewsRequested(events.Payload):
    message_id: uuid.UUID
    email: str = Field(max_length=254)
    name: str = Field(max_length=200)
