/**
 * Search and sharing (decision 0055; VM Website `AdminPost.dc.html`, which
 * `AdminPages.dc.html` shares): the title a search result and a shared link
 * show, and the description under it. Each may be left empty, and then shows,
 * greyed in the field, the words the page will use instead: the module's
 * `fallbackTitle` and `fallbackDescription`, which it makes as its server
 * copy does.
 */
import { Field, Input, TextArea } from "./Field";

/** The longest a title and a description may be, as search engines show them. */
export const SEARCH_TITLE_MAX = 70;
export const SEARCH_DESCRIPTION_MAX = 160;

export type SearchFieldsProps = {
  title: string;
  description: string;
  onTitle: (title: string) => void;
  onDescription: (description: string) => void;
  /** What an empty title becomes: "About | Vibrant Mindz". */
  fallbackTitle: string;
  /** What an empty description becomes: the opening words. */
  fallbackDescription: string;
  /** Under both: "Left empty, these use the title and the page's opening words." */
  hint: string;
  errors?: { title?: string | readonly string[] | undefined; description?: string | readonly string[] | undefined };
};

export function SearchFields({
  title,
  description,
  onTitle,
  onDescription,
  fallbackTitle,
  fallbackDescription,
  hint,
  errors,
}: SearchFieldsProps) {
  return (
    <div className="mf-search-fields">
      <Field label="Title in search results" error={errors?.title}>
        <Input
          value={title}
          maxLength={SEARCH_TITLE_MAX}
          placeholder={fallbackTitle}
          onChange={(event) => {
            onTitle(event.target.value);
          }}
        />
      </Field>
      <Field label="Description" error={errors?.description}>
        <TextArea
          className="mf-search-description"
          value={description}
          maxLength={SEARCH_DESCRIPTION_MAX}
          placeholder={fallbackDescription}
          rows={3}
          onChange={(event) => {
            onDescription(event.target.value);
          }}
        />
      </Field>
      <p className="mf-field-hint">{hint}</p>
    </div>
  );
}
