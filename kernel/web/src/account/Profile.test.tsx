// `/account/profile` (decision 0061): the person's name, changed or removed,
// and "Signed in as" following it.
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it } from "vitest";

import { renderApp, testUser } from "../../testing";
import { problem, routedFetch } from "../test-fetch";

beforeAll(async () => {
  await import("./Profile");
});

const me = testUser();
const NOTICES = { "GET /api/kernel/notifications": { status: 200, body: { items: [], next_cursor: null, unread: 0 } } };

async function opened(session = me) {
  renderApp({ path: "/account/profile", session });
  expect(await screen.findByRole("heading", { level: 1, name: "Profile" })).toBeInTheDocument();
  return within(await screen.findByRole("region", { name: "Name" }));
}

describe("the profile page", () => {
  it("is first in the account's pages, and says there's no name yet", async () => {
    routedFetch(NOTICES);
    const card = await opened();
    const nav = screen.getByRole("navigation", { name: "Your account" });
    const links = within(nav).getAllByRole("link");
    expect(links[0]).toHaveAccessibleName("Profile");
    expect(links[0]).toHaveAttribute("aria-current", "page");
    expect(card.getByText("No name yet")).toBeInTheDocument();
    expect(screen.getByText(`Signed in as ${me.email}`)).toBeInTheDocument();
  });

  it("saves a name, which the session takes at once", async () => {
    const { sent } = routedFetch({
      ...NOTICES,
      "PUT /api/auth/account/name": { status: 200, body: { user: { ...me, name: "Big Haas" } } },
    });
    const card = await opened();
    await userEvent.click(card.getByRole("button", { name: "Add a name" }));
    const dialog = within(await screen.findByRole("dialog", { name: "Your name" }));
    await userEvent.type(dialog.getByRole("textbox", { name: "Name" }), "  Big  Haas ");
    await userEvent.click(dialog.getByRole("button", { name: "Save" }));
    expect(await card.findByText("Big Haas")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByText("Signed in as Big Haas")).toBeInTheDocument();
    expect(await screen.findByText("Saved your name.")).toBeInTheDocument();
    const put = sent.find((request) => request.method === "PUT");
    expect(await put?.json()).toEqual({ name: "  Big  Haas " });
  });

  it("opens with the name there is, to change or empty", async () => {
    const named = testUser({ name: "Big Haas" });
    const { sent } = routedFetch({
      ...NOTICES,
      "PUT /api/auth/account/name": { status: 200, body: { user: { ...named, name: null } } },
    });
    const card = await opened(named);
    await userEvent.click(card.getByRole("button", { name: "Change name" }));
    const field = within(await screen.findByRole("dialog", { name: "Your name" })).getByRole("textbox", { name: "Name" });
    expect(field).toHaveValue("Big Haas");
    await userEvent.clear(field);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await card.findByText("No name yet")).toBeInTheDocument();
    expect(await sent.find((request) => request.method === "PUT")?.json()).toEqual({ name: "" });
  });

  it("shuts on Cancel, sending nothing", async () => {
    const { sent } = routedFetch(NOTICES);
    const card = await opened();
    await userEvent.click(card.getByRole("button", { name: "Add a name" }));
    const dialog = within(await screen.findByRole("dialog", { name: "Your name" }));
    await userEvent.type(dialog.getByRole("textbox", { name: "Name" }), "Big");
    await userEvent.click(dialog.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(card.getByText("No name yet")).toBeInTheDocument();
    expect(sent.filter((request) => request.method === "PUT")).toEqual([]);
  });

  it("says why a name was refused, and stays open", async () => {
    routedFetch({ ...NOTICES, "PUT /api/auth/account/name": problem(422, "kernel.invalid_request") });
    const card = await opened();
    await userEvent.click(card.getByRole("button", { name: "Add a name" }));
    const dialog = within(await screen.findByRole("dialog", { name: "Your name" }));
    await userEvent.type(dialog.getByRole("textbox", { name: "Name" }), "Big");
    await userEvent.click(dialog.getByRole("button", { name: "Save" }));
    expect(await dialog.findByText("A name is up to 120 characters, on one line.")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Your name" })).toBeInTheDocument();
  });
});
