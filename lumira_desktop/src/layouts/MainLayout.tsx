import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, FormEvent, KeyboardEvent } from "react";
import {
	FiArrowUp, FiChevronDown, FiCode, FiCpu, FiCrosshair, FiMenu, FiPaperclip,
	FiSearch, FiSettings, FiSliders, FiX,
} from "react-icons/fi";
import { api, ApiError, type JsonObject } from "../api/client";
import { ChatSidebar, type ChatSession } from "../components/Chat/Chat";
import { RightPanel, type RightTab } from "../components/RightPanel/RightPanel";
import { Sidebar } from "../components/Sidebar/Sidebar";
import { ImageUnderstandingPanel } from "../components/ImageUnderstanding/ImageUnderstandingPanel";
import { ProviderDiagnosticsPanel } from "../components/Common/ProviderDiagnosticsPanel";
import {
	useAppStore, type LumiraMode, type PanelMode,
	type WorkspacePage,
} from "../store/appStore";
import "./MainLayout.css";

type SessionRecord = ChatSession & {
	workspace_id?: string;
	active_mode?: string | null;
	active_version?: string | null;
	goal_id?: string | null;
	context_snapshots?: unknown[];
};

type ApiResponse = JsonObject & {
	success?: boolean;
	session_id?: string;
	message?: string;
	detail?: unknown;
	clarification_required?: boolean;
	result?: JsonObject;
	context?: JsonObject;
};

type Message = {
	id: string;
	prompt?: string;
	transcript?: string;
	response?: ApiResponse;
	error?: string;
	pending?: boolean;
};

type ProjectRecord = { project: string; versions?: number; latest?: JsonObject | null };

const PAGE_TITLES: Record<WorkspacePage, string> = {
	chats: "AI Workspace", projects: "Projects", artifacts: "Artifacts", memory: "Memory",
	goals: "Goals", search: "Unified Search", generator: "Generator", business: "Business",
	operations: "Operations", features: "Feature Control Center", "image-understanding": "Image Analysis", settings: "Workspace Settings",
};

function object(value: unknown): JsonObject {
	return value !== null && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : {};
}

function records(value: unknown, key: string): JsonObject[] {
	const list = object(value)[key];
	return Array.isArray(list) ? list.map(object) : [];
}

function projectRecords(value: unknown): ProjectRecord[] {
	return records(value, "projects")
		.filter((item) => typeof item.project === "string")
		.map((item) => ({
			project: stringValue(item.project),
			versions: typeof item.versions === "number" ? item.versions : undefined,
			latest: item.latest ? object(item.latest) : null,
		}));
}

function stringValue(value: unknown, fallback = "") {
	return typeof value === "string" ? value : fallback;
}

function safeDisplay(value: unknown, key = ""): unknown {
	if (/password|api[_-]?key|jwt[_-]?secret|credential|chain[_-]?of[_-]?thought|hidden[_-]?prompt|private[_-]?state/i.test(key)) return "[redacted]";
	if (Array.isArray(value)) return value.map((item) => safeDisplay(item));
	if (value && typeof value === "object") {
		return Object.fromEntries(Object.entries(value).map(([childKey, child]) => [childKey, safeDisplay(child, childKey)]));
	}
	if (typeof value === "string" && value.length > 20_000) return `${value.slice(0, 20_000)}… [truncated]`;
	return value;
}

function formatError(error: unknown): { message: string; response: ApiResponse } {
	if (error instanceof ApiError) {
		const detail = object(error.body.detail);
		const result = Object.keys(detail).length ? detail : { status: "failed", code: `http_${error.status}`, message: error.message };
		return { message: error.message, response: { success: false, result } };
	}
	const message = error instanceof Error ? error.message : "The request failed.";
	return { message, response: { success: false, result: { status: "failed", code: "request_failed", message } } };
}

function modeFromSession(value?: string | null): LumiraMode | null {
	if (value === "personal" || value === "builder" || value === "growth" || value === "business" || value === "creator" || value === "generator" || value === "research" || value === "assistant" || value === "operations") return value;
	return null;
}

function titleForMode(mode: LumiraMode) {
	return mode === "auto" ? "Auto Category" : `${mode[0].toUpperCase()}${mode.slice(1)}`;
}

function isPanelMode(value: string): value is PanelMode {
	return value === "full" || value === "compact" || value === "hidden";
}

function cyclePanel(mode: PanelMode): PanelMode {
	return mode === "full" ? "compact" : mode === "compact" ? "hidden" : "full";
}

function panelWidth(mode: PanelMode, width: number, compactWidth: number) {
	return mode === "hidden" ? null : mode === "compact" ? `${compactWidth}px` : `${width}px`;
}

