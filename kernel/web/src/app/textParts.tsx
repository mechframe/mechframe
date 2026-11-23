/**
 * The kit's text parts from the slots (decision 0060): `editor.tools`, the
 * kernel's buttons first, then the modules' on in their order, each only for
 * those who hold its permission; and `prose.embed`, the modules' players. The
 * kit reads them from `TextPartsContext`, so it never reads a slot itself.
 * With no entry anywhere it asks nothing: no module switches, no session. The
 * kernel's own Write with AI (decision 0058) is always an entry, so a mounted
 * app reads both here, as its frame already does.
 */
import { useMemo, type ReactNode } from "react";

import { useSession } from "../session/session";
import { useSlot } from "../slots/slots";
import { TEXT_SLOTS, type EditorToolEntry } from "../slots/types";
import { TextPartsContext, type TextParts } from "../ui/textParts";
import { useKernelSetup } from "./context";
import { KERNEL_EDITOR_TOOLS } from "./editorTools";
import { lazyPart } from "./lazy";

export type { EditorToolEntry };

type Given = {
  /** The kernel's own buttons; `KERNEL_EDITOR_TOOLS` unless a test gives others. */
  kernelTools?: readonly EditorToolEntry[];
  children: ReactNode;
};

function Filled({ kernelTools, children }: Required<Given>) {
  const session = useSession();
  const tools = useSlot("editor.tools");
  const embeds = useSlot("prose.embed");
  const may = (permission: string | undefined) =>
    permission === undefined || (session.status === "signed-in" && session.can(permission));
  const kernel = kernelTools.filter((entry) => may(entry.permission));

  // Made again only when what's shown changes, so the editor's parts and Prose's players keep their state.
  const shown = [
    ...kernel.map((entry) => `kernel:${entry.id}`),
    ...tools.map((entry) => entry.key),
    "|",
    ...embeds.map((entry) => entry.key),
  ].join(" ");
  const value = useMemo<TextParts>(
    () => ({
      tools: [
        ...kernel.map((entry) => ({ key: `kernel:editor.tools:${entry.id}`, Part: lazyPart(entry.lazy) })),
        ...tools.map((entry) => ({ key: entry.key, Part: lazyPart(entry.lazy) })),
      ],
      embeds: embeds.map((entry) => ({ key: entry.key, claims: entry.claims, Part: lazyPart(entry.lazy) })),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `shown` names every entry these are made from.
    [shown],
  );
  return <TextPartsContext.Provider value={value}>{children}</TextPartsContext.Provider>;
}

export function TextPartsFromSlots({ kernelTools = KERNEL_EDITOR_TOOLS, children }: Given) {
  const { modules } = useKernelSetup();
  // The setup never changes while the app runs, so neither does which of these draws.
  const filled =
    kernelTools.length > 0 ||
    modules.some((definition) => TEXT_SLOTS.some((name) => (definition.slots?.[name]?.length ?? 0) > 0));
  return filled ? <Filled kernelTools={kernelTools}>{children}</Filled> : <>{children}</>;
}
