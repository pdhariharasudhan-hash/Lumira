import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MainLayout from "../layouts/MainLayout";

const STORAGE_KEY = "lumira.sessionId";

type MockResponse = {
	ok: boolean;
	status?: number;
	json: () => Promise<unknown>;
};

function jsonResponse(body: unknown, status = 200): MockResponse {
	return { ok: status >= 200 && status < 300, status, json: async () => body };
}

function mockFetch(handler: (input: RequestInfo | URL, init?: RequestInit) => MockResponse | Promise<MockResponse>) {
	const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => Promise.resolve(handler(input, init)));
	vi.stubGlobal("fetch", fetchMock);
	return fetchMock;
}

function activeSession(overrides: Record<string, unknown> = {}) {
	return {
		session_id: "session-12345678",
		status: "active",
		active_project: "Lumira workspace",
		current_goal: "Build Lumira",
		recent_messages: [],
		...overrides,
	};
}

function healthResponse(input: RequestInfo | URL) {
	if (String(input) === "/health") return jsonResponse({ status: "ok" });
	return jsonResponse({});
}

function deferred<T>() {
	let resolve!: (value: T) => void;
	const promise = new Promise<T>((resolvePromise) => {
		resolve = resolvePromise;
	});
	return { promise, resolve };
}

beforeEach(() => {
	window.localStorage.clear();
	mockFetch(healthResponse);
});

afterEach(() => {
	cleanup();
	window.localStorage.clear();
	vi.unstubAllGlobals();
});

describe("MainLayout startup and sessions", () => {
	it("shows the ready state when the health check succeeds", async () => {
		render(<MainLayout />);

		expect(await screen.findByText("CORE READY")).toBeTruthy();
		expect(screen.getByText("Local core")).toBeTruthy();
	});

	it("shows the offline state when the health check fails", async () => {
		mockFetch((input) => {
			if (String(input) === "/health") return Promise.reject(new Error("offline"));
			return jsonResponse({});
		});
		render(<MainLayout />);

		expect(await screen.findByText("CORE OFFLINE")).toBeTruthy();
		expect(screen.getByText("Core offline")).toBeTruthy();
	});

	it("shows the welcome UI and skips restoration when there is no stored session", async () => {
		const fetchMock = mockFetch(healthResponse);
		render(<MainLayout />);

		expect(await screen.findByRole("heading", { name: "What are we working on?" })).toBeTruthy();
		expect(fetchMock.mock.calls.some(([input]) => String(input).startsWith("/sessions/"))).toBe(false);
	});

	it("restores an active session and its recent user and assistant messages", async () => {
		window.localStorage.setItem(STORAGE_KEY, "session-12345678");
		mockFetch((input) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/sessions/session-12345678") {
				return jsonResponse(activeSession({
					recent_messages: [
						{ role: "user", content: "Plan a workspace" },
						{ role: "assistant", content: "I can help with that." },
					],
				}));
			}
			return jsonResponse({});
		});
		render(<MainLayout />);

		expect(await screen.findByText("Session session- · active · Build Lumira")).toBeTruthy();
		expect(screen.getByText("Plan a workspace")).toBeTruthy();
		expect(screen.getByText("I can help with that.")).toBeTruthy();
		expect(screen.getByText("Lumira workspace")).toBeTruthy();
	});

	it("resumes a paused stored session and displays the resumed state", async () => {
		window.localStorage.setItem(STORAGE_KEY, "session-12345678");
		const fetchMock = mockFetch((input, init) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/sessions/session-12345678") return jsonResponse(activeSession({ status: "paused" }));
			if (String(input) === "/sessions/session-12345678/resume" && init?.method === "POST") {
				return jsonResponse(activeSession({ status: "active", current_goal: "Resumed goal" }));
			}
			return jsonResponse({});
		});
		render(<MainLayout />);

		expect(await screen.findByText("Session session- · active · Resumed goal")).toBeTruthy();
		expect(fetchMock).toHaveBeenCalledWith("/sessions/session-12345678/resume", { method: "POST" });
	});

	it("clears an invalid stored session and lets the user start a new session", async () => {
		window.localStorage.setItem(STORAGE_KEY, "missing-session");
		mockFetch((input, init) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/sessions/missing-session") return jsonResponse({ detail: "missing" }, 404);
			if (String(input) === "/sessions" && init?.method === "POST") return jsonResponse(activeSession());
			return jsonResponse({});
		});
		render(<MainLayout />);

		expect(await screen.findByText("The saved session could not be restored. Start a new session to continue.")).toBeTruthy();
		expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
		fireEvent.click(screen.getByRole("button", { name: "New session" }));
		expect(await screen.findByText("Session session- · active · Build Lumira")).toBeTruthy();
	});

	it("stores a newly created session and clears the conversation", async () => {
		window.localStorage.setItem(STORAGE_KEY, "session-12345678");
		const fetchMock = mockFetch((input, init) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/sessions/session-12345678") {
				return jsonResponse(activeSession({ recent_messages: [{ role: "user", content: "Old conversation" }] }));
			}
			if (String(input) === "/sessions" && init?.method === "POST") return jsonResponse(activeSession({ session_id: "new-session-87654321" }));
			return jsonResponse({});
		});
		render(<MainLayout />);

		expect(await screen.findByText("Old conversation")).toBeTruthy();
		fireEvent.click(screen.getByRole("button", { name: "New session" }));
		expect(await screen.findByText("What are we working on?")).toBeTruthy();
		expect(screen.queryByText("Old conversation")).toBeNull();
		expect(screen.getByText("Session new-sess · active · Build Lumira")).toBeTruthy();
		expect(window.localStorage.getItem(STORAGE_KEY)).toBe("new-session-87654321");
		expect(fetchMock).toHaveBeenCalledWith("/sessions", expect.objectContaining({
			method: "POST",
			body: JSON.stringify({ workspace_id: "default" }),
		}));
	});
});

