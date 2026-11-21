"""The harness's probe modules, mounted by its test support only
(docs/contracts/auth-api.md, "The harness's test support"; K4 contract
change 19).

The repo's real modules wait as `modules/_<id>/` scaffolds, so without these
the contract suite would have nothing to switch off and no job that fails.
`probe` has a route, a settings section with a secret, and two jobs: one
that fails on its one try and one that does nothing. `probe-addon` requires
`probe`, so switching `probe` off turns it off too.

The contract hooks (decision 0052, `dev plans/contracts/hooks.md`) are
tested on them: `probe` fills each hook and `probe-addon` doesn't. Its notes,
`probe.note`, are publishable (hook 1), with a public page at
`/probe/notes/:slug`, take terms from `topics` (hierarchical) and `tags`
(hook 2), and are found by site search once published (hook 3, `SEARCH`).
Its seed (hook 4, `seed_notes`) makes three of them under the topic `seeded`,
by the seeded editor, two published. Its form, `POST /api/probe/inquiries`,
is judged by the bot check (hook 5), and it adds a bot provider of its own,
`BOT_PROVIDER`, which the setting `kernel.bot` can name. Its `CSP` adds a
video player's host in the category `media` (hook 6), so the site asks
consent for `media` while it's on. A note made by someone signed in is
theirs, and `export_user_data` and `delete_user_data` (hook 7) give and
anonymise a person's notes. Its Dashboard parts (hook 8): the setup step
"Set the probe's count", done once its settings' count is 2 or more, and a
"Needs you" item, both for those who hold `kernel.settings.manage`.
Their table, `probe_note`, lives on a metadata of its own (`TABLES`), which
the test support makes when its app starts, so the migrations never see it.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Mapping
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import MetaData, String, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from kernel import (
    BotProof,
    attention,
    bot,
    jobs,
    lifecycle,
    privacy,
    search,
    seed,
    server_copy,
    settings,
    setup,
    taxonomy,
)
from kernel.access import public
from kernel.answers import Answer, Id, When
from kernel.auth.dependencies import optional_user
from kernel.auth.models import User
from kernel.db import NAMING, get_db
from kernel.errors import Problem
from kernel.modules import InstalledModule, Manifest


class ProbeFailure(Exception):
    """What `probe.fail` raises: its name is the job's last error."""


@jobs.handler("probe.fail", tries=1)
async def _fail(ctx: jobs.Context, payload: dict[str, Any]) -> None:
    raise ProbeFailure


@jobs.handler("probe.ok", tries=1)
async def _ok(ctx: jobs.Context, payload: dict[str, Any]) -> None:
    return None


@jobs.handler("probe-addon.ok", tries=1)
async def _addon_ok(ctx: jobs.Context, payload: dict[str, Any]) -> None:
    return None


class ProbeSettings(BaseModel):
    """The settings section `probe`: a word, a number and a secret."""

    model_config = ConfigDict(extra="forbid")

    greeting: str = Field(default="hello", max_length=200)
    count: int = Field(default=1, ge=0, le=100)
    token: SecretStr | None = None


class Pong(Answer):
    """The probe's answer while it's on."""


router = APIRouter()


@router.get("/ping", dependencies=[Depends(public)], response_model=Pong)
async def ping() -> dict[str, Any]:
    return {}


# --- hook 1, content lifecycle: the probe's notes ----------------------------------------


class _Tables(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


#: The probe's tables, made by the test support when its app starts.
TABLES = _Tables.metadata


class ProbeNote(lifecycle.Publishable, _Tables):
    __tablename__ = "probe_note"
    __content_type__ = "probe.note"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    #: Who wrote it: only the seed says (hook 4).
    author_id: Mapped[uuid.UUID | None] = mapped_column(default=None)


class NewNote(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9-]{1,80}$")
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=10_000)