function MainLayout() {
	const promptInputRef = useRef<HTMLTextAreaElement>(null);
	const searchInputRef = useRef<HTMLInputElement>(null);
	const voiceFileRef = useRef<HTMLInputElement>(null);
	const mediaRecorderRef = useRef<MediaRecorder | null>(null);
	const mediaStreamRef = useRef<MediaStream | null>(null);
	const voiceChunksRef = useRef<Blob[]>([]);
	const voiceUnmountingRef = useRef(false);
	const attachmentFileRef = useRef<HTMLInputElement>(null);
	const [prompt, setPrompt] = useState("");
	const [workflow, setWorkflow] = useState<"brain" | "project">("brain");
	const [messages, setMessages] = useState<Message[]>([]);
	const [isSending, setIsSending] = useState(false);
	const [session, setSession] = useState<SessionRecord | null>(null);
	const [sessions, setSessions] = useState<SessionRecord[]>([]);
	const [isRestoringSession, setIsRestoringSession] = useState(() => Boolean(window.localStorage.getItem("lumira.sessionId")));
	const [connectionStatus, setConnectionStatus] = useState<"checking" | "online" | "offline">("checking");
	const [sessionError, setSessionError] = useState<string | null>(null);
	const [actionNotice, setActionNotice] = useState<string | null>(null);
	const [pageData, setPageData] = useState<JsonObject | null>(null);
	const [pageLoading, setPageLoading] = useState(false);
	const [pageError, setPageError] = useState<string | null>(null);
	const [pageRevision, setPageRevision] = useState(0);
	const [showArchivedArtifacts, setShowArchivedArtifacts] = useState(false);
	const [artifactQuery, setArtifactQuery] = useState("");
	const [artifactTypeFilter, setArtifactTypeFilter] = useState("");
	const [artifactOffset, setArtifactOffset] = useState(0);
	const [artifactPagination, setArtifactPagination] = useState<JsonObject>({ total: 0, limit: 50, offset: 0, has_more: false });
	const [artifactStats, setArtifactStats] = useState<JsonObject | null>(null);
	const [artifactActionBusy, setArtifactActionBusy] = useState<string | null>(null);
	const [selectedArtifact, setSelectedArtifact] = useState<JsonObject | null>(null);
	const [artifactDetailBusy, setArtifactDetailBusy] = useState(false);
	const [artifactDraftTitle, setArtifactDraftTitle] = useState("");
	const [artifactDraftContent, setArtifactDraftContent] = useState("");
	const [artifactCreateBusy, setArtifactCreateBusy] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");
	const [searchResult, setSearchResult] = useState<JsonObject | null>(null);
	const [searchBusy, setSearchBusy] = useState(false);
	const [memorySearchQuery, setMemorySearchQuery] = useState("");
	const [memorySearchResult, setMemorySearchResult] = useState<JsonObject | null>(null);
	const [memorySummary, setMemorySummary] = useState<JsonObject | null>(null);
	const [memoryBusy, setMemoryBusy] = useState(false);
	const [memoryLinkSource, setMemoryLinkSource] = useState("");
	const [memoryLinkTarget, setMemoryLinkTarget] = useState("");
	const [memoryLinkRelation, setMemoryLinkRelation] = useState("related_to");
	const [memoryArchiveCollection, setMemoryArchiveCollection] = useState("goals");
	const [memoryArchiveId, setMemoryArchiveId] = useState("");
	const [decisionText, setDecisionText] = useState("");
	const [decisionReason, setDecisionReason] = useState("");
	const [decisionAlternatives, setDecisionAlternatives] = useState("");
	const [decisionConstraints, setDecisionConstraints] = useState("");
	const [decisionConfidence, setDecisionConfidence] = useState(0.8);
	const [decisionRecords, setDecisionRecords] = useState<JsonObject[]>([]);
	const [goalTitle, setGoalTitle] = useState("");
	const [goalObjective, setGoalObjective] = useState("");
	const [goalDeadline, setGoalDeadline] = useState("");
	const [goalBusy, setGoalBusy] = useState(false);
	const [goalParentId, setGoalParentId] = useState("");
	const [goalObjectivesText, setGoalObjectivesText] = useState("");
	const [goalTree, setGoalTree] = useState<JsonObject | null>(null);
	const [goalPlan, setGoalPlan] = useState<JsonObject | null>(null);
	const [goalExecutionResult, setGoalExecutionResult] = useState<JsonObject | null>(null);
	const [goalDeliverables, setGoalDeliverables] = useState<JsonObject | null>(null);
	const [goalHistory, setGoalHistory] = useState<JsonObject | null>(null);
	const [goalReadiness, setGoalReadiness] = useState<JsonObject | null>(null);
	const [goalSummary, setGoalSummary] = useState<JsonObject | null>(null);
	const [goalIntelligence, setGoalIntelligence] = useState<JsonObject | null>(null);
	const [goalNextActions, setGoalNextActions] = useState<JsonObject | null>(null);
	const [goalMilestoneView, setGoalMilestoneView] = useState<JsonObject | null>(null);
	const [goalDependencies, setGoalDependenciesView] = useState<JsonObject | null>(null);
	const [recoverySnapshot, setRecoverySnapshot] = useState<JsonObject | null>(null);
	const [sessionHealth, setSessionHealth] = useState<JsonObject | null>(null);
	const [sessionWorkflows, setSessionWorkflows] = useState<JsonObject | null>(null);
	const [workflowTitle, setWorkflowTitle] = useState("");
	const [workflowTasksText, setWorkflowTasksText] = useState("");
	const [workflowSearchQuery, setWorkflowSearchQuery] = useState("");
	const [workflowSearchResult, setWorkflowSearchResult] = useState<JsonObject | null>(null);
	const [workflowGraph, setWorkflowGraph] = useState<JsonObject | null>(null);
	const [workflowTaskHistory, setWorkflowTaskHistory] = useState<JsonObject | null>(null);
	const [workflowTaskResult, setWorkflowTaskResult] = useState<JsonObject | null>(null);
	const [workflowTaskDetailBusy, setWorkflowTaskDetailBusy] = useState<string | null>(null);
	const [workflowCategory, setWorkflowCategory] = useState<"business" | "operations">("operations");
	const [projects, setProjects] = useState<ProjectRecord[]>([]);
	const [projectSearchQuery, setProjectSearchQuery] = useState("");
	const [projectSearchResult, setProjectSearchResult] = useState<JsonObject | null>(null);
	const [projectHealth, setProjectHealth] = useState<JsonObject | null>(null);
	const [projectManifest, setProjectManifest] = useState<JsonObject | null>(null);
	const [projectVersionComparison, setProjectVersionComparison] = useState<JsonObject | null>(null);
	const [projectIntegrityReport, setProjectIntegrityReport] = useState<JsonObject | null>(null);
	const [projectSecurityReport, setProjectSecurityReport] = useState<JsonObject | null>(null);
	const [projectReadinessAudit, setProjectReadinessAudit] = useState<JsonObject | null>(null);
	const [projectVersions, setProjectVersions] = useState<string[]>([]);
	const [projectFiles, setProjectFiles] = useState<string[]>([]);
	const [runs, setRuns] = useState<JsonObject[]>([]);
	const [selectedRun, setSelectedRun] = useState<JsonObject | null>(null);
	const [runDetailBusy, setRunDetailBusy] = useState<string | null>(null);
	const [selectedFile, setSelectedFile] = useState<string | null>(null);
	const [fileContent, setFileContent] = useState<string | null>(null);
	const [fileLoading, setFileLoading] = useState(false);
	const [rightTab, setRightTab] = useState<RightTab>("files");
	const [apiPaths, setApiPaths] = useState<string[]>([]);
	const [quickToolsOpen, setQuickToolsOpen] = useState(false);
	const [voiceBusy, setVoiceBusy] = useState(false);
	const [voiceRecording, setVoiceRecording] = useState(false);
	const [voiceRecordingError, setVoiceRecordingError] = useState("");
	const [wakeWordStatus, setWakeWordStatus] = useState<JsonObject>({ state: "stopped", listening: false, activated: false });
	const [wakeWordBusy, setWakeWordBusy] = useState(false);
	const [terminalCommands, setTerminalCommands] = useState<JsonObject>({});
	const [terminalRuns, setTerminalRuns] = useState<JsonObject[]>([]);
	const [terminalBusy, setTerminalBusy] = useState(false);
	const [previewUrl, setPreviewUrl] = useState<string | null>(null);
	const [previewStatus, setPreviewStatus] = useState<string | null>(null);
	const [previewInput, setPreviewInput] = useState("");
	const [workspaceView, setWorkspaceView] = useState<"chat" | "code">("chat");
	const [utilityPanel, setUtilityPanel] = useState<"notepad" | "plugins" | "imagine" | "todo" | null>(null);
	const [note, setNote] = useState(() => window.localStorage.getItem("lumira.notepad") ?? "");
	const [noteId, setNoteId] = useState<string | null>(null);
	const [noteSaveBusy, setNoteSaveBusy] = useState(false);
	const [noteSaveStatus, setNoteSaveStatus] = useState("Local draft");
	const [deviceRecords, setDeviceRecords] = useState<JsonObject[]>([]);
	const [deviceMessages, setDeviceMessages] = useState<JsonObject[]>([]);
	const [deviceMessageSearch, setDeviceMessageSearch] = useState("");
	const [deviceLoading, setDeviceLoading] = useState(false);
	const [deviceMessagesLoading, setDeviceMessagesLoading] = useState(false);
	const [deviceStatusBusy, setDeviceStatusBusy] = useState<string | null>(null);
	const [deviceSearch, setDeviceSearch] = useState("");
	const [deviceIdInput, setDeviceIdInput] = useState("");
	const [deviceTypeInput, setDeviceTypeInput] = useState("esp32");
	const [deviceCapabilitiesText, setDeviceCapabilitiesText] = useState("");
	const [devicePermissionsText, setDevicePermissionsText] = useState("telemetry.read");
	const [deviceConnection, setDeviceConnection] = useState("unverified");
	const [deviceBusy, setDeviceBusy] = useState(false);

	const navMode = useAppStore((state) => state.navMode);
	const chatMode = useAppStore((state) => state.chatMode);
	const rightMode = useAppStore((state) => state.rightMode);
	const navWidth = useAppStore((state) => state.navWidth);
	const chatWidth = useAppStore((state) => state.chatWidth);
	const rightWidth = useAppStore((state) => state.rightWidth);
	const topBarCompact = useAppStore((state) => state.topBarCompact);
	const inputMode = useAppStore((state) => state.inputMode);
	const focusMode = useAppStore((state) => state.focusMode);
	const activePage = useAppStore((state) => state.activePage);
	const activeMode = useAppStore((state) => state.activeMode);
	const selectedProject = useAppStore((state) => state.selectedProject);
	const selectedVersion = useAppStore((state) => state.selectedVersion);
	const setNavMode = useAppStore((state) => state.setNavMode);
	const setChatMode = useAppStore((state) => state.setChatMode);
	const setRightMode = useAppStore((state) => state.setRightMode);
	const setPanelWidth = useAppStore((state) => state.setPanelWidth);
	const setTopBarCompact = useAppStore((state) => state.setTopBarCompact);
	const setInputMode = useAppStore((state) => state.setInputMode);
	const setFocusMode = useAppStore((state) => state.setFocusMode);
	const setActivePage = useAppStore((state) => state.setActivePage);
	const setActiveMode = useAppStore((state) => state.setActiveMode);
	const setSelectedProject = useAppStore((state) => state.setSelectedProject);

	const effectiveNavMode = focusMode ? "hidden" : navMode;
	const effectiveChatMode = focusMode ? "hidden" : chatMode;
	const effectiveRightMode = focusMode ? "hidden" : rightMode;
	const columns = [
		panelWidth(effectiveNavMode, navWidth, 62),
		panelWidth(effectiveChatMode, chatWidth, 66),
		"minmax(0, 1fr)",
		workspaceView === "chat" && !focusMode ? "88px" : panelWidth(effectiveRightMode, rightWidth, 68),
	].filter((value): value is string => value !== null).join(" ");
	const currentProject = selectedProject ?? session?.active_project ?? null;
	const currentTitle = session?.current_goal || currentProject || PAGE_TITLES[activePage];

	const loadSessions = useCallback(async () => {
		try {
			const response = await api.listSessions();
			setSessions(records(response, "sessions") as SessionRecord[]);
		} catch {
			// Existing saved sessions remain visible when the backend is temporarily offline.
		}
	}, []);

	useEffect(() => {
		const handleGlobalShortcut = (event: globalThis.KeyboardEvent) => {
			if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
				event.preventDefault();
				setActivePage("search");
				window.setTimeout(() => searchInputRef.current?.focus(), 0);
			}
			if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "f") {
				event.preventDefault();
				setFocusMode(!focusMode);
			}
		};
		window.addEventListener("keydown", handleGlobalShortcut);
		return () => window.removeEventListener("keydown", handleGlobalShortcut);
	}, [setActivePage, setFocusMode, focusMode]);

	useEffect(() => {
		let cancelled = false;
		void api.health().then(() => { if (!cancelled) setConnectionStatus("online"); }).catch(() => { if (!cancelled) setConnectionStatus("offline"); });
		void loadSessions();
		const storedId = window.localStorage.getItem("lumira.sessionId");
		if (!storedId) {
			setIsRestoringSession(false);
			return () => { cancelled = true; };
		}
		void api.getSession(storedId)
			.then(async (result) => {
				let loaded = result as SessionRecord;
				if (loaded.status === "paused") loaded = await api.resumeSession(storedId) as SessionRecord;
				if (cancelled) return;
				setSession(loaded);
				setActiveMode(modeFromSession(loaded.active_mode) ?? "auto");
				if (loaded.active_project) setSelectedProject(loaded.active_project, loaded.active_version ?? null);
				setMessages((loaded.recent_messages ?? []).map((item, index) => item.role === "user"
					? { id: `restored-${index}`, prompt: item.content }
					: { id: `restored-${index}`, transcript: item.content }));
				void loadSessions();
			})
			.catch(() => {
				if (cancelled) return;
				setSessionError("The saved session could not be restored yet. Its ID was preserved; check the backend connection and reload to retry.");
				setActionNotice("Session recovery was unavailable. Your saved session ID was preserved so you can retry after reconnecting the backend.");
			})
			.finally(() => { if (!cancelled) setIsRestoringSession(false); });
		return () => { cancelled = true; };
	}, [loadSessions, setActiveMode, setSelectedProject]);

	useEffect(() => {
		let cancelled = false;
		async function loadPage() {
			if (activePage === "chats" || activePage === "search" || activePage === "generator" || activePage === "image-understanding") {
				setPageLoading(false);
				setPageError(null);
				return;
			}
			setPageLoading(true);
			setPageError(null);
			try {
				let result: unknown;
				if (activePage === "projects") { const [projectResult, summary] = await Promise.all([api.listProjects(), api.projectSummary().catch(() => null)]); result = { ...object(projectResult), summary }; }
				else if (activePage === "artifacts") {
					const artifactResult = await api.listArtifacts(showArchivedArtifacts, { q: artifactQuery.trim() || undefined, artifact_type: artifactTypeFilter || undefined, limit: 50, offset: artifactOffset });
					result = artifactResult;
					if (!cancelled) setArtifactPagination(object(artifactResult.pagination));
					try {
						const statsResult = await api.artifactStats();
						if (!cancelled) setArtifactStats(object(statsResult.stats));
					} catch {
						if (!cancelled) setArtifactStats(null);
					}
				}
				else if (activePage === "goals") {
					const [goalResult, summaryResult] = await Promise.all([api.listGoals(), api.getGoalSummary().catch(() => null)]);
					result = goalResult;
					if (!cancelled) setGoalSummary(summaryResult);
				}
				else if (activePage === "features") result = await api.listFeatures();
				else if (activePage === "memory") result = await api.getRelevantMemory(searchQuery || "recent activity", session?.session_id);
				else if (activePage === "business") {
					const [goals, workflows] = await Promise.all([api.listGoals(), api.listWorkflows("business")]);
					result = { goals, workflows };
				} else if (activePage === "operations") {
					const [workflows, runs, workflowSummary, workflowAttention] = await Promise.all([api.listWorkflows("operations"), api.listRuns(), api.workflowSummary(undefined, "operations").catch(() => null), api.workflowAttention(undefined, 30).catch(() => null)]);
					result = { workflows, runs, workflowSummary, workflowAttention };
				} else if (activePage === "settings") {
					const [health, schema, intelligence, history, sessionSummary] = await Promise.all([api.health(), api.getOpenApi(), api.intelligenceStatus(), api.intelligenceHistory(10, session?.session_id), api.sessionSummary().catch(() => null)]);
					result = { health, schema, intelligence, history, sessionSummary };
					const paths = object(schema).paths;
					if (!cancelled && paths && typeof paths === "object") setApiPaths(Object.keys(paths));
				}
				if (!cancelled) setPageData(object(result));
			} catch (error) {
				if (!cancelled) setPageError(formatError(error).message);
			} finally {
				if (!cancelled) setPageLoading(false);
			}
		}
		void loadPage();
		return () => { cancelled = true; };
	}, [activePage, pageRevision, searchQuery, session?.session_id, showArchivedArtifacts, artifactQuery, artifactTypeFilter, artifactOffset]);

	useEffect(() => {
		let cancelled = false;
		void api.listProjects().then((response) => {
			if (!cancelled) setProjects(projectRecords(response));
		}).catch(() => undefined);
		return () => { cancelled = true; };
	}, [pageRevision]);

	useEffect(() => {
		let cancelled = false;
		void api.getOpenApi().then((schema) => {
			const paths = object(schema).paths;
			if (!cancelled && paths && typeof paths === "object") setApiPaths(Object.keys(paths));
		}).catch(() => undefined);
		return () => { cancelled = true; };
	}, []);

	useEffect(() => {
		let cancelled = false;
		void api.listRuns().then((response) => { if (!cancelled) setRuns(records(response, "runs")); }).catch(() => undefined);
		return () => { cancelled = true; };
	}, [pageRevision]);

	useEffect(() => {
		if (!currentProject) {
			setProjectVersions([]);
			setProjectFiles([]);
			return;
		}
		let cancelled = false;
		void (async () => {
			try {
				const versionsResponse = await api.getProjectVersions(currentProject);
				const versions = Array.isArray(object(versionsResponse).versions)
					? (object(versionsResponse).versions as unknown[]).filter((item): item is string => typeof item === "string")
					: [];
				if (cancelled) return;
				setProjectVersions(versions);
				const targetVersion = selectedVersion && versions.includes(selectedVersion) ? selectedVersion : versions.at(-1) ?? null;
				if (targetVersion !== selectedVersion) setSelectedProject(currentProject, targetVersion);
				if (!targetVersion) { setProjectFiles([]); return; }
				const fileResponse = await api.getProjectFiles(currentProject, targetVersion);
				if (!cancelled) setProjectFiles(Array.isArray(object(fileResponse).files) ? (object(fileResponse).files as unknown[]).filter((item): item is string => typeof item === "string") : []);
			} catch {
				if (!cancelled) { setProjectVersions([]); setProjectFiles([]); }
			}
		})();
		return () => { cancelled = true; };
	}, [currentProject, selectedVersion, pageRevision, setSelectedProject]);

	useEffect(() => {
		let cancelled = false;
		if (!currentProject || !selectedVersion) {
			setTerminalCommands({});
			setTerminalRuns([]);
			setPreviewUrl(null);
			setPreviewStatus(null);
			return () => { cancelled = true; };
		}
		void Promise.all([
			api.getTerminalCommands(currentProject, selectedVersion),
			api.getTerminalRuns(currentProject, selectedVersion),
			api.getProjectPreview(currentProject, selectedVersion),
		]).then(([commands, runsResponse, preview]) => {
			if (cancelled) return;
			setTerminalCommands(object(commands));
			setTerminalRuns(records(runsResponse, "runs"));
			const item = object(object(preview).preview);
			setPreviewUrl(typeof item.url === "string" && item.status === "registered" ? item.url : null);
			setPreviewStatus(typeof item.status === "string" ? item.status : null);
		}).catch(() => undefined);
		return () => { cancelled = true; };
	}, [currentProject, selectedVersion]);

	useEffect(() => {
		if (activePage !== "settings") return;
		let cancelled = false;
		setDeviceLoading(true);
		void api.listDevices({ limit: 200 }).then((response) => {
			if (!cancelled) setDeviceRecords(records(response, "devices"));
		}).catch((error) => {
			if (!cancelled) setPageError(`Could not load device registry: ${formatError(error).message}`);
		}).finally(() => {
			if (!cancelled) setDeviceLoading(false);
		});
		setDeviceMessagesLoading(true);
		void api.listDeviceMessages(50).then((response) => {
			if (!cancelled) setDeviceMessages(records(response, "messages"));
		}).catch((error) => {
			if (!cancelled) setPageError(`Could not load recent device messages: ${formatError(error).message}`);
		}).finally(() => {
			if (!cancelled) setDeviceMessagesLoading(false);
		});
		return () => { cancelled = true; };
	}, [activePage, pageRevision]);

	useEffect(() => {
		window.localStorage.setItem("lumira.notepad", note);
	}, [note]);



	useEffect(() => {
		let cancelled = false;
		void api.listNotes().then((response) => {
			const saved = records(response, "notes").find((item) => item.title === "Quick Note");
			if (cancelled || !saved) return;
			if (typeof saved.note_id === "string") setNoteId(saved.note_id);
			if (typeof saved.content === "string" && !(window.localStorage.getItem("lumira.notepad") ?? "").trim()) setNote(saved.content);
			setNoteSaveStatus("Synced from Lumira");
		}).catch(() => undefined);
		return () => { cancelled = true; };
	}, []);

	useEffect(() => {
		let cancelled = false;
		const refreshWakeWordStatus = async () => {
			try {
				const status = await api.getWakeWordStatus();
				if (!cancelled) setWakeWordStatus(status);
			} catch {
				if (!cancelled) setWakeWordStatus({ state: "unavailable", listening: false, activated: false });
			}
		};
		void refreshWakeWordStatus();
		const timer = window.setInterval(() => { void refreshWakeWordStatus(); }, 2000);
		return () => { cancelled = true; window.clearInterval(timer); };
	}, []);

	useEffect(() => {
		const listener = (event: globalThis.KeyboardEvent) => {
			const command = event.ctrlKey || event.metaKey;
			const key = event.key.toLowerCase();
			if (command && event.shiftKey && key === "b") { event.preventDefault(); setChatMode(cyclePanel(chatMode)); }
			else if (command && event.shiftKey && key === "f") { event.preventDefault(); setFocusMode(!focusMode); }
			else if (command && key === "b") { event.preventDefault(); setNavMode(cyclePanel(navMode)); }
			else if (command && key === "j") { event.preventDefault(); setRightMode(cyclePanel(rightMode)); }
			else if (command && key === "k") { event.preventDefault(); setActivePage("search"); window.setTimeout(() => searchInputRef.current?.focus(), 0); }
			else if (event.key === "Escape" && focusMode) setFocusMode(false);
		};
		window.addEventListener("keydown", listener);
		return () => window.removeEventListener("keydown", listener);
	}, [chatMode, focusMode, navMode, rightMode, setActivePage, setChatMode, setFocusMode, setNavMode, setRightMode]);

	async function runProjectTerminal(commandId: string) {
		if (!currentProject || !selectedVersion) return;
		const accepted = window.confirm(
			"Run a validation command for this project? Test/build scripts can execute project code. " +
			"This runner is allowlisted but is NOT an OS sandbox. Continue only if you trust this project's files."
		);
		if (!accepted) return;
		setTerminalBusy(true);
		try {
			const result = await api.runTerminalCommand(currentProject, selectedVersion, commandId, true);
			const run = object(object(result).run);
			setTerminalRuns((current) => [run, ...current].filter((item) => Object.keys(item).length).slice(0, 20));
		} catch (error) {
			setActionNotice(formatError(error).message);
		} finally {
			setTerminalBusy(false);
		}
	}

	async function registerPreview() {
		if (!currentProject || !selectedVersion || !previewInput.trim()) return;
		try {
			const result = await api.registerProjectPreview(currentProject, selectedVersion, previewInput.trim());
			const item = object(object(result).preview);
			setPreviewUrl(typeof item.url === "string" ? item.url : null);
			setPreviewStatus(typeof item.status === "string" ? item.status : null);
			setPreviewInput("");
		} catch (error) {
			setActionNotice(formatError(error).message);
		}
	}

	async function stopPreview() {
		if (!currentProject || !selectedVersion) return;
		try {
			await api.stopProjectPreview(currentProject, selectedVersion);
			setPreviewUrl(null);
			setPreviewStatus("stopped");
		} catch (error) {
			setActionNotice(formatError(error).message);
		}
	}

	const projectItems = useMemo(() => projects.filter((item) => typeof item.project === "string"), [projects]);

	async function startNewSession(projectId?: string) {
		try {
			setSessionError(null);
			const created = await api.createSession("default", projectId) as SessionRecord;
			window.localStorage.setItem("lumira.sessionId", created.session_id);
			setSession(created);
			setMessages([]);
			setSelectedProject(projectId ?? created.active_project ?? null, null);
			await loadSessions();
			return created;
		} catch (error) {
			setSessionError(formatError(error).message);
			return null;
		}
	}

	async function ensureProjectSession(projectId?: string) {
		if (!projectId || session?.active_project === projectId) return session;
		return await startNewSession(projectId);
	}

	async function retrySessionRestore() {
		const storedId = window.localStorage.getItem("lumira.sessionId");
		if (!storedId || isRestoringSession) {
			setSessionError(storedId ? "Session recovery is already in progress." : "No saved session ID is available to restore.");
			return;
		}
		setIsRestoringSession(true);
		setSessionError(null);
		try {
			let loaded = await api.getSession(storedId) as SessionRecord;
			if (loaded.status === "paused") loaded = await api.resumeSession(storedId) as SessionRecord;
			setSession(loaded);
			setActiveMode(modeFromSession(loaded.active_mode) ?? "auto");
			if (loaded.active_project) setSelectedProject(loaded.active_project, loaded.active_version ?? null);
			setMessages((loaded.recent_messages ?? []).map((item, index) => item.role === "user" ? { id: `restored-${Date.now()}-${index}`, prompt: item.content } : { id: `restored-${Date.now()}-${index}`, transcript: item.content }));
			setActionNotice("Saved session restored.");
			await loadSessions();
		} catch (error) {
			setSessionError(`Session restoration failed: ${formatError(error).message}. The saved session ID remains available for another retry.`);
		} finally { setIsRestoringSession(false); }
	}

	async function updateSessionFromServer(sessionId: string) {
		try {
			const loaded = await api.getSession(sessionId) as SessionRecord;
			setSession(loaded);
			if (loaded.active_project) setSelectedProject(loaded.active_project, loaded.active_version ?? null);
			setActiveMode(modeFromSession(loaded.active_mode) ?? activeMode);
		} catch {
			// The command result remains visible even if the session refresh fails.
		}
	}

	async function submitInput(rawInput: string, options: { projectPrefix?: boolean; projectId?: string } = {}) {
		const input = rawInput.trim();
		if (!input || isSending || isRestoringSession) return;
		const actualInput = options.projectPrefix ? `Generate project: ${input}` : input;
		const messageId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
		setMessages((current) => [...current, { id: messageId, prompt: actualInput, pending: true }]);
		setIsSending(true);
		setActionNotice(null);
		try {
			const targetSession = await ensureProjectSession(options.projectId);
			const result = await api.command(actualInput, targetSession?.session_id ?? session?.session_id) as ApiResponse;
			const sessionId = stringValue(result.session_id);
			if (sessionId) {
				window.localStorage.setItem("lumira.sessionId", sessionId);
				await updateSessionFromServer(sessionId);
			}
			setMessages((current) => current.map((message) => message.id === messageId ? { ...message, response: result, pending: false } : message));
			await loadSessions();
			setPageRevision((current) => current + 1);
		} catch (error) {
			const failure = formatError(error);
			setMessages((current) => current.map((message) => message.id === messageId ? { ...message, error: failure.message, response: failure.response, pending: false } : message));
		} finally {
			setIsSending(false);
		}
	}

	async function submitPrompt(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const input = prompt.trim();
		if (!input) return;
		setPrompt("");
		await submitInput(input, { projectPrefix: workflow === "project" });
	}

	async function selectProject(projectName: string): Promise<{ files: string[]; version: string | null }> {
		setSelectedProject(projectName, null);
		setRightTab("files");
		setActivePage("projects");
		try {
			const versionsResponse = await api.getProjectVersions(projectName);
			const versions = Array.isArray(object(versionsResponse).versions)
				? (object(versionsResponse).versions as unknown[]).filter((item): item is string => typeof item === "string")
				: [];
			const version = versions.at(-1) ?? null;
			setProjectVersions(versions);
			setSelectedProject(projectName, version);
			if (version) {
				const fileResponse = await api.getProjectFiles(projectName, version);
				const files = Array.isArray(object(fileResponse).files) ? (object(fileResponse).files as unknown[]).filter((item): item is string => typeof item === "string") : [];
				setProjectFiles(files);
				return { files, version };
			}
			setProjectFiles([]);
			return { files: [], version: null };
		} catch (error) {
			setActionNotice(formatError(error).message);
			return { files: [], version: null };
		}
	}

	async function selectVersion(version: string) {
		if (!currentProject) return;
		setSelectedProject(currentProject, version);
		try {
			const fileResponse = await api.getProjectFiles(currentProject, version);
			setProjectFiles(Array.isArray(object(fileResponse).files) ? (object(fileResponse).files as unknown[]).filter((item): item is string => typeof item === "string") : []);
			setSelectedFile(null);
			setFileContent(null);
		} catch (error) {
			setActionNotice(formatError(error).message);
		}
	}

	async function selectFile(file: string, projectName = currentProject, versionName = selectedVersion) {
		if (!projectName || !versionName) return;
		setSelectedFile(file);
		setFileContent(null);
		setFileLoading(true);
		setRightTab("code");
		try {
			const result = await api.getProjectFile(projectName, versionName, file);
			if (object(result).success === false) throw new Error(stringValue(object(result).message, "File could not be loaded."));
			setFileContent(stringValue(object(result).content));
		} catch (error) {
			setActionNotice(formatError(error).message);
		} finally {
			setFileLoading(false);
		}
	}

	async function activateMode(mode: LumiraMode) {
		if (mode === "auto") {
			try {
				if (session?.session_id) await api.selectMode(session.session_id, "auto");
				setActiveMode("auto");
				setSession((current) => current ? { ...current, active_mode: null } : current);
				setActionNotice("Auto Category is active; Lumira will detect the mode for each request.");
			} catch (error) {
				setActionNotice(formatError(error).message);
			}
			return;
		}
		try {
			const targetSession = session ?? await startNewSession();
			if (!targetSession?.session_id) throw new Error("Could not create or restore an active session.");
			const response = await api.selectMode(targetSession.session_id, mode) as ApiResponse;
			if (response.success === false) throw new Error(stringValue(response.message, `Could not activate ${mode} mode.`));
			setActiveMode(mode);
			window.localStorage.setItem("lumira.sessionId", targetSession.session_id);
			await updateSessionFromServer(targetSession.session_id);
			setActionNotice(`${titleForMode(mode)} is active for this session.`);
			await loadSessions();
		} catch (error) {
			setActionNotice(formatError(error).message);
		}
	}

	function navigate(page: WorkspacePage) {
		setActivePage(page);
		if (page === "generator" || page === "business" || page === "operations") void activateMode(page);
		if (page === "search") window.setTimeout(() => searchInputRef.current?.focus(), 0);
	}

	async function runSearch(query = searchQuery) {
		const value = query.trim();
		if (!value) return;
		setSearchBusy(true);
		setSearchResult(null);
		setPageError(null);
		setActivePage("search");
		try { setSearchResult(await api.search(value)); }
		catch (error) { setPageError(formatError(error).message); }
		finally { setSearchBusy(false); }
	}

	async function createGoal(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!goalTitle.trim() || goalBusy) return;
		setGoalBusy(true);
		setPageError(null);
		try {
			await api.createGoal(goalTitle.trim(), goalObjective.trim(), undefined, currentProject ?? undefined, goalDeadline || undefined);
			setGoalTitle("");
			setGoalObjective("");
			setGoalDeadline("");
			setActionNotice("Goal saved to durable memory.");
			setPageRevision((current) => current + 1);
		} catch (error) { setPageError(formatError(error).message); }
		finally { setGoalBusy(false); }
	}

	async function showGoalHistory(goalId: string) {
		setPageError(null);
		try { setGoalHistory(await api.getGoalHistory(goalId)); }
		catch (error) { setPageError(formatError(error).message); }
	}

	async function showGoalReadiness(goalId: string) {
		setPageError(null);
		try {
			setGoalReadiness(await api.getGoalReadiness(goalId));
			setActionNotice("Goal readiness refreshed from persisted dependencies, blockers, deadline, and linked workflows.");
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function showGoalDependencies(goalId: string) {
		setPageError(null);
		try { setGoalDependenciesView(await api.getGoalDependencies(goalId)); }
		catch (error) { setPageError(formatError(error).message); }
	}

	async function manageGoalBlockers(goal: JsonObject) {
		const goalId = stringValue(goal.goal_id);
		const blockers = Array.isArray(goal.blockers) ? goal.blockers.filter((item): item is string => typeof item === "string") : [];
		const action = window.prompt(`Current blockers:\n${blockers.map((item, index) => `${index + 1}. ${item}`).join("\n") || "None"}\n\nType ADD to add a blocker, or REMOVE to remove one exact blocker.`);
		if (!action) return;
		try {
			if (action.trim().toLowerCase() === "add") {
				const blocker = window.prompt("Describe the blocker (maximum 500 characters):")?.trim();
				if (!blocker) return;
				await api.addGoalBlocker(goalId, blocker);
				setActionNotice("Goal blocker persisted.");
			} else if (action.trim().toLowerCase() === "remove") {
				const blocker = window.prompt("Enter the exact blocker text to remove:")?.trim();
				if (!blocker) return;
				await api.removeGoalBlocker(goalId, blocker);
				setActionNotice("Goal blocker removed.");
			} else return;
			setPageRevision((current) => current + 1);
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function saveRecoverySnapshot() {
		if (!session?.session_id) { setActionNotice("Start or select a session before saving a recovery snapshot."); return; }
		setPageError(null);
		try {
			const result = await api.createRecoverySnapshot(session.session_id);
			setRecoverySnapshot(result);
			const summary = object(result.resume_summary);
			setActionNotice(`Recovery snapshot saved: ${Number(summary.pending_task_count ?? 0)} pending task(s), ${Number(summary.blocker_count ?? 0)} blocker(s).`);
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function generateGoalPlan(goalId: string) {
		setPageError(null);
		try {
			const readiness = await api.getGoalReadiness(goalId);
			setGoalReadiness(readiness);
			if (readiness.ready_to_plan !== true) {
				setPageError("Goal planning is blocked. Review the readiness details and resolve blockers or inspect the existing workflow first.");
				return;
			}
			const result = await api.generateGoalPlan(goalId, "operations", session?.session_id);
			setGoalPlan(result);
			setGoalTree(await api.getGoalTree(goalId));
			setActionNotice(`Planner created a persistent workflow with ${records({ tasks: object(result.workflow).tasks }, "tasks").length} task(s).`);
			setPageRevision((current) => current + 1);
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function runGoalWorkflows(goalId: string) {
		if (!window.confirm("Run up to 3 dependency-ready tasks across this goal’s saved workflows? Agent results will be saved to task history and the Artifact Manager.")) return;
		setPageError(null);
		try {
			const result = await api.runGoalReadyWorkflows(goalId, 3);
			setGoalExecutionResult(result);
			setActionNotice(`Goal execution recorded ${Number(result.task_outcomes_count ?? 0)} task outcome(s); stop reason: ${stringValue(result.stop_reason, "unknown")}.`);
			setPageRevision((current) => current + 1);
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function loadGoalDeliverables(goalId: string) {
		setPageError(null);
		try {
			setGoalDeliverables(await api.listGoalDeliverables(goalId));
			setActionNotice("Loaded stored outputs across workflows linked to this goal.");
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function setSessionGoal(goal: JsonObject) {
		if (!session?.session_id) { setActionNotice("Start a session before linking an active goal."); return; }
		try {
			const result = await api.updateSessionContext(session.session_id, { goal_id: stringValue(goal.goal_id), current_goal: stringValue(goal.title) });
			setSession(result as SessionRecord);
			setActionNotice("Active goal linked to this session.");
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function setGoalPriority(goalId: string, priority: "low" | "normal" | "high" | "urgent") {
		setPageError(null);
		try {
			await api.updateGoal(goalId, { priority });
			setActionNotice(`Goal priority changed to ${priority}.`);
			setPageRevision((current) => current + 1);
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function setGoalDependencies(goalId: string, dependencies: string[]) {
		setPageError(null);
		try {
			const currentGoal = goals.find((item) => stringValue(item.goal_id) === goalId);
			const currentDependencies = Array.isArray(currentGoal?.dependencies) ? currentGoal.dependencies.filter((item): item is string => typeof item === "string") : [];
			for (const dependencyId of currentDependencies.filter((item) => !dependencies.includes(item))) await api.removeGoalDependency(goalId, dependencyId);
			for (const dependencyId of dependencies.slice(0, 50).filter((item) => !currentDependencies.includes(item))) await api.addGoalDependency(goalId, dependencyId);
			setActionNotice("Goal dependencies saved with server-side cycle checks. Planning waits for prerequisites to complete.");
			setPageRevision((current) => current + 1);
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function setGoalProgress(goalId: string, progress: number, currentStatus?: string) {
		const bounded = Math.max(0, Math.min(100, Math.round(progress)));
		setPageError(null);
		try {
			const statusUpdate = bounded === 100 ? "completed" : currentStatus === "completed" ? "active" : undefined;
			await api.updateGoal(goalId, { progress: bounded, ...(statusUpdate ? { status: statusUpdate } : {}) });
			setActionNotice(`Goal progress updated to ${bounded}%.`);
			setPageRevision((current) => current + 1);
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function setGoalStatus(goalId: string, status: "active" | "paused" | "completed" | "blocked" | "cancelled") {
		setPageError(null);
		try {
			await api.updateGoal(goalId, { status, ...(status === "completed" ? { progress: 100 } : {}) });
			setActionNotice(`Goal status changed to ${status}.`);
			setPageRevision((current) => current + 1);
			if (goalTree && stringValue(object(goalTree.goal_tree).goal_id) === goalId) setGoalTree(await api.getGoalTree(goalId));
		} catch (error) { setPageError(formatError(error).message); }
	}

	async function decomposeGoal(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const objectives = goalObjectivesText.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
		if (!goalParentId || !objectives.length || goalBusy) return;
		setGoalBusy(true);
		setPageError(null);
		try {
			await api.decomposeGoal(goalParentId, objectives);
			setGoalObjectivesText("");
			setGoalTree(await api.getGoalTree(goalParentId));
			setActionNotice(`Created ${objectives.length} objective(s) under the selected goal.`);
			setPageRevision((current) => current + 1);
		} catch (error) { setPageError(formatError(error).message); }
		finally { setGoalBusy(false); }
	}

	async function loadGoalNextActions() {
		setGoalBusy(true);
		setPageError(null);
		try { setGoalNextActions(await api.getGoalNextActions(currentProject ?? undefined)); }
		catch (error) { setPageError(formatError(error).message); }
		finally { setGoalBusy(false); }
	}

	async function showGoalTree(goalId: string) {
		setGoalParentId(goalId);
		setPageError(null);
		try { setGoalTree(await api.getGoalTree(goalId)); }
		catch (error) { setPageError(formatError(error).message); }
	}


	async function createStandaloneWorkflow(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const title = workflowTitle.trim();
		const tasks = workflowTasksText.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
		if (!title || !tasks.length || goalBusy) return;
		if (tasks.length > 20) { setPageError("A workflow can contain at most 20 tasks. Split the work into smaller workflows."); return; }
		if (tasks.some((task) => task.length > 500)) { setPageError("Each workflow task must be 500 characters or fewer."); return; }
		setGoalBusy(true);
		setPageError(null);
		try {
			const result = await api.createWorkflow({
				category: workflowCategory,
				title,
				request: title,
				tasks,
				...(session?.session_id ? { session_id: session.session_id } : {}),
				...(currentProject ? { project_id: currentProject } : {}),
			});
			setWorkflowTitle("");
			setWorkflowTasksText("");
			setActionNotice(`Saved workflow “${title}” with ${tasks.length} task(s). Nothing was executed.`);
			setWorkflowGraph(null);
			setPageRevision((current) => current + 1);
			const workflowId = stringValue(object(result.workflow).workflow_id, stringValue(result.workflow_id));
			if (workflowId) setWorkflowGraph(await api.workflowDependencyGraph(workflowId));
		} catch (error) { setPageError(formatError(error).message); }
		finally { setGoalBusy(false); }
	}

	async function createGoalWorkflow(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const tasks = workflowTasksText.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
		if (!goalParentId || !workflowTitle.trim() || !tasks.length || goalBusy) return;
		setGoalBusy(true);
		setPageError(null);
		try {
			await api.createWorkflow({ category: workflowCategory, title: workflowTitle.trim(), request: workflowTitle.trim(), tasks, goal_id: goalParentId, ...(session?.session_id ? { session_id: session.session_id } : {}), ...(currentProject ? { project_id: currentProject } : {}) });
			setWorkflowTitle("");
			setWorkflowTasksText("");
			setGoalTree(await api.getGoalTree(goalParentId));
			setActionNotice(`Saved ${tasks.length} task(s) linked to the selected goal.`);
			setPageRevision((current) => current + 1);
		} catch (error) { setPageError(formatError(error).message); }
		finally { setGoalBusy(false); }
	}

	async function toggleWakeWordListener() {
		if (wakeWordBusy) return;
		setWakeWordBusy(true);
		setActionNotice(null);
		try {
			const result = wakeWordStatus.listening === true
				? await api.stopWakeWord()
				: await api.startWakeWord();
			setWakeWordStatus(result);
		} catch (error) {
			setActionNotice(formatError(error).message);
			try { setWakeWordStatus(await api.getWakeWordStatus()); } catch { /* keep last known state */ }
		} finally {
			setWakeWordBusy(false);
		}
	}

	async function startVoiceRecording() {
		if (voiceBusy || voiceRecording) return;
		setVoiceRecordingError("");
		if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
			setVoiceRecordingError("Microphone recording is not supported in this browser. Attach an audio file instead.");
			return;
		}
		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
			mediaStreamRef.current = stream;
			const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus", "audio/ogg"].find((candidate) => MediaRecorder.isTypeSupported(candidate));
			const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
			voiceChunksRef.current = [];
			mediaRecorderRef.current = recorder;
			recorder.addEventListener("dataavailable", (event: BlobEvent) => {
				if (event.data.size > 0) voiceChunksRef.current.push(event.data);
			});
			recorder.addEventListener("stop", () => {
				const recordedType = recorder.mimeType || mimeType || "audio/webm";
				const extension = recordedType.includes("mp4") ? "m4a" : recordedType.includes("ogg") ? "ogg" : "webm";
				const blob = new Blob(voiceChunksRef.current, { type: recordedType });
				voiceChunksRef.current = [];
				mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
				mediaStreamRef.current = null;
				mediaRecorderRef.current = null;
				setVoiceRecording(false);
				if (blob.size === 0) {
					setVoiceRecordingError("No audio was captured. Check microphone permission and try again.");
					return;
				}
				const file = new File([blob], `lumira-voice-${Date.now()}.${extension}`, { type: recordedType });
				void uploadVoice(file);
			});
			recorder.addEventListener("error", () => {
				setVoiceRecordingError("Microphone recording failed. You can retry or attach an audio file.");
				setVoiceRecording(false);
				mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
				mediaStreamRef.current = null;
				mediaRecorderRef.current = null;
			});
			recorder.start(500);
			setVoiceRecording(true);
		} catch (error) {
			mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
			mediaStreamRef.current = null;
			setVoiceRecordingError(error instanceof Error && error.name === "NotAllowedError"
				? "Microphone permission was denied. Allow microphone access or attach an audio file."
				: formatError(error).message);
		}
	}

	function stopVoiceRecording() {
		const recorder = mediaRecorderRef.current;
		if (recorder && recorder.state !== "inactive") recorder.stop();
	}

	useEffect(() => () => {
		voiceUnmountingRef.current = true;
		const recorder = mediaRecorderRef.current;
		if (recorder && recorder.state !== "inactive") recorder.stop();
		mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
		mediaStreamRef.current = null;
	}, []);

	async function uploadVoice(file?: File) {
		if (!file || voiceBusy) return;
		setVoiceBusy(true);
		setActionNotice(null);
		try {
			const upload = await api.uploadVoice(file);
			const artifact = object(object(upload).data).artifact;
			const artifactId = stringValue(object(artifact).artifact_id);
			if (!artifactId) throw new Error("Audio upload returned no artifact identifier.");
			let result: JsonObject = { success: true, capability: "voice_capture", status: "captured", artifact };
			let displayedText = "";
			let transcriptArtifactId = "";
			let summaryArtifactId = "";
			try {
				const pipeline = await api.processVoiceCapture(artifactId, true);
				const transcription = object(pipeline.transcription);
				const pipelineSummary = object(pipeline.summary);
				result = { ...result, voice_pipeline: pipeline, transcript: transcription, summary: pipelineSummary, success: pipeline.success === true, status: stringValue(pipeline.stage, "captured") };
				summaryArtifactId = stringValue(pipeline.summary_artifact_id);
				result = { ...result, transcript: transcription };
				if (transcription.success === true) {
					const transcriptText = stringValue(transcription.transcript_text).trim();
					if (transcriptText) displayedText = `Transcript:\n${transcriptText}`;
					transcriptArtifactId = stringValue(object(transcription.transcript_artifact).artifact_id, stringValue(pipeline.transcript_artifact_id));
					if (transcriptArtifactId) {
						try {
							const summary = pipelineSummary;
						result = { ...result, summary };
						summaryArtifactId = stringValue(object(summary.summary_artifact).artifact_id, summaryArtifactId);
						const summaryText = summary.success === true ? stringValue(summary.summary_text).trim() : "";
						if (summaryText) displayedText += `${displayedText ? "\n\n" : ""}Summary:\n${summaryText}`;
						else if (summary.success !== true) {
							result = { ...result, summarization: { message: "Transcript saved, but summarization did not complete.", detail: summary } };
							displayedText += `${displayedText ? "\n\n" : ""}Summary unavailable: ${stringValue(summary.message, "Summarization did not complete.")}`;
						}
						} catch (error) {
							result = { ...result, summarization: formatError(error).response.result };
							displayedText += `${displayedText ? "\n\n" : ""}Summary unavailable: ${formatError(error).message}`;
						}
					}
				} else {
					displayedText = `Audio saved. ${stringValue(transcription.message, "Transcription did not complete.")}`;
				}
				const memoryResult = object(pipeline.memory);
				if (memoryResult.success === true) displayedText += `${displayedText ? "\n\n" : ""}Memory: ${stringValue(memoryResult.message, "Voice idea saved to memory.")}`;
				else if (memoryResult.code) displayedText += `${displayedText ? "\n\n" : ""}Memory not updated: ${stringValue(memoryResult.message, "Memory persistence did not complete.")}`;
			} catch (error) {
				result = { ...result, transcription: formatError(error).response.result };
				displayedText = `Audio saved. Transcription unavailable: ${formatError(error).message}`;
			}
			if (session?.session_id) {
				try {
					result = { ...result, conversation_persistence: await api.saveVoiceResult(session.session_id, artifactId, transcriptArtifactId || undefined, summaryArtifactId || undefined) };
				} catch (error) { result = { ...result, conversation_persistence: formatError(error).response.result }; }
			}
			setMessages((current) => [...current, { id: `voice-${Date.now()}`, prompt: `Captured voice: ${file.name}`, transcript: displayedText || undefined, response: { success: result.success !== false, result } }]);
			setActivePage("chats");
			setPageRevision((current) => current + 1);
		} catch (error) { setActionNotice(formatError(error).message); }
		finally {
			setVoiceBusy(false);
			if (voiceFileRef.current) voiceFileRef.current.value = "";
		}
	}

	function exportArtifactIndex() {
		const payload = {
			exported_at: new Date().toISOString(),
			filters: { query: artifactQuery.trim(), artifact_type: artifactTypeFilter || null, include_archived: showArchivedArtifacts, offset: artifactOffset },
			pagination: artifactPagination,
			artifacts: artifacts.map((item) => safeDisplay(item)),
		};
		const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement("a");
		anchor.href = url;
		anchor.download = `lumira-artifacts-${new Date().toISOString().slice(0, 10)}.json`;
		anchor.click();
		URL.revokeObjectURL(url);
		setActionNotice(`Exported ${artifacts.length} artifact records from the current page. This export contains metadata, not artifact file contents.`);
	}

	async function importBinaryArtifact(file?: File): Promise<boolean> {
		if (!file || artifactCreateBusy) return false;
		const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
		const textExtensions = new Set(["txt", "md", "markdown", "json", "csv", "yaml", "yml", "log"]);
		if (textExtensions.has(extension)) {
			if (file.size <= 0 || file.size > 1_000_000) { setPageError("Text imports must be non-empty and no larger than 1 MB."); return false; }
			setArtifactCreateBusy(true);
			setPageError(null);
			try {
				const content = await file.text();
				if (!content.trim()) throw new Error("The selected text file is empty.");
				const created = await api.createArtifact({ type: "exports", content, source: `desktop_import:${file.name}`, extension: extension === "markdown" ? "md" : extension });
				const artifactId = stringValue(object(created.artifact).artifact_id);
				setArtifactQuery(file.name);
				setArtifactTypeFilter("exports");
				setShowArchivedArtifacts(false);
				setArtifactOffset(0);
				setActionNotice(`Imported ${file.name} as a text artifact.`);
				setPageRevision((value) => value + 1);
				if (artifactId) void openArtifactDetails(artifactId);
			} catch (error) { setPageError(formatError(error).message); return false; }
			finally { setArtifactCreateBusy(false); }
			return true;
		}
		const typeByExtension: Record<string, string> = { wav: "audio", mp3: "audio", m4a: "audio", ogg: "audio", png: "images", jpg: "images", jpeg: "images", webp: "images", mp4: "video", webm: file.type.startsWith("audio/") ? "audio" : "video", pdf: "pdf", zip: "generated_files" };
		const artifactType = typeByExtension[extension];
		if (!artifactType) { setPageError("Unsupported file. Import TXT/MD/JSON/CSV/YAML/LOG, WAV/MP3/M4A/OGG, PNG/JPG/WEBP, MP4/WebM, PDF, or ZIP."); return false; }
		if (file.size <= 0 || file.size > 25_000_000) { setPageError("Choose a non-empty file no larger than 25 MB."); return false; }
		setArtifactCreateBusy(true);
		setPageError(null);
		try {
			const bytes = new Uint8Array(await file.arrayBuffer());
			let binary = "";
			const chunkSize = 0x8000;
			for (let offset = 0; offset < bytes.length; offset += chunkSize) binary += String.fromCharCode(...bytes.subarray(offset, Math.min(offset + chunkSize, bytes.length)));
			const created = await api.createBinaryArtifact({ type: artifactType, content_base64: btoa(binary), source: `desktop_import:${file.name}`, extension });
			const artifactId = stringValue(object(created.artifact).artifact_id);
			setArtifactQuery(file.name);
			setArtifactTypeFilter(artifactType);
			setShowArchivedArtifacts(false);
			setArtifactOffset(0);
			setActionNotice(`Imported ${file.name} into Artifact Manager.`);
			setPageRevision((value) => value + 1);
			if (artifactId) void openArtifactDetails(artifactId);
		} catch (error) { setPageError(formatError(error).message); return false; }
		finally { setArtifactCreateBusy(false); }
		return true;
	}

	async function importSelectedArtifacts(files: File[]) {
		if (!files.length || artifactCreateBusy) return;
		let imported = 0;
		const failed: string[] = [];
		for (const file of files) {
			const succeeded = await importBinaryArtifact(file);
			if (succeeded) imported += 1;
			else failed.push(file.name);
		}
		setActionNotice(`Imported ${imported} of ${files.length} selected file(s).${failed.length ? ` Failed: ${failed.join(", ")}.` : ""}`);
		if (failed.length) setPageError(`Could not import: ${failed.join(", ")}. Review file types, size limits, and server errors.`);
	}

	async function saveConversationAsArtifact() {
		const newline = String.fromCharCode(10);
		const transcript = messages.map((message, index) => {
			const sections = [`## Exchange ${index + 1}`];
			if (message.prompt) sections.push(`**You:** ${message.prompt}`);
			if (message.transcript) sections.push(`**Lumira:** ${message.transcript}`);
			if (message.error) sections.push(`**Error:** ${message.error}`);
			if (message.response) sections.push("**Structured response:**" + newline + JSON.stringify(safeDisplay(message.response), null, 2));
			return sections.join(newline + newline);
		}).join(newline + newline + "---" + newline + newline);
		if (!transcript.trim()) { setActionNotice("There is no conversation content to save yet."); return; }
		setArtifactCreateBusy(true);
		setPageError(null);
		try {
			const title = `Lumira conversation ${new Date().toISOString().slice(0, 19).replaceAll(":", "-")}`;
			const created = await api.createArtifact({ type: "exports", content: "# " + title + newline + newline + transcript, source: "desktop_conversation_export", extension: "md" });
			setArtifactQuery(title);
			setArtifactTypeFilter("exports");
			setShowArchivedArtifacts(false);
			setArtifactOffset(0);
			setActionNotice(`Saved ${messages.length} conversation exchange(s) as an artifact.`);
			setPageRevision((value) => value + 1);
			const artifactId = stringValue(object(created.artifact).artifact_id);
			if (artifactId) void openArtifactDetails(artifactId);
		} catch (error) { setPageError(formatError(error).message); }
		finally { setArtifactCreateBusy(false); }
	}

	async function createTextArtifact(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const title = artifactDraftTitle.trim();
		const content = artifactDraftContent.trim();
		if (!title || !content || artifactCreateBusy) return;
		setArtifactCreateBusy(true);
		setPageError(null);
		try {
			const created = await api.createArtifact({ type: "exports", content: "# " + title + String.fromCharCode(10, 10) + content, source: `desktop_note:${title}`, extension: "md" });
			setArtifactDraftTitle("");
			setArtifactDraftContent("");
			setArtifactOffset(0);
			setArtifactQuery(title);
			setArtifactTypeFilter("exports");
			setShowArchivedArtifacts(false);
			setActionNotice(`Saved “${title}” to the Artifact Manager.`);
			setPageRevision((value) => value + 1);
			const artifactId = stringValue(object(created.artifact).artifact_id);
			if (artifactId) void openArtifactDetails(artifactId);
		} catch (error) { setPageError(formatError(error).message); }
		finally { setArtifactCreateBusy(false); }
	}

	async function speakArtifactContent(artifact: JsonObject) {
  const text = stringValue(artifact.content).trim();
  if (!text || voiceBusy) return;
  setVoiceBusy(true);
  setPageError(null);
  try {
    const hasTamil = /[஀-௿]/.test(text);
    const hasEnglish = /[A-Za-z]/.test(text);
    const language = hasTamil && hasEnglish ? "ta-en" : hasTamil ? "ta" : "en";
    const result = await api.playVoiceText(text.slice(0, 12000), language);
    setActionNotice(stringValue(result.message, result.success === true ? `Speech playback requested (${language}).` : "Speech playback request did not complete."));
  } catch (error) { setPageError(formatError(error).message); }
  finally { setVoiceBusy(false); }
}

async function runArtifactVoiceAction(artifactId: string, action: "process" | "transcribe" | "summarize" | "activate") {
		if (!artifactId || voiceBusy) return;
		setVoiceBusy(true);
		setPageError(null);
		setActionNotice(null);
		try {
			let result: JsonObject;
			if (action === "process") result = await api.processVoiceCapture(artifactId, true);
			else if (action === "transcribe") result = await api.transcribeVoice(artifactId);
			else if (action === "summarize") result = await api.retryVoiceSummary(artifactId);
			else result = await api.activateVoiceFromArtifact(artifactId);
			if (session?.session_id && action === "process" && result.success === true) {
				const audioId = stringValue(result.audio_artifact_id, artifactId);
				const transcriptId = stringValue(result.transcript_artifact_id || object(result.transcription).transcript_artifact_id || object(object(result.transcription).transcript_artifact).artifact_id);
				const summaryId = stringValue(result.summary_artifact_id || object(result.summary).summary_artifact_id || object(object(result.summary).summary_artifact).artifact_id);
				try { result = { ...result, session_persistence: await api.saveVoiceResult(session.session_id, audioId, transcriptId || undefined, summaryId || undefined) }; }
				catch (error) { result = { ...result, session_persistence_error: formatError(error).message }; }
			}
			const success = result.success === true;
			const message = stringValue(result.message, success ? "Voice action completed." : "Voice action did not complete.");
			setActionNotice(message);
			setMessages((current) => [...current, { id: `artifact-voice-${Date.now()}`, prompt: `Artifact voice action: ${action} (${artifactId})`, transcript: message, response: { success, result } }]);
			const linkedIds = [result.audio_artifact_id, result.transcript_artifact_id, result.summary_artifact_id, object(result.transcript_artifact).artifact_id, object(result.summary_artifact).artifact_id].filter((value): value is string => typeof value === "string" && value.length > 0);
			setPageRevision((value) => value + 1);
			if (linkedIds.length) {
				setArtifactQuery(linkedIds[linkedIds.length - 1]);
				setArtifactTypeFilter("");
				setShowArchivedArtifacts(false);
				setArtifactOffset(0);
			}
		} catch (error) { setPageError(formatError(error).message); }
		finally { setVoiceBusy(false); }
	}

	async function openArtifactDetails(artifactId: string) {
		if (!artifactId || artifactDetailBusy) return;
		setArtifactDetailBusy(true);
		setPageError(null);
		try {
			const response = await api.getArtifact(artifactId);
			const artifact = object(response.artifact);
			if (!Object.keys(artifact).length) throw new Error("Artifact details were not returned.");
			const textArtifactTypes = ["transcripts", "summaries", "reports", "exports"];
			if (artifact.content_available === true && textArtifactTypes.includes(stringValue(artifact.type))) {
				try {
					const content = await api.getArtifactTextContent(artifactId);
					artifact.content = content.slice(0, 12000);
					artifact.content_truncated = content.length > 12000;
				} catch {
					artifact.content = "";
				}
			}
			setSelectedArtifact(artifact);
		} catch (error) { setPageError(formatError(error).message); }
		finally { setArtifactDetailBusy(false); }
	}

	async function retryVoiceTranscriptionForMessage(messageId: string, audioArtifactId: string) {
		if (!audioArtifactId) return;
		setActionNotice("Retrying transcription from the saved audio artifact…");
		try {
			const transcription = await api.transcribeVoice(audioArtifactId);
			const transcriptArtifactId = stringValue(object(transcription.transcript_artifact).artifact_id);
			setMessages((current) => current.map((message) => {
				if (message.id !== messageId) return message;
				const previous = object(message.response?.result);
				const previousTranscript = object(previous.transcript);
				const merged = { ...previous, transcript: { ...previousTranscript, ...transcription }, transcript_artifact_id: transcriptArtifactId || stringValue(previous.transcript_artifact_id), status: stringValue(transcription.state, transcription.success === true ? "transcribed" : "transcription_unavailable") };
				return { ...message, transcript: transcription.success === true ? `Transcript:\n${stringValue(transcription.transcript_text)}` : message.transcript, response: { ...(message.response ?? {}), success: transcription.success === true, result: merged } };
			}));
			if (transcription.success === true && session?.session_id) {
				try {
					await api.saveVoiceResult(session.session_id, audioArtifactId, transcriptArtifactId || undefined);
				} catch (error) {
					setActionNotice(`Transcript recovered, but session history could not be updated: ${formatError(error).message}`);
					return;
				}
			}
			setActionNotice(stringValue(transcription.message, transcription.success === true ? "Transcript recovered and linked to session history." : "Transcription retry did not complete."));
		} catch (error) { setActionNotice(formatError(error).message); }
	}

	async function retryVoiceSummaryForMessage(messageId: string, transcriptArtifactId: string) {
		if (!transcriptArtifactId) return;
		setActionNotice("Retrying summary from the saved transcript…");
		try {
			const summary = await api.retryVoiceSummary(transcriptArtifactId);
			const summaryPayload = object(summary.summary);
			const summaryArtifactId = stringValue(summary.summary_artifact_id || object(summary.summary_artifact).artifact_id || summaryPayload.summary_artifact_id || object(summaryPayload.summary_artifact).artifact_id);
			setMessages((current) => current.map((message) => {
				if (message.id !== messageId) return message;
				const previous = object(message.response?.result);
				const summaryText = summary.success === true ? stringValue(summary.summary_text, stringValue(summaryPayload.summary_text)).trim() : "";
				const transcriptText = stringValue(object(previous.transcript).transcript_text).trim();
				const existingDisplay = stringValue(message.transcript).split("\n\nSummary:")[0];
				const displayBase = transcriptText ? `Transcript:\n${transcriptText}` : existingDisplay;
				const displayText = summaryText ? `${displayBase}${displayBase ? "\n\n" : ""}Summary:\n${summaryText}` : message.transcript;
				return {
					...message,
					transcript: displayText,
					response: {
						...(message.response ?? {}),
						success: summary.success === true,
						result: { ...previous, summary_retry: summary, summary: object(summary.summary), summary_artifact_id: summaryArtifactId || stringValue(previous.summary_artifact_id), status: stringValue(summary.state, summary.success === true ? "completed" : "deferred") },
					},
				};
			}));
			if (summary.success === true && session?.session_id) {
				const message = messages.find((item) => item.id === messageId);
				const previous = object(message?.response?.result);
				const audioArtifactId = stringValue(object(previous.artifact).artifact_id);
				if (audioArtifactId) {
					try { await api.saveVoiceResult(session.session_id, audioArtifactId, transcriptArtifactId, summaryArtifactId || undefined); }
					catch (error) { setActionNotice(`Summary recovered, but session history could not be updated: ${formatError(error).message}`); return; }
				}
			}
			setActionNotice(stringValue(summary.message, summary.success === true ? "Summary recovered and linked to session history." : "Summary retry did not complete."));
		} catch (error) { setActionNotice(formatError(error).message); }
	}

	async function changeSession(sessionId: string) {
		try {
			let loaded = await api.getSession(sessionId) as SessionRecord;
			if (loaded.status === "paused") loaded = await api.resumeSession(sessionId) as SessionRecord;
			setSession(loaded);
			window.localStorage.setItem("lumira.sessionId", sessionId);
			setActiveMode(modeFromSession(loaded.active_mode) ?? "auto");
			setSelectedProject(loaded.active_project ?? null, loaded.active_version ?? null);
			setMessages((loaded.recent_messages ?? []).map((item, index) => item.role === "user" ? { id: `restored-${index}`, prompt: item.content } : { id: `restored-${index}`, transcript: item.content }));
			setActivePage("chats");
		} catch (error) { setActionNotice(formatError(error).message); }
	}

	async function pauseSession(sessionId: string) {
		try {
			const updated = await api.pauseSession(sessionId) as SessionRecord;
			if (session?.session_id === sessionId) setSession(updated);
			await loadSessions();
		} catch (error) { setActionNotice(formatError(error).message); }
	}

	async function closeSession(sessionId: string) {
		try {
			await api.closeSession(sessionId);
			if (session?.session_id === sessionId) {
				setSession(null);
				setMessages([]);
				window.localStorage.removeItem("lumira.sessionId");
			}
			await loadSessions();
		} catch (error) { setActionNotice(formatError(error).message); }
	}

	async function inspectWorkflowTask(workflowId: string, taskId: string, detail: "history" | "result") {
		const key = `${workflowId}:${taskId}:${detail}`;
		if (workflowTaskDetailBusy) return;
		setWorkflowTaskDetailBusy(key);
		try {
			if (detail === "history") {
				setWorkflowTaskHistory(await api.getWorkflowTaskHistory(workflowId, taskId));
				setWorkflowTaskResult(null);
			} else {
				setWorkflowTaskResult(await api.getWorkflowTaskResult(workflowId, taskId));
				setWorkflowTaskHistory(null);
			}
		} catch (error) { setPageError(formatError(error).message); }
		finally { setWorkflowTaskDetailBusy(null); }
	}

	async function updateTask(workflowId: string, taskId: string, status: string, blocker?: string, resultText?: string) {
		try {
			const result = await api.updateWorkflowTask(workflowId, taskId, { status, ...(blocker !== undefined ? { blocker } : {}), ...(resultText !== undefined ? { result: resultText } : {}) });
			const learningStatus = stringValue(result.learning_status, "not_applicable");
			const goalProgressStatus = stringValue(result.goal_progress_status, "not_applicable");
			const eventLogStatus = stringValue(result.event_log_status, "not_applicable");
			const goalProgress = typeof result.goal_progress === "number" ? ` Goal progress: ${result.goal_progress}%.` : "";
			setActionNotice(`Task status changed to ${status}. Learning: ${learningStatus}. Goal progress: ${goalProgressStatus}. Event log: ${eventLogStatus}.${goalProgress}`);
			setPageRevision((current) => current + 1);
		} catch (error) { setActionNotice(formatError(error).message); }
	}

	async function runWorkflowAgents(workflowId: string, agentMode: "auto" | "planner_agent" | "research_agent" | "code_agent" = "auto"): Promise<JsonObject | null> {
		try {
			const preview = await api.previewWorkflowExecution(workflowId);
			const readyCount = Number(preview.ready_count ?? 0);
			if (!Number.isFinite(readyCount) || readyCount <= 0) {
				setActionNotice("No dependency-ready tasks are available. Review workflow blockers and dependencies first.");
				return null;
			}
			if (!window.confirm(`Execution preview found ${readyCount} ready task(s). Run up to 3 through the ${agentMode.replaceAll("_", " ")} agent? Output will be recorded in workflow history; arbitrary project code will not be run.`)) return null;
			const result = await api.runReadyWorkflow(workflowId, 3, true, agentMode);
			const outcomes = records(result, "outcomes");
			setActionNotice(`Agent workflow run finished: ${outcomes.filter((item) => item.success === true).length} task(s) completed; stop reason: ${stringValue(result.stop_reason, "unknown")}.`);
			setPageRevision((current) => current + 1);
			return result;
		} catch (error) {
			setPageError(formatError(error).message);
			return null;
		}
	}

	async function retryFailedWorkflowTasks(workflowId: string): Promise<JsonObject | null> {
		if (!window.confirm("Requeue failed tasks for this workflow? Their history is retained; no agents will run until you explicitly start execution.")) return null;
		try {
			const result = await api.retryFailedWorkflowTasks(workflowId);
			setActionNotice(`Requeued ${Number(result.reset_count ?? 0)} failed task(s).`);
			setPageRevision((current) => current + 1);
			return result;
		} catch (error) {
			setPageError(formatError(error).message);
			return null;
		}
	}

	async function inspectRun(runId: string) {
		if (!runId || runDetailBusy) return;
		setRunDetailBusy(runId);
		try {
			const result = await api.getRun(runId);
			setSelectedRun(object(result));
		} catch (error) { setActionNotice(formatError(error).message); }
		finally { setRunDetailBusy(null); }
	}

	async function resumeRun(runId: string) {
		try {
			const result = await api.resumeRun(runId);
			setActionNotice(stringValue(object(result).message, "Recovery request completed."));
			setPageRevision((current) => current + 1);
		} catch (error) { setActionNotice(formatError(error).message); }
	}

	function openProjectFiles(project: string) {
		void selectProject(project);
		setRightTab("files");
		if (focusMode) setFocusMode(false);
		if (rightMode === "hidden") setRightMode("full");
	}

	async function projectAction(name: string, action: "run" | "edit" | "modify" | "frontend" | "database" | "deploy" | "docs") {
		const selected = await selectProject(name);
		if (action === "run") {
			setRightTab("preview");
			setActionNotice("Project execution is unavailable: no sandboxed project runner or preview service is configured.");
			if (rightMode === "hidden") setRightMode("full");
			return;
		}
		if (action === "edit" || action === "docs") {
			const documentation = selected.files.includes("README.md") ? "README.md" : selected.files[0];
			if (!documentation) { setActionNotice("This project version has no readable files."); return; }
			await selectFile(documentation, name, selected.version);
			if (rightMode === "hidden") setRightMode("full");
			return;
		}
		if (action === "deploy") {
			setActivePage("chats");
			await submitInput(`Automate a deployment plan for ${name}`, { projectId: name });
			return;
		}
		const instructions = {
			modify: `Add the requested change to ${name}: `,
			frontend: `Add a frontend to ${name}`,
			database: `Add a database to ${name}`,
		};
		if (action === "modify") {
			setWorkflow("project");
			setPrompt(instructions.modify);
			setActivePage("chats");
			window.setTimeout(() => promptInputRef.current?.focus(), 0);
			return;
		}
		setActivePage("chats");
		await submitInput(instructions[action], { projectId: name });
	}

	function startNewProject() {
		setActivePage("chats");
		setWorkflow("project");
		setPrompt("");
		window.setTimeout(() => promptInputRef.current?.focus(), 0);
	}

	function startGeneration() {
		setActivePage("generator");
		void activateMode("generator");
		window.setTimeout(() => promptInputRef.current?.focus(), 0);
	}

	function setPromptFromTool(text: string, mode?: LumiraMode) {
		setWorkflow("brain");
		setActivePage("chats");
		setPrompt(text);
		setQuickToolsOpen(false);
		if (mode) void activateMode(mode);
		window.setTimeout(() => promptInputRef.current?.focus(), 0);
	}

	function onPromptKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
		if (event.key === "Enter" && !event.shiftKey) {
			event.preventDefault();
			event.currentTarget.form?.requestSubmit();
		}
	}

	const projectsInPage = projectRecords(pageData);
	const artifacts = records(pageData, "artifacts");
	const goals = activePage === "business" ? records(pageData?.goals, "goals") : records(pageData, "goals");
	const workflows = activePage === "business" || activePage === "operations" ? records(pageData?.workflows, "workflows") : [];
	const memoryData = object(pageData?.data);
	const featureEntries = Object.entries(object(pageData?.features));
	const activationBlocked = object(pageData?.activation_blocked);

	async function runMemorySearch(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!memorySearchQuery.trim() || memoryBusy) return;
		setMemoryBusy(true);
		setPageError(null);
		try { setMemorySearchResult(await api.searchMemory(memorySearchQuery.trim(), { project_id: currentProject ?? undefined, goal_id: session?.goal_id ?? undefined })); }
		catch (error) { setPageError(formatError(error).message); }
		finally { setMemoryBusy(false); }
	}

	async function loadMemorySummary() {
		setMemoryBusy(true);
		setPageError(null);
		try { setMemorySummary(await api.summarizeMemory({ project_id: currentProject ?? undefined, goal_id: session?.goal_id ?? undefined })); }
		catch (error) { setPageError(formatError(error).message); }
		finally { setMemoryBusy(false); }
	}

	async function linkMemoryRecords(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!memoryLinkSource.trim() || !memoryLinkTarget.trim() || !memoryLinkRelation.trim()) return;
		setMemoryBusy(true);
		setPageError(null);
		try {
			await api.linkMemory(memoryLinkSource.trim(), memoryLinkTarget.trim(), memoryLinkRelation.trim());
			setActionNotice("Memory relationship saved.");
			setMemoryLinkSource("");
			setMemoryLinkTarget("");
			setPageRevision((value) => value + 1);
		} catch (error) { setPageError(formatError(error).message); }
		finally { setMemoryBusy(false); }
	}

	async function archiveMemoryRecord(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!memoryArchiveId.trim()) return;
		if (!window.confirm("Archive this memory record? It will be retained, not deleted.")) return;
		setMemoryBusy(true);
		setPageError(null);
		try {
			await api.archiveMemory(memoryArchiveCollection, memoryArchiveId.trim());
			setActionNotice("Memory record archived and retained in history.");
			setMemoryArchiveId("");
			setPageRevision((value) => value + 1);
		} catch (error) { setPageError(formatError(error).message); }
		finally { setMemoryBusy(false); }
	}

	async function loadMemoryDecisions() {
		setMemoryBusy(true);
		setPageError(null);
		try {
			const response = await api.listMemoryDecisions({ project_id: currentProject ?? undefined, goal_id: session?.goal_id ?? undefined, session_id: session?.session_id });
			setDecisionRecords(records(response, "decisions"));
		} catch (error) { setPageError(formatError(error).message); }
		finally { setMemoryBusy(false); }
	}

	async function saveMemoryDecision(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!decisionText.trim() || memoryBusy) return;
		setMemoryBusy(true);
		setPageError(null);
		try {
			await api.createMemoryDecision({
				decision: decisionText.trim(),
				reason: decisionReason.trim(),
				session_id: session?.session_id,
				project_id: currentProject ?? undefined,
				goal_id: session?.goal_id ?? undefined,
				alternatives: decisionAlternatives.split(/\n/).map((item) => item.trim()).filter(Boolean).slice(0, 20),
				constraints: decisionConstraints.split(/\n/).map((item) => item.trim()).filter(Boolean).slice(0, 20),
				confidence: decisionConfidence,
			});
			setDecisionText("");
			setDecisionReason("");
			setDecisionAlternatives("");
			setDecisionConstraints("");
			const response = await api.listMemoryDecisions({ project_id: currentProject ?? undefined, goal_id: session?.goal_id ?? undefined, session_id: session?.session_id });
			setDecisionRecords(records(response, "decisions"));
			setActionNotice("Decision recorded in durable memory.");
			setPageRevision((value) => value + 1);
		} catch (error) { setPageError(formatError(error).message); }
		finally { setMemoryBusy(false); }
	}

	async function registerDevice(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!deviceIdInput.trim() || deviceBusy) return;
		if (!/^[A-Za-z0-9_.:-]{1,128}$/.test(deviceIdInput.trim())) { setPageError("Device ID must be 1–128 characters using only letters, numbers, underscore, period, colon, or hyphen."); return; }
		const splitIdentifiers = (value: string) => [...new Set(value.split(/[,\n]/).map((item) => item.trim()).filter(Boolean))];
		const capabilities = splitIdentifiers(deviceCapabilitiesText);
		const permissions = splitIdentifiers(devicePermissionsText);
		const validCapabilities = capabilities.every((item) => /^[A-Za-z0-9_.:-]{1,80}$/.test(item));
		const allowedPermissions = new Set(["telemetry.read", "commands.receive", "camera.capture", "microphone.capture", "robot.motion", "smart_home.control", "vehicle.read", "files.read", "files.write"]);
		if (capabilities.length > 30 || !validCapabilities) { setPageError("Device capabilities must be valid short identifiers (maximum 30, up to 80 characters each; allowed characters: letters, numbers, _, ., :, -)."); return; }
		if (permissions.length > 20 || permissions.some((permission) => !allowedPermissions.has(permission))) { setPageError("Device permissions must be chosen from: telemetry.read, commands.receive, camera.capture, microphone.capture, robot.motion, smart_home.control, vehicle.read, files.read, files.write (maximum 20)."); return; }
		setDeviceBusy(true);
		try {
			await api.registerDevice({
				device_id: deviceIdInput.trim(),
				device_type: deviceTypeInput,
				capabilities,
				permissions,
				connection: deviceConnection,
			});
			setActionNotice("Device registration saved. This does not confirm a live hardware connection.");
			setDeviceIdInput("");
			setPageRevision((value) => value + 1);
		} catch (error) { setPageError(formatError(error).message); }
		finally { setDeviceBusy(false); }
	}

	async function changeDeviceStatus(deviceId: string, status: string) {
		if (deviceStatusBusy) return;
		setDeviceStatusBusy(deviceId);
		try {
			const response = await api.updateDeviceStatus(deviceId, status);
			const updated = object(response.device);
			if (stringValue(updated.device_id) === deviceId) {
				setDeviceRecords((current) => current.map((item) => stringValue(item.device_id) === deviceId ? { ...item, ...updated } : item));
			}
			setActionNotice(`Device ${deviceId} marked ${status}. This is registry state, not a live connectivity check.`);
		} catch (error) {
			setPageError(formatError(error).message);
			setPageRevision((value) => value + 1);
		} finally { setDeviceStatusBusy(null); }
	}

	async function saveNotepadNote() {
		setNoteSaveBusy(true);
		try {
			const response = noteId ? await api.updateNote(noteId, note) : await api.createNote("Quick Note", note);
			const saved = object(response.note);
			if (typeof saved.note_id === "string") setNoteId(saved.note_id);
			if (typeof saved.content === "string") setNote(saved.content);
			setNoteSaveStatus("Saved to Lumira");
		} catch {
			setNoteSaveStatus("Local draft only — backend unavailable");
		} finally {
			setNoteSaveBusy(false);
		}
	}

	async function toggleFeature(featureId: string, currentlyEnabled: boolean) {
		try {
			const result = currentlyEnabled ? await api.deactivateFeature(featureId) : await api.activateFeature(featureId);
			setActionNotice(`${featureId}: ${stringValue(result.status, currentlyEnabled ? "disabled" : "enabled")}`);
			setPageError(null);
			setPageRevision((value) => value + 1);
		} catch (error) {
			setPageError(formatError(error).message);
		}
	}

	const pageContent = () => {
		if (activePage === "chats") return null;
		if (pageLoading) return <div className="workspace-empty">Loading {PAGE_TITLES[activePage].toLowerCase()}…</div>;
		if (activePage === "projects") return <>
			<div className="workspace-page-heading"><div><span className="eyebrow">WORKSPACE</span><h2>Generated projects</h2><p>Project metadata and versions from Lumira's project store.</p></div><div className="entity-actions"><button type="button" className="secondary-action" onClick={async () => { try { const result = await api.projectSummary(); setActionNotice("Project portfolio summary refreshed."); setProjectSearchResult(null); setPageRevision((value) => value + 1); void result; } catch (error) { setPageError(formatError(error).message); } }}>Refresh portfolio</button><button type="button" className="primary-action" onClick={startNewProject}>New project</button></div></div>
			{pageData?.summary && <div className="metric-strip"><span>{Number(object(pageData.summary).project_count ?? 0)} projects</span><span>{Number(object(pageData.summary).version_count ?? 0)} valid versions</span><span>{Object.keys(object(object(pageData.summary)["project_type_counts"])).length} project types</span><span>{records(pageData.summary, "projects_without_valid_versions").length} without valid versions</span></div>}
			<form className="workspace-search" onSubmit={async (event) => { event.preventDefault(); if (!projectSearchQuery.trim()) { setProjectSearchResult(null); return; } try { setProjectSearchResult(await api.searchProjects(projectSearchQuery.trim(), 50)); } catch (error) { setPageError(formatError(error).message); } }}><FiSearch /><input aria-label="Search generated projects" placeholder="Search project names, ideas, versions, and types" value={projectSearchQuery} onChange={(event) => setProjectSearchQuery(event.target.value)} /><button className="primary-action" type="submit" disabled={!projectSearchQuery.trim()}>Search projects</button><button className="secondary-action" type="button" disabled={!projectSearchQuery && !projectSearchResult} onClick={() => { setProjectSearchQuery(""); setProjectSearchResult(null); }}>Clear</button></form>
			{projectSearchResult && <section className="memory-results"><div className="workspace-page-heading"><div><h3>Project search results</h3><p>{Number(projectSearchResult.total ?? 0)} match(es)</p></div><button className="secondary-action" type="button" onClick={() => setProjectSearchResult(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(projectSearchResult), null, 2)}</pre></section>}
			{projectHealth && <section className="memory-results"><div className="workspace-page-heading"><div><h3>Project health: {stringValue(projectHealth.project)}</h3><p>{Number(projectHealth.finding_count ?? 0)} finding(s) · {projectHealth.is_healthy === true ? "no warning findings" : "review recommended"}</p></div><button className="secondary-action" type="button" onClick={() => setProjectHealth(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(projectHealth), null, 2)}</pre></section>}
			{projectManifest && <section className="memory-results"><div className="workspace-page-heading"><div><h3>File manifest: {stringValue(projectManifest.project)} / {stringValue(projectManifest.version)}</h3><p>{Number(projectManifest.file_count ?? 0)} bounded file entries. File contents are not executed or exposed by this manifest.</p></div><button className="secondary-action" type="button" onClick={() => setProjectManifest(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(projectManifest), null, 2)}</pre></section>}
			{projectSecurityReport && <section className="memory-results"><div className="workspace-page-heading"><div><h3>Static security review: {stringValue(projectSecurityReport.project)} / {stringValue(projectSecurityReport.version)}</h3><p>{Number(projectSecurityReport.scanned_files ?? 0)} source files scanned · {Number(projectSecurityReport.finding_count ?? 0)} heuristic finding(s). Source was not executed.</p></div><button className="secondary-action" type="button" onClick={() => setProjectSecurityReport(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(projectSecurityReport), null, 2)}</pre></section>}
			{projectIntegrityReport && <section className="memory-results"><div className="workspace-page-heading"><div><h3>Integrity scan: {stringValue(projectIntegrityReport.project)} / {stringValue(projectIntegrityReport.version)}</h3><p>{Number(projectIntegrityReport.files_scanned ?? 0)} files scanned · {Number(projectIntegrityReport.finding_count ?? 0)} finding group(s). This scan does not execute project code.</p></div><button className="secondary-action" type="button" onClick={() => setProjectIntegrityReport(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(projectIntegrityReport), null, 2)}</pre></section>}
			{projectReadinessAudit && <section className="memory-results"><div className="workspace-page-heading"><div><h3>Packaging readiness audit: {stringValue(projectReadinessAudit.project)} / {stringValue(projectReadinessAudit.version)}</h3><p>{Number(projectReadinessAudit.passed ?? 0)} of {Number(projectReadinessAudit.check_count ?? 0)} checks pass · {Number(projectReadinessAudit.warnings ?? 0)} recommendations · score {Number(projectReadinessAudit.readiness_score ?? 0)}%. Static checks only; code was not executed.</p></div><div className="entity-actions"><button className="secondary-action" type="button" onClick={async () => { try { await navigator.clipboard.writeText(JSON.stringify(projectReadinessAudit, null, 2)); setActionNotice("Readiness audit JSON copied."); } catch (error) { setPageError(formatError(error).message); } }}>Copy JSON</button><button className="secondary-action" type="button" onClick={() => setProjectReadinessAudit(null)}>Close</button></div></div><pre>{JSON.stringify(safeDisplay(projectReadinessAudit), null, 2)}</pre></section>}
			{projectVersionComparison && <section className="memory-results"><div className="workspace-page-heading"><div><h3>Version path comparison: {stringValue(projectVersionComparison.project)}</h3><p>{stringValue(projectVersionComparison.left_version)} versus {stringValue(projectVersionComparison.right_version)}. Common-file content hashes are compared within a bounded scan budget.</p></div><button className="secondary-action" type="button" onClick={() => setProjectVersionComparison(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(projectVersionComparison), null, 2)}</pre><button className="secondary-action" type="button" onClick={async () => { try { await navigator.clipboard.writeText(JSON.stringify(projectVersionComparison, null, 2)); setActionNotice("Version comparison copied to clipboard."); } catch (error) { setPageError(formatError(error).message); } }}>Copy comparison</button></section>}
			{projectsInPage.length ? <div className="entity-list">{projectsInPage.map((project) => <article className="entity-row" key={project.project}><div className="entity-symbol"><FiCpu /></div><div className="entity-copy"><strong>{project.project}</strong><span>{String(project.latest?.description ?? project.latest?.idea ?? "Generated Lumira project")}</span><small>{project.versions ?? 0} saved versions · {String(project.latest?.status ?? "saved")}</small></div><div className="entity-actions"><button type="button" onClick={() => openProjectFiles(project.project)}>View files</button><button type="button" onClick={() => void projectAction(project.project, "edit")}>Open code</button><button type="button" className="secondary-action" onClick={async () => { try { setProjectHealth(await api.projectHealth(project.project)); } catch (error) { setPageError(formatError(error).message); } }}>Health</button><button type="button" className="secondary-action" onClick={async () => { try { setProjectIntegrityReport(await api.projectIntegrity(project.project)); } catch (error) { setPageError(formatError(error).message); } }}>Integrity</button><button type="button" className="secondary-action" onClick={async () => { try { setProjectSecurityReport(await api.projectSecurityReview(project.project)); } catch (error) { setPageError(formatError(error).message); } }}>Security review</button><button type="button" className="secondary-action" onClick={async () => { try { setProjectReadinessAudit(await api.projectReadinessAudit(project.project)); } catch (error) { setPageError(formatError(error).message); } }}>Readiness audit</button><button type="button" className="secondary-action" onClick={async () => { try { setProjectManifest(await api.projectManifest(project.project)); } catch (error) { setPageError(formatError(error).message); } }}>Manifest</button><button type="button" className="secondary-action" disabled={Number(project.versions ?? 0) < 2} onClick={async () => { const latest = stringValue(project.latest?.version); const left = window.prompt("Older version name to compare", "v1"); if (!left?.trim()) return; const right = window.prompt("Newer version name to compare", latest || "v2"); if (!right?.trim()) return; try { setProjectVersionComparison(await api.compareProjectVersions(project.project, left.trim(), right.trim())); } catch (error) { setPageError(formatError(error).message); } }}>Compare versions</button></div></article>)}</div> : <div className="workspace-empty">No generated projects are recorded yet.</div>}
		</>;
		if (activePage === "artifacts") return <>
			<div className="workspace-page-heading"><div><span className="eyebrow">PERSISTED OUTPUT</span><h2>Artifacts</h2><p>Search, filter, page through, and recover saved Lumira outputs.</p></div><div className="entity-actions"><label className="secondary-action" style={{ cursor: artifactCreateBusy ? "wait" : "pointer" }}>{artifactCreateBusy ? "Importing…" : "Import files (select multiple)"}<input type="file" multiple hidden disabled={artifactCreateBusy} accept=".txt,.md,.markdown,.json,.csv,.yaml,.yml,.log,.wav,.mp3,.m4a,.ogg,.png,.jpg,.jpeg,.webp,.mp4,.webm,.pdf,.zip" onChange={(event) => { void importSelectedArtifacts(Array.from(event.currentTarget.files ?? [])); event.currentTarget.value = ""; }} /></label><button className="secondary-action" type="button" onClick={() => void saveConversationAsArtifact()} disabled={artifactCreateBusy || !messages.some((message) => message.prompt || message.transcript || message.response || message.error)}>{artifactCreateBusy ? "Saving…" : "Save conversation"}</button><button className="secondary-action" type="button" onClick={exportArtifactIndex} disabled={!artifacts.length}>Export page JSON</button><button className="secondary-action" type="button" onClick={() => { setArtifactOffset(0); setPageRevision((value) => value + 1); }}>Refresh</button></div></div>
			{artifactStats && <div className="metric-strip"><span>{Number(artifactStats.total ?? artifactStats.count ?? 0)} total artifacts</span><span>{Number(artifactStats.active ?? 0)} active</span><span>{Number(artifactStats.archived ?? 0)} archived</span></div>}
			<form className="workspace-search" onSubmit={(event) => { event.preventDefault(); setArtifactOffset(0); setPageRevision((value) => value + 1); }}><FiSearch /><input aria-label="Search artifacts" placeholder="Search artifact metadata" value={artifactQuery} onChange={(event) => setArtifactQuery(event.target.value)} /><select aria-label="Filter artifact type" value={artifactTypeFilter} onChange={(event) => { setArtifactTypeFilter(event.target.value); setArtifactOffset(0); }}><option value="">All types</option><option value="audio">Audio</option><option value="transcripts">Transcripts</option><option value="summaries">Summaries</option><option value="images">Images</option><option value="diagrams">Diagrams</option><option value="blueprints">Blueprints</option><option value="schematics">Schematics</option><option value="exports">Exports</option><option value="reports">Reports</option><option value="video">Video</option><option value="pdf">PDF</option><option value="generated_files">Generated files</option></select><label><input type="checkbox" checked={showArchivedArtifacts} onChange={(event) => { setShowArchivedArtifacts(event.target.checked); setArtifactOffset(0); }} /> Show archived</label><button className="primary-action" type="submit">Search</button><button className="secondary-action" type="button" disabled={!artifactQuery && !artifactTypeFilter && !showArchivedArtifacts} onClick={() => { setArtifactQuery(""); setArtifactTypeFilter(""); setShowArchivedArtifacts(false); setArtifactOffset(0); setPageRevision((value) => value + 1); }}>Clear filters</button></form>
			<section className="goal-decomposition"><div className="workspace-page-heading"><div><h3>Capture a new artifact</h3><p>Save an idea, design note, project decision, or reusable reference directly to Lumira’s persistent Artifact Manager.</p></div></div><form className="goal-form" onSubmit={(event) => void createTextArtifact(event)}><input aria-label="Artifact title" required maxLength={200} value={artifactDraftTitle} onChange={(event) => setArtifactDraftTitle(event.target.value)} placeholder="Artifact title" /><textarea aria-label="Artifact content" required maxLength={200000} rows={4} value={artifactDraftContent} onChange={(event) => setArtifactDraftContent(event.target.value)} placeholder="Write the content to preserve…" /><button className="primary-action" type="submit" disabled={artifactCreateBusy || !artifactDraftTitle.trim() || !artifactDraftContent.trim()}>{artifactCreateBusy ? "Saving artifact…" : "Save artifact"}</button></form></section>
			{artifacts.length ? <div className="entity-list">{artifacts.map((item) => { const artifactId = stringValue(item.artifact_id); const archived = item.archived === true; return <article className="entity-row" key={artifactId}><div className="entity-symbol"><FiPaperclip /></div><div className="entity-copy"><strong>{stringValue(item.title, stringValue(item.name, stringValue(item.source).replace(/^desktop_import:/, "") || stringValue(item.type, "artifact")))}</strong><span>{stringValue(item.type, "artifact")} · {stringValue(item.source, "Lumira output")}</span><small>{stringValue(item.timestamp ?? item.created_at)} · {artifactId.slice(0, 8)}{archived ? " · archived" : ""}</small></div><button className="secondary-action" type="button" disabled={!artifactId || artifactDetailBusy} onClick={() => void openArtifactDetails(artifactId)}>{artifactDetailBusy ? "Loading…" : "Details"}</button><a className="text-link" href={`/artifacts/${encodeURIComponent(artifactId)}/content`} target="_blank" rel="noreferrer">Open content</a><button className="secondary-action" type="button" disabled={!artifactId || artifactActionBusy === artifactId} onClick={async () => { setArtifactActionBusy(artifactId); try { await (archived ? api.restoreArtifact(artifactId) : api.archiveArtifact(artifactId)); setActionNotice(archived ? "Artifact restored." : "Artifact archived and retained."); setPageRevision((value) => value + 1); } catch (error) { setPageError(formatError(error).message); } finally { setArtifactActionBusy(null); } }}>{artifactActionBusy === artifactId ? "Saving…" : archived ? "Restore" : "Archive"}</button></article>; })}</div> : <div className="workspace-empty">No artifacts match these filters.</div>}
			{selectedArtifact && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">ARTIFACT DETAILS</span><h3>{stringValue(selectedArtifact.title, stringValue(selectedArtifact.name, stringValue(selectedArtifact.source).replace(/^desktop_import:/, "") || stringValue(selectedArtifact.type, "Saved artifact")))}</h3><p>{stringValue(selectedArtifact.type, "artifact")} · {stringValue(selectedArtifact.source, "Lumira output")} · {stringValue(selectedArtifact.artifact_id)}</p><small>{selectedArtifact.content_available === true ? "Content file available" : selectedArtifact.content_available === false ? "Content file missing or unavailable" : "Content availability not reported"}{selectedArtifact.content_truncated === true ? " · Preview and speech limited to first 12,000 characters" : ""}</small></div><button className="secondary-action" type="button" onClick={() => setSelectedArtifact(null)}>Close details</button></div>{selectedArtifact.type === "images" && <figure className="goal-decomposition"><img src={api.artifactContentUrl(stringValue(selectedArtifact.artifact_id))} alt={stringValue(selectedArtifact.source, "Saved Lumira image")} style={{ display: "block", maxWidth: "100%", maxHeight: 520, objectFit: "contain" }} /><figcaption>Stored image preview · <a className="text-link" href={api.artifactContentUrl(stringValue(selectedArtifact.artifact_id))} target="_blank" rel="noreferrer">Open original</a></figcaption></figure>}{selectedArtifact.type === "audio" && <section className="goal-decomposition"><h4>Audio playback</h4><audio controls preload="metadata" src={api.artifactContentUrl(stringValue(selectedArtifact.artifact_id))}>Audio playback is not supported by this browser.</audio></section>}{selectedArtifact.type === "video" && <section className="goal-decomposition"><h4>Video player</h4><video controls preload="metadata" src={api.artifactContentUrl(stringValue(selectedArtifact.artifact_id))} style={{ display: "block", width: "100%", maxHeight: 520 }}>Video playback is not supported by this browser.</video></section>}{selectedArtifact.type === "pdf" && <section className="goal-decomposition"><h4>PDF preview</h4><iframe title={stringValue(selectedArtifact.source, "Saved PDF document")} src={api.artifactContentUrl(stringValue(selectedArtifact.artifact_id))} style={{ display: "block", width: "100%", height: 620, border: 0 }} /><a className="text-link" href={api.artifactContentUrl(stringValue(selectedArtifact.artifact_id))} target="_blank" rel="noreferrer">Open PDF in a separate tab</a></section>}{selectedArtifact.type === "generated_files" && <section className="goal-decomposition"><h4>Stored file</h4><p>This artifact is stored as a binary file. Use the original content endpoint to open or save it.</p><a className="text-link" href={api.artifactContentUrl(stringValue(selectedArtifact.artifact_id))} target="_blank" rel="noreferrer" download>Open / download stored file</a></section>}{typeof selectedArtifact.content === "string" && selectedArtifact.content.trim() && <details className="goal-decomposition" open><summary>Text content preview</summary><pre>{selectedArtifact.content}</pre></details>}<pre>{JSON.stringify(safeDisplay(selectedArtifact), null, 2)}</pre>{(() => { const linkedIds = [selectedArtifact.audio_artifact_id, selectedArtifact.transcript_artifact_id, selectedArtifact.summary_artifact_id, selectedArtifact.parent_artifact_id, ...(Array.isArray(selectedArtifact.related_artifact_ids) ? selectedArtifact.related_artifact_ids : [])].filter((value): value is string => typeof value === "string" && value.length > 0 && value !== selectedArtifact.artifact_id); return linkedIds.length ? <div className="goal-decomposition"><h4>Linked artifacts</h4><p>Open related audio, transcript, summary, or artifact records when IDs are present.</p><div className="entity-actions">{Array.from(new Set(linkedIds)).map((linkedId) => <button key={linkedId} className="secondary-action" type="button" disabled={artifactDetailBusy} onClick={() => void openArtifactDetails(linkedId)}>{linkedId.slice(0, 12)}…</button>)}</div></div> : null; })()}<div className="entity-actions"><a className="text-link" href={`/artifacts/${encodeURIComponent(stringValue(selectedArtifact.artifact_id))}/content`} target="_blank" rel="noreferrer">Open artifact content</a>{typeof selectedArtifact.content === "string" && selectedArtifact.content.trim() && ["transcripts", "summaries", "reports", "exports"].includes(stringValue(selectedArtifact.type)) && <><button className="secondary-action" type="button" disabled={voiceBusy} onClick={() => void speakArtifactContent(selectedArtifact)}>{voiceBusy ? "Preparing speech…" : "Speak content"}</button><button className="secondary-action" type="button" onClick={async () => { try { await navigator.clipboard.writeText(stringValue(selectedArtifact.content)); setActionNotice("Artifact text copied to clipboard."); } catch (error) { setPageError(formatError(error).message); } }}>Copy text</button></>}{selectedArtifact.type === "audio" && <><button className="secondary-action" type="button" disabled={voiceBusy} onClick={() => void runArtifactVoiceAction(stringValue(selectedArtifact.artifact_id), "process")}>{voiceBusy ? "Processing…" : "Transcribe + summarize"}</button><button className="secondary-action" type="button" disabled={voiceBusy} onClick={() => void runArtifactVoiceAction(stringValue(selectedArtifact.artifact_id), "activate")}>Activate voice interaction</button></>}{selectedArtifact.type === "transcripts" && <button className="secondary-action" type="button" disabled={voiceBusy} onClick={() => void runArtifactVoiceAction(stringValue(selectedArtifact.artifact_id), "summarize")}>{voiceBusy ? "Summarizing…" : "Create / retry summary"}</button>}{selectedArtifact.archived === true ? <button className="secondary-action" type="button" onClick={async () => { const id = stringValue(selectedArtifact.artifact_id); if (!id) return; try { await api.restoreArtifact(id); setSelectedArtifact({ ...selectedArtifact, archived: false }); setActionNotice("Artifact restored."); setPageRevision((value) => value + 1); } catch (error) { setPageError(formatError(error).message); } }}>Restore artifact</button> : <button className="secondary-action" type="button" onClick={async () => { const id = stringValue(selectedArtifact.artifact_id); if (!id) return; try { await api.archiveArtifact(id); setSelectedArtifact({ ...selectedArtifact, archived: true }); setActionNotice("Artifact archived and retained."); setPageRevision((value) => value + 1); } catch (error) { setPageError(formatError(error).message); } }}>Archive artifact</button>}</div></section>}
			<div className="entity-actions"><span>{Number(artifactPagination.total ?? 0)} artifact(s) · page offset {artifactOffset}</span><button className="secondary-action" type="button" disabled={artifactOffset <= 0} onClick={() => setArtifactOffset((value) => Math.max(0, value - 50))}>Previous</button><button className="secondary-action" type="button" disabled={artifactPagination.has_more !== true} onClick={() => setArtifactOffset((value) => value + 50)}>Next</button></div>
		</>;
		if (activePage === "goals") return <>
			<div className="workspace-page-heading"><div><span className="eyebrow">DURABLE MEMORY</span><h2>Goals</h2><p>Persistent goals, progress, objective decomposition, and linked work.</p></div><div className="entity-actions"><button className="secondary-action" type="button" onClick={() => void loadGoalNextActions()} disabled={goalBusy}>{goalBusy ? "Loading…" : "Suggest next actions"}</button><button className="secondary-action" type="button" onClick={() => void saveRecoverySnapshot()}>Save recovery snapshot</button><button className="secondary-action" type="button" onClick={async () => { try { setGoalIntelligence(await api.getGoalIntelligence(currentProject ?? undefined)); setActionNotice("Goal intelligence refreshed from saved goal data."); } catch (error) { setPageError(formatError(error).message); } }}>Analyze portfolio</button><button className="secondary-action" type="button" onClick={async () => { try { const result = await api.exportGoals(currentProject ?? undefined); await navigator.clipboard.writeText(JSON.stringify(result, null, 2)); setActionNotice("Goal export copied to clipboard."); } catch (error) { setPageError(formatError(error).message || "Could not copy goal export."); } }}>Copy goal export</button></div></div>
			{goalIntelligence && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">PORTFOLIO INTELLIGENCE</span><h3>28 deterministic goal signals</h3><p>Generated from saved goals and timestamps. These are diagnostics, not predictions.</p></div><button className="secondary-action" type="button" onClick={() => setGoalIntelligence(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(goalIntelligence), null, 2)}</pre></section>}
			{goalNextActions && <section className="goal-decomposition"><div className="workspace-page-heading"><div><span className="eyebrow">NEXT BEST ACTIONS</span><h3>{Number(goalNextActions.total_eligible ?? records(goalNextActions, "actions").length)} eligible goal(s)</h3><p>Ranked by priority, due date, remaining progress, and readiness. Blocked goals are excluded by the backend.</p></div><button className="secondary-action" type="button" onClick={() => setGoalNextActions(null)}>Close</button></div>{records(goalNextActions, "actions").length ? <div className="entity-list">{records(goalNextActions, "actions").map((item) => { const goal = object(item.goal); const goalId = stringValue(goal.goal_id); return <article className="entity-row" key={goalId}><div className="entity-copy"><strong>{stringValue(goal.title, "Recommended goal")}</strong><span>{stringValue(goal.objective, stringValue(item.reason))}</span><small>{stringValue(goal.priority, "normal")} priority · {Number(goal.progress ?? 0)}% complete · {goal.deadline ? `Due ${stringValue(goal.deadline)}` : "No deadline"}</small></div><button className="secondary-action" type="button" onClick={() => void showGoalTree(goalId)}>Hierarchy</button><button className="primary-action" type="button" onClick={() => void runGoalWorkflows(goalId)}>Run ready tasks</button><button className="secondary-action" type="button" onClick={() => void generateGoalPlan(goalId)}>Generate plan</button></article>; })}</div> : <div className="workspace-empty">No active goals currently meet the next-action readiness rules. Review blocked goals, dependencies, and priorities.</div>}</section>}
			{goalMilestoneView && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">MILESTONE TRACKER</span><h3>{stringValue(goalMilestoneView.goal_id, "Goal milestones")}</h3><p>Milestones are saved to the goal record and retain completion timestamps.</p></div><button className="secondary-action" type="button" onClick={() => setGoalMilestoneView(null)}>Close</button></div>{records(goalMilestoneView, "milestones").length ? <div className="entity-list">{records(goalMilestoneView, "milestones").map((milestone) => { const milestoneId = stringValue(milestone.milestone_id); const goalId = stringValue(goalMilestoneView.goal_id); return <article className="entity-row" key={milestoneId}><div className="entity-copy"><strong>{stringValue(milestone.title, "Milestone")}</strong><small>{stringValue(milestone.status, "pending")} · {stringValue(milestone.deadline, "No deadline")}</small></div><select aria-label={`Milestone status for ${stringValue(milestone.title)}`} value={stringValue(milestone.status, "pending")} onChange={async (event) => { try { await api.updateGoalMilestone(goalId, milestoneId, event.target.value as "pending" | "in_progress" | "completed" | "blocked"); setGoalMilestoneView(await api.getGoalMilestones(goalId)); } catch (error) { setPageError(formatError(error).message); } }}><option value="pending">Pending</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="blocked">Blocked</option></select><button className="secondary-action" type="button" onClick={async () => { if (!window.confirm("Remove this milestone?")) return; try { await api.removeGoalMilestone(goalId, milestoneId); setGoalMilestoneView(await api.getGoalMilestones(goalId)); } catch (error) { setPageError(formatError(error).message); } }}>Remove</button></article>; })}</div> : <p>No milestones saved yet. Use Add milestone on a goal to create one.</p>}</section>}
			{goalSummary && <div className="metric-strip"><span>{Number(goalSummary.total ?? 0)} goals</span><span>{Number(object(goalSummary.by_status).active ?? 0)} active</span><span>{Number(object(goalSummary.by_status).blocked ?? 0)} blocked</span><span>{Number(goalSummary.overdue ?? 0)} overdue</span><span>{Number(goalSummary.invalid_deadlines ?? 0)} invalid deadlines</span></div>}
			{recoverySnapshot && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">SESSION RECOVERY</span><h3>Saved continuation context</h3><p>Compact state for resuming work later without copying the entire conversation.</p></div><button className="secondary-action" type="button" onClick={() => setRecoverySnapshot(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(recoverySnapshot), null, 2)}</pre></section>}
			<form className="goal-form" onSubmit={(event) => void createGoal(event)}><input aria-label="Goal title" placeholder="New goal title" value={goalTitle} onChange={(event) => setGoalTitle(event.target.value)} /><input aria-label="Goal objective" placeholder="Objective (optional)" value={goalObjective} onChange={(event) => setGoalObjective(event.target.value)} /><input aria-label="Goal deadline" type="date" value={goalDeadline} onChange={(event) => setGoalDeadline(event.target.value)} /><button className="primary-action" disabled={!goalTitle.trim() || goalBusy} type="submit">{goalBusy ? "Saving?" : "Create goal"}</button></form>
			{goals.length ? <div className="entity-list">{goals.map((goal) => <article className="entity-row" key={stringValue(goal.goal_id)}><div className="entity-symbol"><FiCrosshair /></div><div className="entity-copy"><strong>{stringValue(goal.title, "Untitled goal")}</strong><span>{stringValue(goal.objective)}</span><small>{stringValue(goal.status, "active")} ? {Number(goal.progress ?? 0)}% complete ? {goal.deadline ? `Due ${stringValue(goal.deadline)}` : "No deadline"} ? {Array.isArray(goal.history) ? goal.history.length : 0} history events</small></div><label className="goal-priority">Priority<select aria-label={`Priority for ${stringValue(goal.title, "goal")}`} value={stringValue(goal.priority, "normal")} onChange={(event) => void setGoalPriority(stringValue(goal.goal_id), event.target.value as "low" | "normal" | "high" | "urgent")}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label><label className="goal-progress">Progress %<input key={`${stringValue(goal.goal_id)}-${Number(goal.progress ?? 0)}`} aria-label={`Progress for ${stringValue(goal.title, "goal")}`} type="number" min={0} max={100} defaultValue={Number(goal.progress ?? 0)} onBlur={(event) => { const value = Number(event.currentTarget.value); if (Number.isFinite(value) && value !== Number(goal.progress ?? 0)) void setGoalProgress(stringValue(goal.goal_id), value, stringValue(goal.status)); }} /></label><label className="goal-dependencies">Prerequisites<select multiple aria-label={`Prerequisites for ${stringValue(goal.title, "goal")}`} value={Array.isArray(goal.dependencies) ? goal.dependencies.filter((item): item is string => typeof item === "string") : []} onChange={(event) => void setGoalDependencies(stringValue(goal.goal_id), Array.from(event.currentTarget.selectedOptions, (option) => option.value))}>{goals.filter((candidate) => stringValue(candidate.goal_id) !== stringValue(goal.goal_id) && !["cancelled"].includes(stringValue(candidate.status))).map((candidate) => <option key={stringValue(candidate.goal_id)} value={stringValue(candidate.goal_id)}>{stringValue(candidate.title, "Untitled goal")}</option>)}</select></label><button className="secondary-action" type="button" onClick={() => void showGoalTree(stringValue(goal.goal_id))}>View hierarchy</button><button className="secondary-action" type="button" onClick={() => void showGoalDependencies(stringValue(goal.goal_id))}>Dependencies</button><button className="secondary-action" type="button" onClick={() => void showGoalReadiness(stringValue(goal.goal_id))}>Readiness</button><button className="secondary-action" type="button" onClick={() => void manageGoalBlockers(goal)}>Manage blockers</button><button className="secondary-action" type="button" onClick={async () => { try { setGoalMilestoneView(await api.getGoalMilestones(stringValue(goal.goal_id))); } catch (error) { setPageError(formatError(error).message); } }}>Milestones</button><button className="secondary-action" type="button" onClick={async () => { const title = window.prompt("Milestone title"); if (!title?.trim()) return; try { await api.addGoalMilestone(stringValue(goal.goal_id), title.trim()); setGoalMilestoneView(await api.getGoalMilestones(stringValue(goal.goal_id))); setActionNotice("Milestone saved."); } catch (error) { setPageError(formatError(error).message); } }}>Add milestone</button><button className="secondary-action" type="button" onClick={async () => { try { const result = await api.duplicateGoal(stringValue(goal.goal_id)); setActionNotice(`Goal duplicated: ${stringValue(object(result.goal).title)}`); setPageRevision((value) => value + 1); } catch (error) { setPageError(formatError(error).message); } }}>Duplicate</button><button className="secondary-action" type="button" onClick={() => void showGoalHistory(stringValue(goal.goal_id))}>History</button><button className="secondary-action" type="button" onClick={() => void generateGoalPlan(stringValue(goal.goal_id))}>Generate plan</button><button className="primary-action" type="button" onClick={() => void runGoalWorkflows(stringValue(goal.goal_id))}>Run ready tasks</button><button className="secondary-action" type="button" onClick={() => void loadGoalDeliverables(stringValue(goal.goal_id))}>Goal deliverables</button><button className="secondary-action" type="button" onClick={() => void setSessionGoal(goal)}>Set session goal</button>{goal.status !== "completed" && goal.status !== "cancelled" && <><button className="secondary-action" type="button" onClick={() => void setGoalStatus(stringValue(goal.goal_id), goal.status === "paused" ? "active" : "paused")}>{goal.status === "paused" ? "Resume" : "Pause"}</button><button className="secondary-action" type="button" onClick={() => void setGoalStatus(stringValue(goal.goal_id), "completed")}>Complete</button><button className="secondary-action" type="button" onClick={() => { if (window.confirm("Cancel this goal?")) void setGoalStatus(stringValue(goal.goal_id), "cancelled"); }}>Cancel</button></>}</article>)}</div> : <div className="workspace-empty">No goals are stored yet.</div>}
			{goals.length > 0 && <section className="goal-decomposition"><div className="workspace-page-heading"><div><span className="eyebrow">GOAL ? OBJECTIVES ? TASKS</span><h3>Break a goal into objectives</h3><p>Enter one objective per line. Objectives are saved as child goals in the existing memory store.</p></div></div><form className="goal-form" onSubmit={(event) => void decomposeGoal(event)}><select aria-label="Parent goal" value={goalParentId} onChange={(event) => setGoalParentId(event.target.value)}><option value="">Choose parent goal</option>{goals.filter((goal) => !["completed", "cancelled"].includes(stringValue(goal.status))).map((goal) => <option key={stringValue(goal.goal_id)} value={stringValue(goal.goal_id)}>{stringValue(goal.title, "Untitled goal")}</option>)}</select><textarea aria-label="Objectives, one per line" placeholder={"Research requirements\nBuild the first version\nConnect it to Lumira Core"} rows={4} value={goalObjectivesText} onChange={(event) => setGoalObjectivesText(event.target.value)} /><button className="primary-action" type="submit" disabled={!goalParentId || !goalObjectivesText.trim() || goalBusy}>{goalBusy ? "Saving?" : "Create objectives"}</button></form></section>}
			{goals.length > 0 && <section className="goal-decomposition"><div className="workspace-page-heading"><div><span className="eyebrow">OBJECTIVES ? WORK ITEMS</span><h3>Create a task workflow</h3><p>Tasks are persisted with dependencies and linked to the selected goal.</p></div></div><form className="goal-form" onSubmit={(event) => void createGoalWorkflow(event)}><input aria-label="Workflow title" placeholder="Workflow title" value={workflowTitle} onChange={(event) => setWorkflowTitle(event.target.value)} /><select aria-label="Workflow category" value={workflowCategory} onChange={(event) => setWorkflowCategory(event.target.value as "business" | "operations")}><option value="operations">Operations</option><option value="business">Business</option></select><textarea aria-label="Tasks, one per line" placeholder={"Inspect existing implementation\nImplement feature\nConnect to Lumira Core"} rows={4} value={workflowTasksText} onChange={(event) => setWorkflowTasksText(event.target.value)} /><button className="primary-action" type="submit" disabled={!goalParentId || !workflowTitle.trim() || !workflowTasksText.trim() || goalBusy}>{goalBusy ? "Saving?" : "Create linked tasks"}</button></form></section>}
			{goalDependencies && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">DEPENDENCY GRAPH</span><h3>{stringValue(goalDependencies.goal_id, "Goal dependencies")}</h3><p>Includes transitive prerequisites, missing references, cycle warnings, and depth limits.</p></div><button className="secondary-action" type="button" onClick={() => setGoalDependenciesView(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(goalDependencies), null, 2)}</pre></section>}
			{goalReadiness && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">GOAL READINESS</span><h3>{goalReadiness.ready_to_execute === true ? "Ready to execute" : "Execution blocked"}</h3><p>{goalReadiness.ready_to_plan === true ? "No active linked workflow blocks planning." : "Resolve the listed blockers or inspect the existing workflow before planning again."}</p></div><button className="secondary-action" type="button" onClick={() => setGoalReadiness(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(goalReadiness), null, 2)}</pre></section>}
			{goalHistory && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">GOAL HISTORY</span><h3>Change history</h3><p>Recorded creation, decomposition, and update events.</p></div><button className="secondary-action" type="button" onClick={() => setGoalHistory(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(goalHistory), null, 2)}</pre></section>}
			{goalTree && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">PERSISTENT HIERARCHY</span><h3>{stringValue(object(goalTree.goal_tree).title, "Goal tree")}</h3><p>Includes child objectives and linked workflows/tasks, with bounded depth.</p></div><button className="secondary-action" type="button" onClick={() => setGoalTree(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(goalTree.goal_tree), null, 2)}</pre></section>}
			{goalExecutionResult && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">GOAL EXECUTION</span><h3>Recorded task outcomes</h3><p>{Number(goalExecutionResult.task_outcomes_count ?? 0)} outcome(s) across {Number(goalExecutionResult.workflows_run ?? 0)} workflow(s) · {stringValue(goalExecutionResult.stop_reason, "unknown")}</p></div><button className="secondary-action" type="button" onClick={() => setGoalExecutionResult(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(goalExecutionResult), null, 2)}</pre></section>}
			{goalDeliverables && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">GOAL DELIVERABLES</span><h3>Stored outputs across linked workflows</h3><p>{Number(goalDeliverables.count ?? 0)} artifact(s) from {Number(goalDeliverables.workflows_scanned ?? 0)} workflow(s). Archived artifacts are excluded by default.</p></div><button className="secondary-action" type="button" onClick={() => setGoalDeliverables(null)}>Close</button></div><div className="entity-list">{records(goalDeliverables, "deliverables").map((artifact, index) => { const artifactId = stringValue(artifact.artifact_id); return <article className="entity-row" key={artifactId || String(index)}><div className="entity-symbol"><FiPaperclip /></div><div className="entity-copy"><strong>{stringValue(artifact.title, stringValue(artifact.type, "Goal deliverable"))}</strong><span>{stringValue(artifact.source, "Linked workflow output")}</span><small>{artifact.content_available === true ? "Content available" : "Metadata only"} · {stringValue(artifact.timestamp)}</small></div>{artifactId && <><button className="secondary-action" type="button" onClick={() => { setActivePage("artifacts"); void openArtifactDetails(artifactId); }}>Details</button>{artifact.content_available === true && <a className="text-link" href={api.artifactContentUrl(artifactId)} target="_blank" rel="noreferrer">Open content</a>}</>}</article>; })}</div><details><summary>Structured deliverables data</summary><pre>{JSON.stringify(safeDisplay(goalDeliverables), null, 2)}</pre></details></section>}
			{goalPlan && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">PLANNER CONTRACT</span><h3>Generated plan and execution contract</h3><p>Saved as metadata on the linked workflow. This plan has not been executed.</p></div><button className="secondary-action" type="button" onClick={() => setGoalPlan(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(goalPlan), null, 2)}</pre></section>}
		</>;
		if (activePage === "memory") return <>
			<div className="workspace-page-heading"><div><span className="eyebrow">DURABLE MEMORY</span><h2>Relevant memory</h2><p>Results are retrieved from the existing memory service for the current session.</p></div><button className="secondary-action" type="button" onClick={() => setPageRevision((value) => value + 1)}>Refresh</button></div>
			<div className="workspace-page-heading"><div><span className="eyebrow">MEMORY OPERATIONS</span><h3>Search and summarize</h3><p>Search durable cognitive memory or view bounded record counts. Archive and linking APIs preserve auditable history.</p></div><button className="secondary-action" type="button" disabled={memoryBusy} onClick={() => void loadMemorySummary()}>{memoryBusy ? "Loading..." : "Summarize memory"}</button></div>
			<form className="workspace-search" onSubmit={(event) => void runMemorySearch(event)}><FiSearch /><input aria-label="Search cognitive memory" placeholder="Search goals, decisions, experiences, learning" value={memorySearchQuery} onChange={(event) => setMemorySearchQuery(event.target.value)} /><button className="primary-action" type="submit" disabled={!memorySearchQuery.trim() || memoryBusy}>{memoryBusy ? "Searching..." : "Search memory"}</button></form>
			{memorySummary && <section className="memory-results"><h3>Memory summary</h3><pre>{JSON.stringify(safeDisplay(memorySummary), null, 2)}</pre></section>}
			{memorySearchResult && <section className="memory-results"><h3>Search results</h3><pre>{JSON.stringify(safeDisplay(memorySearchResult), null, 2)}</pre></section>}
			<section className="goal-decomposition"><div className="workspace-page-heading"><div><h3>Decision log</h3><p>Record a decision with its rationale and link it to the current session, project, and goal.</p></div><button className="secondary-action" type="button" disabled={memoryBusy} onClick={() => void loadMemoryDecisions()}>{memoryBusy ? "Loading..." : "Load decisions"}</button></div><form className="goal-form" onSubmit={(event) => void saveMemoryDecision(event)}><input aria-label="Decision statement" required maxLength={2000} value={decisionText} onChange={(event) => setDecisionText(event.target.value)} placeholder="Decision made" /><textarea aria-label="Decision rationale" maxLength={5000} rows={3} value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} placeholder="Why this decision was made" /><textarea aria-label="Decision alternatives" maxLength={5000} rows={2} value={decisionAlternatives} onChange={(event) => setDecisionAlternatives(event.target.value)} placeholder={"Alternatives considered (one per line)"} /><textarea aria-label="Decision constraints" maxLength={5000} rows={2} value={decisionConstraints} onChange={(event) => setDecisionConstraints(event.target.value)} placeholder={"Constraints to preserve (one per line)"} /><label>Confidence: {Math.round(decisionConfidence * 100)}%<input type="range" min={0} max={1} step={0.05} value={decisionConfidence} onChange={(event) => setDecisionConfidence(Number(event.target.value))} /></label><button className="primary-action" type="submit" disabled={memoryBusy || !decisionText.trim()}>{memoryBusy ? "Saving..." : "Record decision"}</button></form>{decisionRecords.length ? <pre>{JSON.stringify(safeDisplay(decisionRecords), null, 2)}</pre> : <p>No decisions loaded for the current scope.</p>}</section><section className="goal-decomposition"><h3>Link memory records</h3><p>Use record IDs from search results. The API validates that both records exist.</p><form className="goal-form" onSubmit={(event) => void linkMemoryRecords(event)}><input aria-label="Source memory record ID" required value={memoryLinkSource} onChange={(event) => setMemoryLinkSource(event.target.value)} placeholder="Source record ID" /><input aria-label="Target memory record ID" required value={memoryLinkTarget} onChange={(event) => setMemoryLinkTarget(event.target.value)} placeholder="Target record ID" /><input aria-label="Relationship label" required maxLength={100} value={memoryLinkRelation} onChange={(event) => setMemoryLinkRelation(event.target.value)} placeholder="related_to" /><button className="primary-action" type="submit" disabled={memoryBusy || !memoryLinkSource.trim() || !memoryLinkTarget.trim()}>{memoryBusy ? "Saving..." : "Link records"}</button></form></section><section className="goal-decomposition"><h3>Archive memory record</h3><p>Archive retains the record and marks it archived; it does not delete it.</p><form className="goal-form" onSubmit={(event) => void archiveMemoryRecord(event)}><select aria-label="Memory collection to archive" value={memoryArchiveCollection} onChange={(event) => setMemoryArchiveCollection(event.target.value)}><option value="goals">Goals</option><option value="decisions">Decisions</option><option value="experiences">Experiences</option><option value="learning_records">Learning records</option><option value="artifacts">Artifacts</option></select><input aria-label="Record ID to archive" required value={memoryArchiveId} onChange={(event) => setMemoryArchiveId(event.target.value)} placeholder="Record ID" /><button className="secondary-action" type="submit" disabled={memoryBusy || !memoryArchiveId.trim()}>Archive record</button></form></section><div className="memory-results"><h3>Stored memory snapshot</h3><pre>{JSON.stringify(safeDisplay(memoryData), null, 2)}</pre></div>
		</>;
		if (activePage === "search") {
			const resultGroups = object(searchResult?.results);
			const resultCount = Object.values(resultGroups).reduce<number>((total, value) => total + (Array.isArray(value) ? value.length : 0), 0);
			return <>
				<div className="workspace-page-heading"><div><span className="eyebrow">UNIFIED SEARCH</span><h2>Search Lumira</h2><p>Projects, versions, files, artifacts, workflows, goals, devices, sessions, memory, voice ideas, and learning history.</p></div></div>
				<form className="workspace-search" onSubmit={(event) => { event.preventDefault(); void runSearch(); }}><FiSearch /><input ref={searchInputRef} aria-label="Search Lumira" placeholder="Search workspace data" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} /><button className="primary-action" disabled={!searchQuery.trim() || searchBusy}>{searchBusy ? "Searching…" : "Search"}</button></form>
				{searchResult ? <><div className="entity-actions"><span>Results for “{stringValue(searchResult.query, searchQuery)}” · {resultCount} match(es)</span><button className="secondary-action" type="button" onClick={() => setSearchResult(null)}>Clear results</button><button className="secondary-action" type="button" onClick={() => { setSearchQuery(""); setSearchResult(null); }}>New search</button></div>{resultCount === 0 && <div className="workspace-empty">No matching records were found. Try a shorter query or a different keyword.</div>}<div className="search-groups">{Object.entries(resultGroups).map(([group, value]) => {
					const list = Array.isArray(value) ? value : [];
					return <section className="search-group" key={group}><h3>{group.replaceAll("_", " ")} <small>{list.length}</small></h3>{list.map((rawItem, index) => { const item = object(rawItem); const artifactId = stringValue(item.artifact_id); const workflowId = stringValue(item.workflow_id); const goalId = stringValue(item.goal_id); const title = stringValue(item.title ?? item.name ?? item.project ?? item.goal_title ?? item.workflow_title ?? item.artifact_type ?? item.type ?? item.session_id ?? item.memory_id, `${group.replaceAll("_", " ")} result ${index + 1}`); const description = stringValue(item.description ?? item.objective ?? item.summary ?? item.content_preview ?? item.source ?? item.path ?? item.status, "Matched record"); return <article className="memory-results" key={`${group}-${index}`}><strong>{title}</strong><p>{description}</p><details><summary>Record details</summary><pre>{JSON.stringify(safeDisplay(item), null, 2)}</pre></details>{(artifactId || workflowId || goalId) && <div className="entity-actions">{artifactId && <button className="secondary-action" type="button" onClick={() => { setActivePage("artifacts"); void openArtifactDetails(artifactId); }}>Open artifact</button>}{workflowId && <button className="secondary-action" type="button" onClick={() => { setActivePage("operations"); setActionNotice(`Workflow found: ${workflowId}. Inspect it in Operations.`); }}>Open workflow area</button>}{goalId && <button className="secondary-action" type="button" onClick={() => { setActivePage("goals"); setActionNotice(`Goal found: ${goalId}. Inspect its hierarchy and history in Goals.`); }}>Open goal area</button>}</div>}</article>; })}</section>;
				})}</div></> : <div className="workspace-empty">Run a search to query Lumira's unified index.</div>}
			</>;
		}
		if (activePage === "generator") return <>
			<div className="workspace-page-heading"><div><span className="eyebrow">GENERATOR MODE</span><h2>Create with Lumira</h2><p>Local specifications and artifacts work now; rendered media requires a configured provider.</p></div><span className="status-pill">{titleForMode(activeMode)}</span></div>
			<div className="capability-list"><button type="button" onClick={() => setPromptFromTool("Write a report about ", "generator")}><strong>Document outline</strong><span>Creates a truthful, searchable outline artifact.</span></button><button type="button" onClick={() => setPromptFromTool("Generate a diagram for ", "generator")}><strong>Diagrams & blueprints</strong><span>Creates structured local diagram artifacts.</span></button><button type="button" onClick={() => setPromptFromTool("Generate a video about ", "generator")}><strong>Video generation</strong><span>Routes through the provider boundary; unavailable providers return a structured error.</span></button><button type="button" onClick={() => setPromptFromTool("Generate an image of ", "generator")}><strong>Image generation</strong><span>Routes through the configured image provider and artifact manager.</span></button></div>
		</>;
		if (activePage === "business") return <>
			<div className="workspace-page-heading"><div><span className="eyebrow">BUSINESS MODE</span><h2>Objectives & plans</h2><p>Business workflows use saved goals, tasks, decisions, and artifacts.</p></div><button className="primary-action" type="button" onClick={() => setPromptFromTool("Plan for launching ", "business")}>Create business plan</button></div>
			<div className="metric-strip"><span>{goals.length} saved goals</span><span>{workflows.length} business plans</span><span>Metrics only appear when real data exists.</span></div>
			{workflows.length ? <WorkflowList workflows={workflows} onTaskUpdate={updateTask} onRunReady={runWorkflowAgents} onRetryFailed={retryFailedWorkflowTasks} /> : <div className="workspace-empty">No business workflows are recorded.</div>}
		</>;
		if (activePage === "operations") return <>
			<div className="workspace-page-heading"><div><span className="eyebrow">OPERATIONS MODE</span><h2>Workflows & recovery</h2><p>Track dependencies, blockers, statuses, and persisted execution runs.</p></div><div className="entity-actions"><button className="secondary-action" type="button" onClick={async () => { try { const exported = await api.exportWorkflows(undefined, undefined, 200); await navigator.clipboard.writeText(JSON.stringify(exported, null, 2)); setActionNotice("Bounded workflow export copied to clipboard."); } catch (error) { setPageError(formatError(error).message); } }}>Export workflows</button><button className="primary-action" type="button" onClick={() => setPromptFromTool("Plan operational tasks for ", "operations")}>Plan operations</button></div></div>
			<section className="goal-decomposition"><div className="workspace-page-heading"><div><h3>Create a workflow directly</h3><p>Save a task sequence without requiring a parent goal. This creates the workflow only; it does not execute tasks.</p></div></div><form className="goal-form" onSubmit={(event) => void createStandaloneWorkflow(event)}><input aria-label="Standalone workflow title" required maxLength={200} value={workflowTitle} onChange={(event) => setWorkflowTitle(event.target.value)} placeholder="Workflow title" /><select aria-label="Standalone workflow category" value={workflowCategory} onChange={(event) => setWorkflowCategory(event.target.value as "business" | "operations")}><option value="operations">Operations</option><option value="business">Business</option></select><textarea aria-label="Standalone workflow tasks" required maxLength={10000} rows={4} value={workflowTasksText} onChange={(event) => setWorkflowTasksText(event.target.value)} placeholder={"Inspect current state\nImplement the next feature\nRecord the outcome"} />
					<small>{workflowTasksText.split(/\r?\n/).map((task) => task.trim()).filter(Boolean).length}/20 tasks · Each task must be 500 characters or fewer.</small><button className="primary-action" type="submit" disabled={!workflowTitle.trim() || !workflowTasksText.trim() || goalBusy || workflowTasksText.split(/\r?\n/).map((task) => task.trim()).filter(Boolean).length > 20 || workflowTasksText.split(/\r?\n/).some((task) => task.trim().length > 500)}>{goalBusy ? "Saving workflow…" : "Save workflow"}</button></form></section>
			{pageData?.workflowSummary && <div className="metric-strip"><span>{Number(object(pageData.workflowSummary).scanned_workflows ?? 0)} workflows scanned</span><span>{Number(object(object(pageData.workflowSummary)["workflow_status_counts"]).in_progress ?? 0)} in progress</span><span>{Number(object(object(pageData.workflowSummary)["workflow_status_counts"]).blocked ?? 0)} blocked</span><span>{Number(object(object(pageData.workflowSummary)["workflow_status_counts"]).failed ?? 0)} failed</span><span>{Number(object(pageData.workflowSummary).task_completion_percent ?? 0)}% task completion</span></div>}
			<form className="workspace-search" onSubmit={async (event) => { event.preventDefault(); if (!workflowSearchQuery.trim()) { setWorkflowSearchResult(null); return; } try { setWorkflowSearchResult(await api.searchWorkflows(workflowSearchQuery.trim(), { limit: 50 })); } catch (error) { setPageError(formatError(error).message); } }}><FiSearch /><input aria-label="Search all workflows" placeholder="Search all workflows and task titles" value={workflowSearchQuery} onChange={(event) => setWorkflowSearchQuery(event.target.value)} /><button className="primary-action" type="submit" disabled={!workflowSearchQuery.trim()}>Search workflows</button><button className="secondary-action" type="button" disabled={!workflowSearchQuery && !workflowSearchResult} onClick={() => { setWorkflowSearchQuery(""); setWorkflowSearchResult(null); }}>Clear</button></form>
			{workflowSearchResult && <section className="memory-results"><div className="workspace-page-heading"><div><h3>Workflow search results</h3><p>{Number(workflowSearchResult.total ?? 0)} match(es)</p></div><button className="secondary-action" type="button" onClick={() => setWorkflowSearchResult(null)}>Close</button></div><p>{records(workflowSearchResult, "workflows").map((item) => stringValue(item.title, stringValue(item.workflow_id, "Workflow"))).join(" · ") || "No matching workflows."}</p><pre>{JSON.stringify(safeDisplay(workflowSearchResult), null, 2)}</pre></section>}
			{pageData?.workflowAttention && records(pageData.workflowAttention, "items").length > 0 && <section className="run-history"><div className="workspace-page-heading"><div><span className="eyebrow">NEEDS ATTENTION</span><h3>Blocked, failed, or stale workflows</h3><p>Prioritized from persisted workflow/task state; no automatic execution is triggered.</p></div><span className="status-pill">{Number(object(pageData.workflowAttention).total_attention_items ?? 0)} items</span></div>{records(pageData.workflowAttention, "items").map((item) => { const workflowId = stringValue(item.workflow_id); return <article className="entity-row" key={workflowId}><div className="entity-copy"><strong>{stringValue(item.title, workflowId)}</strong><span>{stringValue(item.recommended_action).replaceAll("_", " ")}</span><small>{stringValue(item.status)} · {Number(item.failed_task_count ?? 0)} failed · {Number(item.blocked_task_count ?? 0)} blocked{item.stale === true ? " · stale >7 days" : ""}</small></div><button className="secondary-action" type="button" onClick={async () => { try { setWorkflowGraph(await api.workflowDependencyGraph(workflowId)); } catch (error) { setPageError(formatError(error).message); } }}>Dependency graph</button></article>; })}</section>}
			{workflowGraph && <section className="memory-results"><div className="workspace-page-heading"><div><span className="eyebrow">WORKFLOW DEPENDENCIES</span><h3>{stringValue(workflowGraph.workflow_id)}</h3><p>{Number(workflowGraph.node_count ?? 0)} task nodes · {Number(workflowGraph.edge_count ?? 0)} dependency edges</p></div><button className="secondary-action" type="button" onClick={() => setWorkflowGraph(null)}>Close</button></div><div className="entity-list">{records(workflowGraph, "nodes").map((node) => { const taskId = stringValue(node.task_id); const taskStatus = stringValue(node.status); const runTaskAction = async (action: "start" | "complete" | "retry" | "unblock" | "block" | "fail") => { try { if (action === "start") await api.startWorkflowTask(stringValue(workflowGraph.workflow_id), taskId); else if (action === "complete") await api.completeWorkflowTask(stringValue(workflowGraph.workflow_id), taskId); else if (action === "retry") await api.retryWorkflowTask(stringValue(workflowGraph.workflow_id), taskId); else if (action === "unblock") await api.unblockWorkflowTask(stringValue(workflowGraph.workflow_id), taskId); else { const reason = window.prompt(action === "block" ? "Why is this task blocked?" : "Why did this task fail?")?.trim(); if (!reason) return; if (action === "block") await api.blockWorkflowTask(stringValue(workflowGraph.workflow_id), taskId, reason); else await api.failWorkflowTask(stringValue(workflowGraph.workflow_id), taskId, reason); } setWorkflowGraph(await api.workflowDependencyGraph(stringValue(workflowGraph.workflow_id))); setPageRevision((value) => value + 1); setActionNotice("Workflow task state updated and persisted."); } catch (error) { setPageError(formatError(error).message); } }; return <article className="entity-row" key={taskId}><div className="entity-copy"><strong>{stringValue(node.title, taskId)}</strong><small>{taskStatus}</small></div><div className="entity-actions"><button className="secondary-action" type="button" disabled={workflowTaskDetailBusy !== null} onClick={() => void inspectWorkflowTask(stringValue(workflowGraph.workflow_id), taskId, "history")}>{workflowTaskDetailBusy === `${stringValue(workflowGraph.workflow_id)}:${taskId}:history` ? "Loading history…" : "History"}</button><button className="secondary-action" type="button" disabled={workflowTaskDetailBusy !== null} onClick={() => void inspectWorkflowTask(stringValue(workflowGraph.workflow_id), taskId, "result")}>{workflowTaskDetailBusy === `${stringValue(workflowGraph.workflow_id)}:${taskId}:result` ? "Loading result…" : "Result"}</button>{taskStatus === "pending" && <button className="secondary-action" type="button" onClick={() => void runTaskAction("start")}>Start</button>}{taskStatus === "in_progress" && <><button className="secondary-action" type="button" onClick={() => void runTaskAction("complete")}>Complete</button><button className="secondary-action" type="button" onClick={() => void runTaskAction("block")}>Block</button><button className="secondary-action" type="button" onClick={() => void runTaskAction("fail")}>Mark failed</button></>}{taskStatus === "failed" && <button className="secondary-action" type="button" onClick={() => void runTaskAction("retry")}>Retry</button>}{taskStatus === "blocked" && <button className="secondary-action" type="button" onClick={() => void runTaskAction("unblock")}>Unblock</button>}</div></article>; })}</div><pre>{JSON.stringify(safeDisplay(workflowGraph), null, 2)}</pre></section>}
			{(workflowTaskHistory || workflowTaskResult) && <section className="memory-results"><div className="workspace-page-heading"><div><h3>{workflowTaskHistory ? "Task history" : "Task result"}</h3><p>Persisted workflow task details</p></div><div className="entity-actions"><button className="secondary-action" type="button" onClick={async () => { try { await navigator.clipboard.writeText(JSON.stringify(safeDisplay(workflowTaskHistory ?? workflowTaskResult), null, 2)); setActionNotice("Task details copied to clipboard."); } catch (error) { setPageError(formatError(error).message); } }}>Copy details</button><button className="secondary-action" type="button" onClick={() => { setWorkflowTaskHistory(null); setWorkflowTaskResult(null); }}>Close details</button></div></div><pre>{JSON.stringify(safeDisplay(workflowTaskHistory ?? workflowTaskResult), null, 2)}</pre></section>}
			{workflows.length ? <WorkflowList workflows={workflows} onTaskUpdate={updateTask} onRunReady={runWorkflowAgents} onRetryFailed={retryFailedWorkflowTasks} /> : <div className="workspace-empty">No operations workflows are recorded.</div>}
			<section className="run-history"><h3>Execution recovery</h3>{runs.length ? runs.map((run, index) => <article className="entity-row" key={stringValue(run.run_id, String(index))}><div className="entity-copy"><strong>{stringValue(run.status, "unknown")}</strong><span>{stringValue(run.goal)}</span><small>{stringValue(run.current_stage ?? run.last_completed_stage, "no stage")}</small></div><button className="secondary-action" type="button" disabled={runDetailBusy === stringValue(run.run_id)} onClick={() => void inspectRun(stringValue(run.run_id))}>{runDetailBusy === stringValue(run.run_id) ? "Loading…" : "Details"}</button>{run.status !== "completed" && <button className="secondary-action" type="button" disabled={run.resume_allowed === false} onClick={() => void resumeRun(stringValue(run.run_id))}>{run.resume_allowed === false ? "Reconcile" : "Resume"}</button>}</article>) : <p className="empty-note">No execution runs are recorded.</p>}{selectedRun && <section className="memory-results"><div className="workspace-page-heading"><div><h3>Execution run details</h3><p>{stringValue(selectedRun.run_id)}</p></div><button className="secondary-action" type="button" onClick={() => setSelectedRun(null)}>Close</button></div><pre>{JSON.stringify(safeDisplay(selectedRun), null, 2)}</pre></section>}</section>
		</>;
		if (activePage === "image-understanding") return <ImageUnderstandingPanel />;
		if (activePage === "features") return <>
			<div className="workspace-page-heading"><div><span className="eyebrow">FEATURE REGISTRY</span><h2>Lumira feature control center</h2><p>All 28 catalog entries, dependency blockers, and explicit activation controls. Enabling a registry entry never bypasses provider credentials or the OS-sandbox safety gate.</p></div><button className="secondary-action" type="button" onClick={() => setPageRevision((value) => value + 1)}>Refresh</button></div>
			<div className="metric-strip"><span>{featureEntries.length} registered features</span><span>{Array.isArray(pageData?.enabled) ? pageData.enabled.length : 0} enabled</span><span>{Object.keys(activationBlocked).length} readiness-blocked</span></div>
			{featureEntries.length ? <div className="entity-list">{featureEntries.map(([featureId, rawFeature]) => {
				const feature = object(rawFeature);
				const enabled = feature.enabled === true && feature.status === "ENABLED";
				const blockers = activationBlocked[featureId];
				const blockerList = Array.isArray(blockers) ? blockers.filter((item): item is string => typeof item === "string") : [];
				const capabilities = Array.isArray(feature.capabilities) ? feature.capabilities.filter((item): item is string => typeof item === "string") : [];
				const dependencies = Array.isArray(feature.dependencies) ? feature.dependencies.filter((item): item is string => typeof item === "string") : [];
				const protectedFeature = ["memory", "voice_input", "security"].includes(featureId);
				const blocked = blockerList.length > 0;
				const canAttemptEnable = ["AVAILABLE", "EXPERIMENTAL", "DISABLED", "DEGRADED"].includes(stringValue(feature.status)) && !blocked;
				return <article className="entity-row feature-row" key={featureId}><div className="entity-symbol"><FiCpu /></div><div className="entity-copy"><strong>{featureId.replaceAll("_", " ")}</strong><span>{capabilities.join(" · ") || "No capabilities listed"}</span><small>{stringValue(feature.category, "feature")} · {stringValue(feature.status, "UNKNOWN")} · dependencies: {dependencies.join(", ") || "none"}{blocked ? ` · blocked: ${blockerList.join(", ")}` : ""}</small></div><div className="entity-actions"><span className="status-pill">{enabled ? "Enabled" : stringValue(feature.status, "Unknown")}</span><button type="button" disabled={enabled ? protectedFeature : !canAttemptEnable} title={blocked ? blockerList.join(", ") : undefined} onClick={() => void toggleFeature(featureId, enabled)}>{enabled ? "Disable" : "Enable"}</button></div></article>;
			})}</div> : <div className="workspace-empty">The feature registry returned no entries.</div>}
		</>;
		if (activePage === "settings") return <>
			<div className="workspace-page-heading"><div><span className="eyebrow">PREFERENCES</span><h2>Workspace settings</h2><p>Panel preferences are saved locally on this device.</p></div><button className="secondary-action" type="button" onClick={async () => { try { const result = await api.exportSessions({ limit: 100, include_recent_messages: false }); await navigator.clipboard.writeText(JSON.stringify(result, null, 2)); setActionNotice("Redacted session metadata export copied to clipboard."); } catch (error) { setPageError(formatError(error).message); } }}>Export session metadata</button></div>
			{pageData?.sessionSummary && <div className="metric-strip"><span>{Number(object(pageData.sessionSummary).scanned_sessions ?? 0)} sessions scanned</span><span>{Number(object(object(pageData.sessionSummary)["status_counts"]).active ?? 0)} active</span><span>{Number(object(object(pageData.sessionSummary)["status_counts"]).paused ?? 0)} paused</span><span>{records(pageData.sessionSummary, "stale_session_ids").length} stale</span><span>{records(pageData.sessionSummary, "sessions_with_recovery_snapshots").length} recoverable</span></div>}
			{session?.session_id && <section className="settings-capability-status"><h3>Current session diagnostics</h3><p>Inspect context completeness and linked workflow records without changing the session.</p><div className="entity-actions"><button className="secondary-action" type="button" onClick={async () => { try { setSessionHealth(await api.getSessionHealth(session.session_id)); } catch (error) { setPageError(formatError(error).message); } }}>Inspect session health</button><button className="secondary-action" type="button" onClick={async () => { try { setSessionWorkflows(await api.getSessionWorkflows(session.session_id)); } catch (error) { setPageError(formatError(error).message); } }}>Load linked workflows</button></div>{sessionHealth && <pre>{JSON.stringify(safeDisplay(sessionHealth), null, 2)}</pre>}{sessionWorkflows && <pre>{JSON.stringify(safeDisplay(sessionWorkflows), null, 2)}</pre>}</section>}
			<div className="settings-list"><label>Main navigation<select value={navMode} onChange={(event) => isPanelMode(event.target.value) && setNavMode(event.target.value)}><option value="full">Full</option><option value="compact">Icon only</option><option value="hidden">Hidden</option></select></label><label>Chat sidebar<select value={chatMode} onChange={(event) => isPanelMode(event.target.value) && setChatMode(event.target.value)}><option value="full">Full</option><option value="compact">Compact</option><option value="hidden">Hidden</option></select></label><label>Development panel<select value={rightMode} onChange={(event) => isPanelMode(event.target.value) && setRightMode(event.target.value)}><option value="full">Full</option><option value="compact">Compact</option><option value="hidden">Hidden</option></select></label><label>Assistant input<select value={inputMode} onChange={(event) => setInputMode(event.target.value as "full" | "compact" | "hidden")}><option value="full">Full</option><option value="compact">Compact</option><option value="hidden">Hidden</option></select></label></div>
			<div className="settings-status"><span>Core connection</span><strong>{connectionStatus === "online" ? "Online" : connectionStatus === "checking" ? "Connecting" : "Offline"}</strong><span>Active mode</span><strong>{titleForMode(activeMode)}</strong></div>
			<section className="settings-capability-status"><h3>Core capability status</h3><p>Brain stages: {Array.isArray(object(object(pageData?.intelligence).brain).stages) ? (object(object(pageData?.intelligence).brain).stages as unknown[]).length : "—"}</p><p>Catalog features: {typeof object(pageData?.intelligence).features === "object" ? String(object(object(pageData?.intelligence).features).count ?? "—") : "—"}</p><p>Recent pipeline records: {String(object(pageData?.history).count ?? "—")}</p><p>Registered providers: {Object.entries(object(object(pageData?.intelligence).providers)).filter(([, provider]) => object(provider).registered === true).map(([name]) => name).join(", ") || "None configured"}</p><p>Project terminal: disabled until OS sandbox verification is implemented.</p></section>
			<ProviderDiagnosticsPanel />
			<section className="settings-capability-status">
				<div className="workspace-page-heading"><div><h3>Device registry</h3><p>Register future Lumira devices and declare bounded capabilities/permissions. Commands require a matching registered type, online status, the commands.receive permission, and a configured transport provider.</p></div><button className="secondary-action" type="button" disabled={deviceLoading} onClick={() => setPageRevision((value) => value + 1)}>{deviceLoading ? "Refreshing…" : "Refresh registry"}</button></div>
				<div className="metric-strip"><span>{deviceRecords.length} registered</span><span>{deviceRecords.filter((device) => device.status === "online").length} marked online</span><span>{deviceRecords.filter((device) => device.status === "offline").length} marked offline</span><span>{deviceRecords.filter((device) => device.status === "maintenance").length} in maintenance</span></div>
				<form className="settings-list" onSubmit={(event) => void registerDevice(event)}>
					<label>Device ID<input required maxLength={128} value={deviceIdInput} onChange={(event) => setDeviceIdInput(event.target.value)} placeholder="e.g. cyberdeck-01" /></label>
					<label>Device type<select value={deviceTypeInput} onChange={(event) => setDeviceTypeInput(event.target.value)}><option value="raspberry_pi">Raspberry Pi</option><option value="esp32">ESP32</option><option value="arduino">Arduino</option><option value="robotics">Robotics</option><option value="cyberdeck">Cyberdeck</option><option value="smart_glasses">Smart glasses</option><option value="mobile">Mobile</option><option value="camera">Camera</option><option value="microphone">Microphone</option><option value="sensor">Sensor</option><option value="smart_home">Smart home</option><option value="vehicle">Vehicle</option></select></label>
					<label>Connection<select value={deviceConnection} onChange={(event) => setDeviceConnection(event.target.value)}><option value="unverified">Unverified</option><option value="local">Local</option><option value="wifi">Wi-Fi</option><option value="bluetooth">Bluetooth</option><option value="usb">USB</option><option value="serial">Serial</option><option value="cloud">Cloud</option></select></label>
					<label>Capabilities (comma-separated)<input value={deviceCapabilitiesText} onChange={(event) => setDeviceCapabilitiesText(event.target.value)} placeholder="temperature.read, led.control" /></label>
					<label>Permissions (comma-separated)<input value={devicePermissionsText} onChange={(event) => setDevicePermissionsText(event.target.value)} placeholder="telemetry.read" /></label>
					<small>Allowed: telemetry.read, commands.receive, camera.capture, microphone.capture, robot.motion, smart_home.control, vehicle.read, files.read, files.write.</small>
					<button className="primary-action" type="submit" disabled={!deviceIdInput.trim() || deviceBusy}>{deviceBusy ? "Registering..." : "Register device"}</button>
				</form>
				<input aria-label="Search registered devices" value={deviceSearch} onChange={(event) => setDeviceSearch(event.target.value)} placeholder="Filter by device ID, type, capability, or permission" />
				{deviceRecords.filter((device) => JSON.stringify(device).toLowerCase().includes(deviceSearch.trim().toLowerCase())).length ? <div className="entity-list">{deviceRecords.filter((device) => JSON.stringify(device).toLowerCase().includes(deviceSearch.trim().toLowerCase())).map((device) => <article className="entity-row" key={stringValue(device.device_id)}><div className="entity-copy"><strong>{stringValue(device.device_id)}</strong><span>{stringValue(device.device_type)} · {stringValue(device.connection, "unverified")}</span><small>Capabilities: {Array.isArray(device.capabilities) ? device.capabilities.join(", ") || "none declared" : "none declared"} · Permissions: {Array.isArray(device.permissions) ? device.permissions.join(", ") || "none granted" : "none granted"}</small><small>Last message: {stringValue(device.last_seen, "not seen yet")}</small></div><label>Status<select aria-label={`Status for ${stringValue(device.device_id)}`} value={stringValue(device.status, "registered")} disabled={deviceStatusBusy !== null || deviceLoading} onChange={(event) => void changeDeviceStatus(stringValue(device.device_id), event.target.value)}><option value="registered">Registered</option><option value="online" disabled>Online (heartbeat)</option><option value="offline">Offline</option><option value="maintenance">Maintenance</option></select></label></article>)}</div> : <div className="workspace-empty">{deviceLoading ? "Loading registered devices…" : deviceRecords.length ? "No devices match this filter." : "No devices registered yet."}</div>}
			</section>
			<section className="settings-capability-status">
				<div className="workspace-page-heading"><div><h3>Recent device messages</h3><p>Read-only records accepted by the device gateway. A message record is not proof that a device is currently reachable.</p></div><span className="status-pill">{deviceMessages.length} loaded · up to 10 shown</span></div>
				<input aria-label="Filter device messages" value={deviceMessageSearch} onChange={(event) => setDeviceMessageSearch(event.target.value)} placeholder="Filter by device ID, message type, or payload" />
				{deviceMessages.filter((message) => JSON.stringify(message).toLowerCase().includes(deviceMessageSearch.trim().toLowerCase())).length ? <div className="entity-list">{deviceMessages.filter((message) => JSON.stringify(message).toLowerCase().includes(deviceMessageSearch.trim().toLowerCase())).slice(0, 10).map((message, index) => <article className="entity-row" key={stringValue(message.message_id, `${stringValue(message.device_id, "device")}-${stringValue(message.timestamp, String(index))}`)}><div className="entity-copy"><strong>{stringValue(message.device_id, "Unknown device")}</strong><span>{stringValue(message.message_type, "message")} · {stringValue(message.client_timestamp, stringValue(message.received_at, "timestamp unavailable"))}</span><small>Type: {stringValue(message.device_type, "unknown")} · Message status: {stringValue(message.status, "received")}</small><details><summary>Inspect payload</summary><pre>{JSON.stringify(safeDisplay(message.payload ?? message), null, 2)}</pre></details></div></article>)}</div> : <div className="workspace-empty">{deviceMessagesLoading ? "Loading device messages…" : deviceMessages.length ? "No messages match this filter." : "No device messages have been recorded yet."}</div>}
			</section>
			<IntelligenceProbe />
		</>;
		return <div className="workspace-empty">This workspace view is unavailable.</div>;
	};

	const renderedPage = pageContent();
	const layoutStyle = {
		gridTemplateColumns: columns,
		"--nav-panel-width": `${navWidth}px`,
		"--chat-panel-width": `${chatWidth}px`,
	} as CSSProperties;

	return (
		<main className={`workspace-shell ${focusMode ? "focus-mode" : ""} ${topBarCompact ? "topbar-compact" : ""} ${inputMode === "compact" ? "input-compact" : ""} ${effectiveNavMode === "hidden" ? "nav-hidden" : ""}`} style={layoutStyle} data-testid="workspace-shell">
			<Sidebar mode={effectiveNavMode} activePage={activePage} width={navWidth} onResize={(change) => setPanelWidth("nav", navWidth + change)} onNavigate={navigate} onNewChat={() => void startNewSession()} onModeSelect={() => { setActivePage("settings"); window.setTimeout(() => document.querySelector<HTMLSelectElement>('.mode-select-wrap select')?.focus(), 0); }} onToggle={() => setNavMode(cyclePanel(navMode))} />
			<ChatSidebar mode={effectiveChatMode} sessions={sessions} activeId={session?.session_id} width={chatWidth} onResize={(change) => setPanelWidth("chat", chatWidth + change)} onToggle={() => setChatMode(cyclePanel(chatMode))} onNew={() => void startNewSession()} onSelect={(record) => void changeSession(record.session_id)} onPause={(id) => void pauseSession(id)} onClose={(id) => void closeSession(id)} />
			<section className="center-workspace" aria-label="Central AI workspace">
				<header className="workspace-topbar">
					<div className="topbar-left">
						<button className="icon-button nav-restore" type="button" aria-label="Toggle main sidebar" title="Toggle sidebar (Ctrl/Cmd+B)" onClick={() => setNavMode(cyclePanel(navMode))}><FiMenu /></button>
						<div className="topbar-brand"><span className="brand-mark"><FiCpu /></span><span><strong>LUMIRA</strong><small>Personal AI Core</small></span></div>
						<label className="mode-select-wrap"><span className="sr-only">Select Lumira mode</span><select aria-label="Select Lumira mode" value={activeMode} onChange={(event) => void activateMode(event.target.value as LumiraMode)}><option value="auto">Auto Category</option><option value="personal">Personal</option><option value="builder">Builder</option><option value="growth">Growth</option><option value="business">Business</option><option value="creator">Creator</option><option value="generator">Generator</option><option value="research">Research</option><option value="assistant">Assistant</option><option value="operations">Operations</option></select><FiChevronDown aria-hidden="true" /></label>
					</div>
					<div className="workspace-view-toggle" role="tablist" aria-label="Workspace view">
						<button className={workspaceView === "chat" ? "active" : ""} type="button" role="tab" aria-selected={workspaceView === "chat"} onClick={() => setWorkspaceView("chat")}>Chat</button>
						<button className={workspaceView === "code" ? "active" : ""} type="button" role="tab" aria-selected={workspaceView === "code"} onClick={() => setWorkspaceView("code")}>Code</button>
					</div>
					<div className="topbar-project"><strong>{currentProject ?? "Personal workspace"}</strong><span>{session?.status ?? "Ready"}</span></div>
					<form className="top-search" onSubmit={(event) => { event.preventDefault(); void runSearch(); }}><FiSearch aria-hidden="true" /><input aria-label="Global search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} onFocus={() => undefined} placeholder="Search…  Ctrl K" /><button type="submit" aria-label="Run global search" disabled={!searchQuery.trim()}><FiArrowUp /></button></form>
					<div className="quick-actions"><button type="button" onClick={startNewProject}>New Project</button><button type="button" onClick={startGeneration}>Generate</button><button type="button" onClick={() => voiceRecording ? stopVoiceRecording() : void startVoiceRecording()} disabled={voiceBusy}>{voiceBusy ? "Processing voice…" : voiceRecording ? "Stop & Process Recording" : "Record Voice"}</button><button type="button" onClick={() => void toggleWakeWordListener()} disabled={wakeWordBusy || wakeWordStatus.state === "starting" || wakeWordStatus.state === "stopping"}>{wakeWordBusy ? "Please wait…" : wakeWordStatus.listening === true ? "Stop Wake Word" : "Start Wake Word"}</button><button type="button" onClick={() => navigate("goals")}>Create Goal</button></div>
					<div className="topbar-tools"><ResourceStatus /><span className={`core-status ${connectionStatus}`}><i />{connectionStatus === "online" ? "CORE READY" : connectionStatus === "checking" ? "CONNECTING" : "OFFLINE"}</span><button className="icon-button" type="button" aria-label={focusMode ? "Exit focus mode" : "Enter focus mode"} title="Focus mode (Ctrl/Cmd+Shift+F)" onClick={() => setFocusMode(!focusMode)}><FiCrosshair /></button><button className="icon-button" type="button" aria-label={topBarCompact ? "Expand top bar" : "Compact top bar"} title="Toggle compact top bar" onClick={() => setTopBarCompact(!topBarCompact)}><FiSliders /></button><button className="icon-button settings-shortcut" type="button" aria-label="Open settings" onClick={() => navigate("settings")}><FiSettings /></button></div>
				</header>
				<div className="center-titlebar"><div><span className="eyebrow">{PAGE_TITLES[activePage].toUpperCase()}</span><h1>{currentTitle}</h1></div><div className="center-status">{currentProject && selectedVersion ? `${selectedVersion} · ` : ""}{titleForMode(activeMode)}</div><button className="icon-button panel-restore" type="button" aria-label="Toggle chat sidebar" title="Toggle chats (Ctrl/Cmd+Shift+B)" onClick={() => setChatMode(cyclePanel(chatMode))}><FiMenu /></button><button className="icon-button panel-restore" type="button" aria-label="Toggle development panel" title="Toggle developer panel (Ctrl/Cmd+J)" onClick={() => setRightMode(cyclePanel(rightMode))}><FiCode /></button></div>
				{actionNotice && <div className="action-notice" role="status"><span>{actionNotice}</span><button type="button" aria-label="Dismiss notification" onClick={() => setActionNotice(null)}><FiX /></button></div>}
				{pageError && <div className="workspace-alert error" role="alert"><span>{pageError}</span><button className="secondary-action" type="button" onClick={() => setPageError(null)}>Dismiss</button></div>}
				{sessionError && <div className="workspace-alert error" role="alert"><span>{sessionError}</span><button className="secondary-action" type="button" disabled={isRestoringSession} onClick={() => void retrySessionRestore()}>{isRestoringSession ? "Restoring…" : "Retry session recovery"}</button></div>}
				{renderedPage ? <section className="workspace-page" aria-label={`${PAGE_TITLES[activePage]} workspace`}>{renderedPage}</section> : <>
					<section className="conversation" aria-live="polite">
						{messages.length === 0 ? <div className="welcome-state"><div className="welcome-mark"><FiCpu /></div><p className="eyebrow">LUMIRA / {titleForMode(activeMode).toUpperCase()}</p><h2>What are we working on?</h2><p className="welcome-copy">Send a request through Lumira's routed command pipeline.</p><div className="suggestion-row"><button type="button" onClick={() => setPromptFromTool("Plan for launching ", "business")}>Business plan</button><button type="button" onClick={() => setPromptFromTool("Generate a diagram for ", "generator")}>Generate diagram</button><button type="button" onClick={() => setPromptFromTool("Prepare today's operational tasks for ", "operations")}>Plan operations</button></div></div> : <div className="message-list">{messages.map((message) => {
							const response = message.response ?? {};
							const result = object(response.result ?? response.data ?? response);
							const capability = stringValue(result.capability, "Lumira response");
							const successful = result.success !== false && response.success !== false;
							const status = stringValue(result.status, successful ? "completed" : "unavailable");
							const projectName = stringValue(result.project_name ?? object(result.project).project_name ?? result.code_target);
							const metadata = object(result.metadata);
							const isProjectResult = Boolean(projectName) && successful;
							const safeResult = safeDisplay(Object.fromEntries(Object.entries(result).filter(([key]) => !["brain", "trace", "cognitive_state", "context_snapshots"].includes(key))));
							return <article className="message-run" key={message.id}>
								{message.prompt && <div className="user-message">{message.prompt}</div>}
								{message.transcript && <div className="assistant-message">{message.transcript}</div>}
								{message.response && typeof response.message === "string" && response.message.trim() && <div className="assistant-message">{response.message}</div>}
								{message.pending && <div className="assistant-pending">Lumira is working…</div>}
								{message.error && <div className="workspace-alert error" role="alert">{message.error}</div>}
								{message.response && !["greeting", "conversation"].includes(capability) && <div className={`result-panel ${successful ? "is-success" : "is-failure"}`}>
									<div className="result-panel-heading"><span className="result-icon"><FiCpu /></span><strong>{capability.replaceAll("_", " ")}</strong><span className="status-pill">{status.replaceAll("_", " ")}</span></div>
									{response.clarification_required && <p className="result-message">{stringValue(response.message, "Additional information is required to continue.")}</p>}
									{typeof result.message === "string" && result.message && <p className="result-message">{result.message}</p>}
									{isProjectResult && <section className="project-result-card"><div><span className="eyebrow">PROJECT RESULT</span><h3>{projectName}</h3><p>{stringValue(metadata.description ?? metadata.idea ?? result.idea ?? result.request, "Project files were saved by Lumira.")}</p></div><dl><div><dt>Version</dt><dd>{stringValue(metadata.version, stringValue(result.version, "Latest"))}</dd></div><div><dt>Status</dt><dd>{stringValue(metadata.status, status)}</dd></div><div><dt>Created</dt><dd>{stringValue(metadata.created_at ?? result.created_at, "Recorded by the project service")}</dd></div></dl><div className="project-card-actions"><button type="button" onClick={() => openProjectFiles(projectName)}>View Files</button><button type="button" onClick={() => void projectAction(projectName, "run")}>Run Project</button><button type="button" onClick={() => void projectAction(projectName, "edit")}>Open in Editor</button><button type="button" onClick={() => void projectAction(projectName, "modify")}>Modify Project</button><button type="button" onClick={() => void projectAction(projectName, "frontend")}>Add Frontend</button><button type="button" onClick={() => void projectAction(projectName, "database")}>Add Database</button><button type="button" onClick={() => void projectAction(projectName, "deploy")}>Create Deployment Plan</button><button type="button" onClick={() => void projectAction(projectName, "docs")}>Show Documentation</button></div></section>}
									{capability === "voice_capture" && stringValue(object(result.artifact).artifact_id) && object(result.transcript).success !== true && <button className="secondary-action" type="button" onClick={() => void retryVoiceTranscriptionForMessage(message.id, stringValue(object(result.artifact).artifact_id))}>Retry transcription from saved audio</button>}
									{capability === "voice_capture" && stringValue(object(object(result.transcript).transcript_artifact).artifact_id) && <button className="secondary-action" type="button" onClick={() => void retryVoiceSummaryForMessage(message.id, stringValue(object(object(result.transcript).transcript_artifact).artifact_id))}>Retry summary from saved transcript</button>}
									<details className="result-details"><summary>Structured result</summary><pre>{JSON.stringify(safeResult, null, 2)}</pre></details>
								</div>}
							</article>;
						})}</div>}
					</section>
					{inputMode === "hidden" ? <div className="input-restore"><button type="button" onClick={() => setInputMode("full")}>Restore assistant input</button></div> : <div className={`composer-wrap ${inputMode === "compact" ? "is-compact" : ""}`}>
						{quickToolsOpen && <div className="quick-tools-menu"><button type="button" onClick={startNewProject}>New project workflow</button><button type="button" onClick={startGeneration}>Generator workspace</button><button type="button" onClick={() => navigate("goals")}>Create a durable goal</button></div>}
						<form className="composer" onSubmit={(event) => void submitPrompt(event)}>
							<button className="composer-tool" type="button" aria-label="Open tools" aria-expanded={quickToolsOpen} onClick={() => setQuickToolsOpen(!quickToolsOpen)}><FiSliders /></button>
						<label className="composer-tool file-attach" title="Attach an audio recording"><FiPaperclip /><input ref={attachmentFileRef} type="file" accept="audio/wav,audio/mpeg,audio/mp4,audio/ogg,audio/webm,.wav,.mp3,.m4a,.ogg,.webm" aria-label="Attach audio recording" onChange={(event) => void uploadVoice(event.target.files?.[0])} /></label>
						<button className={`composer-tool ${voiceRecording ? "recording-active" : ""}`} type="button" aria-label={voiceRecording ? "Stop microphone recording" : "Start microphone recording"} title={voiceRecording ? "Stop and process recording" : "Record from microphone"} disabled={voiceBusy} onClick={() => voiceRecording ? stopVoiceRecording() : void startVoiceRecording()}>{voiceRecording ? "■" : "●"}</button>
							<textarea ref={promptInputRef} aria-label="Describe what you want to work on" placeholder={workflow === "project" ? "Describe the project to generate…" : "Message Lumira…"} value={prompt} onChange={(event) => setPrompt(event.target.value)} onKeyDown={onPromptKeyDown} rows={inputMode === "compact" ? 1 : 2} disabled={isRestoringSession} />
							<label className="composer-mode"><span className="sr-only">Select Lumira mode</span><select aria-label="Composer mode" value={activeMode} onChange={(event) => void activateMode(event.target.value as LumiraMode)}><option value="auto">Auto</option><option value="personal">Personal</option><option value="builder">Builder</option><option value="growth">Growth</option><option value="business">Business</option><option value="creator">Creator</option><option value="generator">Generator</option><option value="research">Research</option><option value="assistant">Assistant</option><option value="operations">Operations</option></select></label>
							<button className="send-button" type="submit" disabled={!prompt.trim() || isSending || isRestoringSession} aria-label="Send request" title="Send request"><FiArrowUp /></button>
						</form>
						{voiceRecording && <p className="voice-recording-status" role="status">Recording from your microphone. Select the stop button to save the audio and start transcription.</p>}{voiceRecordingError && <p className="voice-recording-error" role="alert">{voiceRecordingError}</p>}
						<div className="composer-footer"><span>{wakeWordStatus.activated === true ? "Wake word detected: Lumira" : wakeWordStatus.listening === true ? "Wake-word listener is active; commands are not auto-executed." : isRestoringSession ? "Restoring saved session…" : activeMode === "auto" ? "Auto Category routes your request through Lumira's capability architecture." : `${titleForMode(activeMode)} routes through your active Lumira session.`}</span><div><button type="button" onClick={() => setInputMode(inputMode === "compact" ? "full" : "compact")} aria-label={inputMode === "compact" ? "Expand assistant input" : "Compact assistant input"}>{inputMode === "compact" ? "Expand input" : "Compact input"}</button><button type="button" onClick={() => setInputMode("hidden")}>Hide input</button></div></div>
					</div>}
				</>}
				<input ref={voiceFileRef} className="sr-only" type="file" accept="audio/wav,audio/mpeg,audio/mp4,audio/ogg,audio/webm,.wav,.mp3,.m4a,.ogg,.webm" aria-label="Capture voice file" onChange={(event) => void uploadVoice(event.target.files?.[0])} />
			</section>
			{workspaceView === "code" ? <RightPanel mode={effectiveRightMode} width={rightWidth} projects={projectItems} project={currentProject} version={selectedVersion} versions={projectVersions} files={projectFiles} selectedFile={selectedFile} fileContent={fileContent} fileLoading={fileLoading} previewUrl={previewUrl} previewStatus={previewStatus} previewInput={previewInput} onPreviewInput={setPreviewInput} onPreviewRegister={() => void registerPreview()} onPreviewStop={() => void stopPreview()} terminalCommands={terminalCommands} terminalRuns={terminalRuns} terminalBusy={terminalBusy} onTerminalRun={(commandId) => void runProjectTerminal(commandId)} apiPaths={apiPaths} runs={runs} activeTab={rightTab} onToggle={() => setRightMode(cyclePanel(rightMode))} onResize={(change) => setPanelWidth("right", rightWidth + change)} onTabChange={setRightTab} onProjectChange={(project) => project ? void selectProject(project) : setSelectedProject(null)} onVersionChange={(version) => void selectVersion(version)} onFileSelect={(file) => void selectFile(file)} /> : <aside className="utility-rail" aria-label="Lumira tools">
				<button className={utilityPanel === "notepad" ? "active" : ""} type="button" onClick={() => setUtilityPanel(utilityPanel === "notepad" ? null : "notepad")}><span>▤</span>Notepad</button>
				<button className={utilityPanel === "plugins" ? "active" : ""} type="button" onClick={() => setUtilityPanel(utilityPanel === "plugins" ? null : "plugins")}><span>◇</span>Plugins</button>
				<button type="button" onClick={() => { setActivePage("generator"); setUtilityPanel(null); }}><span>✦</span>Imagine</button>
				<button type="button" onClick={() => { setActivePage("goals"); setUtilityPanel(null); }}><span>✓</span>To-Do List</button>
				{utilityPanel === "notepad" && <div className="utility-popover"><strong>Notepad</strong><textarea value={note} maxLength={20000} onChange={(event) => { setNote(event.target.value); setNoteSaveStatus("Unsaved changes"); }} placeholder="Write a quick note…" /><div className="notepad-actions"><small>{noteSaveStatus}</small><button type="button" disabled={noteSaveBusy} onClick={() => void saveNotepadNote()}>{noteSaveBusy ? "Saving…" : "Save to Lumira"}</button></div></div>}
				{utilityPanel === "plugins" && <div className="utility-popover"><strong>Plugins</strong><p>Plugin slots are ready. No plugins are installed yet.</p></div>}
			</aside>}
		</main>
	);
}

function IntelligenceProbe() {
	const [text, setText] = useState("");
	const [result, setResult] = useState<JsonObject | null>(null);
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);

	async function analyze(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!text.trim() || busy) return;
		setBusy(true);
		setError("");
		try {
			setResult(await api.analyzeInput(text.trim()));
		} catch (cause) {
			setError(formatError(cause).message);
		} finally {
			setBusy(false);
		}
	}

	return <section className="settings-capability-status" aria-label="Request analysis preview">
		<h3>Request analysis (no execution)</h3>
		<p>Preview Lumira's deterministic intent, language, and mode detection without running the requested action.</p>
		<form className="settings-list" onSubmit={(event) => void analyze(event)}>
			<label>Sample request<input value={text} maxLength={10000} onChange={(event) => setText(event.target.value)} placeholder="e.g. Build a small ESP32 project" /></label>
			<button type="submit" disabled={!text.trim() || busy}>{busy ? "Analyzing…" : "Analyze request"}</button>
		</form>
		{error && <p role="alert">{error}</p>}
		{result && <pre>{JSON.stringify(safeDisplay(result), null, 2)}</pre>}
	</section>;
}

function WorkflowList({ workflows, onTaskUpdate, onRunReady, onRetryFailed }: { workflows: JsonObject[]; onTaskUpdate: (workflowId: string, taskId: string, status: string, blocker?: string, resultText?: string) => void; onRunReady: (workflowId: string, agentMode: "auto" | "planner_agent" | "research_agent" | "code_agent") => Promise<JsonObject | null>; onRetryFailed: (workflowId: string) => Promise<JsonObject | null> }) {
	const [progressByWorkflow, setProgressByWorkflow] = useState<Record<string, JsonObject>>({});
	const [progressLoading, setProgressLoading] = useState<string | null>(null);
	const [agentRunBusy, setAgentRunBusy] = useState<string | null>(null);
	const [agentMode, setAgentMode] = useState<"auto" | "planner_agent" | "research_agent" | "code_agent">("auto");
	const [agentRunResults, setAgentRunResults] = useState<Record<string, JsonObject>>({});
	const [retryBusy, setRetryBusy] = useState<string | null>(null);
	const [executionPreviews, setExecutionPreviews] = useState<Record<string, JsonObject>>({});
	const [previewBusy, setPreviewBusy] = useState<string | null>(null);
	const [taskHistoryById, setTaskHistoryById] = useState<Record<string, JsonObject>>({});
	const [historyLoading, setHistoryLoading] = useState<string | null>(null);
	const [taskResultsById, setTaskResultsById] = useState<Record<string, JsonObject>>({});
	const [taskResultLoading, setTaskResultLoading] = useState<string | null>(null);
	const [deliverablesByWorkflow, setDeliverablesByWorkflow] = useState<Record<string, JsonObject>>({});
	const [deliverablesLoading, setDeliverablesLoading] = useState<string | null>(null);

	async function retryFailed(workflowId: string) {
		setRetryBusy(workflowId);
		try {
			const result = await onRetryFailed(workflowId);
			if (result) setAgentRunResults((current) => ({ ...current, [workflowId]: result }));
		} finally {
			setRetryBusy(null);
		}
	}

	async function previewExecution(workflowId: string) {
		setPreviewBusy(workflowId);
		try {
			const result = await api.previewWorkflowExecution(workflowId);
			setExecutionPreviews((current) => ({ ...current, [workflowId]: result }));
		} catch (error) {
			setExecutionPreviews((current) => ({ ...current, [workflowId]: { error: formatError(error).message } }));
		} finally {
			setPreviewBusy(null);
		}
	}

	async function runAgents(workflowId: string) {
		setAgentRunBusy(workflowId);
		try {
			const result = await onRunReady(workflowId, agentMode);
			if (result) setAgentRunResults((current) => ({ ...current, [workflowId]: result }));
		} finally {
			setAgentRunBusy(null);
		}
	}

	async function loadProgress(workflowId: string) {
		setProgressLoading(workflowId);
		try {
			const progress = await api.getWorkflowProgress(workflowId);
			setProgressByWorkflow((current) => ({ ...current, [workflowId]: progress }));
		} catch (error) {
			setProgressByWorkflow((current) => ({ ...current, [workflowId]: { error: formatError(error).message } }));
		} finally {
			setProgressLoading(null);
		}
	}

	async function loadTaskHistory(workflowId: string, taskId: string) {
		setHistoryLoading(taskId);
		try {
			const history = await api.getWorkflowTaskHistory(workflowId, taskId);
			setTaskHistoryById((current) => ({ ...current, [taskId]: history }));
		} catch (error) {
			setTaskHistoryById((current) => ({ ...current, [taskId]: { error: formatError(error).message } }));
		} finally {
			setHistoryLoading(null);
		}
	}

	async function loadTaskResult(workflowId: string, taskId: string) {
		setTaskResultLoading(taskId);
		try {
			const result = await api.getWorkflowTaskResult(workflowId, taskId);
			setTaskResultsById((current) => ({ ...current, [taskId]: result }));
		} catch (error) {
			setTaskResultsById((current) => ({ ...current, [taskId]: { error: formatError(error).message } }));
		} finally {
			setTaskResultLoading(null);
		}
	}

	async function loadWorkflowDeliverables(workflowId: string) {
		setDeliverablesLoading(workflowId);
		try {
			const result = await api.listWorkflowDeliverables(workflowId);
			setDeliverablesByWorkflow((current) => ({ ...current, [workflowId]: result }));
		} catch (error) {
			setDeliverablesByWorkflow((current) => ({ ...current, [workflowId]: { error: formatError(error).message } }));
		} finally {
			setDeliverablesLoading(null);
		}
	}

	if (!workflows.length) return <div className="workspace-empty">No workflows are recorded.</div>;
	return <div className="workflow-list">{workflows.map((workflow, index) => {
		const id = stringValue(workflow.workflow_id, `workflow-${index}`);
		const tasks = Array.isArray(workflow.tasks) ? workflow.tasks.map(object) : [];
		const failedTaskCount = tasks.filter((task) => task.status === "failed").length;
		return <article className="workflow-card" key={id}><header><div><span className="eyebrow">{stringValue(workflow.category, "workflow").toUpperCase()}</span><h3>{stringValue(workflow.title, "Workflow")}</h3><p>{stringValue(workflow.request)}</p></div><button type="button" className="secondary-action" disabled={progressLoading === id} onClick={() => void loadProgress(id)}>{progressLoading === id ? "Loading..." : "Next actions"}</button><button type="button" className="secondary-action" disabled={previewBusy === id} onClick={() => void previewExecution(id)}>{previewBusy === id ? "Previewing…" : "Preview run"}</button><button type="button" className="secondary-action" disabled={deliverablesLoading === id} onClick={() => void loadWorkflowDeliverables(id)}>{deliverablesLoading === id ? "Loading files…" : "Deliverables"}</button><select aria-label="Agent routing mode" value={agentMode} onChange={(event) => setAgentMode(event.target.value as "auto" | "planner_agent" | "research_agent" | "code_agent")}><option value="auto">Auto agent</option><option value="planner_agent">Planner agent</option><option value="research_agent">Research agent</option><option value="code_agent">Code agent</option></select>{failedTaskCount > 0 && <button type="button" className="secondary-action" disabled={retryBusy === id} onClick={() => void retryFailed(id)}>{retryBusy === id ? "Requeueing…" : `Retry failed (${failedTaskCount})`}</button>}<button type="button" className="primary-action" disabled={agentRunBusy === id || !tasks.some((task) => task.status === "pending")} onClick={() => void runAgents(id)}>{agentRunBusy === id ? "Agent working…" : "Run with agent"}</button><span className="status-pill">{stringValue(workflow.status, "planned")}</span></header>{progressByWorkflow[id] && <pre>{JSON.stringify(safeDisplay(progressByWorkflow[id]), null, 2)}</pre>}{deliverablesByWorkflow[id] && <section className="memory-results"><div className="workspace-page-heading"><div><h4>Workflow deliverables</h4><p>{Number(deliverablesByWorkflow[id].count ?? 0)} stored artifact(s) · files remain in Lumira's artifact store</p></div><button type="button" className="secondary-action" onClick={() => setDeliverablesByWorkflow((current) => { const next = { ...current }; delete next[id]; return next; })}>Close</button></div><div className="entity-list">{records(deliverablesByWorkflow[id], "deliverables").map((artifact, artifactIndex) => { const artifactId = stringValue(artifact.artifact_id); return <article className="entity-row" key={artifactId || String(artifactIndex)}><div className="entity-symbol"><FiPaperclip /></div><div className="entity-copy"><strong>{stringValue(artifact.title, stringValue(artifact.type, "Stored artifact"))}</strong><span>{stringValue(artifact.source, "Workflow output")}</span><small>{artifact.content_available === true ? "Content available" : "Metadata only"} · {stringValue(artifact.timestamp)}</small></div>{artifactId && artifact.content_available === true && <button type="button" className="secondary-action" onClick={() => window.open(api.artifactContentUrl(artifactId), "_blank", "noopener,noreferrer")}>Open content</button>}</article>; })}</div><details><summary>Structured deliverables data</summary><pre>{JSON.stringify(safeDisplay(deliverablesByWorkflow[id]), null, 2)}</pre></details></section>}{executionPreviews[id] && <section className="memory-results"><div className="workspace-page-heading"><div><h4>Execution preview</h4><p>{Number(executionPreviews[id].ready_count ?? 0)} task(s) ready · no agents invoked</p></div><button type="button" className="secondary-action" onClick={() => setExecutionPreviews((current) => { const next = { ...current }; delete next[id]; return next; })}>Close</button></div><pre>{JSON.stringify(safeDisplay(executionPreviews[id]), null, 2)}</pre></section>}{agentRunResults[id] && <section className="memory-results"><div className="workspace-page-heading"><div><h4>Agent execution result</h4><p>{Number(agentRunResults[id].executed_count ?? 0)} task outcome(s) recorded · {stringValue(agentRunResults[id].stop_reason, "unknown")}</p></div><button type="button" className="secondary-action" onClick={() => setAgentRunResults((current) => { const next = { ...current }; delete next[id]; return next; })}>Close</button></div><pre>{JSON.stringify(safeDisplay(agentRunResults[id]), null, 2)}</pre></section>}<div className="workflow-tasks">{tasks.map((task, taskIndex) => <div className="workflow-task" key={stringValue(task.task_id, String(taskIndex))}><div><strong>{stringValue(task.title, `Task ${taskIndex + 1}`)}</strong><span>{stringValue(task.status, "pending")}{Array.isArray(task.dependencies) && task.dependencies.length ? ` · depends on ${task.dependencies.length}` : ""}</span>{typeof task.blocker === "string" && task.blocker && <small className="blocker">Blocker: {task.blocker}</small>}</div><div className="task-actions"><button type="button" disabled={historyLoading === stringValue(task.task_id)} onClick={() => void loadTaskHistory(id, stringValue(task.task_id))}>{historyLoading === stringValue(task.task_id) ? "Loading history..." : "History"}</button>{taskHistoryById[stringValue(task.task_id)] && <pre>{JSON.stringify(safeDisplay(taskHistoryById[stringValue(task.task_id)]), null, 2)}</pre>}{Boolean(task.result) && <button type="button" disabled={taskResultLoading === stringValue(task.task_id)} onClick={() => void loadTaskResult(id, stringValue(task.task_id))}>{taskResultLoading === stringValue(task.task_id) ? "Loading result..." : "Result"}</button>}{taskResultsById[stringValue(task.task_id)] && <><pre>{JSON.stringify(safeDisplay(taskResultsById[stringValue(task.task_id)]), null, 2)}</pre>{stringValue(taskResultsById[stringValue(task.task_id)].artifact_id, stringValue(object(taskResultsById[stringValue(task.task_id)].artifact).artifact_id)) && <button type="button" onClick={() => window.open(api.artifactContentUrl(stringValue(taskResultsById[stringValue(task.task_id)].artifact_id, stringValue(object(taskResultsById[stringValue(task.task_id)].artifact).artifact_id))), "_blank", "noopener,noreferrer")}>Open task artifact</button>}</>}{task.status === "failed" && <button type="button" onClick={() => onTaskUpdate(id, stringValue(task.task_id), "pending")}>Retry</button>}{task.status === "pending" && <button type="button" onClick={() => onTaskUpdate(id, stringValue(task.task_id), "in_progress")}>Start</button>}{task.status === "in_progress" && <><button type="button" onClick={() => { const outcome = window.prompt("Record the task outcome before completing:"); if (outcome !== null && outcome.trim()) onTaskUpdate(id, stringValue(task.task_id), "completed", undefined, outcome.trim()); }}>Complete</button><button type="button" onClick={() => { const reason = window.prompt("Why is this task blocked?"); if (reason !== null && reason.trim()) onTaskUpdate(id, stringValue(task.task_id), "blocked", reason.trim()); }}>Block</button><button type="button" onClick={() => { const reason = window.prompt("Why did this task fail?"); if (reason !== null && reason.trim()) onTaskUpdate(id, stringValue(task.task_id), "failed", reason.trim()); }}>Fail</button></>}</div></div>)}</div></article>;
	})}</div>;
}

function ResourceStatus() {
	const [snapshot, setSnapshot] = useState<JsonObject | null>(null);

	useEffect(() => {
		let cancelled = false;
		const refresh = async () => {
			try {
				const result = await api.resourceRuntime();
				if (!cancelled) setSnapshot(result);
			} catch {
				if (!cancelled) setSnapshot(null);
			}
		};
		void refresh();
		const timer = window.setInterval(() => void refresh(), 30000);
		return () => {
			cancelled = true;
			window.clearInterval(timer);
		};
	}, []);

	const memory = object(snapshot?.memory);
	const pressure = stringValue(snapshot?.resource_pressure, "unknown");
	const freeGiB = typeof memory.available_gib === "number" ? memory.available_gib.toFixed(1) : null;
	const state = pressure === "critical" ? "offline" : pressure === "constrained" ? "checking" : pressure === "normal" ? "online" : "checking";
	const label = freeGiB !== null ? `RAM ${freeGiB} GiB free` : "RAM status unknown";
	return <span className={`core-status ${state}`} title={`Resource pressure: ${pressure}. Values refresh every 30 seconds when the backend is available.`}><i />{label}</span>;
}

export default MainLayout;
