import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithKernel } from "@/kernel/testing";
import { CONSENT_COOKIE, ConsentGate, useConsent, type ConsentCategory } from "./consent";

/** Every cookie this page can read, by name. */
function cookies(): Record<string, string> {
  return Object.fromEntries(
    document.cookie
      .split(";")
      .map((pair) => pair.trim())
      .filter(Boolean)
      .map((pair) => {
        const at = pair.indexOf("=");
        return [pair.slice(0, at), pair.slice(at + 1)];
      }),
  );
}

function forget(): void {
  document.cookie = `${CONSENT_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax; Secure`;
}

/** An embed as a module draws one: its facade until `media` is granted, then the player. */
function Embed({ category = "media" }: { category?: ConsentCategory }) {
  return (
    <ConsentGate
      category={category}
      fallback={(grant) => (
        <button type="button" onClick={grant}>
          Play the video
        </button>
      )}
    >
      <iframe title="The player" src="https://www.youtube-nocookie.com/embed/x" />
    </ConsentGate>
  );
}

function Choice({ category }: { category: ConsentCategory }) {
  const { granted, grant, withdraw } = useConsent(category);
  return (
    <p>
      {category}: {granted ? "granted" : "held"}
      <button type="button" onClick={grant}>
        Allow {category}
      </button>
      <button type="button" onClick={withdraw}>
        Withdraw {category}
      </button>
    </p>
  );
}

const ASK = { consent: { mode: "ask" as const, categories: ["media" as const] } };

afterEach(() => {
  forget();
  vi.useRealTimers();
});

describe("ConsentGate and useConsent (hook 6, consent categories)", () => {
  it("hold the player until grant(), then draw it and keep the choice in __Host-mf_consent", () => {
    renderWithKernel(<Embed />, { site: ASK });
    expect(screen.queryByTitle("The player")).toBeNull();
    expect(cookies()[CONSENT_COOKIE]).toBeUndefined();

    fireEvent.click(screen.getByRole("button", { name: "Play the video" }));
    expect(screen.getByTitle("The player")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Play the video" })).toBeNull();
    expect(cookies()[CONSENT_COOKIE]).toBe("media");
  });

  it("write the cookie as a __Host- cookie must be: Secure, Path=/, no Domain, for 180 days", () => {
    const written: string[] = [];
    const real = Object.getOwnPropertyDescriptor(Document.prototype, "cookie");
    const set = real?.set?.bind(document);
    const get = real?.get?.bind(document);
    if (!set || !get) throw new Error("No cookie property.");
    vi.spyOn(document, "cookie", "set").mockImplementation((value: string) => {
      written.push(value);
      set(value);
    });
    vi.spyOn(document, "cookie", "get").mockImplementation(() => get() as string);
    renderWithKernel(<Choice category="media" />, { site: ASK });
    fireEvent.click(screen.getByRole("button", { name: "Allow media" }));
    expect(written).toEqual([`${CONSENT_COOKIE}=media; Path=/; Max-Age=15552000; SameSite=Lax; Secure`]);
    expect(written[0]).not.toMatch(/Domain=/i);
  });

  it("open every gate of a category at once, and only that category's", () => {
    renderWithKernel(
      <>
        <Embed />
        <Choice category="media" />
        <Choice category="analytics" />
      </>,
      { site: ASK },
    );
    expect(screen.getByText("media: held")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Allow media" }));
    expect(screen.getByTitle("The player")).toBeInTheDocument();
    expect(screen.getByText("media: granted")).toBeInTheDocument();
    expect(screen.getByText("analytics: held")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Allow analytics" }));
    expect(cookies()[CONSENT_COOKIE]).toBe("analytics.media");
  });

  it("hold again once withdrawn, and forget the cookie when nothing is left", () => {
    renderWithKernel(<Choice category="media" />, { site: ASK });
    fireEvent.click(screen.getByRole("button", { name: "Allow media" }));
    expect(screen.getByText("media: granted")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Withdraw media" }));
    expect(screen.getByText("media: held")).toBeInTheDocument();
    expect(cookies()[CONSENT_COOKIE]).toBeUndefined();
  });

  it("read a choice made on an earlier visit, ignoring what it doesn't know", () => {
    document.cookie = `${CONSENT_COOKIE}=media.cookies.necessary.analytics; Path=/; Max-Age=60; SameSite=Lax; Secure`;
    renderWithKernel(
      <>
        <Embed />
        <Choice category="analytics" />
        <Choice category="marketing" />
      </>,
      { site: ASK },
    );
    expect(screen.getByTitle("The player")).toBeInTheDocument();
    expect(screen.getByText("analytics: granted")).toBeInTheDocument();
    expect(screen.getByText("marketing: held")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Allow marketing" }));
    expect(cookies()[CONSENT_COOKIE]).toBe("analytics.marketing.media");
  });

  it("grant everything while CONSENT_MODE is off", () => {
    renderWithKernel(
      <>
        <Embed />
        <Choice category="marketing" />
      </>,
      { site: { consent: { mode: "off", categories: ["media"] } } },
    );
    expect(screen.getByTitle("The player")).toBeInTheDocument();
    expect(screen.getByText("marketing: granted")).toBeInTheDocument();
  });

  it("hold while the site isn't read yet, but never what's necessary", () => {
    renderWithKernel(
      <>
        <Embed />
        <Choice category="necessary" />
      </>,
      { site: "loading" },
    );
    expect(screen.queryByTitle("The player")).toBeNull();
    expect(screen.getByRole("button", { name: "Play the video" })).toBeInTheDocument();
    expect(screen.getByText("necessary: granted")).toBeInTheDocument();
  });

  it("draw nothing in the gate's place when it has no fallback", () => {
    const { container } = renderWithKernel(
      <ConsentGate category="analytics">
        <p>The counter</p>
      </ConsentGate>,
      { site: ASK },
    );
    expect(screen.queryByText("The counter")).toBeNull();
    expect(container).toBeEmptyDOMElement();
  });

  it("take a choice made in another tab once this one has the focus again", () => {
    renderWithKernel(<Embed />, { site: ASK });
    act(() => {
      document.cookie = `${CONSENT_COOKIE}=media; Path=/; Max-Age=60; SameSite=Lax; Secure`;
      window.dispatchEvent(new Event("focus"));
    });
    expect(screen.getByTitle("The player")).toBeInTheDocument();
  });
});
