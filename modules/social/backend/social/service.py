"""social's logic (`dev plans/contracts/social.md` §2): the token in use, the
channels it reached, and each thing's shares.

**The token.** One saved in Settings (the section `social`'s `buffer_token`,
sealed by the kernel) wins; the host's BUFFER_ACCESS_TOKEN is the fallback, as
`kernel.ai`'s key is (decision 0058). A saved token that can't be opened is
reported, never swapped for the host's. A host value that couldn't be a token
counts as none. This module is the only place the token is opened, just before
a call.

**A share** names its thing by content type and id. The kernel's
`server_copy.preview` says whether it's public and gives its link, so social
reads no other module's rows. Each channel's share is stored as `sending` and
committed before its call, under a lock on the thing, so two presses can't both
pass the check; the chosen channels' calls then go at once.
"""

from __future__ import annotations

import asyncio
import os
import uuid
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, attention, clock, crypto, server_copy, setup
from kernel import settings as module_settings
from social import buffer
from social.models import NOT_POSTED, WAITING, Channel, Share
from social.schemas import MAX_CHANNELS, Settings, ShareSend, Source

MODULE = "social"
SEND_PERMISSION = "social.post.send"
HOST_VARIABLE = "BUFFER_ACCESS_TOKEN"
RATE_VARIABLE = "SOCIAL_RATE_LIMIT"
DEFAULT_RATE = "30/1h"
#: A set time must be at least this far ahead, so it hasn't passed by the time Buffer reads it.
LEAD = timedelta(minutes=1)
#: How far back the Dashboard looks for a share that failed or wasn't confirmed.
RECENTLY = timedelta(days=14)
#: The advisory lock class a thing's shares are checked under.
LOCK_CLASS = zlib.crc32(b"social.share") - 2**31

NO_TOKEN = (
    "No Buffer token is set, so sharing is off. An admin can save one in Settings, under Social, "
    f"or set {HOST_VARIABLE} on the host."
)
UNREADABLE_SAVED = (
    "The saved Buffer token can't be read, which happens when the server's ENCRYPTION_KEYS change. "
    "An admin can save it again in Settings, under Social."
)
NOT_LISTED = "Buffer's channels aren't listed yet. Check the channels, then share."

#: How a share's state reads in a sentence.
STATE_WORDS = {
    "sending": "not confirmed",
    "unknown": "not confirmed",
    "queued": "queued in Buffer",
    "draft": "a draft in Buffer",
    "sent": "sent",
    "failed": "failed in Buffer",
    "refused": "not taken by Buffer",
    "removed": "taken back",
}


def rate_rule() -> str:
    """SOCIAL_RATE_LIMIT: the shares and channel checks one person may make."""
    return (os.environ.get(RATE_VARIABLE) or "").strip() or DEFAULT_RATE


# --- the token ------------------------------------------------------------------------------


def _host_token() -> str | None:
    token = (os.environ.get(HOST_VARIABLE) or "").strip()
    return token if token and buffer.token_problem(token) is None else None


async def _saved_kept(db: AsyncSession) -> bool:
    """A token is saved in Settings, without opening it."""
    form = await module_settings.form(db, MODULE)
    return bool((form["values"].get("buffer_token") or {}).get("kept"))


async def _saved_token(db: AsyncSession) -> str | None:
    """The saved token opened; None when it can't be."""
    try:
        saved = cast(Settings, await module_settings.for_module(db, MODULE))
    except crypto.SealError:
        return None
    return saved.buffer_token.get_secret_value() if saved.buffer_token is not None else None


@dataclass(frozen=True)
class TokenState:
    source: Source
    unreadable: bool

    @property
    def usable(self) -> bool:
        return self.source != "none" and not self.unreadable


async def token_state(db: AsyncSession) -> TokenState:
    """Where the token in use comes from, opening a saved one only to tell
    whether it can be."""
    if await _saved_kept(db):
        return TokenState("saved", unreadable=await _saved_token(db) is None)
    return TokenState("host" if _host_token() is not None else "none", unreadable=False)


