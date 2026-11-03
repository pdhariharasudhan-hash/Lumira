import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MainLayout from "../layouts/MainLayout";
import { initialWorkspaceUiState, useAppStore } from "../store/appStore";

type MockResponse = { ok: boolean; status?: number; json: () => Promise<unknown>; text?: () => Promise<string> };
type FetchHandler = (input: RequestInfo | URL, init?: RequestInit) => MockResponse | Promise<MockResponse>;

function jsonResponse(body: unknown, status = 200): MockResponse {
	return { ok: status >= 200 && status < 300, status, json: async () => body, text: async () => JSON.stringify(body) };
}

function mockFetch(handler: FetchHandler = defaultResponse) {
	const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => Promise.resolve(handler(input, init)));
	vi.stubGlobal("fetch", fetchMock);
	return fetchMock;
}

function defaultResponse(input: RequestInfo | URL): MockResponse {
	const path = String(input);
	if (path === "/health") return jsonResponse({ status: "ok" });
	if (path.startsWith("/sessions?")) return jsonResponse({ sessions: [] });
	if (path === "/projects") return jsonResponse({ projects: [] });
	if (path === "/openapi.json") return jsonResponse({ paths: {} });
	if (path === "/runs") return jsonResponse({ runs: [] });
	if (path === "/artifacts") return jsonResponse({ artifacts: [] });
	if (path === "/goals") return jsonResponse({ goals: [] });
	if (path.startsWith("/workflows")) return jsonResponse({ workflows: [] });
	if (path.startsWith("/memory/")) return jsonResponse({ data: {} });
	if (path.startsWith("/search?")) return jsonResponse({ results: {} });
	return jsonResponse({});
}

function setSessionId(sessionId: string) {
	window.localStorage.setItem("lumira.sessionId", sessionId);
}

function activeSession(overrides: Record<string, unknown> = {}) {
	return {
		session_id: "session-12345678",
		status: "active",
		active_project: null,
		current_goal: "Workspace session",
		recent_messages: [],
		...overrides,
	};
}

beforeEach(() => {
	window.localStorage.clear();
	useAppStore.setState(initialWorkspaceUiState);
	mockFetch();
});

afterEach(() => {
	cleanup();
	window.localStorage.clear();
	useAppStore.setState(initialWorkspaceUiState);
	vi.unstubAllGlobals();
});

