/**
 * The kernel's own buttons for every MarkdownEditor (`editor.tools`, decision
 * 0060), drawn before the modules': the AI's writing help (decision 0058),
 * for those holding `kernel.ai.write`.
 */
import type { EditorToolEntry } from "../slots/types";

export const KERNEL_EDITOR_TOOLS: readonly EditorToolEntry[] = [
  { id: "kernel.ai", permission: "kernel.ai.write", lazy: () => import("../ai/WritingHelp") },
];
