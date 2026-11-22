// The library's writes, shared by its admin page and the picker: an upload, a
// replace, a change to what an image means, and a delete. Every refusal comes
// back as the kernel's ApiProblem, its `detail` a sentence for the person.
import { api, fileBody, type Image } from "../api";

/** The kinds the server takes, as it judges them by their bytes. */
export const ACCEPT = "image/png,image/jpeg,image/webp";
/** The server's limit, refused here before a phone's photo takes minutes to go up. */
export const MAX_BYTES = 15 * 1024 * 1024;

/** Why a file isn't sent at all, or null. */
export function tooLarge(file: File): string | null {
  return file.size > MAX_BYTES ? "That file is over 15 MB. Make the image smaller and upload it again." : null;
}

export async function uploadImage(file: File): Promise<Image> {
  const { data } = await api.POST("/api/media/admin/images", {
    body: { file: file as unknown as string },
    bodySerializer: () => fileBody(file),
  });
  if (!data) throw new Error("The library answered without the image.");
  return data;
}

export async function replaceImage(image: Image, file: File): Promise<Image> {
  const { data } = await api.PUT("/api/media/admin/images/{image_id}/file", {
    params: { path: { image_id: image.id } },
    body: { file: file as unknown as string },
    bodySerializer: () => fileBody(file),
  });
  if (!data) throw new Error("The library answered without the image.");
  return data;
}

export async function describeImage(image: Image, change: { alt: string; decorative: boolean }): Promise<Image> {
  const { data } = await api.PATCH("/api/media/admin/images/{image_id}", {
    params: { path: { image_id: image.id } },
    body: { version: image.version, alt: change.decorative ? null : change.alt, decorative: change.decorative },
  });
  if (!data) throw new Error("The library answered without the image.");
  return data;
}

export async function deleteImage(image: Image): Promise<void> {
  await api.DELETE("/api/media/admin/images/{image_id}", { params: { path: { image_id: image.id } } });
}