async def token_in_use(db: AsyncSession) -> str:
    """The token to call Buffer with: 503 `social.no_token` with none,
    `social.token_unreadable` for a saved one that can't be opened."""
    if await _saved_kept(db):
        token = await _saved_token(db)
        if token is None:
            raise Problem("social.token_unreadable", 503, UNREADABLE_SAVED)
        return token
    host = _host_token()
    if host is None:
        raise Problem("social.no_token", 503, NO_TOKEN)
    return host


def buffer_failed(error: buffer.BufferError) -> Problem:
    """A refused token or request is the admin's to fix (422, never 401, which
    the admin reads as its own session ending); Buffer out of reach is 502."""
    if isinstance(error, buffer.TokenRefused):
        return Problem("social.token_refused", 422, str(error))
    if isinstance(error, buffer.Refused):
        return Problem("social.buffer_refused", 422, str(error))
    return Problem("social.buffer_failed", 502, str(error))


# --- the channels ---------------------------------------------------------------------------


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def channel_problem(channel: Channel) -> str:
    return buffer.problem(
        name=channel.name,
        descriptor=channel.descriptor,
        service=channel.service,
        disconnected=channel.disconnected,
        locked=channel.locked,
    )


def channel_out(channel: Channel) -> dict[str, Any]:
    problem = channel_problem(channel)
    return {
        "id": channel.id,
        "name": channel.name,
        "service": channel.service,
        "network": buffer.network(channel.service),
        "descriptor": channel.descriptor,
        "usable": not problem,
        "problem": problem,
        "queue_paused": channel.queue_paused,
        "limit": buffer.LIMITS.get(channel.service),
    }


async def _version(db: AsyncSession) -> int:
    """The settings section's version now: the token's."""
    return int((await module_settings.form(db, MODULE))["version"])


async def channels(db: AsyncSession) -> list[Channel]:
    """The channels Buffer listed for the token in use: a list checked before
    the token last changed is no one's (Codex on #152)."""
    statement = (
        select(Channel)
        .where(Channel.settings_version == await _version(db))
        .order_by(Channel.position)
    )
    return list(await db.scalars(statement))


async def listed_at(db: AsyncSession) -> datetime | None:
    statement = select(func.max(Channel.listed_at)).where(
        Channel.settings_version == await _version(db)
    )
    found: datetime | None = await db.scalar(statement)
    return found


async def list_channels(db: AsyncSession) -> dict[str, Any]:
    """Asks Buffer which channels the token in use reaches, and keeps them in
    Buffer's order in place of the last list. Settings' Check and the Share
    card's Refresh both come here."""
    token = await token_in_use(db)
    try:
        found = await buffer.Client(token).channels()
    except buffer.BufferError as error:
        raise buffer_failed(error) from None
    now = clock.now()
    version = await _version(db)
    await db.execute(delete(Channel))
    rows = [
        Channel(
            id=listed.id[:100],
            name=listed.name[:300],
            service=listed.service[:40],
            descriptor=listed.descriptor[:300],
            avatar=listed.avatar[:600],
            organization_id=listed.organization_id[:100],
            disconnected=listed.disconnected,
            locked=listed.locked,
            queue_paused=listed.queue_paused,
            position=at,
            listed_at=now,
            settings_version=version,
        )
        for at, listed in enumerate({one.id: one for one in found}.values())
    ]
    db.add_all(rows)
    await db.flush()
    return {"channels": [channel_out(row) for row in rows], "listed_at": now.isoformat()}


async def forget_channels(db: AsyncSession, before: int) -> None:
    """The token changed at version `before`: what an older one reached is no
    longer known. A list checked since is kept, however late this runs."""
    await db.execute(delete(Channel).where(Channel.settings_version < before))


async def state(db: AsyncSession) -> dict[str, Any]:
    token = await token_state(db)
    kept = await channels(db) if token.usable else []
    return {
        "source": token.source,
        "unreadable": token.unreadable,
        "channels": [channel_out(row) for row in kept],
        "listed_at": _iso(await listed_at(db)) if kept else None,
    }