describe("MainLayout requests", () => {
	it("sends the original Brain prompt with the workspace and current session", async () => {
		window.localStorage.setItem(STORAGE_KEY, "session-12345678");
		const fetchMock = mockFetch((input) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/sessions/session-12345678") return jsonResponse(activeSession());
			if (String(input) === "/brain") return jsonResponse({ result: { capability: "planning" }, message: "Plan ready" });
			return jsonResponse({});
		});
		render(<MainLayout />);
		const prompt = await screen.findByRole("textbox", { name: "Describe what you want to work on" });
		fireEvent.change(prompt, { target: { value: "  Plan my week  " } });
		fireEvent.click(screen.getByRole("button", { name: "Send request" }));

		expect(await screen.findByText("Plan ready")).toBeTruthy();
		const brainCall = fetchMock.mock.calls.find(([input]) => String(input) === "/brain");
		expect(brainCall).toBeDefined();
		expect(JSON.parse(String(brainCall?.[1]?.body))).toEqual({
			input: "Plan my week",
			session_id: "session-12345678",
			workspace_id: "default",
		});
	});

	it("sends project prompts to command with the expected prefix", async () => {
		window.localStorage.setItem(STORAGE_KEY, "session-12345678");
		const fetchMock = mockFetch((input) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/sessions/session-12345678") return jsonResponse(activeSession());
			if (String(input) === "/command") return jsonResponse({ result: { project_name: "Notes app" } });
			return jsonResponse({});
		});
		render(<MainLayout />);
		fireEvent.click(await screen.findByRole("button", { name: "Generate project" }));
		fireEvent.change(screen.getByRole("textbox", { name: "Describe what you want to work on" }), {
			target: { value: "a notes app" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Send request" }));

		expect(await screen.findByText("Project saved: Notes app")).toBeTruthy();
		const projectCall = fetchMock.mock.calls.find(([input]) => String(input) === "/command");
		expect(JSON.parse(String(projectCall?.[1]?.body))).toEqual({
			input: "Generate project: a notes app",
			session_id: "session-12345678",
			workspace_id: "default",
		});
	});

	it("persists a returned session ID and loads that session", async () => {
		const fetchMock = mockFetch((input) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/brain") return jsonResponse({ session_id: "returned-session-123", message: "Created" });
			if (String(input) === "/sessions/returned-session-123") return jsonResponse(activeSession({
				session_id: "returned-session-123",
				current_goal: "Loaded after request",
			}));
			return jsonResponse({});
		});
		render(<MainLayout />);
		fireEvent.change(await screen.findByRole("textbox", { name: "Describe what you want to work on" }), {
			target: { value: "Start work" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Send request" }));

		expect(await screen.findByText("Session returned · active · Loaded after request")).toBeTruthy();
		expect(window.localStorage.getItem(STORAGE_KEY)).toBe("returned-session-123");
		expect(fetchMock).toHaveBeenCalledWith("/sessions/returned-session-123");
	});

	it("renders clarification as a response instead of an error", async () => {
		mockFetch((input) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/brain") return jsonResponse({
				clarification_required: true,
				message: "Which platform should I target?",
				data: { stage: "clarification" },
			});
			return jsonResponse({});
		});
		render(<MainLayout />);
		fireEvent.change(await screen.findByRole("textbox", { name: "Describe what you want to work on" }), {
			target: { value: "Build an app" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Send request" }));

		expect(await screen.findByText("Which platform should I target?")).toBeTruthy();
		expect(screen.getByText("clarification")).toBeTruthy();
		expect(screen.queryByText("The request could not be completed.")).toBeNull();
	});

	it("renders the backend detail when a request fails", async () => {
		mockFetch((input) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/brain") return jsonResponse({ detail: "Backend is unavailable" }, 503);
			return jsonResponse({});
		});
		render(<MainLayout />);
		fireEvent.change(await screen.findByRole("textbox", { name: "Describe what you want to work on" }), {
			target: { value: "Do something" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Send request" }));

		expect(await screen.findByText("Backend is unavailable")).toBeTruthy();
	});

	it("renders an unsuccessful result as an error", async () => {
		mockFetch((input) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/brain") return jsonResponse({ result: { success: false }, error: "Generation failed" });
			return jsonResponse({});
		});
		render(<MainLayout />);
		fireEvent.change(await screen.findByRole("textbox", { name: "Describe what you want to work on" }), {
			target: { value: "Generate something" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Send request" }));

		expect(await screen.findByText("Generation failed")).toBeTruthy();
	});
});

describe("MainLayout workflow and composer", () => {
	it("switches between Brain and project workflow labels and placeholders", async () => {
		render(<MainLayout />);
		const brainButton = screen.getByRole("button", { name: "Brain" });
		const projectButton = screen.getByRole("button", { name: "Generate project" });
		expect(brainButton.getAttribute("aria-pressed")).toBe("true");
		expect(screen.getByRole("textbox", { name: "Describe what you want to work on" }).getAttribute("placeholder"))
			.toBe("Describe a goal for the Brain...");

		fireEvent.click(projectButton);
		expect(projectButton.getAttribute("aria-pressed")).toBe("true");
		expect(screen.getByRole("textbox", { name: "Describe what you want to work on" }).getAttribute("placeholder"))
			.toBe("Describe the project to generate...");
		expect(screen.getByText("LUMIRA / PROJECT ENGINE")).toBeTruthy();

		fireEvent.click(brainButton);
		expect(brainButton.getAttribute("aria-pressed")).toBe("true");
	});

	it("keeps Send disabled for empty and whitespace prompts, then enables it for text", async () => {
		render(<MainLayout />);
		const sendButton = screen.getByRole("button", { name: "Send request" });
		const prompt = await screen.findByRole("textbox", { name: "Describe what you want to work on" });
		expect((sendButton as HTMLButtonElement).disabled).toBe(true);
		fireEvent.change(prompt, { target: { value: "   \n " } });
		expect((sendButton as HTMLButtonElement).disabled).toBe(true);
		fireEvent.change(prompt, { target: { value: "Hello" } });
		expect((sendButton as HTMLButtonElement).disabled).toBe(false);
	});

	it("disables Send while a request is in progress", async () => {
		const request = deferred<MockResponse>();
		mockFetch((input) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/brain") return request.promise;
			return jsonResponse({});
		});
		render(<MainLayout />);
		fireEvent.change(await screen.findByRole("textbox", { name: "Describe what you want to work on" }), {
			target: { value: "Wait for response" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Send request" }));

		expect(await screen.findByText("Running through the core...")).toBeTruthy();
		expect((screen.getByRole("button", { name: "Send request" }) as HTMLButtonElement).disabled).toBe(true);
		request.resolve(jsonResponse({ message: "Done" }));
		expect(await screen.findByText("Done")).toBeTruthy();
	});

	it("blocks submission while restoring, then becomes usable after restoration", async () => {
		window.localStorage.setItem(STORAGE_KEY, "session-12345678");
		const restoration = deferred<MockResponse>();
		const fetchMock = mockFetch((input) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/sessions/session-12345678") return restoration.promise;
			return jsonResponse({});
		});
		render(<MainLayout />);
		const prompt = screen.getByRole("textbox", { name: "Describe what you want to work on" });
		const sendButton = screen.getByRole("button", { name: "Send request" });
		expect((sendButton as HTMLButtonElement).disabled).toBe(true);
		fireEvent.change(prompt, { target: { value: "Start after restore" } });
		expect((sendButton as HTMLButtonElement).disabled).toBe(true);
		expect(fetchMock.mock.calls.some(([input]) => String(input) === "/brain")).toBe(false);

		restoration.resolve(jsonResponse(activeSession()));
		await waitFor(() => expect((screen.getByRole("button", { name: "Send request" }) as HTMLButtonElement).disabled).toBe(false));
	});

	it("submits on Enter and preserves Shift+Enter as a newline", async () => {
		const fetchMock = mockFetch((input) => {
			if (String(input) === "/health") return jsonResponse({});
			if (String(input) === "/brain") return jsonResponse({ message: "Submitted" });
			return jsonResponse({});
		});
		render(<MainLayout />);
		const prompt = await screen.findByRole("textbox", { name: "Describe what you want to work on" });
		fireEvent.change(prompt, { target: { value: "Keyboard request" } });
		fireEvent.keyDown(prompt, { key: "Enter", shiftKey: true });
		expect(fetchMock.mock.calls.some(([input]) => String(input) === "/brain")).toBe(false);

		fireEvent.keyDown(prompt, { key: "Enter", shiftKey: false });
		expect(await screen.findByText("Submitted")).toBeTruthy();
		expect(fetchMock.mock.calls.filter(([input]) => String(input) === "/brain")).toHaveLength(1);
	});
});
