import { describe, expect, it } from "vitest";
import viteConfig from "../../vite.config";

describe("desktop development API proxy", () => {
  it("forwards every API root used by the desktop client to the loopback backend", () => {
    const proxyRoots = Object.keys(viteConfig.server?.proxy ?? {});
    const requiredRoots = [
      "/health",
      "/intelligence",
      "/images",
      "/modes",
      "/features",
      "/notepad",
      "/sessions",
      "/command",
      "/projects",
      "/artifacts",
      "/goals",
      "/workflows",
      "/search",
      "/memory",
      "/runs",
      "/voice",
      "/openapi.json",
    ];

    expect(proxyRoots).toEqual(expect.arrayContaining(requiredRoots));
  });

  it("keeps the development server bound to loopback", () => {
    expect(viteConfig.server?.host).toBe("127.0.0.1");
  });
});
