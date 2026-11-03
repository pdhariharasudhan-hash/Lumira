import { createRequire } from "node:module";
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

const require = createRequire(import.meta.url);
const { backendFingerprint, installBackendRuntime, prepareWorkspace } = require("../../backend-runtime.cjs") as {
  backendFingerprint: (root: string) => string;
  installBackendRuntime: (options: { userData: string; bundled: string; appVersion: string }) => string;
  prepareWorkspace: (userData: string) => string;
};

const temporaryRoots: string[] = [];

function temporaryRoot() {
  const root = mkdtempSync(path.join(tmpdir(), "lumira-backend-runtime-"));
  temporaryRoots.push(root);
  return root;
}

function write(root: string, relative: string, content: string) {
  const target = path.join(root, relative);
  mkdirSync(path.dirname(target), { recursive: true });
  writeFileSync(target, content, "utf8");
}

afterEach(() => {
  for (const root of temporaryRoots.splice(0)) rmSync(root, { recursive: true, force: true });
});

describe("persistent backend runtime", () => {
  it("moves legacy user data out of the replaceable backend directory", () => {
    const userData = temporaryRoot();
    const legacy = path.join(userData, "backend");
    write(legacy, "run.py", "old application code");
    write(legacy, "memory/cognitive_sessions.json", '{"sessions":["keep"]}');
    write(legacy, "artifacts/image.bin", "user image");
    write(legacy, "data/project_memory.json", '{"projects":["keep"]}');

    const workspace = prepareWorkspace(userData);

    expect(existsSync(path.join(userData, "backend"))).toBe(false);
    expect(readFileSync(path.join(workspace, "memory/cognitive_sessions.json"), "utf8")).toContain("keep");
    expect(readFileSync(path.join(workspace, "artifacts/image.bin"), "utf8")).toBe("user image");
    expect(readFileSync(path.join(workspace, "data/project_memory.json"), "utf8")).toContain("keep");
  });

  it("merges only missing legacy files and never overwrites workspace data", () => {
    const userData = temporaryRoot();
    const workspace = path.join(userData, "workspace");
    const legacy = path.join(userData, "backend");
    write(workspace, "memory/existing.json", "newer workspace data");
    write(legacy, "memory/existing.json", "older legacy data");
    write(legacy, "memory/missing.json", "recoverable legacy data");

    prepareWorkspace(userData);

    expect(readFileSync(path.join(workspace, "memory/existing.json"), "utf8")).toBe("newer workspace data");
    expect(readFileSync(path.join(workspace, "memory/missing.json"), "utf8")).toBe("recoverable legacy data");
    expect(existsSync(path.join(legacy, "memory/missing.json"))).toBe(true);
  });

  it("detects changes to any backend source file and keeps user data outside code updates", () => {
    const userData = temporaryRoot();
    const bundled = path.join(userData, "bundled");
    write(bundled, "run.py", "entry point");
    write(bundled, "app/routes/command.py", "command v1");
    write(bundled, "app/services/health.py", "health v1");
    write(bundled, "generated_templates/starter.txt", "required builder template");
    write(bundled, "memory/shipped-data.json", "must not ship");
    write(bundled, "tests/test_example.py", "must not ship");

    const workspace = prepareWorkspace(userData);
    write(workspace, "memory/cognitive_sessions.json", "session survives");
    const firstFingerprint = backendFingerprint(bundled);
    const runtime = installBackendRuntime({ userData, bundled, appVersion: "1.0.0" });

    expect(readFileSync(path.join(runtime, "app/services/health.py"), "utf8")).toBe("health v1");
    expect(readFileSync(path.join(runtime, "generated_templates/starter.txt"), "utf8")).toBe("required builder template");
    expect(existsSync(path.join(runtime, "memory"))).toBe(false);
    expect(existsSync(path.join(runtime, "tests"))).toBe(false);

    write(bundled, "app/services/health.py", "health v2");
    expect(backendFingerprint(bundled)).not.toBe(firstFingerprint);
    const updatedRuntime = installBackendRuntime({ userData, bundled, appVersion: "1.0.0" });

    expect(readFileSync(path.join(updatedRuntime, "app/services/health.py"), "utf8")).toBe("health v2");
    expect(readFileSync(path.join(workspace, "memory/cognitive_sessions.json"), "utf8")).toBe("session survives");
    expect(readdirSync(userData).some(name => name.startsWith("backend-runtime.previous-"))).toBe(true);
  });
});
