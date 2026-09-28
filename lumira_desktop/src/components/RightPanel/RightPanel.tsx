import { useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { FiCode, FiExternalLink, FiFile, FiFolder, FiMinus, FiMonitor, FiPlus, FiTerminal, FiX } from "react-icons/fi";
import type { PanelMode } from "../../store/appStore";

type ProjectItem = { project: string; versions?: number; latest?: Record<string, unknown> | null };
type Props = {
	mode: PanelMode;
	width: number;
	projects: ProjectItem[];
	project: string | null;
	version: string | null;
	versions: string[];
	files: string[];
	selectedFile: string | null;
	fileContent: string | null;
	fileLoading: boolean;
	previewUrl?: string | null;
	apiPaths: string[];
	runs: Record<string, unknown>[];
	onToggle: () => void;
	onResize: (change: number) => void;
	onTabChange: (tab: RightTab) => void;
	activeTab: RightTab;
	onProjectChange: (project: string) => void;
	onVersionChange: (version: string) => void;
	onFileSelect: (file: string) => void;
};

export type RightTab = "files" | "code" | "preview" | "terminal";

const tabs: Array<{ id: RightTab; label: string; icon: ReactNode }> = [
	{ id: "files", label: "Files", icon: <FiFolder /> },
	{ id: "code", label: "Code", icon: <FiCode /> },
	{ id: "preview", label: "Preview", icon: <FiMonitor /> },
	{ id: "terminal", label: "Terminal", icon: <FiTerminal /> },
];

export function RightPanel(props: Props) {
	const [openSections, setOpenSections] = useState<string[]>([]);
	const compact = props.mode === "compact";
	if (props.mode === "hidden") return null;
	const toggleSection = (name: string) => setOpenSections((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name]);
	const paths = props.files.map((file) => file.replace(/\\/g, "/").split("/").filter(Boolean));
	const folders = [...new Set(paths.filter((parts) => parts.length > 1).map((parts) => parts.slice(0, -1).join("/")))];
	const sourceLines = (props.fileContent ?? "").split("\n");
	const lineCount = Math.min(sourceLines.length, 20_000);

	return (
		<aside className={`dev-panel ${compact ? "is-compact" : ""}`} style={{ "--dev-width": `${props.width}px` } as CSSProperties} aria-label="Development panel">
			<header className="dev-panel-heading">
				{!compact && <div><strong>Development</strong><small>{props.project ?? "No project selected"}</small></div>}
				<div className="panel-tools">
					{!compact && <><button className="icon-button" type="button" aria-label="Narrow development panel" onClick={() => props.onResize(-24)}><FiMinus /></button><button className="icon-button" type="button" aria-label="Widen development panel" onClick={() => props.onResize(24)}><FiPlus /></button></>}
					<button className="icon-button" type="button" aria-label={compact ? "Expand development panel" : "Hide development panel"} onClick={props.onToggle}>{compact ? <FiExternalLink /> : <FiX />}</button>
				</div>
			</header>
			<nav className="dev-tabs" aria-label="Development tools">
				{tabs.map((tab) => <button key={tab.id} className={props.activeTab === tab.id ? "active" : ""} type="button" aria-label={tab.label} aria-pressed={props.activeTab === tab.id} title={compact ? tab.label : undefined} onClick={() => props.onTabChange(tab.id)}><span>{tab.icon}</span>{!compact && tab.label}</button>)}
			</nav>
			{!compact && <>
				{props.activeTab === "files" && <section className="dev-content" aria-label="Project files">
					<label className="field-label">PROJECT<select aria-label="Select project" value={props.project ?? ""} onChange={(event) => props.onProjectChange(event.target.value)}><option value="">Select a project</option>{props.projects.map((item) => <option key={item.project} value={item.project}>{item.project}</option>)}</select></label>
					<label className="field-label">VERSION<select aria-label="Select project version" value={props.version ?? ""} onChange={(event) => props.onVersionChange(event.target.value)} disabled={!props.versions.length}><option value="">Select a version</option>{props.versions.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
					<div className="tree-root"><FiFolder /> <span>{props.project ? `${props.project}/${props.version ?? ""}` : "Project root"}</span></div>
					{folders.map((folder) => <div className="tree-folder" key={folder}><FiFolder />{folder}</div>)}
					<div className="file-list">{props.files.map((file) => <button type="button" className={`file-item ${props.selectedFile === file ? "selected" : ""}`} key={file} onClick={() => props.onFileSelect(file)}><FiFile aria-hidden="true" /><span>{file}</span></button>)}</div>
					{props.project && props.files.length === 0 && <p className="empty-note">No files are available in this version.</p>}
					{!props.project && <p className="empty-note">Choose a generated project to inspect its real files.</p>}
				</section>}
				{props.activeTab === "code" && <section className="dev-content code-view" aria-label="Code viewer">
					<div className="code-tab"><FiFile />{props.selectedFile ?? "No file selected"}</div>
					{props.fileLoading ? <p className="empty-note">Loading file…</p> : props.fileContent !== null ? <pre className="source-code">{sourceLines.slice(0, lineCount).map((line, index) => `${String(index + 1).padStart(4, " ")}  ${line}`).join("\n")}</pre> : <p className="empty-note">Select a project file to view its source.</p>}
				</section>}
				{props.activeTab === "preview" && <section className="dev-content preview-view" aria-label="Project preview">
					{props.previewUrl ? <><div className="preview-toolbar"><span>{props.previewUrl}</span><button className="icon-button" type="button" aria-label="Open preview externally" onClick={() => window.open(props.previewUrl!, "_blank", "noopener,noreferrer")}><FiExternalLink /></button></div><iframe title="Project preview" src={props.previewUrl} /></> : <div className="unavailable-state"><FiMonitor /><strong>Preview unavailable</strong><p>No running project preview is registered.</p><small>Run the project to start a preview when a safe runner is configured.</small></div>}
				</section>}
				{props.activeTab === "terminal" && <section className="dev-content unavailable-state" aria-label="Terminal"><FiTerminal /><strong>Terminal unavailable</strong><p>No sandboxed project terminal is configured.</p><small>Arbitrary shell execution is not enabled.</small></section>}
				<div className="dev-secondary" aria-label="Developer details">
					{[
						{ id: "api", label: "API Docs", body: props.apiPaths.length ? <ul>{props.apiPaths.slice(0, 80).map((path) => <li key={path}><code>{path}</code></li>)}</ul> : <p>API schema is unavailable.</p> },
						{ id: "database", label: "Database", body: <p>Lumira currently stores local project, session, memory, and artifact data in files. No database service is configured.</p> },
						{ id: "logs", label: "Runs & Logs", body: props.runs.length ? <ul>{props.runs.map((run, index) => <li key={String(run.run_id ?? index)}>{String(run.status ?? "unknown")} · {String(run.current_stage ?? run.last_completed_stage ?? "no stage")}</li>)}</ul> : <p>No workflow runs are recorded.</p> },
						{ id: "terminal", label: "Terminal", body: <p>Unavailable: no sandboxed terminal provider is configured.</p> },
					].map((section) => <section className="dev-accordion" key={section.id}>
						<button type="button" aria-expanded={openSections.includes(section.id)} onClick={() => toggleSection(section.id)}>{section.label}<span>{openSections.includes(section.id) ? "−" : "+"}</span></button>
						{openSections.includes(section.id) && <div className="accordion-body">{section.body}</div>}
					</section>)}
				</div>
			</>}
		</aside>
	);
}

export default RightPanel;