class Schedule(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    #: An ISO 8601 time with its zone.
    at: str


class NoteMade(Answer):
    id: Id


class TermsOf(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    vocabulary: str
    slugs: list[str]


class NoteTerm(Answer):
    vocabulary: str
    slug: str
    label: str


class NoteTerms(Answer):
    terms: list[NoteTerm]


class NoteShown(Answer):
    slug: str
    title: str
    published_at: When
    terms: list[NoteTerm]


class NotesFound(Answer):
    items: list[str]


def _terms(found: list[taxonomy.Term]) -> list[dict[str, str]]:
    return [{"vocabulary": t.vocabulary, "slug": t.slug, "label": t.label} for t in found]


async def _note(db: AsyncSession, note_id: uuid.UUID, *, lock: bool = False) -> ProbeNote:
    """The note; locked, so a tagging and a deletion of it take turns."""
    found = await db.get(ProbeNote, note_id, with_for_update=lock)
    if found is None:
        raise Problem("probe.note_not_found", 404, "There's no such note.")
    return found


async def _shown(db: AsyncSession, slug: str) -> ProbeNote | None:
    statement = select(ProbeNote).where(ProbeNote.slug == slug, lifecycle.visible(ProbeNote))
    found: ProbeNote | None = await db.scalar(statement)
    return found


@router.post("/notes", status_code=201, response_model=NoteMade)
async def new_note(
    body: NewNote,
    user: User | None = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A note, the signed-in person's own when there is one (hook 7)."""
    note = ProbeNote(
        slug=body.slug, title=body.title, body=body.body, author_id=user.id if user else None
    )
    db.add(note)
    await db.commit()
    return {"id": str(note.id)}


@router.post("/notes/{note_id}/publish", dependencies=[Depends(public)], status_code=204)
async def publish_note(note_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    await lifecycle.publish(db, await _note(db, note_id))
    await db.commit()
    return Response(status_code=204)


@router.post("/notes/{note_id}/schedule", dependencies=[Depends(public)], status_code=204)
async def schedule_note(
    note_id: uuid.UUID, body: Schedule, db: AsyncSession = Depends(get_db)
) -> Response:
    try:
        at = datetime.fromisoformat(body.at)
        if at.utcoffset() is None:
            raise ValueError("The time needs its zone, such as 2026-12-01T09:00:00+00:00.")
    except ValueError as error:
        raise Problem("probe.bad_time", 422, str(error)) from None
    await lifecycle.schedule(db, await _note(db, note_id), at)
    await db.commit()
    return Response(status_code=204)


@router.post("/notes/{note_id}/unpublish", dependencies=[Depends(public)], status_code=204)
async def unpublish_note(note_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    await lifecycle.unpublish(db, await _note(db, note_id))
    await db.commit()
    return Response(status_code=204)


@router.put("/notes/{note_id}/terms", dependencies=[Depends(public)], response_model=NoteTerms)
async def tag_note(
    note_id: uuid.UUID, body: TermsOf, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    note = await _note(db, note_id, lock=True)
    try:
        found = await taxonomy.tag(
            db, ProbeNote.__content_type__, note.id, body.vocabulary, body.slugs
        )
    except ValueError as error:
        raise Problem("probe.bad_vocabulary", 422, str(error)) from None
    await db.commit()
    return {"terms": _terms(found)}


@router.delete("/notes/{note_id}", dependencies=[Depends(public)], status_code=204)
async def delete_note(note_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    note = await _note(db, note_id, lock=True)
    await taxonomy.untag_all(db, ProbeNote.__content_type__, note.id)
    await db.execute(delete(ProbeNote).where(ProbeNote.id == note.id))
    await db.commit()
    return Response(status_code=204)


@router.get("/notes", dependencies=[Depends(public)], response_model=NotesFound)
async def notes_under(
    vocabulary: str, term: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """The published notes holding a term, by slug."""
    holding = taxonomy.tagged(ProbeNote.__content_type__, vocabulary, term)
    found = await db.scalars(
        select(ProbeNote.slug)
        .where(ProbeNote.id.in_(holding), lifecycle.visible(ProbeNote))
        .order_by(ProbeNote.slug)
    )
    return {"items": list(found)}


@router.get("/notes/{slug}", dependencies=[Depends(public)], response_model=NoteShown)
async def show_note(slug: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    note = await _shown(db, slug)
    if note is None or note.published_at is None:
        raise Problem("probe.note_not_found", 404, "There's no such note.")
    found = await taxonomy.terms_for(db, ProbeNote.__content_type__, [note.id])
    return {
        "slug": note.slug,
        "title": note.title,
        "published_at": note.published_at.isoformat(),
        "terms": _terms(found[note.id]),
    }


class ProbePages(server_copy.Pages):
    async def page(
        self, db: AsyncSession, path: str, params: Mapping[str, str]
    ) -> server_copy.Page | None:
        note = await _shown(db, params["slug"])
        if note is None:
            return None
        return server_copy.Page(note.title, "A probe note.", server_copy.h1(note.title))

    async def sitemap(self, db: AsyncSession) -> list[server_copy.Entry]:
        found = await db.scalars(select(ProbeNote).where(lifecycle.visible(ProbeNote)))
        return [server_copy.Entry(f"/probe/notes/{note.slug}", title=note.title) for note in found]


# --- hook 3, search index: the probe's notes found by site search -----------------------


def _document(note: ProbeNote) -> search.Document:
    return search.Document(
        ProbeNote.__content_type__, note.id, note.title, note.body, f"/probe/notes/{note.slug}"
    )


class ProbeSearch(search.Source):
    """The probe's notes as site search finds them: published ones only."""

    content_type = ProbeNote.__content_type__

    async def document(self, db: AsyncSession, content_id: uuid.UUID) -> search.Document | None:
        note = await db.scalar(
            select(ProbeNote).where(ProbeNote.id == content_id, lifecycle.visible(ProbeNote))
        )
        return None if note is None else _document(note)

    async def documents(self, db: AsyncSession) -> AsyncIterator[search.Document]:
        published = select(ProbeNote).where(lifecycle.visible(ProbeNote)).order_by(ProbeNote.id)
        for note in await db.scalars(published):
            yield _document(note)


SEARCH = (ProbeSearch(),)


# --- hook 4, seed data: notes a demo can start from ---------------------------------------

#: The seeded notes' slugs: the first two published, the third a draft.
SEEDED = ("seed-note-1", "seed-note-2", "seed-note-3")
_WORDS = ("amber", "bridge", "copper", "delta", "ember", "fjord", "grove", "harbor")


async def seed_notes(db: AsyncSession, ctx: seed.Context) -> None:
    """Three notes under the topic `seeded`, by the seeded editor, the first
    two published. Their slugs are fixed and the random's draws the same each
    run, so a second run finds them and changes nothing."""
    author = await ctx.user("editor")
    for number, slug in enumerate(SEEDED, 1):
        words = " and ".join(ctx.random.sample(_WORDS, 2))  # drawn every run, alike
        if await db.scalar(select(ProbeNote.id).where(ProbeNote.slug == slug)) is not None:
            continue
        note = ProbeNote(
            slug=slug,
            title=f"Seeded note {number}: {words}",
            body=f"A seeded note on {words}, for a demo of the probe.",
            author_id=author,
        )
        db.add(note)
        await db.flush()
        await taxonomy.tag(db, ProbeNote.__content_type__, note.id, "topics", ["seeded"])
        if number < len(SEEDED):
            await lifecycle.publish(db, note)


# --- hook 5, bot check: a public form, and a provider of the probe's own -----------------


class Inquiry(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    message: str = Field(min_length=1, max_length=2_000)
    # `kernel.BotProof`, not `bot.BotProof`: a field named `bot` hides the module.
    bot: BotProof | None = None


class Judged(Answer):
    #: The verdict, which a real module never tells its visitor: the suite reads it.
    held: str | None


@router.post("/inquiries", dependencies=[Depends(public)], status_code=201, response_model=Judged)
async def send_inquiry(
    body: Inquiry, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """A public form's submission, judged as `contact` will judge an inquiry."""
    found = await bot.verify(request, body.bot, form="probe.inquiry", db=db)
    return {"held": found.reason if isinstance(found, bot.Held) else None}


#: The one token the probe's provider passes: the suite's, never a secret.
PROBE_TOKEN = "probe-ok"  # noqa: S105


class ProbeBotCheck:
    """The probe's provider, for the setting `kernel.bot` to name: it passes
    a proof whose token is `PROBE_TOKEN` and holds the rest."""

    async def verify(
        self, request: Request, proof: BotProof | None, form: str
    ) -> bot.Pass | bot.Held:
        if proof is not None and proof.token == PROBE_TOKEN:
            return bot.Pass()
        return bot.Held("probe_token")


BOT_PROVIDER = ProbeBotCheck()

# --- hook 7, export and erase ------------------------------------------------------------


async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
    """The person's notes, by slug."""
    notes = await db.scalars(
        select(ProbeNote).where(ProbeNote.author_id == subject.user_id).order_by(ProbeNote.slug)
    )
    return {
        "notes": [
            {
                "id": str(note.id),
                "slug": note.slug,
                "title": note.title,
                "body": note.body,
                "status": note.status,
            }
            for note in notes
        ]
    }


async def delete_user_data(db: AsyncSession, subject: privacy.Subject) -> None:
    """A person's notes stay, theirs no longer: the author goes."""
    for note in await db.scalars(
        select(ProbeNote).where(ProbeNote.author_id == subject.user_id).with_for_update()
    ):
        note.author_id = None


# --- hook 8, dashboard cards ----------------------------------------------------------------

#: Who sees the probe's step and item: an admin, not an editor.
_SETTINGS = "kernel.settings.manage"


async def _count_set(db: AsyncSession) -> bool:
    found = await settings.for_module(db, "probe")
    return isinstance(found, ProbeSettings) and found.count >= 2


SETUP = (
    setup.Step(
        key="probe.count",
        title="Set the probe's count",
        why="The probe's setup step: done once its count is 2 or more, so the suite can flip it.",
        link="/admin/settings/probe",
        permission=_SETTINGS,
        done=_count_set,
    ),
)


async def _attention(db: AsyncSession, user: User) -> list[attention.Item]:
    return [
        attention.Item(
            key="probe.waiting",
            tone="info",
            what="The probe is waiting",
            why="The probe's item, shown to those who can change settings.",
            label="Open its settings",
            to="/admin/settings/probe",
            permission=_SETTINGS,
        )
    ]


ATTENTION = _attention


#: An embed's player host, held for the visitor's consent to `media` (hook 6).
CSP = (("frame-src", "https://www.youtube-nocookie.com", "media"),)


def _manifest(
    module_id: str, name: str, summary: str, requires: dict[str, str], **more: Any
) -> Manifest:
    return Manifest.from_dict(
        {
            "id": module_id,
            "name": name,
            "version": "0.1.0",
            "summary": summary,
            "category": "admin",
            "requires": {"modules": requires},
            **more,
        }
    )


MODULES = (
    InstalledModule(
        _manifest(
            "probe",
            "Probe",
            "The test support's module: a route, settings, jobs and the hooks",
            {},
            routes={"api": "/api/probe", "public": ["/probe/notes/:slug"]},
            vocabularies=[
                {"key": "topics", "label": "Topics", "hierarchical": True},
                {"key": "tags", "label": "Tags"},
            ],
            content_types=[
                {
                    "key": "probe.note",
                    "label": "Note",
                    "lifecycle": True,
                    "taxonomy": ["topics", "tags"],
                    "search": True,
                }
            ],
            data_hooks={"export": True, "delete": True},
        ),
        router=router,
        settings=ProbeSettings,
        jobs=(_fail, _ok),
        pages=ProbePages(),
        publishable=(ProbeNote,),
        searchable=SEARCH,
        seed=seed_notes,
        bot_provider=BOT_PROVIDER,
        csp=CSP,
        export_user_data=export_user_data,
        delete_user_data=delete_user_data,
        attention=ATTENTION,
        setup=SETUP,
    ),
    InstalledModule(
        _manifest(
            "probe-addon",
            "Probe add-on",
            "Needs the probe, to show a switch-off spreading",
            {"probe": "^0.1"},
        ),
        jobs=(_addon_ok,),
    ),
)
