import { useMemo, useState } from "react";
import { FiChevronDown, FiMessageSquare, FiMinus, FiMoreHorizontal, FiPlus, FiSearch } from "react-icons/fi";
import type { CSSProperties } from "react";
import type { PanelMode } from "../../store/appStore";

export type ChatSession = {
	session_id: string;
	status: string;
	active_project?: string | null;
	current_goal?: string | null;
	created_at?: string;
	updated_at?: string;
	recent_messages?: Array<{ role: string; content: string }>;
};

type Props = {
	mode: PanelMode;
	sessions: ChatSession[];
	activeId?: string;
	width: number;
	onToggle: () => void;
	onResize: (change: number) => void;
	onNew: () => void;
	onSelect: (session: ChatSession) => void;
	onPause: (sessionId: string) => void;
	onClose: (sessionId: string) => void;
};

function titleFor(session: ChatSession) {
	return session.recent_messages?.find((message) => message.role === "user")?.content
		?? session.current_goal
		?? session.active_project
		?? "New conversation";
}

function dayKey(value?: string) {
	if (!value) return "previous";
	const timestamp = Date.parse(value);
	if (!Number.isFinite(timestamp)) return "previous";
	const then = new Date(timestamp);
	const now = new Date();
	return then.toDateString() === now.toDateString() ? "today" : "previous";
}

export function ChatSidebar({ mode, sessions, activeId, width, onToggle, onResize, onNew, onSelect, onPause, onClose }: Props) {
	const [query, setQuery] = useState("");
	const [menuId, setMenuId] = useState<string | null>(null);
	const filtered = useMemo(() => sessions.filter((session) => titleFor(session).toLowerCase().includes(query.toLowerCase())), [sessions, query]);
	if (mode === "hidden") return null;
	const compact = mode === "compact";
	const today = filtered.filter((session) => dayKey(session.updated_at ?? session.created_at) === "today");
	const previous = filtered.filter((session) => !today.includes(session));
	const renderSessions = (records: ChatSession[]) => records.map((session) => (
		<div className={`chat-row ${activeId === session.session_id ? "active" : ""}`} key={session.session_id}>
			<button className="chat-row-select" type="button" title={compact ? titleFor(session) : undefined} aria-label={`Open chat ${titleFor(session)}`} onClick={() => onSelect(session)}>
				<FiMessageSquare aria-hidden="true" />
				{!compact && <span><span className="chat-title">{titleFor(session)}</span><small>{session.updated_at ? new Date(session.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : session.status}</small></span>}
			</button>
			{!compact && <button className="icon-button chat-menu-trigger" type="button" aria-label={`Conversation menu ${titleFor(session)}`} onClick={() => setMenuId(menuId === session.session_id ? null : session.session_id)}><FiMoreHorizontal /></button>}
			{menuId === session.session_id && !compact && <div className="chat-menu"><button type="button" onClick={() => { onPause(session.session_id); setMenuId(null); }}>Pause</button><button type="button" onClick={() => { onClose(session.session_id); setMenuId(null); }}>Close</button></div>}
		</div>
	));
	return (
		<aside className={`chat-sidebar ${compact ? "is-compact" : ""}`} style={{ "--chat-panel-width": `${width}px` } as CSSProperties} aria-label="Chat sidebar">
			<header className="panel-heading">
				{!compact && <div><strong>Conversations</strong><small>Saved sessions</small></div>}
				{!compact && <div className="panel-tools"><button className="icon-button" type="button" aria-label="Narrow chat sidebar" onClick={() => onResize(-16)}><FiMinus /></button><button className="icon-button" type="button" aria-label="Widen chat sidebar" onClick={() => onResize(16)}><FiPlus /></button><button className="icon-button" type="button" aria-label="Collapse chat sidebar" title="Collapse chats" onClick={onToggle}><FiChevronDown /></button></div>}
				{compact && <button className="icon-button" type="button" aria-label="Expand chat sidebar" title="Expand chats" onClick={onToggle}><FiChevronDown /></button>}
			</header>
			<button className="new-chat-button" type="button" aria-label="New chat" onClick={onNew}><FiPlus />{!compact && <span>New Chat</span>}</button>
			{!compact && <label className="conversation-search"><FiSearch aria-hidden="true" /><input aria-label="Search conversations" placeholder="Search conversations" value={query} onChange={(event) => setQuery(event.target.value)} /></label>}
			<div className="chat-list">
				{today.length > 0 && <><div className="list-caption">TODAY</div>{renderSessions(today)}</>}
				{previous.length > 0 && <><div className="list-caption">PREVIOUS</div>{renderSessions(previous)}</>}
				{filtered.length === 0 && !compact && <p className="empty-note">No saved conversations yet.</p>}
			</div>
		</aside>
	);
}

export default ChatSidebar;
