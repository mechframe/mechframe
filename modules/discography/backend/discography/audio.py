"""Reading a master and making its stream file and peaks (decision 0070).

soundfile reads the master through libsndfile (LGPL-2.1, loaded as a library
of its own) and writes the stream as MP3 at a constant bitrate; numpy works
out the waveform. Everything here is synchronous and blocking: the job runs
it in a thread (`asyncio.to_thread`).

- **What's taken:** WAV, AIFF, FLAC, Ogg and MP3 masters, mono or more
  channels, up to 60 minutes. libsndfile reads no M4A or ALAC.
- **The stream** is 44.1 or 48 kHz MP3, stereo unless the master is mono. A
  master above 48 kHz at a whole multiple of 44.1 or 48 (88.2, 96, 176.4,
  192) is low-passed with a windowed sinc and taken down to it; any other
  rate above 48 kHz is refused. Rates MP3 holds pass as they are.
- **The peaks** are 1,000 integers from 0 to 255: the loudest sample across
  the channels in each thousandth of the track, scaled so the loudest is 255.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, BinaryIO

import numpy as np
import soundfile as sf

from discography.models import PEAKS

#: The formats a master may be, as libsndfile names them, with the file's
#: extension and content type when it's stored.
FORMATS: dict[str, tuple[str, str]] = {
    "WAV": (".wav", "audio/wav"),
    "WAVEX": (".wav", "audio/wav"),
    "AIFF": (".aiff", "audio/aiff"),
    "FLAC": (".flac", "audio/flac"),
    "OGG": (".ogg", "audio/ogg"),
    "MP3": (".mp3", "audio/mpeg"),
}
MAX_SECONDS = 60 * 60
#: The sample rates an MP3 may have.
MP3_RATES = frozenset({8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000})
#: Frames read at a time.
BLOCK = 65536
#: The low-pass filter's taps, per step down.
TAPS_PER_STEP = 64
MIN_KBPS, MAX_KBPS = 128, 320


class NotAudio(ValueError):
    """The file isn't audio libsndfile reads, or isn't one of `FORMATS`."""


class TooLong(ValueError):
    """Over `MAX_SECONDS`."""


class Unsupported(ValueError):
    """Audio, but at a sample rate the stream can't be made from."""


@dataclass(frozen=True)
class Probe:
    format: str
    extension: str
    content_type: str
    samplerate: int
    channels: int
    frames: int
    title: str | None

    @property
    def seconds(self) -> float:
        return self.frames / self.samplerate if self.samplerate else 0.0


@dataclass(frozen=True)
class Made:
    duration_ms: int
    peaks: list[int]
    samplerate: int
    channels: int


def _step(samplerate: int) -> int:
    """How many times over 44.1 or 48 kHz a rate is: 1 for one MP3 holds."""
    if samplerate in MP3_RATES:
        return 1
    for base in (44100, 48000):
        if samplerate > base and samplerate % base == 0:
            return samplerate // base
    raise Unsupported(
        f"A master at {samplerate} Hz can't be streamed: export it at 44.1 or 48 kHz, "
        "or a whole multiple of either."
    )


def probe(source: BinaryIO) -> Probe:
    """What the master is, read from its bytes; `source` is left at its start."""
    source.seek(0)
    try:
        with sf.SoundFile(source) as audio:
            fmt, rate, channels, frames = (
                audio.format,
                audio.samplerate,
                audio.channels,
                audio.frames,
            )
            title = (audio.copy_metadata().get("title") or "").strip() or None
    except (sf.LibsndfileError, RuntimeError, TypeError) as error:
        raise NotAudio("The file isn't audio this site reads.") from error
    finally:
        source.seek(0)
    if fmt not in FORMATS or channels < 1 or rate <= 0 or frames <= 0:
        raise NotAudio("The file isn't audio this site reads.")
    found = Probe(fmt, *FORMATS[fmt], rate, channels, frames, title)
    if found.seconds > MAX_SECONDS:
        raise TooLong("The file runs over 60 minutes.")
    _step(rate)
    return found


