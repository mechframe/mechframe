---
feature: The media module, the library every module picks images from (Vibrant Mindz step 1; M3's job)
status: approved
plan: `docs/plans/vibrant-mindz-backend/extraction/media.md`; `dev plans/2026-11-21-vibrant-mindz-push-plan.md` (M3); the canvas's AdminMedia board (`C:\DEV\VM Website\design\site\AdminMedia.dc.html`)
approved: 2026-11-21 (the owner: "Nope that all looks good, approved", the three answers in §8 as recommended)
pr: to predict at push time
---

# Contract: `media`

## 1. Goal

One library of images for the whole site: covers, member photos, artwork, product shots. A person uploads an image once, gives it alt text, and any module places it; `blog` requires it. Lifted from VybeSite's media library (`media_service.py`, `models/media_image.py`, `routers/media.py`, `ImagePicker.tsx`), whose upload rules are kept whole: judged by its bytes, read within limits, re-encoded with no metadata, named by us, stored once.

## 2. Interfaces

**Permissions:** `media.image.upload` (owner, admin, editor) to upload and pick; `media.image.manage` (owner, admin, editor) to change alt text, replace and delete.

**HTTP** (`/api/media`, behind `require_module("media")`; RFC 9457 codes `media.*`):

| Route | Access | Does |
| --- | --- | --- |
| `POST /admin/images` (multipart `file`) | `media.image.upload` | 201 `Image`; 200 with the stored one when the same image is uploaded again. 413 `media.too_large`, 415 `media.not_an_image`, 422 `media.unreadable`, 503 `media.storage_off` |
| `GET /admin/images?cursor=&q=&missing_alt=` | `media.image.upload` | `Page[Image]`, newest first, 40 a page |
| `GET /admin/images/{id}` | `media.image.upload` | `Image`, with `uses` |
| `PATCH /admin/images/{id}` `{alt, decorative, version}` | `media.image.manage` | 409 `kernel.save_conflict` on a stale `version` |
| `PUT /admin/images/{id}/file` (multipart) | `media.image.manage` | The same id, a new file: every use shows it |
| `DELETE /admin/images/{id}` | `media.image.manage` | 204; 409 `media.in_use`, naming the uses |

`Image`: `id`, `url`, `srcset`, `width`, `height`, `bytes`, `content_type`, `filename` (a label only, cleaned; never in a key), `alt`, `decorative`, `uploaded_by` (name or null), `created_at`, `version`, and on the one-image read `uses: [{label, link}]`.

**`public.py`** (for modules that list `media` in `requires`): `picture(db, id) -> Picture | None` and `pictures(db, ids)` (`url`, `srcset`, `width`, `height`, `alt`, `decorative`); `use(db, image_id, *, owner, label, link)` and `release(db, *, owner)`, where `owner` is the using thing's key, `<module>.<type>:<id>`, in the caller's transaction.

**`web/public.ts`:** `<ImagePicker title onPick onClose />` (the library in a dialog, paged and searchable, upload in place, alt text asked before it's placed; changes after approval) and `<Picture image sizes />` (an `<img>` with `srcset`, `width`, `height` and the image's alt).

**Admin page** `/admin/media` (`nav.admin` under Content), as the board draws it: the "N images have no alt text" card with Fix the first, search, the grid with "No alt text" badges, and the side panel (alt text, file, size, added, used in, Copy link, Replace, Delete, and why Delete waits).

**Hooks:** seed (three generated images with alt text); export and erase (`privacy.py`: the images a person uploaded, listed; erase keeps them as the site's and clears `uploaded_by`); dashboard (`ATTENTION`: images without alt text, `media.image.manage`; `SETUP`: the public bucket on). No lifecycle, taxonomy, search, bot check or consent: media loads nothing from a third party.

## 3. Data

`media_image`: `id` uuid, `version` int, `content_type` (`image/png`, `image/jpeg`, `image/webp`), `sha256` unique, `width`, `height`, `bytes`, `filename`, `alt` (≤ 250, one line, VybeSite's checks), `decorative` (empty alt only), `uploaded_by` → `auth_user` `ON DELETE SET NULL`, `created_at` (indexed), `updated_at`. `media_use`: `image_id` → `media_image` `ON DELETE RESTRICT`, `owner`, `label`, `link`, `created_at`, unique (`image_id`, `owner`). Branch `media`, `media_0001`, `depends_on` `kernel_0002`.

Files in the public bucket: `media/<id>/<version>.<ext>` and `media/<id>/<version>-<width>.<ext>` at 480, 960 and 1600 below the image's width, all made at upload in a thread. A replace writes the new version and deletes the old one's files after the commit.

## 4. Files

`modules/media/` as `modules/_template/` lays out: `backend/media/` (`__init__`, `models`, `schemas`, `service`, `pictures` (the Pillow rules), `router`, `public`, `privacy`, `dashboard`, `seed`), `migrations/`, `web/` (`module.web.ts`, `api.ts`, `public.ts`, `pages/AdminMedia.tsx`, `components/ImagePicker.tsx`, `Picture.tsx`), `tests/` (`backend/`, `contract/`, `web/`, `e2e/`), `module.json`, `MODULE.md`, `CHANGELOG.md`, `openapi.json`. `requirements.in`: Pillow. `catalog.json` regenerated. Kernel: `STORAGE_PUBLIC_URL`'s origin joins `img-src` while the public bucket is on (§8, 2).

## 5. Conventions this follows

SPEC 4 to 8 and 16; `skills/mechframe-module-extractor/SKILL.md` and `module-contract-lint`; the kit for every screen; the save-conflict pattern (decision 0046).

## 6. Non-goals

- Audio, video and documents (§8, 1). Embeds: the `embeds` module, with VybeSite's `EmbedPicker.tsx`.
- Resizing on request, crops, focal points and an image CDN worker (Basefra.me's `transforms.py`): fixed widths made at upload.
- SVG, GIF, HEIC and AVIF uploads, as VybeSite refuses them.
- Folders, tags or collections in the library.

## 7. Acceptance

- `pictures` ports VybeSite's upload tests: each refusal and its sentence, a decompression bomb refused from its header, EXIF and GPS gone, orientation applied, sRGB, the longest side 2400, the same upload stored once.
- Contract tests: every route's access (anonymous 401, member 403, editor allowed), delete refused while used and allowed once released, a replace keeping the id and its uses, a stale `version` 409, storage off 503.
- Migration round trip; the seed run twice gives the same rows; export lists a person's uploads; erase clears `uploaded_by`.
- Web: the admin page in both themes against the board, axe clean; `ImagePicker` picks, uploads and asks for alt text.
- `python -m tools.validate_schemas`, `module-contract-lint`, the brand check, and `mechframe add media` then `mechframe check` on a new site.

## 8. Open questions for the owner

1. **Images only for now?** Recommended: yes. The brief names images; the board's Audio, Video and Documents tabs wait until a module stores those (`discography` and `audio-player` keep their own audio, which needs streaming).
2. **Where the files live.** Recommended: the kernel's public bucket (R2, decision 0032), each size made at upload, the kernel adding the bucket's address to the CSP's `img-src`. VybeSite keeps images in the database so its nightly backup covers them; R2 is the backup's own store here.
3. **"Used in" and Delete, as the board draws them.** Recommended: yes. Modules record each use through `public.use`, Delete waits until none is left, and Replace keeps the id. VybeSite never deleted an image.

## Changes after approval

- 2026-11-21 (the build): **no kernel change for the CSP.** `img-src` already allows `https:` (`kernel/security.py`'s base policy), so the public bucket's images load as they are; §4's kernel line is dropped.
- 2026-11-21 (the build): **two counters.** `version` counts the row's edits and is what a change sends back; `file_version` is the file's, in its keys (`media/<id>/<file_version>.<ext>`), raised only by a replace. One number for both would have moved an image's address on every alt-text change.
- 2026-11-21 (the build): **a stale `version` is 409 `media.changed`**, with the image's `version`, `alt` and `decorative` now, not `kernel.save_conflict`: the kernel's conflict answer is the settings sections' (decision 0046), and has no row-level helper.
- 2026-11-21 (the build): **the grants are in `media_0001`.** Nothing reads a manifest's `default_roles`, so the migration grants admin and editor both permissions, as the kernel's own migrations do, and its downgrade takes them back.
- 2026-11-21 (the build): **the seed stores its own files.** `ctx.put_image` gives one key per name, where a library image needs its smaller copies under the library's keys. Each seed image has a fixed id, so a rerun writes the same keys.
- 2026-11-21 (the build): **`python-multipart`** joins `requirements.in` beside Pillow: FastAPI's `File` and `UploadFile` need it, and the kernel took no uploads before.
- 2026-11-21 (the build; the owner chose it the same day, "Per route limit"): **its upload routes take 16 MB.** The kernel refused any body over MAX_BODY_BYTES (1 MB) before media read it, which its HTTP tests found. A module's `BODY_LIMITS` now lets named routes take more while it's on (decision 0054).
- 2026-11-21 (the build): **an image's address while the public bucket is off is 503 `media.storage_off`**, as an upload is, not a 500.
- 2026-11-21 (CodeRabbit on #116): **`ImagePicker` takes `title`, `onPick` and `onClose`**, not §2's `value`, `onChange` and `label`: it's a dialog a module opens and closes, and it hands back the image picked, so the module keeps its own value.
- 2026-11-21 (CodeRabbit on #116): **a replace's `file_version` comes from the sequence `media_file_version_seq`**, not the old one plus one. A rolled-back try's files are deleted after it ends, and a retry that took the same number and committed would have lost its own files to that cleanup. A number from the sequence is never given twice, since nextval isn't rolled back.
- 2026-11-21 (the build): **the admin page's filter is one chip, "No alt text"**, not the board's All, Images, Audio, Video and Documents tabs: images are the only kind (§8, 1).
- 2026-11-22 (VM Website Dev 08's check of media against its board, with the owner's OK, 2026-11-21 and 22; the board at canvas version 82): **the page is drawn to the board.** Each image is a card, its picture square, its file name under it and the "No alt text" pill under that (on the picture, the pill failed 4.5:1 over some images); a tile's name starts with the file name it shows. The panel is a 320px column with no title: a square preview, the alt text a three-line box with its hint under it, the "Only decoration" row and Save (which the board now draws), the facts with their values right-aligned and "Used in" as links, then Copy link (no icon), Replace and Delete. The search is the kit's `SearchBox`.
- 2026-11-22 (media's round 2, #126: VM Website Dev 09's second check against the board, sent with the owner's OK; `dev plans/done/2026-11-22-media-round-2.md`): **the board's measures.** The search row sits above the library and the panel both, so the panel starts level with the grid; the alt text is a two-line box at its 64px least height (three lines made it 81); a tile's corner is `radius.md`, its pill spans the tile in 12px words; the hint is weight 400, "Only decoration" 16px weight 400, "Used in"'s links `color.info`. The admin's labels and panels take the boards' normal line height, prose keeping its own (decision 0042, amended).
