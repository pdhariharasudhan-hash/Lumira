import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";
import viteConfig from "../../vite.config";

const require = createRequire(import.meta.url);
const { API_ROOTS } = require("../../electron-api-proxy.cjs") as { API_ROOTS: Set<string> };
const plugins = viteConfig.plugins ?? [];

describe("desktop development API proxy", () => {
  it("forwards every API root used by the desktop client through the shared proxy", () => {
    const requiredRoots = [
      "health", "ai-mode", "providers", "resources", "intelligence",
      "images", "modes", "features", "notepad", "sessions", "command",
      "projects", "artifacts", "goals", "workflows", "search", "memory",
      "runs", "voice", "devices", "openapi.json",
    ];

    expect([...API_ROOTS]).toEqual(expect.arrayContaining(requiredRoots));
  });

  it("installs the shared API proxy in both development and preview servers", () => {
    const pluginNames = plugins.flatMap((plugin) => {
      const entries = Array.isArray(plugin) ? plugin : [plugin];
      return entries
        .map((entry) => (entry as { name?: string } | null)?.name)
        .filter((name): name is string => typeof name === "string");
    });

    expect(pluginNames).toContain("lumira-api-proxy");
    const proxy = plugins.find((plugin) =>
      !Array.isArray(plugin) && (plugin as { name?: string }).name === "lumira-api-proxy",
    ) as { configureServer?: unknown; configurePreviewServer?: unknown } | undefined;
    expect(typeof proxy?.configureServer).toBe("function");
    expect(typeof proxy?.configurePreviewServer).toBe("function");
  });

  it("keeps development and preview servers bound to loopback", () => {
    expect(viteConfig.server?.host).toBe("127.0.0.1");
    expect(viteConfig.preview?.host).toBe("127.0.0.1");
  });
});