def level_for(kbps: int) -> float:
    """libsndfile's compression level for a constant `kbps`: 0 is 320 kbps,
    each step of 0.1 about 29 kbps less, taken by LAME to the nearest
    standard rate."""
    kbps = max(MIN_KBPS, min(MAX_KBPS, kbps))
    return round((MAX_KBPS - kbps) / 288, 4)


def _lowpass(step: int) -> np.ndarray[Any, np.dtype[np.float32]]:
    """A Blackman-windowed sinc passing below the new rate's Nyquist."""
    taps = TAPS_PER_STEP * step + 1
    cutoff = 0.95 / (2 * step)  # of the old rate, a little under the new Nyquist
    n = np.arange(taps) - (taps - 1) / 2
    kernel = 2 * cutoff * np.sinc(2 * cutoff * n) * np.blackman(taps)
    return np.asarray(kernel / kernel.sum(), dtype=np.float32)


class _Down:
    """Low-passes and decimates by `step`, block by block, keeping the filter's tail."""

    def __init__(self, step: int, channels: int) -> None:
        self.step = step
        self.kernel = _lowpass(step) if step > 1 else None
        width = 0 if self.kernel is None else len(self.kernel) - 1
        self.tail = np.zeros((width, channels), dtype=np.float32)
        self.phase = 0

    def __call__(self, block: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        if self.kernel is None:
            return block
        joined = np.concatenate([self.tail, block])
        filtered = np.stack(
            [
                np.convolve(joined[:, channel], self.kernel, mode="valid")
                for channel in range(joined.shape[1])
            ],
            axis=1,
        )
        if len(self.kernel) > 1:
            self.tail = joined[-(len(self.kernel) - 1) :]
        start = (-self.phase) % self.step
        kept = filtered[start :: self.step]
        self.phase = (self.phase + len(block)) % self.step
        return kept


def make_stream(
    source: BinaryIO,
    into: BinaryIO,
    *,
    kbps: int,
    progress: Callable[[int], None] = lambda percent: None,
) -> Made:
    """Reads the master from `source` and writes its MP3 to `into`: the stream
    file's duration and peaks. `progress` hears whole percents as it goes."""
    found = probe(source)
    step = _step(found.samplerate)
    rate = found.samplerate // step
    channels = 1 if found.channels == 1 else 2
    down = _Down(step, channels)
    loudest = np.zeros(PEAKS, dtype=np.float32)
    done = 0
    told = -1
    try:
        with (
            sf.SoundFile(source) as master,
            sf.SoundFile(
                into,
                "w",
                samplerate=rate,
                channels=channels,
                format="MP3",
                subtype="MPEG_LAYER_III",
                compression_level=level_for(kbps),
                bitrate_mode="CONSTANT",
            ) as stream,
        ):
            for block in master.blocks(blocksize=BLOCK, dtype="float32", always_2d=True):
                if block.shape[1] > 2:
                    mixed = block.mean(axis=1, keepdims=True)
                    block = np.repeat(mixed, 2, axis=1)
                elif channels == 2 and block.shape[1] == 1:
                    block = np.repeat(block, 2, axis=1)
                level = np.abs(block).max(axis=1)
                slices = (np.arange(done, done + len(block)) * PEAKS) // found.frames
                np.maximum.at(loudest, np.minimum(slices, PEAKS - 1), level)
                done += len(block)
                stream.write(np.clip(down(block), -1.0, 1.0))
                percent = min(99, done * 100 // found.frames)
                if percent != told:
                    told = percent
                    progress(percent)
    except (sf.LibsndfileError, RuntimeError) as error:
        raise NotAudio("The file couldn't be read to its end.") from error
    top = float(loudest.max())
    peaks = [0] * PEAKS if top <= 0 else [round(255 * float(each) / top) for each in loudest]
    duration_ms = math.floor(done * 1000 / found.samplerate + 0.5)
    progress(100)
    return Made(duration_ms=duration_ms, peaks=peaks, samplerate=rate, channels=channels)
