// Paste links (`dev plans/contracts/featured.md` §8, 7): one or several YouTube
// links at once, read by the server (embeds' reading of a link) and titled from
// YouTube while the setting is on; each title can be typed or changed, and given a
// kind. A link that isn't a YouTube video is said so, and left out.
import { useState } from "react";

import { ApiProblem, Button, Dialog, Field, Input, Select, TextArea, failureWords } from "@/kernel";

import { MAX_PASTE, MAX_TITLE, api, type Kind } from "../api";

export type PastedVideo = { url: string; video_id: string; title: string; kind: string | null };

export type PasteLinksProps = {
  kinds: readonly Kind[];
  /** How many more the list can hold. */
  room: number;
  onAdd: (videos: PastedVideo[]) => void;
  onClose: () => void;
};

export function PasteLinks({ kinds, room, onAdd, onClose }: PasteLinksProps) {
  const [text, setText] = useState("");
  const [videos, setVideos] = useState<PastedVideo[] | null>(null);
  const [refused, setRefused] = useState<string[]>([]);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const urls = text
    .split(/\s+/)
    .map((each) => each.trim())
    .filter(Boolean);

  async function read() {
    setBusy(true);
    setProblem("");
    try {
      const { data } = await api.POST("/api/featured/admin/youtube", { body: { urls: urls.slice(0, MAX_PASTE) } });
      if (!data) throw new Error("The site answered without the links.");
      setVideos(data.items.map((each) => ({ url: each.url, video_id: each.video_id, title: each.title ?? "", kind: null })));
      setRefused(data.refused.map((each) => each.url));
    } catch (error) {
      setProblem(error instanceof ApiProblem ? error.detail : error instanceof Error ? failureWords(error) : "The links couldn't be read. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const untitled = videos?.some((each) => !each.title.trim()) ?? false;
  const over = videos ? videos.length > room : false;
  const set = (at: number, change: Partial<PastedVideo>) => {
    setVideos((now) => (now ? now.map((each, index) => (index === at ? { ...each, ...change } : each)) : now));
  };

  return (
    <Dialog title="Paste links" onClose={onClose} wide>
      {videos === null ? (
        <form
          className="mf-featured-stack"
          onSubmit={(event) => {
            event.preventDefault();
            if (urls.length) void read();
          }}
        >
          <Field label="YouTube links" hint={`One a line, or with spaces between: up to ${String(MAX_PASTE)} at once.`}>
            <TextArea
              rows={6}
              value={text}
              onChange={(event) => {
                setText(event.target.value);
              }}
            />
          </Field>
          {urls.length > MAX_PASTE ? <p className="mf-featured-hint">The first {String(MAX_PASTE)} are read; paste the rest after.</p> : null}
          {problem ? <p className="mf-featured-error">{problem}</p> : null}
          <div className="mf-dialog-actions">
            <Button type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={busy || urls.length === 0}>
              {busy ? "Reading the links…" : "Read the links"}
            </Button>
          </div>
        </form>
      ) : (
        <form
          className="mf-featured-stack"
          onSubmit={(event) => {
            event.preventDefault();
            if (!untitled && !over && videos.length) onAdd(videos.map((each) => ({ ...each, title: each.title.trim() })));
          }}
        >
          {refused.length ? (
            <div className="mf-featured-refused" role="status">
              <p className="mf-featured-error">{refused.length === 1 ? "This isn't a YouTube video's link, so it's left out:" : "These aren't YouTube videos' links, so they're left out:"}</p>
              <ul>
                {refused.map((url, at) => (
                  <li key={`${url}-${String(at)}`}>{url}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {videos.length === 0 ? <p className="mf-featured-hint">No YouTube videos were found in what was pasted.</p> : null}
          <ol className="mf-featured-pasted">
            {videos.map((video, at) => (
              <li key={`${video.video_id}-${String(at)}`} className="mf-featured-fields">
                <Field label={`Title of youtu.be/${video.video_id}`} error={video.title.trim() ? undefined : "Type a title: YouTube didn't give one."}>
                  <Input
                    value={video.title}
                    maxLength={MAX_TITLE}
                    required
                    onChange={(event) => {
                      set(at, { title: event.target.value });
                    }}
                  />
                </Field>
                {kinds.length ? (
                  <Field label="Kind">
                    <Select
                      value={video.kind ?? ""}
                      onChange={(event) => {
                        set(at, { kind: event.target.value || null });
                      }}
                    >
                      <option value="">No kind</option>
                      {kinds.map((each) => (
                        <option key={each.key} value={each.key}>
                          {each.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                ) : null}
              </li>
            ))}
          </ol>
          {over ? <p className="mf-featured-error">The player has room for {String(room)} more. Take some out of the list first.</p> : null}
          <div className="mf-dialog-actions">
            <Button
              type="button"
              onClick={() => {
                setVideos(null);
              }}
            >
              Back
            </Button>
            <Button type="submit" variant="primary" disabled={untitled || over || videos.length === 0}>
              {videos.length === 1 ? "Add 1 video" : `Add ${String(videos.length)} videos`}
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