# --- a thing's shares -----------------------------------------------------------------------


def content_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise Problem(
            "kernel.invalid_request", 422, "That isn't an id.", errors={"id": ["Not an id."]}
        ) from None


def share_out(row: Share) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "channel_id": row.channel_id,
        "channel_name": row.channel_name,
        "service": row.service,
        "network": buffer.network(row.service),
        "text": row.text,
        "link": row.link,
        "mode": row.mode,
        "due_at": _iso(row.due_at),
        "state": row.state,
        "error": row.error,
        "external_link": row.external_link,
        "sent_at": _iso(row.sent_at),
        "sent_by_name": row.sent_by_name,
        "created_at": row.created_at.isoformat(),
    }


async def history(db: AsyncSession, content_type: str, thing: uuid.UUID) -> list[Share]:
    statement = (
        select(Share)
        .where(Share.content_type == content_type, Share.content_id == thing)
        .order_by(Share.created_at.desc(), Share.id)
        .execution_options(populate_existing=True)
    )
    return list(await db.scalars(statement))


def first_text(card: server_copy.Preview | None) -> str:
    """The text to start from: the title, a blank line, then the description."""
    if card is None:
        return ""
    return f"{card.title}\n\n{card.description}" if card.description else card.title


def _card_out(card: server_copy.Preview | None) -> dict[str, Any] | None:
    if card is None:
        return None
    return {
        "url": card.url,
        "title": card.title,
        "description": card.description,
        "image": card.image,
    }


async def view(db: AsyncSession, content_type: str, thing: uuid.UUID) -> dict[str, Any]:
    """What the Share card opens with: no call to Buffer."""
    token = await token_state(db)
    card = await server_copy.preview(db, content_type, thing)
    kept = await channels(db) if token.usable else []
    return {
        "ready": token.usable and bool(kept),
        "source": token.source,
        "unreadable": token.unreadable,
        "live": card is not None,
        "card": _card_out(card),
        "text": first_text(card),
        "channels": [channel_out(row) for row in kept],
        "listed_at": _iso(await listed_at(db)) if kept else None,
        "history": [share_out(row) for row in await history(db, content_type, thing)],
    }


def _admin_path(value: str) -> str:
    path = value.split("?", 1)[0].split("#", 1)[0]
    if (
        not path.startswith("/admin/")
        or "//" in path
        or "\\" in path
        or any(ord(character) < 32 or character.isspace() for character in path)
    ):
        raise Problem(
            "kernel.invalid_request",
            422,
            "The admin page it's shared from must be a path under /admin.",
            errors={"admin_path": ["A path under /admin."]},
        )
    return path


def _due(body: ShareSend) -> datetime | None:
    if body.when != "at":
        return None
    if body.due_at is None:
        raise Problem("social.time_needed", 422, "Pick when it goes out.")
    try:
        due = datetime.fromisoformat(body.due_at.replace("Z", "+00:00"))
    except ValueError:
        raise Problem(
            "social.time_needed", 422, "That isn't a time. Pick when it goes out."
        ) from None
    if due.tzinfo is None:
        raise Problem("social.time_needed", 422, "Say the time with its zone.")
    if due < clock.now() + LEAD:
        raise Problem("social.time_passed", 422, "That time has already passed. Pick one ahead.")
    return due


def _chosen(kept: list[Channel], ids: list[str]) -> list[Channel]:
    known = {row.id: row for row in kept}
    chosen: list[Channel] = []
    for channel_id in dict.fromkeys(ids):
        row = known.get(channel_id)
        if row is None:
            raise Problem(
                "social.channel_unknown",
                422,
                "That isn't one of the channels Buffer last listed. Check the channels again.",
            )
        problem = channel_problem(row)
        if problem:
            raise Problem("social.channel_unusable", 422, problem)
        chosen.append(row)
    return chosen[:MAX_CHANNELS]


def _day(when: datetime) -> str:
    return f"{when.day} {when:%B}"


