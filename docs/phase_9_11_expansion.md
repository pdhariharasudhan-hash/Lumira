# Lumira Expansion Roadmap — Phases 9–11

**Roadmap selection:** The user explicitly selected the older expansion roadmap on 2026-11-06. This document governs the expansion work in this handoff and is separate from the newer 0–9 release-hardening roadmap.

**Implementation status:** Backend and desktop source implementation in progress. Runtime tests, desktop tests, lint, builds, provider calls and hardware acceptance were explicitly deferred by the user. Do not label these phases fully verified or release complete.

## Phase 9 — Market Intelligence / Kronos

### Implemented source surface
- Persistent watchlist for NSE, BSE, NASDAQ, NYSE, crypto and other ticker namespaces.
- Manual portfolio holdings with quantity and average cost.
- Bounded OHLCV import with date, duplicate, finite-number and OHLC consistency validation.
- Optional Yahoo Finance chart-history adapter, registered only when `LUMIRA_MARKET_DATA_ENABLED=true`.
- External market-data access passes through Lumira's provider access policy. Offline mode or disabled cloud consent blocks the provider call.
- Daily/weekly/monthly history storage; intraday candle import is not supported because the current history key is daily-date based.
- Technical analysis: SMA 20/50, EMA-derived MACD and signal, RSI 14, Bollinger Bands 20, ATR 14 and deterministic trend classification.
- Watchlist scanner evaluates only stored history.
- Fundamental snapshot import for EPS, P/E, debt/equity, ROE, revenue growth, profit margin and market capitalization; peer descriptive averages.
- Long-only SMA crossover backtest with configurable periods, capital, fees and slippage. No leverage or short selling.
- Position-risk calculator derives risk budget, risk per unit, estimated maximum units and notional from account size, risk percentage, entry and stop prices (maximum 5% risk input).

### Acceptance limits
- Yahoo Finance is an optional public adapter, not a guaranteed exchange feed. It may be delayed, incomplete, rate-limited or unavailable.
- No live quote, exchange-certified feed, corporate-action adjustment, tax model, order routing, broker integration, paper-trading order ledger or real-money trade execution is implemented.
- Fundamental metrics are user-imported; no audited filing ingestion or automated fundamental provider is configured.
- News/social sentiment scoring, forecasting models, automated pattern discovery, intraday feeds and exchange-certified real-time quotes are not implemented.
- Scanner output is historical analysis, not a prediction or investment recommendation.
- Enable the adapter only after the user explicitly configures the environment flag and external provider consent. No external calls were made during implementation.

## Phase 10 — Creator OS

### Implemented source surface
- Creator API and desktop Creator Studio.
- Editable SVG concepts for posters, logos, thumbnails, infographics, UI mockups and blueprint concepts.
- HTML slide-deck artifact generation.
- JSON storyboard generation.
- Markdown scripts, video scripts, social posts, documents and marketing briefs.
- All successful outputs are saved through Artifact Manager and linked to the artifact library.

### Acceptance limits
- SVG concepts and HTML/Markdown/JSON deliverables are editable source artifacts, not claims of polished raster rendering.
- Creator Studio can invoke the existing image-generation API, which persists successful output through Artifact Manager and retains its resource guard and external-provider consent policy. Actual raster output still depends on an enabled image provider.
- Finished video rendering, audio generation, timeline editing, animation and export encoding are not implemented by this Creator OS pass.
- Template quality, browser rendering, accessibility and exported artifact acceptance remain unverified.

## Phase 11 — Device Ecosystem

### Implemented source surface
- Device registry type coverage expanded for laptop, Raspberry Pi Pico, drone, wearable, smart display and printer in addition to existing device families.
- Device profiles support more hardware types and bounded JSON metadata.
- Profile metadata rejects secret-like keys and bounds nesting, string sizes, array sizes and total encoded size.
- Ecosystem overview combines registered devices, profiles, type/connection counts and fresh-heartbeat state.
- Capability planning reports whether a registered device has a fresh heartbeat, declared capability, matching permission and configured transport; it never sends a command.
- Desktop Device Ecosystem page supports hardware registration, profile metadata entry, inventory inspection and capability readiness checks.
- Existing device gateway continues to enforce transport provider policy, device permissions, fresh heartbeat, bounded payloads and confirmed command IDs.

