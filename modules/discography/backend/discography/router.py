"""discography's routes (`dev plans/contracts/discography.md` §2), mounted by
the kernel at /api/discography behind require_module("discography"). The live
releases, their tracks, the artist's links and a track's play are the
public's; everything under /admin needs `discography.release.manage`."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from discography import service
from discography.schemas import (
    AdminArtistLinks,
    AdminPersonList,
    AdminReleaseList,
    AdminRoleList,
    AdminTrackList,
    ArtistLinks,
    FullRelease,
    FullTrack,
    LinksPut,
    LiveRelease,
    LiveTrack,
    MusicMoved,
    NewRelease,
    NewTrack,
    PersonChange,
    PlaysWeek,
    PublishRelease,
    ReleaseCards,
    ReleaseChange,
    RolesPut,
    TrackCards,
    TrackChange,
)
from kernel import Problem, clock, get_db, public, rate_limit, require_permission

router = APIRouter()

MANAGE = require_permission("discography.release.manage")
#: Plays from one address in an hour: a whole album twice over, and then some.
PLAYS_PER_IP = "60/1h"


def _size(file: UploadFile) -> int:
    if file.size is not None:
        return file.size
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    return size


# --- the public ------------------------------------------------------------------------------


@router.get("/releases", response_model=ReleaseCards, dependencies=[Depends(public)])
async def list_releases(
    kind: Literal["album", "ep", "single"] | None = None,
    cursor: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = service.PER_PAGE,
    ids: Annotated[list[uuid.UUID] | None, Query(max_length=service.MAX_IDS)] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The live releases, newest first, 12 a page; or with `ids` (50 at most),
    the live ones among them in the order given, on one page (0.1.2)."""
    if ids is not None:
        if cursor is not None:
            raise Problem(
                "kernel.invalid_request",
                422,
                "A read by ids is one page: it takes no cursor.",
                errors={"cursor": ["A read by ids takes no cursor."]},
            )
        return {"items": await service.releases_by_id(db, ids, kind=kind), "next_cursor": None}
    return await service.page_of(db, kind=kind, cursor=cursor, limit=limit)


