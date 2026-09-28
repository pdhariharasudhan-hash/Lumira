export type JsonObject = Record<string, unknown>;

export class ApiError extends Error {
	readonly status: number;
	readonly body: JsonObject;

	constructor(message: string, status: number, body: JsonObject) {
		super(message);
		this.status = status;
		this.body = body;
		this.name = "ApiError";
	}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const response = await fetch(path, init);
	const body = (await response.json().catch(() => ({}))) as JsonObject;
	if (!response.ok) {
		const detail = body.detail;
		const message = typeof detail === "string"
			? detail
			: typeof detail === "object" && detail !== null
				? String((detail as JsonObject).message ?? (detail as JsonObject).code ?? `Request failed (${response.status})`)
				: String(body.message ?? body.error ?? `Request failed (${response.status})`);
		throw new ApiError(message, response.status, body);
	}
	return body as T;
}

function json(method: string, body: unknown): RequestInit {
	return {
		method,
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	};
}

export const api = {
	health: () => request<JsonObject>("/health"),
	createSession: (workspace_id = "default", project_id?: string) =>
		request<JsonObject>("/sessions", json("POST", { workspace_id, ...(project_id ? { project_id } : {}) })),
	listSessions: (limit = 100) => request<{ sessions: JsonObject[] }>(`/sessions?limit=${limit}`),
	getSession: (sessionId: string) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}`),
	resumeSession: (sessionId: string) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/resume`, { method: "POST" }),
	pauseSession: (sessionId: string) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/pause`, { method: "POST" }),
	closeSession: (sessionId: string) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/close`, { method: "POST" }),
	command: (input: string, session_id?: string) =>
		request<JsonObject>("/command", json("POST", { input, session_id, workspace_id: "default" })),
	listProjects: () => request<JsonObject>("/projects"),
	getProjectVersions: (project: string) => request<JsonObject>(`/projects/${encodeURIComponent(project)}`),
	getProjectVersion: (project: string, version: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}`),
	getProjectFiles: (project: string, version: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}/files`),
	getProjectFile: (project: string, version: string, file: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}/${encodeURIComponent(file)}`),
	listArtifacts: () => request<JsonObject>("/artifacts"),
	listGoals: () => request<JsonObject>("/goals"),
	createGoal: (title: string, objective = "") => request<JsonObject>("/goals", json("POST", { title, objective })),
	listWorkflows: (category?: "business" | "operations") =>
		request<JsonObject>(`/workflows${category ? `?category=${category}` : ""}`),
	getWorkflow: (workflowId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}`),
	updateWorkflowTask: (workflowId: string, taskId: string, body: JsonObject) =>
		request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/tasks/${encodeURIComponent(taskId)}`, json("PATCH", body)),
	search: (query: string) => request<JsonObject>(`/search?q=${encodeURIComponent(query)}`),
	getRelevantMemory: (query: string, sessionId?: string) =>
		request<JsonObject>(`/memory/relevant?q=${encodeURIComponent(query)}${sessionId ? `&session_id=${encodeURIComponent(sessionId)}` : ""}`),
	getOpenApi: () => request<JsonObject>("/openapi.json"),
	listRuns: () => request<JsonObject>("/runs"),
	getRun: (runId: string) => request<JsonObject>(`/runs/${encodeURIComponent(runId)}`),
	resumeRun: (runId: string) => request<JsonObject>(`/runs/${encodeURIComponent(runId)}/resume`, { method: "POST" }),
	uploadVoice: async (file: File) => {
		const form = new FormData();
		form.append("audio", file);
		return request<JsonObject>("/voice/upload", { method: "POST", body: form });
	},
	transcribeVoice: (artifact_id: string) => request<JsonObject>("/voice/transcript", json("POST", { artifact_id })),
};
