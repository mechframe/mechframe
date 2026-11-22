"""The app factory: refusals at start, docs, health, access marks and the harness."""

from __future__ import annotations

import json
import types
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Union, get_args, get_origin

import httpx
import pytest
from fastapi import APIRouter, Depends, WebSocket

import kernel
from harness.layout import KERNEL
from kernel.access import ACCESS_MARK, public, undeclared
from kernel.modules import InstalledModule

from .conftest import AppFactory, Client, manifest


def test_refuses_to_start_on_a_bad_secret(app_factory: AppFactory) -> None:
    with pytest.raises(RuntimeError, match="SECRET_KEY is shorter than 43 characters"):
        app_factory(secret_key="short")


def test_refuses_to_start_on_an_unknown_module(app_factory: AppFactory) -> None:
    with pytest.raises(RuntimeError, match="MODULES names blgo, which is not installed"):
        app_factory([InstalledModule(manifest("blog"))], modules="blgo")


def test_refuses_a_missing_requirement(app_factory: AppFactory) -> None:
    with pytest.raises(RuntimeError, match="comments requires blog"):
        app_factory([InstalledModule(manifest("comments", requires={"blog": "^0.1"}))])


async def test_docs_only_with_debug(app_factory: AppFactory) -> None:
    async with Client(app_factory()) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert (await client.get(path)).status_code == 404
    async with Client(app_factory(debug=True)) as client:
        assert (await client.get("/openapi.json")).status_code == 200


async def test_health(app_factory: AppFactory) -> None:
    async with Client(app_factory()) as client:
        response = await client.get("/api/kernel/health")
    assert response.json() == {"status": "ok", "version": kernel.__version__, "database": "ok"}
    assert response.headers["x-frame-options"] == "DENY"


async def test_health_without_a_database(app_factory: AppFactory) -> None:
    app = app_factory(database_url="postgresql://mechframe:mechframe@127.0.0.1:1/none")
    async with Client(app, drain=False) as client:  # no database: no queue to run
        response = await client.get("/api/kernel/health")
    assert (response.status_code, response.json()["database"]) == (503, "unreachable")


def test_every_kernel_route_declares_its_access(app_factory: AppFactory) -> None:
    assert undeclared(app_factory()) == []


def test_a_route_with_no_access_fails_the_audit(app_factory: AppFactory) -> None:
    router = APIRouter()

    @router.post("/open")
    async def open_route() -> None: ...

    app = app_factory([InstalledModule(manifest("leaky"), router=router)])
    assert undeclared(app) == ["POST /api/leaky/open"]


def test_the_audit_sees_admin_routes_marked_public_by_their_router(
    app_factory: AppFactory,
) -> None:
    router = APIRouter()
    admin = APIRouter(prefix="/admin", dependencies=[Depends(public)])

    @admin.delete("/users/{user_id}")
    async def delete_user(user_id: str) -> None: ...

    router.include_router(admin)
    app = app_factory([InstalledModule(manifest("forum"), router=router)])
    assert undeclared(app) == [
        "DELETE /api/forum/admin/users/{user_id} (an admin route can't be public)"
    ]


def test_the_audit_refuses_public_beside_another_mark(app_factory: AppFactory) -> None:
    def member() -> None: ...

    setattr(member, ACCESS_MARK, "member")
    router = APIRouter(dependencies=[Depends(public)])

    @router.get("/mine", dependencies=[Depends(member)])
    async def mine() -> None: ...

    app = app_factory([InstalledModule(manifest("mixed"), router=router)])
    assert undeclared(app) == ["GET /api/mixed/mine (public beside member)"]


def test_the_audit_sees_websockets_and_mounts(app_factory: AppFactory) -> None:
    from starlette.applications import Starlette

    router = APIRouter()

    @router.websocket("/live")
    async def live(websocket: WebSocket) -> None: ...

    @router.websocket("/open-live", dependencies=[Depends(public)])
    async def open_live(websocket: WebSocket) -> None: ...

    app = app_factory([InstalledModule(manifest("chat"), router=router)])
    app.mount("/api/legacy", Starlette())
    assert undeclared(app) == [
        "MOUNT /api/legacy (a mounted app under /api can't declare access)",
        "WEBSOCKET /api/chat/live",
    ]


def test_the_versions_agree() -> None:
    manifest_version = json.loads((KERNEL / "kernel.json").read_text("utf-8"))["version"]
    web = (KERNEL / "web" / "src" / "version.ts").read_text("utf-8")
    assert kernel.__version__ == manifest_version
    assert f'"{manifest_version}"' in web


def test_the_public_surface() -> None:
    for name in kernel.__all__:
        assert hasattr(kernel, name), name


def test_the_harness_builds(monkeypatch: pytest.MonkeyPatch, migrated_url: str) -> None:
    import importlib

    from kernel.config import reset_config

    monkeypatch.setenv("DATABASE_URL", migrated_url)
    reset_config()
    try:
        main = importlib.import_module("harness.main")
        assert undeclared(main.app) == []
        assert Path(main.__file__).name == "main.py"
    finally:
        monkeypatch.undo()
        reset_config()


