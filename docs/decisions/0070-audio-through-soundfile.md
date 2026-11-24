# 0070: Uploaded audio goes through soundfile, and the public bucket plays in `<audio>`

- **Status:** Decided. The owner approved `dev plans/contracts/discography.md` on 2026-11-24, then chose soundfile over PyAV after the licence check (the contract's "Changes after approval"). Applied with the discography module.
- **Context:**
  - discography turns an uploaded master into a public stream file, its length and 1,000 waveform peaks, in a kernel job (decision 0035).
  - The contract first recommended PyAV, whose wheels carry FFmpeg's libraries.
  - `oss-licence-gate`, run on PyAV 19.0.2's own wheels on 2026-11-24, found libx264 and libx265 bundled in both the Windows and manylinux wheels. FFmpeg's configuration says LGPL v3 with no `--enable-gpl`, but x264 and x265 are GPL-2.0-or-later, and they'd load into the same process as closed-source code. The gate rates that "don't ship".
  - A stream file in the public bucket is played by `<audio>`, and the kernel's `media-src` allowed `'self'` alone.
- **Decision:**
  1. **soundfile** (BSD-3) reads masters and writes the stream, through the libsndfile its wheels bundle (LGPL-2.1, loaded as a library of its own, so it can be replaced). **numpy** (BSD-3) works out the peaks. Both are pinned with hashes; no system package, no Dockerfile change.
  2. **Masters** are WAV, AIFF, FLAC, Ogg or MP3 (no M4A or ALAC), mono or more channels, up to 60 minutes and 60 MB. A master above 48 kHz at a whole multiple of 44.1 or 48 kHz is low-passed and taken down to it.
  3. **The stream** is MP3 at a constant `stream_bitrate_kbps` (128 to 320, 256 by default), which LAME takes to MP3's nearest standard rate. MP3's patents have expired.
  4. **The kernel adds the public bucket's origin to `media-src`** while `STORAGE_PUBLIC_URL` is set and https (`security.public_origin`). Its photos are `img-src`'s already.
- **The licence check** (2026-11-24; general information, not legal advice):

  | Item | Version | Layer | Licence | Evidence | ✅/⚠ | Verdict |
  |---|---|---|---|---|---|---|
  | soundfile | 0.14.0 | code | BSD-3-Clause | the wheel's `METADATA` | ✅ | SHIP |
  | libsndfile | 1.2.2, in soundfile's wheels | library | LGPL-2.1 | the wheel's `_soundfile_data/COPYING` | ✅ | CARE: keep the notice; it stays a separate library |
  | LAME, mpg123, FLAC, Ogg, Vorbis, Opus | inside libsndfile | codecs | LGPL / BSD | libsndfile's build notes | ⚠ | CARE |
  | numpy | 2.5.5 | code | BSD-3-Clause | PyPI | ⚠ | SHIP |
  | PyAV | 19.0.2 | code | BSD-3-Clause | the wheel's `LICENSE.txt` | ✅ | SHIP |
  | FFmpeg, in PyAV's wheels | 8.x (libavcodec 63) | library | LGPL v3, as built | `av._core.library_meta` | ✅ | CARE |
  | libx264, libx265, in PyAV's wheels | 165, 217 | library | GPL-2.0-or-later | the files in `av.libs` | ✅ files, ⚠ licence | DON'T, in-process with closed code |
  | MP3 | | patents | expired 2017 | | ⚠ | SHIP |

  An IP attorney should review the list before launch.
- **Alternatives:**
  - *PyAV:* every format and AAC, but GPL x264 and x265 come in the wheel.
  - *The `ffmpeg` program from apt, run as a process of its own:* its GPL would cover only ffmpeg. But it isn't pinned by hash, it needs a Dockerfile change, and it isn't on the owner's PC, so the tests would skip there.
  - *AAC through anything:* no LGPL-only encoder ships in a pinned wheel.
- **Consequences:**
  - A site with discography takes about 30 MB more image (numpy and libsndfile).
  - M4A and ALAC masters are refused with 415 `discography.not_audio`, and the message names the formats.
  - `kernel/backend/kernel/security.py` and `app.py` change by a few lines, and `kernel/tests/test_security.py` holds the rule.
- **See:** `dev plans/contracts/discography.md`; `modules/discography/backend/discography/audio.py`; SPEC 6 (storage) and 15; decisions 0032, 0035 and 0054.