@router.get("/tracks", response_model=TrackCards, dependencies=[Depends(public)])
async def read_tracks(
    ids: Annotated[list[uuid.UUID], Query(min_length=1, max_length=service.MAX_IDS)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The live tracks that play among `ids` (50 at most), in the order given,
    each with its release: a homepage's Spotlight queue (0.1.2)."""
    return {"items": await service.tracks_by_id(db, ids)}


@router.get(
    "/releases/{slug}", response_model=LiveRelease | MusicMoved, dependencies=[Depends(public)]
)
async def read_release(slug: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The live release at /music/<slug>, or `{moved}` for an address it left."""
    found = await service.live(db, slug)
    if found is None:
        raise Problem("discography.release_not_found", 404, "There's no release at that address.")
    if isinstance(found, str):
        return {"moved": found}
    return await service.shown(db, found)


@router.get(
    "/releases/{slug}/tracks/{track}",
    response_model=LiveTrack | MusicMoved,
    dependencies=[Depends(public)],
)
async def read_track(slug: str, track: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """A live, playable track's page, or `{moved}` for an address it left."""
    found = await service.live_track(db, slug, track)
    if found is None:
        raise Problem("discography.track_not_found", 404, "There's no track at that address.")
    if isinstance(found, str):
        return {"moved": found}
    return await service.track_shown(db, *found)


@router.get("/links", response_model=ArtistLinks, dependencies=[Depends(public)])
async def list_artist_links(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The artist's own links: the Music page's "Listen everywhere"."""
    return {"items": await service.artist_links(db)}


@router.post(
    "/tracks/{track_id}/plays",
    status_code=204,
    dependencies=[Depends(public), Depends(rate_limit(PLAYS_PER_IP))],
)
async def played(
    track_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    """The player heard the track long enough: one play of a live track that
    plays, counted once a listener a day. 204 whether it counted or not, so a
    draft's id says nothing."""
    if await service.count_play(db, request, track_id):
        await db.commit()
    return Response(status_code=204)


# --- the dashboard ---------------------------------------------------------------------------


@router.get("/admin/plays", response_model=PlaysWeek, dependencies=[Depends(MANAGE)])
async def read_plays(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The Dashboard's "Plays this week": the last seven days' plays (UTC), the
    seven before, and the track played most."""
    return await service.plays_week(db, clock.now().date())


# --- releases --------------------------------------------------------------------------------


@router.get("/admin/releases", response_model=AdminReleaseList, dependencies=[Depends(MANAGE)])
async def list_admin_releases(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Every release, newest edit first, with what needs doing."""
    return {"items": await service.every_release(db)}


@router.post("/admin/releases", response_model=FullRelease, status_code=201)
async def new_release(
    body: NewRelease, user: Any = Depends(MANAGE), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """A draft; 409 `discography.slug_taken` for a slug another release has."""
    release = await service.create_release(db, body.model_dump(exclude_unset=True), by=user.id)
    shown = await service.full_release(db, release)
    await db.commit()
    return shown


@router.get(
    "/admin/releases/{release_id}", response_model=FullRelease, dependencies=[Depends(MANAGE)]
)
async def read_admin_release(
    release_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await service.full_release(db, await service.get_release(db, release_id))


@router.patch("/admin/releases/{release_id}", response_model=FullRelease)
async def save_release(
    release_id: uuid.UUID,
    body: ReleaseChange,
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Saves it, credits, links and the tracks' order with it; a live release
    changes on the site at once. 409 `discography.changed` on a stale `version`."""
    fields = body.model_dump(include=body.model_fields_set - {"version"})
    release = await service.change_release(db, release_id, body.version, fields, by=user.id)
    shown = await service.full_release(db, release)
    await db.commit()
    return shown


@router.post("/admin/releases/{release_id}/publish", response_model=FullRelease)
async def publish_release(
    release_id: uuid.UUID,
    body: PublishRelease | None = None,
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Live now, or on release day at `at`."""
    release = await service.publish(db, release_id, body.at if body else None, by=user.id)
    shown = await service.full_release(db, release)
    await db.commit()
    return shown


@router.post("/admin/releases/{release_id}/unpublish", response_model=FullRelease)
async def unpublish_release(
    release_id: uuid.UUID, user: Any = Depends(MANAGE), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Back to a draft: its pages answer 404."""
    release = await service.unpublish(db, release_id, by=user.id)
    shown = await service.full_release(db, release)
    await db.commit()
    return shown


@router.delete("/admin/releases/{release_id}", status_code=204)
async def delete_release(
    release_id: uuid.UUID, user: Any = Depends(MANAGE), db: AsyncSession = Depends(get_db)
) -> Response:
    """Gone, with its tracks, credits, links and moves; their files after the commit."""
    await service.remove_release(db, release_id, by=user.id)
    await db.commit()
    return Response(status_code=204)


# --- tracks ----------------------------------------------------------------------------------


@router.post("/admin/releases/{release_id}/tracks", response_model=FullTrack, status_code=201)
async def new_track(
    release_id: uuid.UUID,
    body: NewTrack,
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A track at the end of the release, with a SoundCloud link or no audio yet."""
    track = await service.create_track(db, release_id, body.title, body.soundcloud_url, by=user.id)
    shown = await service.full_track(db, track)
    await db.commit()
    return shown


@router.post(
    "/admin/releases/{release_id}/tracks/upload", response_model=FullTrack, status_code=201
)
async def upload_track(
    release_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A track from an uploaded master, titled from its tags or its name, its
    stream made by a job. 413, 415 or 422 when the file can't be taken."""
    track = await service.upload_track(
        db, release_id, file.file, _size(file), file.filename, by=user.id
    )
    shown = await service.full_track(db, track)
    await db.commit()
    return shown


@router.get("/admin/tracks", response_model=AdminTrackList, dependencies=[Depends(MANAGE)])
async def list_tracks(
    q: Annotated[str | None, Query(max_length=200)] = None,
    show: Literal["all", "cant_play", "no_lyrics", "no_credits"] = "all",
    cursor: Annotated[str | None, Query(max_length=10)] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Every track on every release: the Tracks board."""
    return await service.every_track(db, q=q, show=show, cursor=cursor)


@router.get("/admin/tracks/{track_id}", response_model=FullTrack, dependencies=[Depends(MANAGE)])
async def read_track_admin(
    track_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await service.full_track(db, await service.get_track(db, track_id))


@router.patch("/admin/tracks/{track_id}", response_model=FullTrack)
async def save_track(
    track_id: uuid.UUID,
    body: TrackChange,
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    fields = body.model_dump(include=body.model_fields_set - {"version"})
    track = await service.change_track(db, track_id, body.version, fields, by=user.id)
    shown = await service.full_track(db, track)
    await db.commit()
    return shown


@router.delete("/admin/tracks/{track_id}", status_code=204)
async def delete_track(
    track_id: uuid.UUID, user: Any = Depends(MANAGE), db: AsyncSession = Depends(get_db)
) -> Response:
    await service.remove_track(db, track_id, by=user.id)
    await db.commit()
    return Response(status_code=204)


@router.put("/admin/tracks/{track_id}/audio", response_model=FullTrack)
async def replace_audio(
    track_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A new master: the old stream plays until the new one is ready."""
    track = await service.replace_audio(
        db, track_id, file.file, _size(file), file.filename, by=user.id
    )
    shown = await service.full_track(db, track)
    await db.commit()
    return shown


@router.delete("/admin/tracks/{track_id}/audio", response_model=FullTrack)
async def remove_audio(
    track_id: uuid.UUID, user: Any = Depends(MANAGE), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """The upload gone: the track plays from its link, if it has one."""
    track = await service.remove_audio(db, track_id, by=user.id)
    shown = await service.full_track(db, track)
    await db.commit()
    return shown


@router.post("/admin/tracks/{track_id}/audio/retry", response_model=FullTrack)
async def retry_audio(
    track_id: uuid.UUID, user: Any = Depends(MANAGE), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    track = await service.retry(db, track_id, by=user.id)
    shown = await service.full_track(db, track)
    await db.commit()
    return shown


# --- people, roles and links -----------------------------------------------------------------


@router.get("/admin/people", response_model=AdminPersonList, dependencies=[Depends(MANAGE)])
async def list_people(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Everyone credited, with what they're credited for: the Credits board."""
    return await service.every_person(db)


@router.patch("/admin/people/{person_id}", response_model=AdminPersonList)
async def save_person(
    person_id: uuid.UUID,
    body: PersonChange,
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    fields = body.model_dump(include=body.model_fields_set - {"version"})
    await service.change_person(db, person_id, body.version, fields, by=user.id)
    shown = await service.every_person(db)
    await db.commit()
    return shown


@router.get("/admin/roles", response_model=AdminRoleList, dependencies=[Depends(MANAGE)])
async def list_roles(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return {"items": await service.every_role(db)}


@router.put("/admin/roles", response_model=AdminRoleList)
async def put_roles(
    body: RolesPut, user: Any = Depends(MANAGE), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """The whole list, in order; 409 `discography.role_in_use` for one a credit names."""
    await service.put_roles(db, [each.model_dump() for each in body.items], by=user.id)
    shown = {"items": await service.every_role(db)}
    await db.commit()
    return shown


@router.get("/admin/links", response_model=AdminArtistLinks, dependencies=[Depends(MANAGE)])
async def list_admin_links(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return {"items": await service.artist_links(db)}


@router.put("/admin/links", response_model=AdminArtistLinks)
async def put_links(
    body: LinksPut, user: Any = Depends(MANAGE), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """The artist's own links, in order: one a platform."""
    await service.put_artist_links(db, body.links, by=user.id)
    shown = {"items": await service.artist_links(db)}
    await db.commit()
    return shown