def _boom_module() -> InstalledModule:
    router = APIRouter()

    @router.get("/boom", dependencies=[Depends(public)])
    async def boom() -> None:
        raise RuntimeError("kaboom")

    @router.post("/echo", dependencies=[Depends(public)])
    async def echo(body: dict[str, str]) -> dict[str, int]:
        return {"keys": len(body)}

    return InstalledModule(manifest("probe"), router=router)


async def test_an_unexpected_error_keeps_the_security_headers(app_factory: AppFactory) -> None:
    """Handled inside SecurityHeaders and not raised on, so the 500 carries the
    headers and the server logs it once (no second "Exception in ASGI
    application")."""
    app = app_factory([_boom_module()])
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="https://mechframe.test") as c:
            response = await c.get("/api/probe/boom")  # raises here if the error escapes
    assert (response.status_code, response.json()["code"]) == (500, "kernel.internal_error")
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_a_body_over_the_limit_is_refused(app_factory: AppFactory) -> None:
    app = app_factory([_boom_module()], max_body_bytes=1024)
    big = {"text": "x" * 2000}
    async with Client(app) as client:
        assert (await client.post("/api/probe/echo", json={"a": "b"})).status_code == 200
        declared = await client.post("/api/probe/echo", json=big)
        assert (declared.status_code, declared.json()["code"]) == (413, "kernel.too_large")

        async def chunks() -> AsyncIterator[bytes]:  # no Content-Length: counted as it comes
            yield b'{"text": "'
            for _ in range(20):
                yield b"x" * 100
            yield b'"}'

        streamed = await client.post(
            "/api/probe/echo", content=chunks(), headers={"Content-Type": "application/json"}
        )
        assert (streamed.status_code, streamed.json()["code"]) == (413, "kernel.too_large")


def _uploading_module(
    limits: tuple[tuple[str, str, int], ...], module_id: str = "probe"
) -> InstalledModule:
    router = APIRouter()

    @router.post("/echo", dependencies=[Depends(public)])
    async def echo(body: dict[str, str]) -> dict[str, int]:
        return {"keys": len(body)}

    @router.put("/items/{item_id}/file", dependencies=[Depends(public)])
    async def item_file(item_id: str, body: dict[str, str]) -> dict[str, int]:
        return {"keys": len(body)}

    @router.post("/other", dependencies=[Depends(public)])
    async def other(body: dict[str, str]) -> dict[str, int]:
        return {"keys": len(body)}

    return InstalledModule(manifest(module_id), router=router, body_limits=limits)


async def test_a_modules_route_may_take_a_larger_body_than_the_site(
    app_factory: AppFactory,
) -> None:
    """A module's BODY_LIMITS (media's uploads, decision 0054): the named routes
    take up to their own limit, every other keeps the site's."""
    limits = (("POST", "/echo", 4096), ("PUT", "/items/{item_id}/file", 4096))
    app = app_factory([_uploading_module(limits)], max_body_bytes=1024)
    middling = {"text": "x" * 2000}
    async with Client(app) as client:
        assert (await client.post("/api/probe/echo", json=middling)).status_code == 200
        assert (await client.put("/api/probe/items/7/file", json=middling)).status_code == 200
        other = await client.post("/api/probe/other", json=middling)
        assert (other.status_code, other.json()["code"]) == (413, "kernel.too_large")
        wrong_method = await client.put("/api/probe/echo", json=middling)
        assert wrong_method.status_code == 413
        deeper = await client.put("/api/probe/items/7/file/x", json=middling)
        assert deeper.status_code == 413

        too_big = await client.post("/api/probe/echo", json={"text": "x" * 5000})
        assert (too_big.status_code, too_big.json()["code"]) == (413, "kernel.too_large")
        assert "4,096 bytes" in too_big.json()["detail"]

        async def chunks(count: int) -> AsyncIterator[bytes]:
            yield b'{"text": "'
            for _ in range(count):
                yield b"x" * 100
            yield b'"}'

        headers = {"Content-Type": "application/json"}
        streamed = await client.post("/api/probe/echo", content=chunks(20), headers=headers)
        assert streamed.status_code == 200
        overflowing = await client.post("/api/probe/echo", content=chunks(50), headers=headers)
        assert overflowing.status_code == 413


async def test_a_larger_body_needs_its_module_on(app_factory: AppFactory) -> None:
    limits = (("POST", "/echo", 4096),)
    app = app_factory(
        [_uploading_module(limits), _uploading_module((), "other")],
        max_body_bytes=1024,
        modules="other",
    )
    async with Client(app) as client:
        response = await client.post("/api/probe/echo", json={"text": "x" * 2000})
        assert (response.status_code, response.json()["code"]) == (413, "kernel.too_large")


