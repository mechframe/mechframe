"""The site's seed data: `python -m app.seed` (MechFrame's hook 4, decision
0052). It refuses unless MECHFRAME_ALLOW_SEED=1 is in the environment, which
`.railway/railway.ts` never sets; then it seeds the modules and the site's own
`app/site/seed.py` last, and a second run changes nothing."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from app import seed
from app.migrations import upgrade
from kernel import storage
from kernel.config import reset_config

# A module's seed may store files (media's stores its images in the public
# bucket), so the run gets a stand-in S3 (moto) with both buckets, as the
# modules' own tests make theirs. Stand-in values only: nothing here reaches a
# real bucket.
FAKE_STORAGE = {
    "STORAGE_ENDPOINT_URL": "https://r2.example.test",
    "STORAGE_ACCESS_KEY_ID": "seed-test-key-id",
    "STORAGE_SECRET_ACCESS_KEY": "seed-test-secret",
    "STORAGE_BUCKET": "seed-private",
    "STORAGE_PUBLIC_BUCKET": "seed-public",
    "STORAGE_PUBLIC_URL": "https://files.example.test",
}


@pytest.fixture
def fake_buckets(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # moto answers only AWS's own hosts unless told this one, before it loads.
    monkeypatch.setenv("MOTO_S3_CUSTOM_ENDPOINTS", FAKE_STORAGE["STORAGE_ENDPOINT_URL"])
    from moto import mock_aws

    for name, value in FAKE_STORAGE.items():
        monkeypatch.setenv(name, value)
    storage._client.cache_clear()
    with mock_aws():
        client = storage._client(
            FAKE_STORAGE["STORAGE_ENDPOINT_URL"],
            "auto",
            FAKE_STORAGE["STORAGE_ACCESS_KEY_ID"],
            FAKE_STORAGE["STORAGE_SECRET_ACCESS_KEY"],
        )
        for bucket in (FAKE_STORAGE["STORAGE_BUCKET"], FAKE_STORAGE["STORAGE_PUBLIC_BUCKET"]):
            client.create_bucket(
                Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": "auto"}
            )
        try:
            yield
        finally:
            storage._client.cache_clear()


def test_without_the_variable_it_refuses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("MECHFRAME_ALLOW_SEED", raising=False)
    assert seed.main([]) == 2
    assert "MECHFRAME_ALLOW_SEED=1" in capsys.readouterr().err


async def test_it_seeds_the_site_last_and_twice_the_same(
    empty_database_url: str,
    fake_buckets: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await asyncio.to_thread(upgrade, empty_database_url)
    monkeypatch.setenv("DATABASE_URL", empty_database_url)
    monkeypatch.setenv("MECHFRAME_ALLOW_SEED", "1")
    reset_config()  # the app's settings, read again with this database
    try:
        for _ in range(2):
            assert await asyncio.to_thread(seed.main, []) == 0
            # Each module first, then the site's own seed last: "Seeded: media, site."
            said = capsys.readouterr().out.strip().splitlines()[-1]
            assert said.startswith("Seeded: ")
            assert said.endswith("site.")
    finally:
        reset_config()


def test_the_command_takes_no_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert seed.main(["extra"]) == 2
    assert "usage: python -m app.seed" in capsys.readouterr().err