def _went_before(earlier: list[Share]) -> str:
    said = [
        f"{buffer.label(row.channel_name, '')} on {_day(row.created_at)} ({STATE_WORDS.get(row.state, row.state)})"
        for row in earlier
    ]
    return (
        f"This already went to {'; '.join(said)}. Share it again only if that's meant: "
        "choose Share again."
    )


async def _hold(db: AsyncSession, content_type: str, thing: uuid.UUID) -> None:
    """Held until this transaction ends: a second send of the thing waits here,
    then finds the first one's shares."""
    key = zlib.crc32(f"{content_type}:{thing}".encode()) - 2**31
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:kind, :key)"), {"kind": LOCK_CLASS, "key": key}
    )


def _sender(user: Any) -> tuple[uuid.UUID | None, str]:
    name = (getattr(user, "display_name", None) or "").strip()
    return getattr(user, "id", None), (name or str(getattr(user, "email", "")))[:300]


async def send(db: AsyncSession, body: ShareSend, *, user: Any) -> dict[str, Any]:
    """Shares the thing to the chosen channels, each refusal before anything
    leaves (§2). Commits the shares as `sending` before Buffer is asked, then
    each as it's answered."""
    thing = content_id(body.id)
    admin_path = _admin_path(body.admin_path)
    token = await token_in_use(db)
    card = await server_copy.preview(db, body.type, thing)
    if card is None:
        raise Problem(
            "social.not_live",
            409,
            "Publish it before sharing it: only what's public can be shared.",
        )
    kept = await channels(db)
    if not kept:
        raise Problem("social.channels_unlisted", 409, NOT_LISTED)
    chosen = _chosen(kept, body.channel_ids)
    words = body.text.strip()
    if not words:
        raise Problem("social.text_needed", 422, "Write the text it goes out with.")
    for row in chosen:
        problem = buffer.text_problem(
            name=row.name, descriptor=row.descriptor, service=row.service, text=words, link=card.url
        )
        if problem:
            raise Problem("social.text_too_long", 422, problem)
    due_at = _due(body)
    if body.when != "draft":
        problem = await buffer.link_problem(card.url)
        if problem:
            raise Problem("social.address_not_answering", 409, problem)

    await _hold(db, body.type, thing)
    picked = {row.id for row in chosen}
    earlier = [
        row
        for row in await history(db, body.type, thing)
        if row.channel_id in picked and row.state not in NOT_POSTED
    ]
    if earlier and not body.again:
        raise Problem("social.shared_before", 409, _went_before(earlier))
    sender_id, sender_name = _sender(user)
    now = clock.now()
    shares = [
        Share(
            id=uuid.uuid4(),
            content_type=body.type,
            content_id=thing,
            admin_path=admin_path,
            channel_id=row.id,
            channel_name=buffer.label(row.name, row.descriptor)[:300],
            service=row.service,
            text=words,
            link=card.url,
            mode=body.when,
            due_at=due_at,
            state="sending",
            error="",
            sent_by_id=sender_id,
            sent_by_name=sender_name,
            created_at=now,
            updated_at=now,
        )
        for row in chosen
    ]
    db.add_all(shares)
    await db.commit()

    client = buffer.Client(token)
    link_card = buffer.LinkCard(
        url=card.url, title=card.title, description=card.description, thumbnail=card.image
    )
    answers = await asyncio.gather(
        *(
            client.create_post(
                channel_id=row.channel_id,
                service=row.service,
                text=words,
                when=body.when,
                card=link_card,
                due_at=due_at,
            )
            for row in shares
        ),
        return_exceptions=True,
    )
    for made, answer in zip(shares, answers, strict=True):
        _answered(made, answer)
    await db.commit()
    return {
        "results": [share_out(made) for made in shares],
        "history": [share_out(row) for row in await history(db, body.type, thing)],
    }


