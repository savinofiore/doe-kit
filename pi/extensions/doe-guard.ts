import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

type ToolInput = Record<string, unknown>;

const GUARD_PATH = resolve(__dirname, "../../core/execution/directive_guard.py");

const asRecord = (value: unknown): ToolInput =>
  typeof value === "object" && value !== null ? value as ToolInput : {};

const runGuard = (payload: ToolInput): string | undefined => {
  const result = spawnSync("python3", [GUARD_PATH], {
    input: JSON.stringify(payload),
    encoding: "utf8",
  });
  if (result.error) return `DOE guard unavailable: ${result.error.message}`;

  const output = String(result.stdout).trim();
  if (!output) return result.status === 0 ? undefined : String(result.stderr).trim();

  try {
    const parsed = JSON.parse(output) as { hookSpecificOutput?: { permissionDecisionReason?: string } };
    return parsed.hookSpecificOutput?.permissionDecisionReason;
  } catch {
    return `DOE guard returned invalid output: ${output}`;
  }
};

const legacyInput = (toolName: string, input: ToolInput): ToolInput => {
  if (toolName === "bash") return { command: input.command };
  return { file_path: input.path };
};

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", (event, ctx) => {
    if (!["bash", "edit", "write"].includes(event.toolName)) return;

    const input = asRecord(event.input);
    const toolName = event.toolName === "bash" ? "Bash" : "Write";
    const reason = runGuard({
      tool_name: toolName,
      tool_input: legacyInput(event.toolName, input),
      cwd: ctx.cwd,
    });
    if (reason) return { block: true, reason };
  });
}
