# media

The library every module picks images from: covers, member photos, artwork, product shots. The contract is `dev plans/contracts/media.md`.

## What it does

An editor uploads an image once and gives it alt text, and any module places it. Each upload is judged by its bytes: PNG, JPEG or WebP only, and refused with a sentence otherwise. It's re-encoded with no metadata, so EXIF, GPS and XMP are gone. It's turned the way its camera meant, converted to sRGB and kept to 2400 px a side. It's stored once in the kernel's public bucket, with copies 480, 960 and 1600 px wide for `srcset`. The library shows where each image is placed, and an image can't be deleted while anything places it. A replace keeps the id, so every page shows the new file.

## Use when / avoid when

Use it when the site's editors upload images that more than one module places, or when photos come from phones and cameras and must lose their metadata before they're public. Avoid it for audio, video or documents, which it doesn't take. Avoid it too for a module's own few images that nothing else places: `storage.put` in that module is enough.

## What it adds

- **Routes**, all staff's, under `/api/media/admin/images`:
  - `POST` uploads, answering 201, or 200 for an image already stored;
  - `GET` lists 40 a page, newest first, with `q`, `missing_alt` and `cursor`;
  - `GET /{id}` reads one image with its uses;
  - `PATCH /{id}` changes the alt text or whether it's only decoration, with `version` (409 `media.changed`);
  - `PUT /{id}/file` replaces the file;
  - `DELETE /{id}` deletes it (409 `media.in_use` while it's placed).
- **The admin page** at `/admin/media`, under Content in the sidebar.
- **Tables:** `media_image` and `media_use` (migration `media_0001`).
- **Permissions:**
  - `media.image.upload` (upload and pick) and `media.image.manage` (alt text, replace, delete);
  - both go to admin and editor, granted in the migration; an owner holds every permission.
- **Hooks:**
  - seed: three images with alt text;
  - export and erase: a person's uploads listed, and on erase, who uploaded them forgotten;
  - dashboard: "N images have no alt text" (`media.image.manage`), and a Set up step for the public bucket.
- **Body limits:** its two upload routes take 16 MB (`BODY_LIMITS`, decision 0054).

## Settings and env vars

None of its own. Uploads need the kernel's public bucket: `STORAGE_PUBLIC_BUCKET` and `STORAGE_PUBLIC_URL`, with the storage variables. Until they're set, uploads and image addresses answer 503 `media.storage_off`.

## Install notes

`mechframe add media`, then the migrations. The page's images load from the public bucket's address, which the CSP's `img-src` already allows (`https:`). Pillow and python-multipart are in the kernel's pinned requirements.

## Extension points

- **Backend:** `media.public` gives `picture(db, id)` and `pictures(db, ids)` to draw an image, and `use(db, image_id, owner=, label=, link=)` and `release(db, owner=, keep=)` to record where one is placed. `owner` is `<module>.<type>:<id>`, in the caller's transaction. `store(db, data, *, filename=, alt=, by=)` takes another module's own image, such as blog's generated cover, through an upload's checks, with its alt text, and `storage_on()` says whether it can now (0.1.4).
- **Web:** `public.ts` gives `<ImagePicker title onPick onClose />`, which asks for alt text before placing an image that has none, and `<Picture image sizes />`.

## Known limits

- Images only: no audio, video or documents.
- No crops, focal points or sizes made on request.
- No folders or tags in the library.
- A replace's old files are deleted after its commit. One whose delete fails stays in the bucket, unreachable.

## Source and license

Lifted from VybeSite at `43b64c6`: `backend/app/services/media_service.py`, its tests, `backend/app/models/media_image.py` and `frontend/src/components/ImagePicker.tsx`. The owner's code, proprietary. Its files are kept in the kernel's public bucket here, not in the database as VybeSite keeps them.
