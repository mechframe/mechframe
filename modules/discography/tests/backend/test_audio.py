"""Reading masters and making stream files (`discography.audio`, decision 0070):
no database, no storage, every file made by the test."""

from __future__ import annotations

import io

import numpy as np
import pytest
import soundfile as sf
from discography import audio

from ..conftest import master


@pytest.mark.parametrize(
    ("rate", "channels", "fmt", "out_rate", "out_channels"),
    [
        (44100, 2, "WAV", 44100, 2),
        (48000, 1, "FLAC", 48000, 1),
        (96000, 2, "WAV", 48000, 2),
        (88200, 2, "AIFF", 44100, 2),
        (48000, 6, "WAV", 48000, 2),
    ],
)
def test_a_master_becomes_an_mp3_of_its_length_with_1000_peaks(
    rate: int, channels: int, fmt: str, out_rate: int, out_channels: int
) -> None:
    source = io.BytesIO(master(4.0, rate, channels, fmt))
    into = io.BytesIO()
    heard: list[int] = []

    made = audio.make_stream(source, into, kbps=256, progress=heard.append)

    into.seek(0)
    stream = sf.info(into)
    assert stream.format == "MP3"
    assert (stream.samplerate, stream.channels) == (out_rate, out_channels)
    assert (made.samplerate, made.channels) == (out_rate, out_channels)
    assert abs(made.duration_ms - 4000) <= 50
    assert abs(stream.duration - 4.0) < 0.1
    kbps = into.getbuffer().nbytes * 8 / stream.duration / 1000
    assert 240 <= kbps <= 270
    assert len(made.peaks) == 1000
    assert made.peaks[0] < 20
    assert max(made.peaks) == 255
    assert all(0 <= each <= 255 for each in made.peaks)
    assert heard[-1] == 100
    assert heard == sorted(heard)


@pytest.mark.parametrize(("kbps", "lowest", "highest"), [(128, 120, 140), (320, 300, 330)])
def test_the_bitrate_follows_the_setting(kbps: int, lowest: int, highest: int) -> None:
    into = io.BytesIO()
    audio.make_stream(io.BytesIO(master(4.0)), into, kbps=kbps)
    into.seek(0)
    found = into.getbuffer().nbytes * 8 / sf.info(into).duration / 1000
    assert lowest <= found <= highest


def test_a_probe_reads_what_the_master_is_and_leaves_it_at_its_start() -> None:
    source = io.BytesIO(master(2.0, 48000, 1, "FLAC"))
    found = audio.probe(source)
    assert (found.format, found.extension, found.content_type) == ("FLAC", ".flac", "audio/flac")
    assert (found.samplerate, found.channels, round(found.seconds, 2)) == (48000, 1, 2.0)
    assert source.tell() == 0


def test_bytes_that_arent_audio_are_refused() -> None:
    with pytest.raises(audio.NotAudio):
        audio.probe(io.BytesIO(b"<html>not a song</html>" * 200))


def test_a_rate_that_isnt_a_whole_multiple_is_refused() -> None:
    with pytest.raises(audio.Unsupported, match=r"44\.1 or 48 kHz"):
        audio.probe(io.BytesIO(master(1.0, 64000)))


def test_a_master_over_an_hour_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio, "MAX_SECONDS", 1)
    with pytest.raises(audio.TooLong):
        audio.probe(io.BytesIO(master(2.0)))


@pytest.mark.parametrize(("kbps", "level"), [(320, 0.0), (256, 0.2222), (128, 0.6667), (999, 0.0)])
def test_the_compression_level_for_a_bitrate(kbps: int, level: float) -> None:
    assert audio.level_for(kbps) == level


@pytest.mark.parametrize(
    ("rate", "kbps", "lowest", "highest"), [(22050, 128, 118, 140), (22050, 320, 145, 170)]
)
def test_a_low_rate_master_streams_at_the_bitrate_it_can_hold(
    rate: int, kbps: int, lowest: int, highest: int
) -> None:
    """CodeRabbit on #145: below 32 kHz an MP3 is MPEG-2, from 160 kbps down."""
    into = io.BytesIO()
    audio.make_stream(io.BytesIO(master(4.0, rate)), into, kbps=kbps)
    into.seek(0)
    found = into.getbuffer().nbytes * 8 / sf.info(into).duration / 1000
    assert lowest <= found <= highest


@pytest.mark.parametrize(
    ("kbps", "rate", "level"),
    [(128, 44100, 0.6667), (128, 22050, 0.2105), (320, 22050, 0.0), (128, 11025, 0.0)],
)
def test_the_compression_level_follows_the_streams_rate(kbps: int, rate: int, level: float) -> None:
    assert audio.level_for(kbps, rate) == level


def test_a_master_with_samples_that_arent_numbers_is_refused() -> None:
    """CodeRabbit on #145: a NaN in a float WAV fails the track with words, not the job."""
    wave = np.zeros((44100, 2), dtype="float32")
    wave[100, 0] = np.nan
    out = io.BytesIO()
    sf.write(out, wave, 44100, format="WAV", subtype="FLOAT")
    with pytest.raises(audio.NotAudio):
        audio.make_stream(io.BytesIO(out.getvalue()), io.BytesIO(), kbps=128)


def test_a_downmix_of_loud_float_channels_stays_a_number() -> None:
    """CodeRabbit on #145: four float samples of 1e38 sum past float32's range; the
    mix is worked out wider, so its peaks are numbers."""
    wave = np.full((44100, 4), 1e38, dtype="float32")
    out = io.BytesIO()
    sf.write(out, wave, 44100, format="WAV", subtype="FLOAT")
    made = audio.make_stream(io.BytesIO(out.getvalue()), io.BytesIO(), kbps=128)
    assert max(made.peaks) == 255