describe("Lumira workspace shell", () => {
	it("exposes the existing core modules through the main navigation", async () => {
		render(<MainLayout />);

		fireEvent.click(screen.getByRole("button", { name: "Memory" }));
		expect(await screen.findByRole("heading", { name: "Relevant memory" })).toBeTruthy();

		fireEvent.click(screen.getByRole("button", { name: "Goals" }));
		expect(await screen.findByRole("heading", { name: "Goals" })).toBeTruthy();

		fireEvent.click(screen.getByRole("button", { name: "Unified Search" }));
		expect(await screen.findByRole("heading", { name: "Search Lumira" })).toBeTruthy();

		fireEvent.click(screen.getByRole("button", { name: "Project Generator" }));
		expect(await screen.findByRole("heading", { name: "Create with Lumira" })).toBeTruthy();

		fireEvent.click(screen.getByRole("button", { name: "Operations" }));
		expect(await screen.findByRole("heading", { name: "Workflows & recovery" })).toBeTruthy();
	});

	it("restores a saved session and its real recent conversation", async () => {
		setSessionId("session-12345678");
		const fetchMock = mockFetch((input) => {
			if (String(input) === "/sessions/session-12345678") return jsonResponse(activeSession({
				recent_messages: [
					{ role: "user", content: "Plan my release" },
					{ role: "assistant", content: "I saved the release plan.", metadata: { response: { success: true, message: "I saved the release plan.", result: { capability: "planning", status: "completed" }, attachments: [{ artifact_id: "restored-image", kind: "image", title: "Release diagram", url: "/artifacts/restored-image/content" }] } } },
				],
			}));
			return defaultResponse(input);
		});
		render(<MainLayout />);

		expect(await screen.findByText("Plan my release")).toBeTruthy();
		expect(screen.getByText("I saved the release plan.")).toBeTruthy();
		expect(await screen.findByRole("img", { name: "Release diagram" })).toBeTruthy();
		expect(fetchMock.mock.calls.some(([input]) => String(input) === "/sessions/session-12345678")).toBe(true);
		expect(await screen.findByText("CORE READY")).toBeTruthy();
	});

	it("preserves saved media when switching to another conversation", async () => {
		setSessionId("session-12345678");
		const fetchMock = mockFetch((input) => {
			const path = String(input);
			if (path === "/sessions?limit=100") return jsonResponse({ sessions: [
				activeSession({ recent_messages: [{ role: "user", content: "Current conversation" }] }),
				activeSession({ session_id: "session-2", current_goal: "Other conversation", recent_messages: [{ role: "user", content: "Other conversation" }] }),
			] });
			if (path === "/sessions/session-12345678") return jsonResponse(activeSession({ recent_messages: [{ role: "user", content: "Current conversation" }] }));
			if (path === "/sessions/session-2") return jsonResponse(activeSession({
				session_id: "session-2",
				recent_messages: [
					{ role: "user", content: "Show the diagram again" },
					{ role: "assistant", content: "Here is the saved diagram.", metadata: { response: {
						success: true,
						message: "Here is the saved diagram.",
						result: { capability: "image_generation", status: "completed" },
						attachments: [{ artifact_id: "diagram-2", kind: "image", title: "Saved diagram", url: "/artifacts/diagram-2/content" }],
					} } },
				],
			}));
			return defaultResponse(input);
		});
		render(<MainLayout />);
		fireEvent.click(await screen.findByRole("button", { name: "Open chat Other conversation" }));

		expect(await screen.findByText("Show the diagram again")).toBeTruthy();
		expect(await screen.findByRole("img", { name: "Saved diagram" })).toBeTruthy();
		expect(fetchMock.mock.calls.some(([input]) => String(input) === "/sessions/session-2")).toBe(true);
	});

	it("sends chat prompts through the routed command API with the active session", async () => {
		setSessionId("session-12345678");
		const fetchMock = mockFetch((input) => {
			if (String(input) === "/sessions/session-12345678") return jsonResponse(activeSession());
			if (String(input) === "/command") return jsonResponse({
				result: { capability: "planning", status: "completed", message: "The plan is ready." },
			});
			return defaultResponse(input);
		});
		render(<MainLayout />);
		const composer = await screen.findByRole("textbox", { name: "Describe what you want to work on" });
		fireEvent.change(composer, { target: { value: "  Plan my week  " } });
		fireEvent.click(screen.getByRole("button", { name: "Send request" }));

		expect(await screen.findByText("The plan is ready.")).toBeTruthy();
		expect(screen.queryByText("Technical details (raw JSON)")).toBeNull();
		expect(screen.queryByText("JSON response")).toBeNull();
		const command = fetchMock.mock.calls.find(([input]) => String(input) === "/command");
		expect(JSON.parse(String(command?.[1]?.body))).toEqual({
			input: "Plan my week", session_id: "session-12345678", workspace_id: "default",
		});
	});

	it("shows structured JSON only when the user explicitly asks for JSON", async () => {
		setSessionId("session-12345678");
		mockFetch((input) => {
			if (String(input) === "/sessions/session-12345678") return jsonResponse(activeSession());
			if (String(input) === "/command") return jsonResponse({
				result: { capability: "planning", status: "completed", message: "Here is the requested data.", answer: 42 },
			});
			return defaultResponse(input);
		});
		render(<MainLayout />);
		const composer = await screen.findByRole("textbox", { name: "Describe what you want to work on" });
		fireEvent.change(composer, { target: { value: "Return the result as JSON." } });
		fireEvent.click(screen.getByRole("button", { name: "Send request" }));

		expect(await screen.findByText("JSON response")).toBeTruthy();
		expect(await screen.findByText(/"answer": 42/)).toBeTruthy();
		expect(screen.queryByText("Technical details (raw JSON)")).toBeNull();
	});

	it("renders image, video, audio, document, and code attachments as usable previews", async () => {
		setSessionId("session-12345678");
		const fetchMock = mockFetch((input) => {
			const path = String(input);
			if (path === "/sessions/session-12345678") return jsonResponse(activeSession());
			if (path === "/command") return jsonResponse({
				success: true,
				message: "Your generated files are ready.",
				result: { capability: "media_generation", status: "completed" },
				attachments: [
					{ artifact_id: "image-1", kind: "image", title: "Generated image", url: "/artifacts/image-1/content" },
					{ artifact_id: "video-1", kind: "video", title: "Demo video", url: "/artifacts/video-1/content" },
					{ artifact_id: "audio-1", kind: "audio", title: "Voice sample", url: "/artifacts/audio-1/content" },
					{ artifact_id: "doc-1", kind: "document", title: "Project notes", extension: "md", url: "/artifacts/doc-1/content" },
					{ artifact_id: "code-1", kind: "code", title: "main.py", extension: "py", url: "/artifacts/code-1/content" },
				],
			});
			if (path === "/artifacts/doc-1/content") return { ...jsonResponse({}), text: async () => "# Project Notes\nA readable document." };
			if (path === "/artifacts/code-1/content") return { ...jsonResponse({}), text: async () => "print('hello')" };
			return defaultResponse(input);
		});
		const { container } = render(<MainLayout />);
		const composer = await screen.findByRole("textbox", { name: "Describe what you want to work on" });
		fireEvent.change(composer, { target: { value: "Create a demo with image, video, audio, document and code." } });
		fireEvent.click(screen.getByRole("button", { name: "Send request" }));

		expect(await screen.findByRole("img", { name: "Generated image" })).toBeTruthy();
		expect(container.querySelector('video[aria-label="Demo video"]')).toBeTruthy();
		expect(container.querySelector('audio[aria-label="Voice sample"]')).toBeTruthy();
		expect(container.querySelectorAll(".assistant-attachment-preview")).toHaveLength(2);
		expect(await screen.findByText(/# Project Notes/)).toBeTruthy();
		expect(await screen.findByText("print('hello')")).toBeTruthy();
		expect(fetchMock.mock.calls.some(([input]) => String(input) === "/artifacts/doc-1/content")).toBe(true);
		expect(fetchMock.mock.calls.some(([input]) => String(input) === "/artifacts/code-1/content")).toBe(true);
	});

	it("cycles panel states with keyboard shortcuts, expands the center, and persists preferences", async () => {
		render(<MainLayout />);
		const shell = screen.getByTestId("workspace-shell");
		expect(shell.style.gridTemplateColumns).toBe("204px 248px minmax(0, 1fr) 88px");
		fireEvent.click(screen.getByRole("button", { name: "Widen main sidebar" }));
		expect(useAppStore.getState().navWidth).toBe(220);
		expect(shell.style.gridTemplateColumns).toContain("220px");

		fireEvent.keyDown(window, { key: "b", ctrlKey: true });
		expect(useAppStore.getState().navMode).toBe("compact");
		fireEvent.keyDown(window, { key: "b", ctrlKey: true });
		expect(useAppStore.getState().navMode).toBe("hidden");
		fireEvent.keyDown(window, { key: "j", ctrlKey: true });
		expect(useAppStore.getState().rightMode).toBe("compact");
		fireEvent.keyDown(window, { key: "b", ctrlKey: true, shiftKey: true });
		expect(useAppStore.getState().chatMode).toBe("compact");
		fireEvent.keyDown(window, { key: "f", ctrlKey: true, shiftKey: true });
		expect(shell.classList.contains("focus-mode")).toBe(true);
		expect(shell.style.gridTemplateColumns).toBe("minmax(0, 1fr)");
		fireEvent.keyDown(window, { key: "Escape" });
		expect(shell.classList.contains("focus-mode")).toBe(false);
		const savedPreferences = JSON.parse(window.localStorage.getItem("lumira.workspace") ?? "{}").state;
		expect(savedPreferences.navMode).toBe("hidden");
		expect(savedPreferences.navWidth).toBe(220);
	});

	it("supports compact and hidden composer states, compact top bar, and keyboard search", async () => {
		render(<MainLayout />);
		const shell = screen.getByTestId("workspace-shell");
		fireEvent.click(screen.getByRole("button", { name: "Compact top bar" }));
		expect(shell.classList.contains("topbar-compact")).toBe(true);
		fireEvent.click(screen.getByRole("button", { name: "Compact assistant input" }));
		expect(shell.classList.contains("input-compact")).toBe(true);
		fireEvent.click(screen.getByRole("button", { name: "Hide input" }));
		expect(screen.getByRole("button", { name: "Restore assistant input" })).toBeTruthy();
		fireEvent.click(screen.getByRole("button", { name: "Restore assistant input" }));
		expect(screen.getByRole("textbox", { name: "Describe what you want to work on" })).toBeTruthy();
		fireEvent.keyDown(window, { key: "k", ctrlKey: true });
		expect(await screen.findByRole("heading", { name: "Search Lumira" })).toBeTruthy();
		expect(screen.getByRole("textbox", { name: "Search Lumira" })).toBeTruthy();
	});

	it("loads project files and opens their source from the development panel", async () => {
		const fetchMock = mockFetch((input) => {
			const path = String(input);
			if (path === "/projects") return jsonResponse({ projects: [{ project: "demo", versions: 1 }] });
			if (path === "/projects/demo") return jsonResponse({ versions: ["v1"] });
			if (path === "/projects/demo/v1/files") return jsonResponse({ files: ["app.ts", "README.md"] });
			if (path === "/projects/demo/v1/app.ts") return jsonResponse({ success: true, content: "export const answer = 42;" });
			return defaultResponse(input);
		});
		render(<MainLayout />);
		fireEvent.click(screen.getByRole("tab", { name: "Code" }));
		const projectSelect = await screen.findByRole("combobox", { name: "Select project" });
		fireEvent.change(projectSelect, { target: { value: "demo" } });
		const file = await screen.findByRole("button", { name: "app.ts" });
		fireEvent.click(file);

		expect(await screen.findByText(/export const answer = 42;/)).toBeTruthy();
		expect(fetchMock.mock.calls.some(([input]) => String(input) === "/projects/demo/v1/app.ts")).toBe(true);
	});

	it("uses unified search and creates durable goals through backend APIs", async () => {
		const fetchMock = mockFetch((input, init) => {
			const path = String(input);
			if (path.startsWith("/search?")) return jsonResponse({ results: { artifacts: [{ title: "Launch checklist" }] } });
			if (path === "/goals" && init?.method === "POST") return jsonResponse({ success: true, goal: { title: "Ship Lumira" } });
			return defaultResponse(input);
		});
		render(<MainLayout />);
		fireEvent.change(screen.getByRole("textbox", { name: "Global search" }), { target: { value: "launch" } });
		fireEvent.click(screen.getByRole("button", { name: "Run global search" }));
		expect(await screen.findByText("Launch checklist", { selector: "strong" })).toBeTruthy();
		expect(fetchMock.mock.calls.some(([input]) => String(input) === "/search?q=launch")).toBe(true);

		fireEvent.click(screen.getByRole("button", { name: "Create Goal" }));
		fireEvent.change(await screen.findByRole("textbox", { name: "Goal title" }), { target: { value: "Ship Lumira" } });
		fireEvent.change(screen.getByRole("textbox", { name: "Goal objective" }), { target: { value: "Complete the workspace." } });
		fireEvent.click(screen.getByRole("button", { name: "Create goal" }));
		await waitFor(() => expect(fetchMock.mock.calls.some(([input, init]) => String(input) === "/goals" && init?.method === "POST")).toBe(true));
		expect(await screen.findByRole("status")).toBeTruthy();
	});

	it("starts and stops wake-word listening only after explicit user action", async () => {
		let listening = false;
		const fetchMock = mockFetch((input, init) => {
			const path = String(input);
			if (path === "/voice/wake-word/status") {
				return jsonResponse({ state: listening ? "listening" : "stopped", listening, activated: false });
			}
			if (path === "/voice/wake-word/start" && init?.method === "POST") {
				listening = true;
				return jsonResponse({ success: true, state: "listening", listening: true, activated: false });
			}
			if (path === "/voice/wake-word/stop" && init?.method === "POST") {
				listening = false;
				return jsonResponse({ success: true, state: "stopped", listening: false, activated: false });
			}
			return defaultResponse(input);
		});
		render(<MainLayout />);

		fireEvent.click(await screen.findByRole("button", { name: "Start Wake Word" }));
		expect(await screen.findByRole("button", { name: "Stop Wake Word" })).toBeTruthy();
		expect(fetchMock.mock.calls.some(([input, init]) => String(input) === "/voice/wake-word/start" && init?.method === "POST")).toBe(true);

		fireEvent.click(screen.getByRole("button", { name: "Stop Wake Word" }));
		expect(await screen.findByRole("button", { name: "Start Wake Word" })).toBeTruthy();
		expect(fetchMock.mock.calls.some(([input, init]) => String(input) === "/voice/wake-word/stop" && init?.method === "POST")).toBe(true);
	});

	it("routes mode selection to the backend and reports unavailable developer tools truthfully", async () => {
		const fetchMock = mockFetch((input, init) => {
			const path = String(input);
			if (path === "/sessions" && init?.method === "POST") return jsonResponse(activeSession({ active_mode: "generator" }));
			if (path === "/sessions/session-12345678") return jsonResponse(activeSession({ active_mode: "generator" }));
			if (path === "/modes/select") return jsonResponse({ success: true, active_mode: "generator" });
			return defaultResponse(input);
		});
		render(<MainLayout />);
		fireEvent.change(screen.getByRole("combobox", { name: "Select Lumira mode" }), { target: { value: "generator" } });
		await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input) === "/modes/select")).toBe(true));
		const modeCall = fetchMock.mock.calls.find(([input]) => String(input) === "/modes/select");
		expect(JSON.parse(String(modeCall?.[1]?.body))).toEqual({ session_id: "session-12345678", mode_id: "generator" });

		fireEvent.click(screen.getByRole("tab", { name: "Code" }));
		fireEvent.click(screen.getByRole("button", { name: "Terminal" }));
		expect(screen.getByText("Allowlisted Project Runner")).toBeTruthy();
		expect(screen.getByText(/disabled because no OS-level sandbox is configured/)).toBeTruthy();
		fireEvent.click(screen.getByRole("button", { name: "Preview" }));
		expect(screen.getByText("Register local preview")).toBeTruthy();
		fireEvent.click(screen.getByRole("button", { name: /API Docs/ }));
		expect(screen.getByText("API schema is unavailable.")).toBeTruthy();
		fireEvent.click(screen.getByRole("button", { name: /Database/ }));
		expect(screen.getByText(/No database service is configured/)).toBeTruthy();
		fireEvent.click(screen.getByRole("button", { name: /Runs & Logs/ }));
		expect(screen.getByText("No workflow runs are recorded.")).toBeTruthy();
	});

	it("records microphone audio and sends it through the saved voice pipeline", async () => {
		setSessionId("session-12345678");
		const stoppedTrack = vi.fn();
		vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stoppedTrack }] }) } });
		class FakeMediaRecorder {
			static isTypeSupported() { return true; }
			mimeType: string;
			state = "inactive";
			listeners: Record<string, Array<(event: Event | { data: Blob }) => void>> = {};
			constructor(_stream: MediaStream, options?: MediaRecorderOptions) { this.mimeType = options?.mimeType ?? "audio/webm"; }
			addEventListener(type: string, callback: (event: Event | { data: Blob }) => void) { (this.listeners[type] ??= []).push(callback); }
			start() { this.state = "recording"; }
			stop() {
				this.state = "inactive";
				for (const callback of this.listeners.dataavailable ?? []) callback({ data: new Blob(["audio-data"], { type: this.mimeType }) });
				for (const callback of this.listeners.stop ?? []) callback(new Event("stop"));
			}
		}
		vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
		const fetchMock = mockFetch((input) => {
			const path = String(input);
			if (path === "/sessions/session-12345678") return jsonResponse(activeSession());
			if (path === "/voice/upload") return jsonResponse({ success: true, data: { artifact: { artifact_id: "audio-1", type: "audio" } } });
			if (path === "/voice/process") return jsonResponse({
				success: true, stage: "completed", audio_artifact_id: "audio-1", transcript_artifact_id: "transcript-1", summary_artifact_id: "summary-1",
				transcription: { success: true, transcript_text: "வணக்கம் Lumira, save this idea", transcript_artifact: { artifact_id: "transcript-1" } },
				summary: { success: true, summary_text: "A voice idea was captured.", summary_artifact: { artifact_id: "summary-1" } },
				memory: { success: true, state: "saved", message: "Voice idea saved to memory and linked to its artifacts." },
			});
			if (path === "/sessions/session-12345678/voice-result") return jsonResponse({ success: true, linked_artifact_ids: ["audio-1", "transcript-1", "summary-1"] });
			return defaultResponse(input);
		});
		render(<MainLayout />);
		fireEvent.click(await screen.findByRole("button", { name: "Start microphone recording" }));
		expect(await screen.findByRole("status")).toBeTruthy();
		fireEvent.click(screen.getByRole("button", { name: "Stop microphone recording" }));
		expect(await screen.findByText(/வணக்கம் Lumira, save this idea/, { selector: ".assistant-message" })).toBeTruthy();
		expect(await screen.findByText(/A voice idea was captured\./, { selector: ".assistant-message" })).toBeTruthy();
		expect(await screen.findByText(/Voice idea saved to memory and linked to its artifacts/, { selector: ".assistant-message" })).toBeTruthy();
		expect(stoppedTrack).toHaveBeenCalledTimes(1);
		const uploadCall = fetchMock.mock.calls.find(([input]) => String(input) === "/voice/upload");
		expect(uploadCall?.[1]?.method).toBe("POST");
		expect(uploadCall?.[1]?.body).toBeInstanceOf(FormData);
		expect(fetchMock.mock.calls.some(([input]) => String(input) === "/voice/process")).toBe(true);
		expect(fetchMock.mock.calls.some(([input]) => String(input) === "/sessions/session-12345678/voice-result")).toBe(true);
	});

});
