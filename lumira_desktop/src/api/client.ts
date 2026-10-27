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

async function requestText(path: string): Promise<string> {
  const response = await fetch(path);
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new ApiError(detail || `Request failed (${response.status})`, response.status, {});
  }
  return response.text();
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
	providerStatus: () => request<JsonObject>("/providers/status"),
	resourceRuntime: () => request<JsonObject>("/resources/runtime"),
	resourcePolicy: () => request<JsonObject>("/resources/policy"),
	intelligenceStatus: () => request<JsonObject>("/intelligence/status"),
	intelligenceHistory: (limit = 20, sessionId?: string) => request<JsonObject>(`/intelligence/history?limit=${limit}${sessionId ? `&session_id=${encodeURIComponent(sessionId)}` : ""}`),
	analyzeInput: (text: string) => request<JsonObject>("/intelligence/analyze", json("POST", { text })),
	analyzeImage: (image_base64: string, prompt: string, saveArtifact = false) => request<JsonObject>("/images/analyze", json("POST", { image_base64, prompt, save_artifact: saveArtifact })),
	listModes: (sessionId?: string) => request<JsonObject>(`/modes${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`),
	selectMode: (session_id: string, mode_id: string) => request<JsonObject>("/modes/select", json("POST", { session_id, mode_id })),
	listFeatures: () => request<JsonObject>("/features"),
	activateFeature: (featureId: string) => request<JsonObject>(`/features/${encodeURIComponent(featureId)}/activate`, { method: "POST" }),
	deactivateFeature: (featureId: string) => request<JsonObject>(`/features/${encodeURIComponent(featureId)}/deactivate`, { method: "POST" }),
	listNotes: () => request<JsonObject>("/notepad"),
	createNote: (title: string, content: string) => request<JsonObject>("/notepad", json("POST", { title, content })),
	updateNote: (noteId: string, content: string) => request<JsonObject>(`/notepad/${encodeURIComponent(noteId)}`, json("PATCH", { content })),
	deleteNote: (noteId: string) => request<JsonObject>(`/notepad/${encodeURIComponent(noteId)}`, { method: "DELETE" }),
	sessionSummary: () => request<JsonObject>("/sessions/summary"),
	searchSessions: (query: string, filters: { status?: string; project_id?: string; limit?: number } = {}) => { const params = new URLSearchParams({ q: query }); for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") params.set(key, String(value)); return request<JsonObject>(`/sessions/search?${params.toString()}`); },
	exportSessions: (filters: { status?: string; project_id?: string; include_recent_messages?: boolean; limit?: number } = {}) => { const params = new URLSearchParams(); for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") params.set(key, String(value)); return request<JsonObject>(`/sessions/export${params.size ? `?${params.toString()}` : ""}`); },
	getSessionHealth: (sessionId: string) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/health`),
	getSessionWorkflows: (sessionId: string, limit = 50) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/related-workflows?limit=${limit}`),
	createSession: (workspace_id = "default", project_id?: string) =>
		request<JsonObject>("/sessions", json("POST", { workspace_id, ...(project_id ? { project_id } : {}) })),
	listSessions: (limit = 100) => request<{ sessions: JsonObject[] }>(`/sessions?limit=${limit}`),
	getSession: (sessionId: string) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}`),
	createRecoverySnapshot: (sessionId: string) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/recovery-snapshot`, { method: "POST" }),
	updateSessionContext: (sessionId: string, updates: JsonObject) =>
		request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/context`, json("PATCH", updates)),
	resumeSession: (sessionId: string) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/resume`, { method: "POST" }),
	pauseSession: (sessionId: string) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/pause`, { method: "POST" }),
	closeSession: (sessionId: string) => request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/close`, { method: "POST" }),
	command: (input: string, session_id?: string) =>
		request<JsonObject>("/command", json("POST", { input, session_id, workspace_id: "default" })),
	listProjects: () => request<JsonObject>("/projects"),
	projectSummary: () => request<JsonObject>("/projects/summary"),
	searchProjects: (query: string, limit = 30) => request<JsonObject>(`/projects/search?q=${encodeURIComponent(query)}&limit=${limit}`),
	projectHealth: (project: string) => request<JsonObject>(`/projects/${encodeURIComponent(project)}/health`),
	projectIntegrity: (project: string, version?: string) => request<JsonObject>(`/projects/${encodeURIComponent(project)}/integrity${version ? `?version=${encodeURIComponent(version)}` : ""}`),
	projectSecurityReview: (project: string, version?: string) => request<JsonObject>(`/projects/${encodeURIComponent(project)}/security-review${version ? `?version=${encodeURIComponent(version)}` : ""}`),
	projectReadinessAudit: (project: string, version?: string) => request<JsonObject>(`/projects/${encodeURIComponent(project)}/readiness-audit${version ? `?version=${encodeURIComponent(version)}` : ""}`),
	projectManifest: (project: string, version?: string, limit = 200) => request<JsonObject>(`/projects/${encodeURIComponent(project)}/manifest?limit=${limit}${version ? `&version=${encodeURIComponent(version)}` : ""}`),
	compareProjectVersions: (project: string, left: string, right: string) => request<JsonObject>(`/projects/${encodeURIComponent(project)}/compare-versions?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`),
	getProjectVersions: (project: string) => request<JsonObject>(`/projects/${encodeURIComponent(project)}`),
	getProjectVersion: (project: string, version: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}`),
	getProjectFiles: (project: string, version: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}/files`),
	getProjectFile: (project: string, version: string, file: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}/${encodeURIComponent(file)}`),
	getTerminalCommands: (project: string, version: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}/terminal/commands`),
	runTerminalCommand: (project: string, version: string, command_id: string, trusted_project = false) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}/terminal/run`, json("POST", { project, version, command_id, trusted_project })),
	getTerminalRuns: (project: string, version: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}/terminal/runs`),
	getProjectPreview: (project: string, version: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}/preview`),
	registerProjectPreview: (project: string, version: string, url: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}/preview`, json("POST", { project, version, url })),
	stopProjectPreview: (project: string, version: string) =>
		request<JsonObject>(`/projects/${encodeURIComponent(project)}/${encodeURIComponent(version)}/preview/stop`, { method: "POST" }),
	createArtifact: (input: { type: string; content: string; source?: string; extension?: string }) =>
		request<JsonObject>("/artifacts", json("POST", input)),
	createBinaryArtifact: (input: { type: string; content_base64: string; source?: string; extension: string }) =>
		request<JsonObject>("/artifacts/binary", json("POST", input)),
	artifactContentUrl: (artifactId: string) => `/artifacts/${encodeURIComponent(artifactId)}/content`,
	getArtifactTextContent: (artifactId: string) => requestText(`/artifacts/${encodeURIComponent(artifactId)}/content`),
	deleteArtifact: (artifactId: string) => request<JsonObject>(`/artifacts/${encodeURIComponent(artifactId)}`, { method: "DELETE" }),
	listArtifacts: (includeArchived = false, filters: { artifact_type?: string; q?: string; limit?: number; offset?: number } = {}) => {
		const params = new URLSearchParams();
		if (includeArchived) params.set("include_archived", "true");
		for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") params.set(key, String(value));
		return request<JsonObject>(`/artifacts${params.size ? `?${params.toString()}` : ""}`);
	},
	getArtifact: (artifactId: string) => request<JsonObject>(`/artifacts/${encodeURIComponent(artifactId)}`),
	artifactStats: () => request<JsonObject>("/artifacts/stats"),
	restoreArtifact: (artifactId: string) => request<JsonObject>(`/artifacts/${encodeURIComponent(artifactId)}/restore`, { method: "POST" }),
	archiveArtifact: (artifactId: string) => request<JsonObject>(`/artifacts/${encodeURIComponent(artifactId)}/archive`, { method: "POST" }),
	listGoals: (filters: { project_id?: string; status?: string; parent_goal_id?: string } = {}) => {
		const query = new URLSearchParams();
		for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value);
		return request<JsonObject>(`/goals${query.size ? `?${query.toString()}` : ""}`);
	},
	createGoal: (title: string, objective = "", parent_goal_id?: string, project_id?: string, deadline?: string) =>
		request<JsonObject>("/goals", json("POST", { title, objective, ...(parent_goal_id ? { parent_goal_id } : {}), ...(project_id ? { project_id } : {}), ...(deadline ? { deadline } : {}) })),
	decomposeGoal: (goalId: string, objectives: string[]) =>
		request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/decompose`, json("POST", { objectives })),
	getGoalTree: (goalId: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/tree`),
	getGoalReadiness: (goalId: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/readiness`),
	getGoalSummary: (projectId?: string) => request<JsonObject>(`/goals/summary${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`),
	getGoalIntelligence: (projectId?: string) => request<JsonObject>(`/goals/intelligence${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`),
	searchGoals: (query: string, filters: { project_id?: string; status?: string; limit?: number } = {}) => { const params = new URLSearchParams({ q: query }); for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") params.set(key, String(value)); return request<JsonObject>(`/goals/search?${params.toString()}`); },
	getGoalTimeline: (days = 30, projectId?: string) => request<JsonObject>(`/goals/timeline?days=${days}${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""}`),
	getGoalNextActions: (projectId?: string) => request<JsonObject>(`/goals/next-actions${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`),
	getGoalMilestones: (goalId: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/milestones`),
	addGoalMilestone: (goalId: string, title: string, deadline?: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/milestones`, json("POST", { title, ...(deadline ? { deadline } : {}) })),
	updateGoalMilestone: (goalId: string, milestoneId: string, status: "pending" | "in_progress" | "completed" | "blocked") => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/milestones/${encodeURIComponent(milestoneId)}?status=${status}`, { method: "PATCH" }),
	removeGoalMilestone: (goalId: string, milestoneId: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/milestones/${encodeURIComponent(milestoneId)}`, { method: "DELETE" }),
	bulkUpdateGoals: (input: { goal_ids: string[]; status?: string; priority?: string; project_id?: string; set_project?: boolean }) => request<JsonObject>("/goals/bulk-update", json("POST", input)),
	archiveGoal: (goalId: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/archive`, { method: "POST" }),
	restoreGoal: (goalId: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/restore`, { method: "POST" }),
	duplicateGoal: (goalId: string, includeChildren = false) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/duplicate?include_children=${includeChildren}`, { method: "POST" }),
	getGoalRollup: (goalId: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/rollup`),
	compareGoals: (goalId: string, otherGoalId: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/compare/${encodeURIComponent(otherGoalId)}`),
	exportGoals: (projectId?: string, includeArchived = false) => request<JsonObject>(`/goals/export?include_archived=${includeArchived}${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""}`),
	getGoalDependencies: (goalId: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/dependencies`),
	addGoalDependency: (goalId: string, dependency_goal_id: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/dependencies`, json("POST", { dependency_goal_id })),
	removeGoalDependency: (goalId: string, dependency_goal_id: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/dependencies?dependency_goal_id=${encodeURIComponent(dependency_goal_id)}`, { method: "DELETE" }),
	addGoalBlocker: (goalId: string, blocker: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/blockers`, json("POST", { blocker })),
	removeGoalBlocker: (goalId: string, blocker: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/blockers?blocker=${encodeURIComponent(blocker)}`, { method: "DELETE" }),
	getGoalHistory: (goalId: string) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/history`),
	generateGoalPlan: (goalId: string, category: "business" | "operations" = "operations", sessionId?: string) =>
		request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/plan?category=${category}${sessionId ? `&session_id=${encodeURIComponent(sessionId)}` : ""}`, { method: "POST" }),
	updateGoal: (goalId: string, updates: JsonObject) =>
		request<JsonObject>(`/goals/${encodeURIComponent(goalId)}`, json("PATCH", updates)),
	workflowSummary: (projectId?: string, category?: "business" | "operations") => request<JsonObject>(`/workflows/summary${projectId || category ? `?${new URLSearchParams({ ...(projectId ? { project_id: projectId } : {}), ...(category ? { category } : {}) }).toString()}` : ""}`),
	workflowAttention: (projectId?: string, limit = 20) => request<JsonObject>(`/workflows/attention?limit=${limit}${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""}`),
	workflowTimeline: (days = 30, projectId?: string, limit = 100) => request<JsonObject>(`/workflows/timeline?days=${days}&limit=${limit}${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""}`),
	searchWorkflows: (query: string, filters: { project_id?: string; status?: string; category?: "business" | "operations"; limit?: number } = {}) => { const params = new URLSearchParams({ q: query }); for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") params.set(key, String(value)); return request<JsonObject>(`/workflows/search?${params.toString()}`); },
	exportWorkflows: (projectId?: string, status?: string, limit = 100) => request<JsonObject>(`/workflows/export?limit=${limit}${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""}${status ? `&status=${encodeURIComponent(status)}` : ""}`),
	workflowDependencyGraph: (workflowId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/dependency-graph`),
	workflowHealth: (workflowId: string, staleDays = 7) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/health?stale_days=${staleDays}`),
	workflowReadyTasks: (workflowId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/ready-tasks`),
	workflowTaskResults: (workflowId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/task-results`),
	workflowMetricsByProject: () => request<JsonObject>("/workflows/metrics/by-project"),
	blockWorkflowTask: (workflowId: string, taskId: string, reason: string, result?: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/tasks/${encodeURIComponent(taskId)}/block`, json("POST", { reason, ...(result ? { result } : {}) })),
	failWorkflowTask: (workflowId: string, taskId: string, reason: string, result?: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/tasks/${encodeURIComponent(taskId)}/fail`, json("POST", { reason, ...(result ? { result } : {}) })),
	retryWorkflowTask: (workflowId: string, taskId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/tasks/${encodeURIComponent(taskId)}/retry`, { method: "POST" }),
	unblockWorkflowTask: (workflowId: string, taskId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/tasks/${encodeURIComponent(taskId)}/unblock`, { method: "POST" }),
	startWorkflowTask: (workflowId: string, taskId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/tasks/${encodeURIComponent(taskId)}/start`, { method: "POST" }),
	completeWorkflowTask: (workflowId: string, taskId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/tasks/${encodeURIComponent(taskId)}/complete`, { method: "POST" }),
	listWorkflows: (category?: "business" | "operations", filters: { session_id?: string; project_id?: string; goal_id?: string; status?: string; limit?: number } = {}) => {
		const query = new URLSearchParams();
		if (category) query.set("category", category);
		for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") query.set(key, String(value));
		return request<JsonObject>(`/workflows${query.size ? `?${query.toString()}` : ""}`);
	},
	createWorkflow: (input: { category: "business" | "operations"; title: string; request: string; tasks: string[]; goal_id?: string; project_id?: string; session_id?: string }) =>
		request<JsonObject>("/workflows", json("POST", input)),
	runReadyWorkflow: (workflowId: string, max_tasks = 1, stop_on_failure = true, agent_mode: "auto" | "planner_agent" | "research_agent" | "code_agent" = "auto") =>
		request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/run-ready`, json("POST", { max_tasks, stop_on_failure, agent_mode })),
	previewWorkflowExecution: (workflowId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/execution-preview`),
	retryFailedWorkflowTasks: (workflowId: string, max_tasks = 20) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/retry-failed`, json("POST", { max_tasks })),
	runGoalReadyWorkflows: (goalId: string, max_tasks = 3) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/run-ready`, json("POST", { max_tasks })),
	listGoalDeliverables: (goalId: string, includeArchived = false) => request<JsonObject>(`/goals/${encodeURIComponent(goalId)}/deliverables${includeArchived ? "?include_archived=true" : ""}`),
	getWorkflow: (workflowId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}`),
	getWorkflowProgress: (workflowId: string) => request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/progress`),
	getWorkflowTaskHistory: (workflowId: string, taskId: string) =>
		request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/tasks/${encodeURIComponent(taskId)}/history`),
	getWorkflowTaskResult: (workflowId: string, taskId: string) =>
		request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/tasks/${encodeURIComponent(taskId)}/result`),
	listWorkflowDeliverables: (workflowId: string, includeArchived = false) =>
		request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/deliverables${includeArchived ? "?include_archived=true" : ""}`),
	updateWorkflowTask: (workflowId: string, taskId: string, body: JsonObject) =>
		request<JsonObject>(`/workflows/${encodeURIComponent(workflowId)}/tasks/${encodeURIComponent(taskId)}`, json("PATCH", body)),
	listDeviceMessages: (limit = 50) => request<JsonObject>(`/devices/messages?limit=${Math.min(200, Math.max(0, Math.floor(limit)))}`),
	listDevices: (filters: { status?: string; device_type?: string; limit?: number } = {}) => {
		const query = new URLSearchParams();
		for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") query.set(key, String(value));
		return request<JsonObject>(`/devices${query.size ? `?${query.toString()}` : ""}`);
	},
	registerDevice: (input: { device_id: string; device_type: string; capabilities: string[]; permissions: string[]; connection: string }) =>
		request<JsonObject>("/devices/register", json("POST", input)),
	updateDeviceStatus: (deviceId: string, status: string) =>
		request<JsonObject>(`/devices/${encodeURIComponent(deviceId)}/status`, json("PATCH", { status })),
	search: (query: string) => request<JsonObject>(`/search?q=${encodeURIComponent(query)}`),
	getRelevantMemory: (query: string, sessionId?: string) =>
		request<JsonObject>(`/memory/relevant?q=${encodeURIComponent(query)}${sessionId ? `&session_id=${encodeURIComponent(sessionId)}` : ""}`),
	createMemoryDecision: (input: { decision: string; reason?: string; session_id?: string; project_id?: string; goal_id?: string; alternatives?: string[]; constraints?: string[]; confidence?: number }) =>
		request<JsonObject>("/memory/decisions", json("POST", input)),
	listMemoryDecisions: (filters: { project_id?: string; goal_id?: string; session_id?: string; limit?: number } = {}) => {
		const params = new URLSearchParams();
		for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") params.set(key, String(value));
		return request<JsonObject>(`/memory/decisions${params.size ? `?${params.toString()}` : ""}`);
	},
	searchMemory: (query: string, filters: { project_id?: string; goal_id?: string; limit?: number } = {}) => {
		const params = new URLSearchParams({ q: query });
		for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") params.set(key, String(value));
		return request<JsonObject>(`/memory/search?${params.toString()}`);
	},
	summarizeMemory: (filters: { project_id?: string; goal_id?: string } = {}) => {
		const params = new URLSearchParams();
		for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") params.set(key, value);
		return request<JsonObject>(`/memory/summary${params.size ? `?${params.toString()}` : ""}`);
	},
	linkMemory: (source_id: string, target_id: string, relation: string) =>
		request<JsonObject>("/memory/link", json("POST", { source_id, target_id, relation })),
	archiveMemory: (collection: string, record_id: string) =>
		request<JsonObject>("/memory/archive", json("POST", { collection, record_id })),
	getArtifactLinks: (artifactId: string) => request<JsonObject>(`/artifacts/${encodeURIComponent(artifactId)}/links`),
	linkArtifacts: (sourceArtifactId: string, targetArtifactId: string, relation = "related_to") =>
		request<JsonObject>(`/artifacts/${encodeURIComponent(sourceArtifactId)}/links`, json("POST", { target_artifact_id: targetArtifactId, relation })),
	unlinkArtifacts: (sourceArtifactId: string, targetArtifactId: string, relation = "related_to") => {
		const params = new URLSearchParams({ target_artifact_id: targetArtifactId, relation });
		return request<JsonObject>(`/artifacts/${encodeURIComponent(sourceArtifactId)}/links?${params.toString()}`, { method: "DELETE" });
	},
	analyzeImageArtifact: (artifactId: string, prompt = "Describe this image and extract any readable text.", saveArtifact = true) =>
		request<JsonObject>("/images/analyze-artifact", json("POST", { artifact_id: artifactId, prompt, save_artifact: saveArtifact })),
	getOpenApi: () => request<JsonObject>("/openapi.json"),
	listRuns: () => request<JsonObject>("/runs"),
	getRun: (runId: string) => request<JsonObject>(`/runs/${encodeURIComponent(runId)}`),
	resumeRun: (runId: string) => request<JsonObject>(`/runs/${encodeURIComponent(runId)}/resume`, { method: "POST" }),
	uploadVoice: async (file: File) => {
		const form = new FormData();
		form.append("audio", file);
		return request<JsonObject>("/voice/upload", { method: "POST", body: form });
	},
	processVoiceCapture: (audio_artifact_id: string, generate_summary = true) =>
		request<JsonObject>("/voice/process", json("POST", { audio_artifact_id, generate_summary })),
	activateVoiceFromArtifact: (artifact_id: string) => request<JsonObject>("/voice/activation", json("POST", { artifact_id })),
	playVoiceText: (text: string, language: "en" | "ta" | "ta-en" = "en") =>
		request<JsonObject>("/voice/playback", json("POST", { text, language })),
	retryVoiceSummary: (transcript_artifact_id: string) =>
		request<JsonObject>("/voice/retry-summary", json("POST", { transcript_artifact_id })),
	transcribeVoice: (artifact_id: string) => request<JsonObject>("/voice/transcript", json("POST", { artifact_id })),
	summarizeVoice: (artifact_id: string) => request<JsonObject>("/voice/summary", json("POST", { artifact_id })),
	saveVoiceResult: (sessionId: string, audio_artifact_id: string, transcript_artifact_id?: string, summary_artifact_id?: string) =>
		request<JsonObject>(`/sessions/${encodeURIComponent(sessionId)}/voice-result`, json("POST", { audio_artifact_id, ...(transcript_artifact_id ? { transcript_artifact_id } : {}), ...(summary_artifact_id ? { summary_artifact_id } : {}) })),
	getWakeWordStatus: () => request<JsonObject>("/voice/wake-word/status"),
	startWakeWord: () => request<JsonObject>("/voice/wake-word/start", { method: "POST" }),
	stopWakeWord: () => request<JsonObject>("/voice/wake-word/stop", { method: "POST" }),
};