def _answered(row: Share, answer: buffer.PostState | BaseException) -> None:
    row.updated_at = clock.now()
    if isinstance(answer, buffer.Unanswered):
        row.state, row.error = "unknown", str(answer)
    elif isinstance(answer, buffer.BufferError):
        row.state, row.error = "refused", str(answer)
    elif isinstance(answer, BaseException):
        # Anything else (a bug, a cancel) may have left after the request went:
        # kept as not confirmed, never as refused.
        row.state, row.error = "unknown", buffer.MAYBE_SENT
    else:
        _took(row, answer)


def _took(row: Share, answer: buffer.PostState) -> None:
    row.state, row.buffer_post_id = answer.state, answer.id[:100]
    row.due_at = answer.due_at or row.due_at
    row.sent_at = answer.sent_at
    row.external_link = (answer.external_link or "")[:600] or None
    row.error = answer.error


async def refresh(db: AsyncSession, content_type: str, thing: uuid.UUID) -> dict[str, Any]:
    """Asks Buffer how each of the thing's posts still waiting there stands:
    sent, with its address on the network, failed with Buffer's reason,
    deleted there, or still waiting."""
    waiting = [
        row
        for row in await history(db, content_type, thing)
        if row.state in WAITING and row.buffer_post_id
    ]
    if waiting:
        client = buffer.Client(await token_in_use(db))
        for row in waiting:
            try:
                answer = await client.post_state(row.buffer_post_id or "")
            except buffer.NotFound:
                row.state, row.error = "removed", "Buffer no longer has it: it was deleted there."
                row.updated_at = clock.now()
            except buffer.BufferError as error:
                await db.commit()
                raise buffer_failed(error) from None
            else:
                _took(row, answer)
                row.updated_at = clock.now()
        await db.commit()
    return {"history": [share_out(row) for row in await history(db, content_type, thing)]}


async def take_back(db: AsyncSession, share_id: uuid.UUID) -> dict[str, Any]:
    """Takes a post still waiting in Buffer, queued or a draft, back out of it."""
    row = await db.get(Share, share_id, populate_existing=True)
    if row is None:
        raise Problem("social.share_not_found", 404, "That share isn't recorded.")
    if row.state not in WAITING or not row.buffer_post_id:
        raise Problem(
            "social.not_waiting",
            409,
            "Only a post still waiting in Buffer can be taken back; this one is "
            f"{STATE_WORDS.get(row.state, row.state)}.",
        )
    try:
        await buffer.Client(await token_in_use(db)).delete_post(row.buffer_post_id)
    except buffer.NotFound:
        pass  # gone from Buffer already: taken back either way
    except buffer.BufferError as error:
        raise buffer_failed(error) from None
    row.state, row.error, row.updated_at = "removed", "", clock.now()
    await db.commit()
    return {
        "history": [share_out(one) for one in await history(db, row.content_type, row.content_id)]
    }


# --- the Dashboard (hook 8) -----------------------------------------------------------------


async def troubled_item(db: AsyncSession) -> attention.Item | None:
    """While a share failed in Buffer or wasn't confirmed in the last 14 days:
    the newest one's admin page."""
    statement = (
        select(Share)
        .where(Share.state.in_(("failed", "unknown")), Share.created_at > clock.now() - RECENTLY)
        .order_by(Share.created_at.desc())
    )
    found = list(await db.scalars(statement.limit(50)))
    if not found:
        return None
    newest = found[0]
    count = len(found)
    what = (
        f"A post to {newest.channel_name} needs a look"
        if count == 1
        else f"{count} posts to the site's channels need a look"
    )
    return attention.Item(
        key="social.troubled",
        tone="warning",
        what=what,
        why="Buffer said it failed, or didn't answer, so it may not have gone. Check it in Buffer, then refresh the Share card.",
        label="Open it",
        to=newest.admin_path,
        permission=SEND_PERMISSION,
    )


async def _connected(db: AsyncSession) -> bool:
    if not (await token_state(db)).usable:
        return False
    return bool(await channels(db))


CONNECT_BUFFER = setup.Step(
    key="social.connect_buffer",
    title="Connect Buffer",
    why="Sharing to the site's channels goes through Buffer. Save its token, then check the channels it reaches.",
    link="/admin/settings",
    permission="kernel.settings.manage",
    done=_connected,
)
