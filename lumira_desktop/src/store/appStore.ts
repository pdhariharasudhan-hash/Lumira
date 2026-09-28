import { create } from "zustand";
import { persist } from "zustand/middleware";

export type PanelMode = "full" | "compact" | "hidden";
export type InputMode = "full" | "compact" | "hidden";
export type WorkspacePage = "chats" | "projects" | "artifacts" | "memory" | "goals" | "search" | "generator" | "business" | "operations" | "settings";
export type LumiraMode = "auto" | "creator" | "generator" | "business" | "operations";

export interface WorkspaceUiState {
	navMode: PanelMode;
	chatMode: PanelMode;
	rightMode: PanelMode;
	navWidth: number;
	chatWidth: number;
	rightWidth: number;
	topBarCompact: boolean;
	inputMode: InputMode;
	focusMode: boolean;
	activePage: WorkspacePage;
	activeMode: LumiraMode;
	selectedProject: string | null;
	selectedVersion: string | null;
	setNavMode: (mode: PanelMode) => void;
	setChatMode: (mode: PanelMode) => void;
	setRightMode: (mode: PanelMode) => void;
	setPanelWidth: (panel: "nav" | "chat" | "right", width: number) => void;
	setTopBarCompact: (compact: boolean) => void;
	setInputMode: (mode: InputMode) => void;
	setFocusMode: (focus: boolean) => void;
	setActivePage: (page: WorkspacePage) => void;
	setActiveMode: (mode: LumiraMode) => void;
	setSelectedProject: (project: string | null, version?: string | null) => void;
}

export const initialWorkspaceUiState = {
	navMode: "full" as const,
	chatMode: "full" as const,
	rightMode: "full" as const,
	navWidth: 204,
	chatWidth: 248,
	rightWidth: 330,
	topBarCompact: false,
	inputMode: "full" as const,
	focusMode: false,
	activePage: "chats" as const,
	activeMode: "auto" as const,
	selectedProject: null as string | null,
	selectedVersion: null as string | null,
};

export const useAppStore = create<WorkspaceUiState>()(persist((set) => ({
	...initialWorkspaceUiState,
	setNavMode: (navMode) => set({ navMode }),
	setChatMode: (chatMode) => set({ chatMode }),
	setRightMode: (rightMode) => set({ rightMode }),
	setPanelWidth: (panel, width) => {
		const bounds = panel === "nav" ? [176, 280] : panel === "chat" ? [210, 390] : [260, 480];
		const key = panel === "nav" ? "navWidth" : panel === "chat" ? "chatWidth" : "rightWidth";
		set({ [key]: Math.max(bounds[0], Math.min(bounds[1], width)) });
	},
	setTopBarCompact: (topBarCompact) => set({ topBarCompact }),
	setInputMode: (inputMode) => set({ inputMode }),
	setFocusMode: (focusMode) => set({ focusMode }),
	setActivePage: (activePage) => set({ activePage }),
	setActiveMode: (activeMode) => set({ activeMode }),
	setSelectedProject: (selectedProject, selectedVersion = null) => set({ selectedProject, selectedVersion }),
}), {
	name: "lumira.workspace",
	partialize: (state) => ({
		navMode: state.navMode,
		chatMode: state.chatMode,
		rightMode: state.rightMode,
		navWidth: state.navWidth,
		chatWidth: state.chatWidth,
		rightWidth: state.rightWidth,
		topBarCompact: state.topBarCompact,
		inputMode: state.inputMode,
		focusMode: state.focusMode,
		activePage: state.activePage,
		activeMode: state.activeMode,
		selectedProject: state.selectedProject,
		selectedVersion: state.selectedVersion,
	}) as WorkspaceUiState,
}));
