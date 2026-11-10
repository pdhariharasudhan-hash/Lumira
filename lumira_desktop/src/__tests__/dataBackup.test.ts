import { describe, expect, it, vi } from "vitest";
import { api } from "../api/client";

describe("data backup API", () => {
	it("downloads a backup blob", async () => {
		const blob = new Blob(["zip"]);
		vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
			ok: true,
			blob: async () => blob,
		}));
		await expect(api.downloadDataBackup()).resolves.toBe(blob);
	});

	it("uploads a selected zip without forcing JSON headers", async () => {
		const response = { success: true };
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => response,
		});
		vi.stubGlobal("fetch", fetchMock);
		const file = new File(["zip"], "backup.zip", { type: "application/zip" });
		await expect(api.restoreDataBackup(file)).resolves.toEqual(response);
		expect(fetchMock.mock.calls[0][1].headers).toBeUndefined();
	});
});
