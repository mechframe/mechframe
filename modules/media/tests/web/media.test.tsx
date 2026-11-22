/**
 * The media library's web (`dev plans/contracts/media.md`): the admin page,
 * the picker another module places an image with, and the picture that draws
 * one. Every answer comes from a fetch that answers by method and path.
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithKernel, testUser } from "@/kernel/testing";

import type { Image } from "../../web/api";
import { ImagePicker } from "../../web/components/ImagePicker";
import { Picture } from "../../web/components/Picture";
import AdminMedia from "../../web/pages/AdminMedia";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

function routed(answers: Answers) {
  const sent: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      sent.push(request.clone());
      const found = answers[`${request.method} ${new URL(request.url).pathname}`];
      if (!found) throw new TypeError("Failed to fetch");
      const answer = typeof found === "function" ? await found(request) : found;
      const type = answer.status >= 400 ? "application/problem+json" : "application/json";
      return new Response(answer.body === undefined ? null : JSON.stringify(answer.body), {
        status: answer.status,
        headers: { "content-type": type },
      });
    }),
  );
  return sent;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function image(overrides: Partial<Image> = {}): Image {
  const id = overrides.id ?? "11111111-1111-4111-8111-111111111111";
  return {
    id,
    url: `https://files.test/media/${id}/1.png`,
    srcset: `https://files.test/media/${id}/1-480.png 480w, https://files.test/media/${id}/1.png 1000w`,
    width: 1000,
    height: 600,
    bytes: 48_000,
    content_type: "image/png",
    filename: "door.png",
    alt: null,
    decorative: false,
    uploaded_by: "Pat",
    created_at: "2026-11-21T12:00:00+00:00",
    version: 1,
    ...overrides,
  };
}

const staff = testUser({ roles: ["member", "editor"], second_factor: true, permissions: ["media.image.upload", "media.image.manage"] });
const LIST = "GET /api/media/admin/images";
const DOOR = image();
const DESCRIBED = image({ id: "22222222-2222-4222-8222-222222222222", filename: "studio.png", alt: "A mixing desk" });

function problem(status: number, code: string, extra: Record<string, unknown> = {}): Answer {
  return { status, body: { type: `urn:mechframe:problem:${code}`, title: "Refused", status, detail: "Refused.", code, ...extra } };
}

describe("the admin page", () => {
  it("lists the library and calls out the images with no alt text", async () => {
    routed({ [LIST]: { status: 200, body: { items: [DOOR, DESCRIBED], next_cursor: null, missing_alt: 1 } } });
    renderWithKernel(<AdminMedia />, { path: "/admin/media", session: staff });

    expect(await screen.findByRole("heading", { level: 1, name: "Media" })).toBeInTheDocument();
    expect(await screen.findByText("1 image has no alt text")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Fix the first" })).toHaveAttribute("href", "/admin/media?missing_alt=1");
    expect(screen.getByRole("button", { name: "door.png, 1000 × 600, no alt text" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "A mixing desk, 1000 × 600" })).toBeInTheDocument();
  });

  it("opens an image beside the list, with what it is and where it's used, and holds Delete while it's used", async () => {
    const used = { ...DOOR, uses: [{ label: "Hello, a post", link: "/admin/blog/1" }] };
    routed({
      [LIST]: { status: 200, body: { items: [DOOR], next_cursor: null, missing_alt: 1 } },
      [`GET /api/media/admin/images/${DOOR.id}`]: { status: 200, body: used },
    });
    renderWithKernel(<AdminMedia />, { path: "/admin/media", session: staff });

    await userEvent.click(await screen.findByRole("button", { name: /door\.png, 1000 × 600/ }));

    expect(await screen.findByRole("link", { name: "Hello, a post" })).toHaveAttribute("href", "/admin/blog/1");
    expect(screen.getByText("1000 × 600, 47 KB")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
    expect(screen.getByText("A file that's in use can't be deleted until it's removed from those pages.")).toBeInTheDocument();
  });

  it("opens the first without alt text from Fix the first", async () => {
    routed({
      [LIST]: { status: 200, body: { items: [DOOR], next_cursor: null, missing_alt: 1 } },
      [`GET /api/media/admin/images/${DOOR.id}`]: { status: 200, body: { ...DOOR, uses: [] } },
    });
    renderWithKernel(<AdminMedia />, { path: "/admin/media?missing_alt=1", session: staff });

    expect(await screen.findByText("Nowhere yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "No alt text" })).toHaveAttribute("aria-pressed", "true");
  });

  it("saves alt text with the version it read, and says so when someone got there first", async () => {
    let tries = 0;
    const sent = routed({
      [LIST]: { status: 200, body: { items: [DOOR], next_cursor: null, missing_alt: 1 } },
      [`GET /api/media/admin/images/${DOOR.id}`]: { status: 200, body: { ...DOOR, uses: [] } },
      [`PATCH /api/media/admin/images/${DOOR.id}`]: () => {
        tries += 1;
        return tries === 1
          ? problem(409, "media.changed", { version: 2, alt: "Theirs", decorative: false })
          : { status: 200, body: { ...DOOR, alt: "A red door", version: 3, uses: [] } };
      },
    });
    renderWithKernel(<AdminMedia />, { path: "/admin/media", session: staff });
    await userEvent.click(await screen.findByRole("button", { name: /door\.png/ }));
    const alt = await screen.findByRole("textbox", { name: /Alt text/ });

    await userEvent.type(alt, "A red door");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText(/Someone changed this image since you opened it/)).toBeInTheDocument();
    const patch = sent.find((request) => request.method === "PATCH");
    expect(await patch?.json()).toEqual({ version: 1, alt: "A red door", decorative: false });

    await userEvent.type(screen.getByRole("textbox", { name: /Alt text/ }), "A red door");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("uploads a file as a form and opens what came back", async () => {
    const made = image({ id: "33333333-3333-4333-8333-333333333333", filename: "new.png" });
    const sent = routed({
      [LIST]: { status: 200, body: { items: [], next_cursor: null, missing_alt: 0 } },
      "POST /api/media/admin/images": { status: 201, body: made },
      [`GET /api/media/admin/images/${made.id}`]: { status: 200, body: { ...made, uses: [] } },
    });
    renderWithKernel(<AdminMedia />, { path: "/admin/media", session: staff });
    expect(await screen.findByText("No images yet")).toBeInTheDocument();

    await userEvent.upload(screen.getByLabelText("Upload an image"), new File([new Uint8Array(64)], "new.png", { type: "image/png" }));

    expect(await screen.findByText("new.png is in the library.")).toBeInTheDocument();
    const post = sent.find((request) => request.method === "POST");
    expect(post?.headers.get("content-type")).toMatch(/^multipart\/form-data/);
    expect(await screen.findByText("Nowhere yet")).toBeInTheDocument();
  });

  it("refuses a file over 15 MB before sending it", async () => {
    const sent = routed({ [LIST]: { status: 200, body: { items: [], next_cursor: null, missing_alt: 0 } } });
    renderWithKernel(<AdminMedia />, { path: "/admin/media", session: staff });
    await screen.findByText("No images yet");
    const big = new File([new Uint8Array(15 * 1024 * 1024 + 1)], "big.png", { type: "image/png" });

    await userEvent.upload(screen.getByLabelText("Upload an image"), big);

    expect(await screen.findByText(/That file is over 15 MB/)).toBeInTheDocument();
    expect(sent.some((request) => request.method === "POST")).toBe(false);
  });
});

describe("the library's pages", () => {
  const OLDER = image({ id: "44444444-4444-4444-8444-444444444444", filename: "older.png", alt: "An older one" });

  function paged(): Answers {
    return {
      [LIST]: (request) =>
        new URL(request.url).searchParams.get("cursor") === "page-2"
          ? { status: 200, body: { items: [OLDER], next_cursor: null, missing_alt: 1 } }
          : { status: 200, body: { items: [DOOR], next_cursor: "page-2", missing_alt: 1 } },
    };
  }

  it("shows the older images on the admin page once asked (Codex on #116)", async () => {
    routed(paged());
    renderWithKernel(<AdminMedia />, { path: "/admin/media", session: staff });
    await screen.findByRole("button", { name: /door\.png/ });
    expect(screen.queryByRole("button", { name: /An older one/ })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Show more" }));

    expect(await screen.findByRole("button", { name: /An older one/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /door\.png/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
  });

  it("lets the picker reach the older images and find one by its words", async () => {
    const sent = routed(paged());
    renderWithKernel(<ImagePicker title="Choose" onPick={vi.fn()} onClose={vi.fn()} />, { session: staff });
    await screen.findByRole("button", { name: /door\.png/ });

    await userEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(await screen.findByRole("button", { name: /An older one/ })).toBeInTheDocument();

    await userEvent.type(screen.getByRole("searchbox", { name: "Search the library" }), "older");
    await waitFor(() => {
      expect(sent.some((request) => new URL(request.url).searchParams.get("q") === "older")).toBe(true);
    });
  });
});

describe("the picker", () => {
  it("hands back an image that has alt text at once", async () => {
    routed({ [LIST]: { status: 200, body: { items: [DESCRIBED], next_cursor: null, missing_alt: 0 } } });
    const onPick = vi.fn();
    const onClose = vi.fn();
    renderWithKernel(<ImagePicker title="Choose a cover image" onPick={onPick} onClose={onClose} />, { session: staff });

    const dialog = await screen.findByRole("dialog", { name: "Choose a cover image" });
    await userEvent.click(await within(dialog).findByRole("button", { name: "A mixing desk, 1000 × 600" }));

    expect(onPick).toHaveBeenCalledWith(DESCRIBED);
    expect(onClose).toHaveBeenCalled();
  });

  it("asks for alt text before it places an image that has none", async () => {
    const sent = routed({
      [LIST]: { status: 200, body: { items: [DOOR], next_cursor: null, missing_alt: 1 } },
      [`PATCH /api/media/admin/images/${DOOR.id}`]: { status: 200, body: { ...DOOR, alt: "A red door", version: 2 } },
    });
    const onPick = vi.fn();
    renderWithKernel(<ImagePicker title="Choose a cover image" onPick={onPick} onClose={vi.fn()} />, { session: staff });

    await userEvent.click(await screen.findByRole("button", { name: "door.png, 1000 × 600" }));
    await userEvent.click(screen.getByRole("button", { name: "Place it" }));
    expect(await screen.findByText("Say what's in the picture, or mark it as only decoration.")).toBeInTheDocument();
    expect(onPick).not.toHaveBeenCalled();

    await userEvent.type(screen.getByRole("textbox", { name: /Alt text/ }), "A red door");
    await userEvent.click(screen.getByRole("button", { name: "Place it" }));

    await waitFor(() => {
      expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ alt: "A red door", version: 2 }));
    });
    expect(await sent.find((request) => request.method === "PATCH")?.json()).toEqual({ version: 1, alt: "A red door", decorative: false });
  });
});

describe("unsaved alt text (CodeRabbit on #116)", () => {
  it("asks before the picker's Back drops what's typed", async () => {
    routed({ [LIST]: { status: 200, body: { items: [DOOR], next_cursor: null, missing_alt: 1 } } });
    renderWithKernel(<ImagePicker title="Choose" onPick={vi.fn()} onClose={vi.fn()} />, { session: staff });
    await userEvent.click(await screen.findByRole("button", { name: "door.png, 1000 × 600" }));
    await userEvent.type(screen.getByRole("textbox", { name: /Alt text/ }), "A red");

    await userEvent.click(screen.getByRole("button", { name: "Back to the library" }));
    expect(screen.getByText("Your alt text isn't saved. Leave it?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Keep writing" }));
    expect(screen.getByRole("textbox", { name: /Alt text/ })).toHaveValue("A red");

    await userEvent.click(screen.getByRole("button", { name: "Back to the library" }));
    await userEvent.click(screen.getByRole("button", { name: "Leave it" }));
    expect(await screen.findByRole("button", { name: "door.png, 1000 × 600" })).toBeInTheDocument();
  });

  it("takes another's change on a conflict, and saves with its version", async () => {
    let tries = 0;
    const sent = routed({
      [LIST]: { status: 200, body: { items: [DOOR], next_cursor: null, missing_alt: 1 } },
      [`PATCH /api/media/admin/images/${DOOR.id}`]: () => {
        tries += 1;
        return tries === 1
          ? problem(409, "media.changed", { version: 2, alt: "Theirs", decorative: false })
          : { status: 200, body: { ...DOOR, alt: "Theirs", version: 3 } };
      },
    });
    const onPick = vi.fn();
    renderWithKernel(<ImagePicker title="Choose" onPick={onPick} onClose={vi.fn()} />, { session: staff });
    await userEvent.click(await screen.findByRole("button", { name: "door.png, 1000 × 600" }));
    await userEvent.type(screen.getByRole("textbox", { name: /Alt text/ }), "Mine");
    await userEvent.click(screen.getByRole("button", { name: "Place it" }));

    expect(await screen.findByText(/Here is how it reads now/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /Alt text/ })).toHaveValue("Theirs");
    await userEvent.click(screen.getByRole("button", { name: "Place it" }));

    await waitFor(() => {
      expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ version: 3 }));
    });
    const patches = sent.filter((request) => request.method === "PATCH");
    expect(await patches[1]?.json()).toEqual({ version: 2, alt: "Theirs", decorative: false });
  });

  it("asks before the admin page opens another image over what's typed", async () => {
    routed({
      [LIST]: { status: 200, body: { items: [DOOR, DESCRIBED], next_cursor: null, missing_alt: 1 } },
      [`GET /api/media/admin/images/${DOOR.id}`]: { status: 200, body: { ...DOOR, uses: [] } },
      [`GET /api/media/admin/images/${DESCRIBED.id}`]: { status: 200, body: { ...DESCRIBED, uses: [] } },
    });
    renderWithKernel(<AdminMedia />, { path: "/admin/media", session: staff });
    await userEvent.click(await screen.findByRole("button", { name: /door\.png/ }));
    await userEvent.type(await screen.findByRole("textbox", { name: /Alt text/ }), "A red door");

    await userEvent.click(screen.getByRole("button", { name: /A mixing desk/ }));
    const asking = await screen.findByRole("dialog", { name: "Your alt text isn't saved" });
    await userEvent.click(within(asking).getByRole("button", { name: "Keep editing" }));
    expect(screen.getByRole("textbox", { name: /Alt text/ })).toHaveValue("A red door");

    await userEvent.click(screen.getByRole("button", { name: /A mixing desk/ }));
    await userEvent.click(within(await screen.findByRole("dialog", { name: "Your alt text isn't saved" })).getByRole("button", { name: "Leave it" }));
    expect(await screen.findByRole("textbox", { name: /Alt text/ })).toHaveValue("A mixing desk");
  });

  it("saves a draft with the version it was typed against, though a refresh brought a newer one", async () => {
    let reads = 0;
    const sent = routed({
      [LIST]: { status: 200, body: { items: [DOOR], next_cursor: null, missing_alt: 1 } },
      [`GET /api/media/admin/images/${DOOR.id}`]: () => {
        reads += 1;
        return { status: 200, body: { ...DOOR, version: reads === 1 ? 1 : 2, alt: reads === 1 ? null : "Theirs", uses: [] } };
      },
      [`PATCH /api/media/admin/images/${DOOR.id}`]: problem(409, "media.changed", { version: 2, alt: "Theirs", decorative: false }),
    });
    const { queryClient } = renderWithKernel(<AdminMedia />, { path: "/admin/media", session: staff });
    await userEvent.click(await screen.findByRole("button", { name: /door\.png/ }));
    await userEvent.type(await screen.findByRole("textbox", { name: /Alt text/ }), "Mine");

    await queryClient.invalidateQueries({ queryKey: ["get", "/api/media/admin/images/{image_id}"] });
    await waitFor(() => {
      expect(reads).toBe(2);
    });
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText(/Someone changed this image since you opened it/)).toBeInTheDocument();
    expect(await sent.find((request) => request.method === "PATCH")?.json()).toEqual({ version: 1, alt: "Mine", decorative: false });
  });

  it("holds the form while a save or a replace is under way, so nothing typed meanwhile is lost", async () => {
    let answer: (value: Answer) => void = () => undefined;
    const waiting = () =>
      new Promise<Answer>((resolve) => {
        answer = resolve;
      });
    routed({
      [LIST]: { status: 200, body: { items: [DOOR], next_cursor: null, missing_alt: 1 } },
      [`GET /api/media/admin/images/${DOOR.id}`]: { status: 200, body: { ...DOOR, uses: [] } },
      [`PATCH /api/media/admin/images/${DOOR.id}`]: waiting,
      [`PUT /api/media/admin/images/${DOOR.id}/file`]: waiting,
    });
    renderWithKernel(<AdminMedia />, { path: "/admin/media", session: staff });
    await userEvent.click(await screen.findByRole("button", { name: /door\.png/ }));
    const alt = await screen.findByRole("textbox", { name: /Alt text/ });
    await userEvent.type(alt, "A red door");

    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("button", { name: "Saving…" })).toBeDisabled();
    expect(alt).toBeDisabled();
    expect(screen.getByRole("button", { name: "Replace" })).toBeDisabled();
    answer({ status: 200, body: { ...DOOR, alt: "A red door", version: 2, uses: [] } });
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /Alt text/ })).toBeEnabled();

    await userEvent.upload(screen.getByLabelText("Replace the file"), new File([new Uint8Array(64)], "new.png", { type: "image/png" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Replace" })).toBeDisabled();
    });
    expect(screen.getByRole("textbox", { name: /Alt text/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
    answer({ status: 200, body: { ...DOOR, alt: "A red door", version: 3, uses: [] } });
    expect(await screen.findByText(/Replaced: every page that places it/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Replace" })).toBeEnabled();
  });

  it("keeps the file inputs out of the tab order, named for what they do", async () => {
    routed({ [LIST]: { status: 200, body: { items: [], next_cursor: null, missing_alt: 0 } } });
    renderWithKernel(<ImagePicker title="Choose" onPick={vi.fn()} onClose={vi.fn()} />, { session: staff });
    expect(await screen.findByLabelText("Upload an image")).toHaveAttribute("tabindex", "-1");
  });
});

describe("Picture", () => {
  it("draws the image with its copies, its size and its alt text, and says nothing of decoration", () => {
    const { rerender } = render(<Picture image={DESCRIBED} sizes="50vw" />);
    const drawn = screen.getByRole("img", { name: "A mixing desk" });
    expect(drawn).toHaveAttribute("srcset", DESCRIBED.srcset);
    expect(drawn).toHaveAttribute("sizes", "50vw");
    expect(drawn).toHaveAttribute("width", "1000");
    expect(drawn).toHaveAttribute("loading", "lazy");

    rerender(<Picture image={{ ...DESCRIBED, decorative: true }} />);
    expect(screen.getByRole("presentation")).toHaveAttribute("alt", "");
  });
});
