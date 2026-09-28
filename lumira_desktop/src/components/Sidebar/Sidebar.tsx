import {
	FiArchive, FiBriefcase, FiClock, FiCpu, FiFolder, FiMessageSquare,
	FiMinus, FiPlus, FiSearch, FiSettings, FiTarget, FiZap,
} from "react-icons/fi";
import type { CSSProperties, ReactNode } from "react";
import type { PanelMode, WorkspacePage } from "../../store/appStore";

type Props = {
	mode: PanelMode;
	activePage: WorkspacePage;
	width: number;
	onNavigate: (page: WorkspacePage) => void;
	onToggle: () => void;
	onResize: (change: number) => void;
};

const items: Array<{ id: WorkspacePage; label: string; icon: ReactNode }> = [
	{ id: "chats", label: "Chats", icon: <FiMessageSquare /> },
	{ id: "projects", label: "Projects", icon: <FiFolder /> },
	{ id: "artifacts", label: "Artifacts", icon: <FiArchive /> },
	{ id: "memory", label: "Memory", icon: <FiCpu /> },
	{ id: "goals", label: "Goals", icon: <FiTarget /> },
	{ id: "search", label: "Search", icon: <FiSearch /> },
	{ id: "generator", label: "Generator", icon: <FiZap /> },
	{ id: "business", label: "Business", icon: <FiBriefcase /> },
	{ id: "operations", label: "Operations", icon: <FiClock /> },
	{ id: "settings", label: "Settings", icon: <FiSettings /> },
];

export function Sidebar({ mode, activePage, width, onNavigate, onToggle, onResize }: Props) {
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
						key={item.id}
						className={`nav-item ${activePage === item.id ? "active" : ""}`}
						type="button"
						aria-label={item.label}
						aria-current={activePage === item.id ? "page" : undefined}
						title={compact ? item.label : undefined}
						onClick={() => onNavigate(item.id)}
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