### Acceptance limits
- Registration is not physical discovery or proof of connectivity.
- No BLE/Wi-Fi/USB/serial discovery daemon, device-side agent firmware, mobile app bridge, vehicle interface, robot motion acceptance or smart-home adapter is supplied by this pass.
- Physical commands remain unavailable unless a real device transport provider is explicitly configured and the device has granted the relevant permission.
- Offline/hybrid/cloud recommendations are policy guidance, not an assertion that every device can operate in each mode.

## Deferred by explicit instruction
- No backend or desktop test suites were run.
- No Python compile/AST check, frontend lint, TypeScript check, desktop build, package build or installer run was performed.
- No live provider request, model inference, device scan or hardware command was performed.
- No Git commit, push, reset, cleanup or deletion of user data was performed.

## Required next acceptance pass
1. Review source diffs and route registration for Phases 9–11.
2. Run focused backend tests for market validation/indicators/backtest, Creator artifact generation and device metadata/heartbeat/capability planning.
3. Run desktop tests, lint and TypeScript/Vite build.
4. Configure market-data consent and validate quote freshness/provider failure handling.
5. Validate generated SVG/HTML/JSON artifacts in the desktop app and Artifact Library.
6. Test device adapters only with explicitly registered hardware and permission-limited test commands.
7. Add missing broker/paper-trading, media-rendering and device transport adapters only after their provider/security contracts are approved.

**Verdict:** Meaningful Phase 9–11 implementation slices have been added. These phases are not complete or verified until the deferred checks and provider/hardware acceptance are performed.


## Source-bridge review update — 2026-11-06

- Reviewed the actual router registry, market/creator/device routes, API client, workspace routing, sidebar imports, page components, device registry and profile service.
- Confirmed the three desktop workspaces are included in the persisted workspace-page union, sidebar navigation, MainLayout imports and page rendering. Sidebar icon imports are present.
- Removed an unnecessary duplicate Device Ecosystem overview request from MainLayout; the Device Ecosystem page owns its inventory load.
- Completed the missing Kronos desktop bridges for imported fundamental lookup, peer comparison, and the position-risk calculator; added a reporting-date input for imported fundamentals and the matching API client method.
- Aligned the Device Profile accepted type set with the types exposed by the Device Ecosystem profile selector, including robotics, wearable, smart display, printer, vehicle, Bluetooth and Wi-Fi profile categories.
- Source review found no duplicate router registration for the new Market or Creator routers. Device routes and device-profile routes are both already registered in the central registry.
- These are source-level integration findings only. No Python compile, TypeScript check, lint, tests, build, live provider request or hardware command was run. The expansion phases remain unverified and their external provider/hardware/media gaps remain open.

- Final low-cost source-integrity review: `git diff --check` exited 0. Git status shows the existing broad working tree (88 tracked files changed plus untracked additions at review time); all changes were preserved and no commit/reset/cleanup was performed. This is not a compile, test, lint or build result.


## 2026-11-06 — Phase 9–11 bridge completion pass

- Phase 9: added deterministic descriptive candle-shape detection (doji, hammer-like/inverted-hammer-like, shooting-star-like/hanging-man-like, engulfing and price gaps), exposed through GET /market/patterns/{symbol}, and connected the Kronos workspace. The output explicitly labels these as heuristic descriptions, not validated signals.
- Phase 9: persistent paper ledger and desktop controls were added in the previous pass. Trades remain simulated and cannot reach a broker.
- Phase 10: added POST /creator/video, a provider-policy-gated video-generation bridge, desktop API method, generate-video control and video artifact preview. The bridge returns provider_unavailable when no provider is registered; it does not fake a rendered file. Current environment has no registered video provider, so real video output remains externally blocked.
- Phase 10: audio narration is provider-backed and saved to Artifact Manager when a compatible speech provider is configured.
- Phase 11: device registry/profile/gateway, explicit command UI, private-network-only local HTTP adapter and fail-closed capability/permission/heartbeat checks are present. Physical discovery and hardware acceptance remain dependent on actual devices and adapters.
- Added regression coverage for candle pattern detection and the no-video-provider failure path.
- This is an implementation/bridge milestone, not full release acceptance. Real market feed certification, audited fundamental data, real media providers, physical device discovery/commands, packaged Windows app and visual acceptance remain outstanding.