@pytest.mark.parametrize(
    ("limit", "says"),
    [
        (("GET", "/echo", 4096), "POST, PUT or PATCH"),
        (("POST", "echo", 4096), "starts with /"),
        (("POST", "/echo", 0), "bytes"),
        (("POST", "/echo", 65 * 1024 * 1024), "bytes"),
        (("POST", "/echo", True), "bytes"),
    ],
)
def test_a_body_limit_the_kernel_cant_keep_is_refused_at_the_start(
    app_factory: AppFactory, limit: tuple[str, str, int], says: str
) -> None:
    with pytest.raises(ValueError, match="BODY_LIMITS") as refused:
        app_factory([_uploading_module((limit,))])
    assert says in str(refused.value)


def _routes_module(
    limits: tuple[tuple[str, str, int], ...], *paths: tuple[str, str]
) -> InstalledModule:
    router = APIRouter()
    for method, path in paths:

        async def take(body: dict[str, str]) -> dict[str, int]:
            return {"keys": len(body)}

        router.add_api_route(path, take, methods=[method], dependencies=[Depends(public)])
    return InstalledModule(manifest("probe"), router=router, body_limits=limits)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("/items/{item_id}", "/items/import"),
        ("/items/{item_id}/edit", "/items/special/{action}"),
    ],
)
def test_two_body_limits_that_can_match_one_request_are_refused_at_the_start(
    app_factory: AppFactory, first: str, second: str
) -> None:
    """CodeRabbit on #116: which applied hung on their order. Compared segment by segment."""
    limits = (("POST", first, 4096), ("POST", second, 8192))
    with pytest.raises(ValueError, match="BODY_LIMITS") as refused:
        app_factory([_routes_module(limits, ("POST", first), ("POST", second))])
    assert "both match" in str(refused.value)


def test_body_limits_that_dont_meet_are_taken(app_factory: AppFactory) -> None:
    paths = (
        ("POST", "/items/{item_id}"),
        ("PUT", "/items/import"),
        ("POST", "/items/{item_id}/edit"),
    )
    limits = (
        ("POST", "/items/{item_id}", 4096),
        ("PUT", "/items/import", 8192),
        ("POST", "/items/{item_id}/edit", 8192),
    )
    app_factory([_routes_module(limits, *paths)])


def test_a_body_limit_for_a_route_the_module_doesnt_serve_is_refused_at_the_start(
    app_factory: AppFactory,
) -> None:
    """CodeRabbit on #116: it raised the limit for a request nothing answers."""
    with pytest.raises(ValueError, match="BODY_LIMITS") as refused:
        app_factory([_routes_module((("POST", "/uploads", 4096),), ("POST", "/echo"))])
    assert "names no route" in str(refused.value)


def test_the_kernels_permissions_match_its_manifest() -> None:
    """Keys, words and order: the Roles page lists them as the manifest has
    them, and a site never receives the manifest (K4.7)."""
    from kernel.auth.permissions import KERNEL_PERMISSION_WORDS, KERNEL_PERMISSIONS

    manifest = json.loads((KERNEL / "kernel.json").read_text("utf-8"))
    assert {permission["key"] for permission in manifest["permissions"]} == KERNEL_PERMISSIONS
    assert [(p["key"], p["description"]) for p in manifest["permissions"]] == list(
        KERNEL_PERMISSION_WORDS.items()
    )


def test_the_kernels_pages_match_its_manifest() -> None:
    """A site never receives kernel.json, so the backend keeps the list in
    code; this holds it to the manifest (K4 contract, change 8). The web
    side's list has a test of its own (kernel/web/src/app/pages.test.ts)."""
    from kernel.server_copy import KERNEL_PAGES

    manifest = json.loads((KERNEL / "kernel.json").read_text("utf-8"))
    listed = [(page["path"], page["title"], page["access"]) for page in manifest["pages"]]
    assert listed == [(page.path, page.title, page.access) for page in KERNEL_PAGES]


def test_every_request_body_is_strict(app_factory: AppFactory) -> None:
    """SPEC.md 7: every body is a Pydantic model in strict mode, so nothing is
    coerced silently that a port would have to copy (CodeRabbit on #42)."""
    from fastapi.routing import APIRoute, iter_route_contexts

    bodies: dict[str, object] = {}
    for context in iter_route_contexts(app_factory().routes):
        route = context.original_route
        if isinstance(route, APIRoute) and route.body_field is not None:
            name = f"{','.join(sorted(route.methods))} {context.path}"
            bodies[name] = route.body_field.field_info.annotation
    assert "POST /api/auth/code" in bodies  # the control: the walk finds the bodies

    def strict(model: object) -> bool:
        # A body of two shapes is a union of models, each strict (decision 0042).
        if get_origin(model) in (Union, types.UnionType):
            return all(strict(member) for member in get_args(model))
        return getattr(model, "model_config", {}).get("strict") is True

    assert get_origin(bodies["POST /api/kernel/notifications/read"]) is not None
    loose = sorted(name for name, model in bodies.items() if not strict(model))
    assert loose == []
