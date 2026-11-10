import {
	FiActivity, FiArchive, FiBriefcase, FiCode, FiCpu, FiDatabase,
	FiEye, FiFolder, FiLayers, FiMessageSquare, FiMinus, FiPlus,
	FiSearch, FiTarget, FiZap, FiCalendar, FiUsers, FiClock, FiTrendingUp, FiHome,
} from "react-icons/fi";
import type { CSSProperties, ReactNode } from "react";
import type { PanelMode, WorkspacePage } from "../../store/appStore";

type Props = {
	mode: PanelMode;
	activePage: WorkspacePage;
	width: number;
	onNavigate: (page: WorkspacePage) => void;
	onNewChat: () => void;
	onModeSelect: () => void;
	onToggle: () => void;
	onResize: (change: number) => void;
};

const items: Array<{ id: WorkspacePage; label: string; icon: ReactNode }> = [
	{ id: "dashboard", label: "Dashboard", icon: <FiHome /> },
	{ id: "chats", label: "New Chat", icon: <FiPlus /> },
	{ id: "settings", label: "Mode Selector", icon: <FiZap /> },
	{ id: "projects", label: "Projects", icon: <FiFolder /> },
	{ id: "artifacts", label: "Artifact Library", icon: <FiArchive /> },
	{ id: "memory", label: "Memory", icon: <FiDatabase /> },
	{ id: "goals", label: "Goals", icon: <FiTarget /> },
	{ id: "planner", label: "Planner", icon: <FiCalendar /> },
	{ id: "search", label: "Unified Search", icon: <FiSearch /> },
	{ id: "generator", label: "Project Generator", icon: <FiCode /> },
	{ id: "business", label: "Business", icon: <FiBriefcase /> },
	{ id: "market", label: "Kronos Market Intelligence", icon: <FiTrendingUp /> },
	{ id: "creator", label: "Creator Studio", icon: <FiLayers /> },
	{ id: "devices", label: "Device Ecosystem", icon: <FiCpu /> },
	{ id: "operations", label: "Operations", icon: <FiActivity /> },
	{ id: "agents", label: "Agents", icon: <FiUsers /> },
	{ id: "background", label: "Background Tasks", icon: <FiClock /> },
	{ id: "learning", label: "Self-Improvement", icon: <FiTrendingUp /> },
	{ id: "observability", label: "System Observability", icon: <FiActivity /> },
	{ id: "features", label: "Feature Control (28)", icon: <FiLayers /> },
	{ id: "image-understanding", label: "Image Analysis", icon: <FiEye /> },
	{ id: "chats", label: "Recent Chats", icon: <FiMessageSquare /> },
];

export function Sidebar({ mode, activePage, width, onNavigate, onNewChat, onModeSelect, onToggle, onResize }: Props) {
	if (mode === "hidden") return null;
	const compact = mode === "compact";
	return (
		<aside className={`nav-panel ${compact ? "is-compact" : ""}`} style={{ "--nav-panel-width": `${width}px` } as CSSProperties} aria-label="Main navigation">
			<div className="nav-brand-row">
				<div className="brand-lockup"><span className="brand-mark"><FiCpu /></span>{!compact && <span>LUMIRA</span>}</div>
				{!compact && <div className="sidebar-width-tools"><button className="icon-button" type="button" aria-label="Narrow main sidebar" onClick={() => onResize(-16)}><FiMinus /></button><button className="icon-button" type="button" aria-label="Widen main sidebar" onClick={() => onResize(16)}><FiPlus /></button></div>}
				<button className="icon-button nav-collapse" type="button" aria-label={compact ? "Expand main sidebar" : "Collapse main sidebar"} title={compact ? "Expand sidebar" : "Collapse sidebar"} onClick={onToggle}>⇔</button>
			</div>
			<div className="nav-label">{compact ? "" : "WORKSPACE"}</div>
			<nav className="nav-items" aria-label="Workspace pages">
				{items.map((item) => (
					<button
						key={`${item.id}-${item.label}`}
						className={`nav-item ${activePage === item.id ? "active" : ""}`}
						type="button"
						aria-label={item.label}
						aria-current={activePage === item.id ? "page" : undefined}
						title={compact ? item.label : undefined}
						onClick={() => {
						if (item.label === "New Chat") onNewChat();
						else if (item.label === "Mode Selector") onModeSelect();
						else if (item.label === "Recent Chats") onNavigate("chats");
						else onNavigate(item.id);
					}}
					>
						<span className="nav-icon" aria-hidden="true">{item.icon}</span>
						{!compact && <span>{item.label}</span>}
					</button>
				))}
			</nav>
			<div className="nav-footer"><span className="connection-dot" />{!compact && <span>LOCAL CORE</span>}</div>
		</aside>
	);
}

export default Sidebar;
