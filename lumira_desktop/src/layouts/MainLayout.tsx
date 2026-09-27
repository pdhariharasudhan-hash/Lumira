import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { FiArrowUp, FiCpu, FiPlus } from "react-icons/fi";
import "./MainLayout.css";

type BrainResponse = {
	success?: boolean;
	session_id?: string;
	message?: string;
	detail?: string;
	clarification_required?: boolean;
	data?: {
		stage?: string;
		status?: string;
		state?: {
			execution_context?: { session_id?: string };
			[key: string]: unknown;
		};
		[key: string]: unknown;
	};
	result?: {
		capability?: string;
		status?: string;
		project_name?: string;
		saved_path?: string;
		success?: boolean;
		[key: string]: unknown;
	};
	context?: {
		active_project?: string | null;
		current_goal?: string | null;
	};
	error?: string;
};

type Message = {
	prompt?: string;
	transcript?: string;
	response?: BrainResponse;
	error?: string;
};

type SessionRecord = {
	session_id: string;
	status: string;
	active_project?: string | null;
	current_goal?: string | null;
	recent_messages?: Array<{ role: string; content: string }>;
};

function MainLayout() {
	const [prompt, setPrompt] = useState("");
	const [workflow, setWorkflow] = useState<"brain" | "project">("brain");
	const [messages, setMessages] = useState<Message[]>([]);
	const [isSending, setIsSending] = useState(false);
	const [session, setSession] = useState<SessionRecord | null>(null);
	const [isRestoringSession, setIsRestoringSession] = useState(() => Boolean(window.localStorage.getItem("lumira.sessionId")));
	const [connectionStatus, setConnectionStatus] = useState<"checking" | "online" | "offline">("checking");
	const [sessionError, setSessionError] = useState<string | null>(null);

	useEffect(() => {
		void fetch("/health")
			.then((response) => {
				if (!response.ok) throw new Error("Health check failed");
				setConnectionStatus("online");
			})
			.catch(() => setConnectionStatus("offline"));

		const storedId = window.localStorage.getItem("lumira.sessionId");
		if (!storedId) {
			return;
		}

		void fetch(`/sessions/${encodeURIComponent(storedId)}`)
			.then(async (response) => {
				if (!response.ok) throw new Error("Session unavailable");
				let loaded = (await response.json()) as SessionRecord;
				if (loaded.status === "paused") {
					const resumed = await fetch(`/sessions/${encodeURIComponent(storedId)}/resume`, { method: "POST" });
					if (!resumed.ok) throw new Error("Session could not be resumed");
					loaded = (await resumed.json()) as SessionRecord;
				}
				setSession(loaded);
				setMessages((loaded.recent_messages ?? []).map((message) =>
					message.role === "user"
						? { prompt: message.content }
						: { transcript: message.content },
				));
			})
			.catch(() => {
				window.localStorage.removeItem("lumira.sessionId");
				setSessionError("The saved session could not be restored. Start a new session to continue.");
			})
			.finally(() => setIsRestoringSession(false));
	}, []);

	async function startNewSession() {
		try {
			setSessionError(null);
			const response = await fetch("/sessions", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ workspace_id: "default" }),
			});
			if (!response.ok) throw new Error("Could not create a new session");
			const created = (await response.json()) as SessionRecord;
			window.localStorage.setItem("lumira.sessionId", created.session_id);
			setSession(created);
			setMessages([]);
		} catch (error) {
			setSessionError(error instanceof Error ? error.message : "Could not create a new session.");
		}
	}

	async function submitPrompt(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const input = prompt.trim();
		if (!input || isSending || isRestoringSession) return;

		setPrompt("");
		setMessages((current) => [...current, { prompt: input }]);
		setIsSending(true);

		try {
			const isProjectRequest = workflow === "project";
			const response = await fetch(isProjectRequest ? "/command" : "/brain", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					input: isProjectRequest ? `Generate project: ${input}` : input,
					session_id: session?.session_id,
					workspace_id: "default",
				}),
			});
			const result = (await response.json()) as BrainResponse;

			if (!response.ok) {
				throw new Error(result.detail || result.error || result.message || `Request failed (${response.status})`);
			}

			if (result.clarification_required) {
				setMessages((current) =>
					current.map((message, index) =>
						index === current.length - 1 ? { ...message, response: result } : message,
					),
				);
				return;
			}

			if (result.success === false || result.result?.success === false) {
				throw new Error(result.error || result.message || result.detail || "The request could not be completed.");
			}

			const sessionId = result.session_id ?? result.data?.state?.execution_context?.session_id;
			if (sessionId) {
				window.localStorage.setItem("lumira.sessionId", sessionId);
				const loadedSession = await fetch(`/sessions/${encodeURIComponent(sessionId)}`);
				if (loadedSession.ok) setSession((await loadedSession.json()) as SessionRecord);
			}

			setMessages((current) =>
				current.map((message, index) =>
					index === current.length - 1 ? { ...message, response: result } : message,
				),
			);
		} catch (error) {
			const message = error instanceof Error ? error.message : "The request failed.";
			setMessages((current) =>
				current.map((item, index) =>
					index === current.length - 1 ? { ...item, error: message } : item,
				),
			);
		} finally {
			setIsSending(false);
		}
	}

	return (
		<main className="lumira-shell">
			<aside className="lumira-rail">
				<a className="lumira-brand" href="/" aria-label="Lumira home">
					<span className="brand-mark"><FiCpu aria-hidden="true" /></span>
					<span>LUMIRA</span>
				</a>
				<button
					className="new-session"
					type="button"
					onClick={() => void startNewSession()}
					disabled={isRestoringSession || isSending}
					title="Start a new session"
				>
					<FiPlus aria-hidden="true" />
					<span>New session</span>
				</button>
				<div className="rail-caption">WORKSPACE</div>
				<div className="workspace-item" aria-current="page">
					<span className="workspace-dot" />
					<span>{session?.active_project ?? "Personal workspace"}</span>
				</div>
				<div className="rail-footer">
					<span className="connection-dot" />
					<span>{connectionStatus === "online" ? "Local core" : connectionStatus === "checking" ? "Checking core" : "Core offline"}</span>
				</div>
			</aside>

			<section className="lumira-main">
				<header className="topbar">
					<div>
						<div className="eyebrow">PERSONAL AI SYSTEM</div>
						<h1>Workbench</h1>
						{session && <div className="session-context">Session {session.session_id.slice(0, 8)} · {session.status}{session.current_goal ? ` · ${session.current_goal}` : ""}</div>}
					</div>
					<div className="runtime-label">
						<span className="connection-dot" />
						{connectionStatus === "online" ? "CORE READY" : connectionStatus === "checking" ? "CONNECTING" : "CORE OFFLINE"}
					</div>
				</header>

				<section className="conversation" aria-live="polite">
					{sessionError && <p className="run-error session-error">{sessionError}</p>}
					{messages.length === 0 ? (
						<div className="welcome-state">
							<div className="welcome-mark"><FiCpu aria-hidden="true" /></div>
							<p className="eyebrow">LUMIRA / {workflow === "brain" ? "BRAIN" : "PROJECT ENGINE"}</p>
							<h2>What are we working on?</h2>
							<p className="welcome-copy">Describe a goal to start a run through the core.</p>
						</div>
					) : (
						<div className="message-list">
							{messages.map((message, index) => {
								const output = message.response?.result ?? message.response?.data ?? message.response;
								const status = message.response?.data?.status ?? message.response?.result?.status ?? "ready";
								const label = message.response?.result?.project_name
									? `Project saved: ${message.response.result.project_name}`
									: message.response?.result?.capability ?? "Core response";
								return (
									<article className="run" key={`${message.prompt ?? message.transcript}-${index}`}>
										{message.prompt && <div className="user-prompt">{message.prompt}</div>}
										{message.transcript && <p className="assistant-transcript">{message.transcript}</p>}
										{message.response ? (
											<div className="run-result">
												<div className="run-heading">
													<span className="result-icon"><FiCpu aria-hidden="true" /></span>
													<strong>{label}</strong>
													<span className="run-stage">
														{message.response.data?.stage ?? message.response.result?.status ?? "complete"}
													</span>
												</div>
												<div className="run-status">{status.replaceAll("_", " ")}</div>
												{message.response.message && <p className="run-error">{message.response.message}</p>}
												{message.response.result?.saved_path && <p className="saved-path">Saved to {message.response.result.saved_path}</p>}
												<pre>{JSON.stringify(output, null, 2)}</pre>
											</div>
										) : message.error ? (
											<p className="run-error">{message.error}</p>
										) : isSending && index === messages.length - 1 ? (
											<p className="run-pending">Running through the core...</p>
										) : null}
									</article>
								);
							})}
						</div>
					)}
				</section>

				<div className="composer-wrap">
					<div className="workflow-switch" role="group" aria-label="Choose workflow">
						<button className={workflow === "brain" ? "workflow-option active" : "workflow-option"} type="button" aria-pressed={workflow === "brain"} onClick={() => setWorkflow("brain")}>Brain</button>
						<button className={workflow === "project" ? "workflow-option active" : "workflow-option"} type="button" aria-pressed={workflow === "project"} onClick={() => setWorkflow("project")}>Generate project</button>
					</div>
					<form className="composer" onSubmit={submitPrompt}>
						<textarea
							aria-label="Describe what you want to work on"
							placeholder={workflow === "brain" ? "Describe a goal for the Brain..." : "Describe the project to generate..."}
							value={prompt}
							onChange={(event) => setPrompt(event.target.value)}
							onKeyDown={(event) => {
								if (event.key === "Enter" && !event.shiftKey) {
									event.preventDefault();
									event.currentTarget.form?.requestSubmit();
								}
							}}
							rows={2}
						/>
						<button className="send-button" type="submit" disabled={!prompt.trim() || isSending || isRestoringSession} aria-label="Send request" title="Send request"><FiArrowUp aria-hidden="true" /></button>
					</form>
					<div className="composer-note">
						{workflow === "brain" ? "Requests are processed by your local Lumira core." : "Generated projects are validated and saved in your workspace."}
					</div>
				</div>
			</section>
		</main>
	);
}

export default MainLayout;
