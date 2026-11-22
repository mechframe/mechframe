/**
 * A search box (VM Website's admin boards: AdminMedia's "Search files" and
 * every admin search after it): one 38px box with the magnifier inside and
 * the label as its placeholder, which is also its name for a screen reader.
 * The box is the field, so its edge is a field's and the admin's ring goes
 * round it (kit.css).
 */
import type { ComponentPropsWithRef } from "react";

import { Icon } from "./Icon";

export type SearchBoxProps = Omit<ComponentPropsWithRef<"input">, "type" | "placeholder" | "aria-label"> & {
  /** What it searches, as the box says it: "Search files". */
  label: string;
};

export function SearchBox({ label, className, ...rest }: SearchBoxProps) {
  return (
    <div className={className ? `mf-search ${className}` : "mf-search"}>
      <Icon name="search" size={18} />
      <input {...rest} type="search" className="mf-search-input" aria-label={label} placeholder={label} />
    </div>
  );
}
