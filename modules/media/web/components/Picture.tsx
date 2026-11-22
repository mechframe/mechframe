// An image from the library as a page draws it: its smaller copies in
// `srcset`, its size so nothing shifts as it loads, and its alt text ("" for
// one that's only decoration, so screen readers skip it).
import type { ImgHTMLAttributes } from "react";

export type PictureImage = {
  url: string;
  srcset: string;
  width: number;
  height: number;
  alt?: string | null;
  decorative?: boolean;
};

export type PictureProps = Omit<ImgHTMLAttributes<HTMLImageElement>, "src" | "srcSet" | "alt" | "width" | "height"> & {
  image: PictureImage;
  /** The `sizes` the page lays it out at, such as "(min-width: 60rem) 50vw, 100vw". */
  sizes?: string;
};

export function Picture({ image, sizes = "100vw", loading = "lazy", ...rest }: PictureProps) {
  return (
    <img
      {...rest}
      src={image.url}
      srcSet={image.srcset}
      sizes={sizes}
      width={image.width}
      height={image.height}
      alt={image.decorative ? "" : (image.alt ?? "")}
      loading={loading}
      decoding="async"
    />
  );
}
