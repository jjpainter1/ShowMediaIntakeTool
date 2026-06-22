# Show Media Intake Tool — AI Agent Integration

**Status:** Goals & scope (pre-implementation)  
**Last updated:** 2026-06-10  
**Related:** `DESIGN-V2.md`, `README.md`, `backend/`, `modules/`

---

## 1. Goal

Enable AI agents (e.g. in Cursor, Claude Desktop, or custom automations) to operate the Show Media Intake Tool **headlessly** on a Windows machine — using the same business rules as the GUI and CLI — so operators and producers can describe work in natural language instead of clicking through the app.

The agent is a **copilot for media intake**, not a replacement for operator judgment on edge cases. It should be able to run full intake workflows end-to-end, report results clearly, and handle show setup — while respecting the tool’s existing safety model (plan before copy, never delete, transparent validation).

### What success looks like

An operator can say:

> “I have new files for **ExampleShow** at **D:\Delivery\Batch3**. Run them through the Intake Tool and let me know if there are any issues.”

The agent will:

1. Resolve the show (recent shows list or known path).
2. Ensure the show’s media folder structure exists.
3. Scan the source folder (naming, specs, routing).
4. Execute the intake copy (unless the user asked for scan-only).
5. Report when copying is finished, including warnings, failures, and files sent to `_REVIEW`.

Similarly:

> “I just got an updated opening video — let me know when it’s ready.”

The agent will run that delivery through intake for the active show and notify the user when copying completes, including any spec or naming issues.

Show creation should feel natural:

> “Create a new show called **SummerFest** on **2026-08-15** using the **Pixera** preset, with screens SCR01–SCR04 at 1920×1080.”

The agent creates the folder, writes `show_config.json`, and confirms the show is ready for intake.

---

## 2. Why this fits the project

v2 already separates concerns in a way that supports agents:

| Layer | Role today | Role for agents |
|-------|------------|-----------------|
| `modules/` | Business logic (intake, config, dashboard) | **Direct integration point** |
| `backend/` (FastAPI) | HTTP API for React/Tauri UI | Optional transport; not required if MCP calls `modules/` |
| `frontend/` | Human UI (pickers, tables, progress) | Unchanged; agents use paths, not dialogs |
| `cli_intake.py` | Power-user terminal workflow | Precedent for headless operation |

The intake workflow is already two-phase (`build_intake_plan` → `execute_plan`), which maps well to agent behavior: scan and summarize, then copy when instructed.

Configuration **is** JSON (`show_config.json`), but agents should use the tool’s config APIs/helpers — not hand-edit raw JSON — so presets, validation rules, and schema version stay correct.

---

## 3. Primary use cases (requested)

### 3.1 Full batch intake from natural language

**Trigger:** User names a show and a source folder path.

**Agent workflow:**

1. Load show (`show_config.json`, show root path).
2. Call `ensure_media_structure` (via scan path) so `Media/`, screen folders, `_REVIEW`, `_LOGS`, etc. exist.
3. Scan source folder → intake plan (per-file action, destination, warnings, failures).
4. Execute plan → copy/route files, write intake log, append delivery log.
5. Return structured summary to the user.

**Report should include:**

- Counts: copied, skipped (identical), routed to review, copy failures.
- Per-file issues: bad naming, codec/resolution/fps failures or warnings.
- Version conflicts (incoming vs. existing versions of same slug).
- Stale folders detected in the source (informational).
- Path to intake log for audit.

**Example user phrasing:**

- “Run the files at `E:\ClientDrop\Reel2` through **Glastonbury_20260620**.”
- “Intake everything in `D:\Inbox\Monday` for ExampleShow and tell me what broke.”

---

### 3.2 Single-file / “updated asset” intake

**Trigger:** User mentions one updated video (opening, bumper, loop, etc.) and wants notification when it’s done.

**Agent workflow:**

Same as §3.1, but source is typically a folder containing one file (or a path the agent normalizes to a folder). The tool scans **folders**, not individual file paths — the agent is responsible for passing a directory (e.g. the parent of the dropped file).

**Report should emphasize:**

- Whether the file copied successfully and its destination screen folder.
- If it superseded or coexists with other versions (multi-version slug).
- Any spec warnings that mean “usable but not ideal.”
- Clear done/failed status for async-style requests (“let me know when it’s ready”).

**Example user phrasing:**

- “I just got an updated opening video in `D:\Downloads\open_v3.mov` — run it through and ping me when it’s on the server.”
- “New SCR02_main_03 file landed in `\\NAS\drop` — intake it for tonight’s show.”

---

### 3.3 Create show and configure

**Trigger:** User wants a new show before any media arrives.

**Agent workflow:**

1. Create show folder (`ShowName_YYYYMMDD`) under a parent path.
2. Write starter `show_config.json` (schema v2).
3. Apply a preset (Pixera, PlayBack Pro, custom, etc.).
4. Set show metadata: name, date, operator, screens, expected codecs/specs, validation strictness.
5. Confirm show path and readiness for intake.

**Note:** Config is JSON, but the agent should use validated save paths (`create_new_show`, `load_config` / `validate_config`, preset apply helpers) so invalid combinations are caught before show day.

**Example user phrasing:**

- “Set up a new show **CorporateGala** for July 4th in `D:\Shows` with the PlayBack Pro preset.”
- “Add SCR05 at 3840×2160 to the ExampleShow config.”

---

## 4. Additional use cases (recommended)

These follow naturally from existing modules and APIs and are high value for agents without expanding core intake logic.

### 4.1 Pre-show health check

**Trigger:** “How does **ExampleShow** look?” / “Anything I should worry about before load-in?”

**Agent:** Call `gather_snapshot` (dashboard). Summarize in plain language:

- Days until show date.
- Per-screen file/slug counts.
- Multi-version conflicts.
- Stale folders on the show side.
- Files in `_REVIEW`.
- Last delivery timestamp and stats.

Useful for morning-of briefings and producer check-ins.

---

### 4.2 Scan-only / “don’t copy yet”

**Trigger:** “Check this folder before we commit” or “What would happen if we ran intake?”

**Agent:** Run scan only; return full plan without `execute_plan`. Valuable when a client drop arrives before the operator is ready to copy.

---

### 4.3 Post-intake audit and history

**Trigger:** “What did we intake yesterday?” / “Summarize the last delivery.”

**Agent:** Read `DeliveryLog.txt` and structured delivery history; optionally pull linked intake log content. Translate log lines into a short narrative for non-technical stakeholders.

---

### 4.4 Review queue triage

**Trigger:** “What’s in `_REVIEW` and why?”

**Agent:** Dashboard snapshot + screen file details; list files routed to review with naming/spec reasons from the last intake or current show state.

---

### 4.5 Naming and spec coaching (pre-intake)

**Trigger:** “Will `video_final_FINAL2.mov` pass intake for SCR01?”

**Agent:** Scan a folder (or explain naming rules from config + `filename_parser` behavior) without copying. Reduces back-and-forth with content creators before files are delivered.

---

### 4.6 Generate delivery specification document

**Trigger:** “Generate the spec doc for this show for the client.”

**Agent:** Call `generate_spec` (Phase 6 — when implemented). Return path to the `.docx` and confirm success.

---

### 4.7 Migrate legacy v1 show

**Trigger:** “This show is still on old config format — fix it.”

**Agent:** Detect v1 config on load; run migration with backup; confirm `show_config.v1.bak.json` written.

---

### 4.8 Screen-level queries

**Trigger:** “What’s on SCR03?” / “List files failing resolution check on the wide screen.”

**Agent:** `GET` screen-files style data — filenames, locations, spec status, warnings/failures — for one screen without loading the full GUI.

---

### 4.9 Config read-back and validation

**Trigger:** “What codecs does this show expect?” / “Is our config valid?”

**Agent:** Load and summarize `show_config.json` through validated loaders; report preset name, screens, strictness, expected specs. Catch errors before intake.

---

### 4.10 Recent shows discovery

**Trigger:** User says “ExampleShow” without a path.

**Agent:** Resolve from recent shows list (`recent_shows`) or ask for clarification if ambiguous. Reduces need for users to memorize `D:\Shows\...` paths.

---

## 5. Out of scope (for initial agent integration)

| Item | Reason |
|------|--------|
| GUI folder/file pickers | Agents pass explicit paths |
| Opening Explorer or Notepad++ | OS convenience actions, not agent workflows |
| Deleting or moving existing media | Violates design principles |
| Bypassing validation / forcing bad files into screen folders | Agent uses same rules as GUI |
| Running without ffprobe | Tool requires ffprobe; agent should check health first |
| Non-Windows platforms | Tool target is Windows |
| Autonomous watch-folder monitoring | Possible future enhancement; not required for v1 goals |

---

## 6. Agent interaction model

### 6.1 Transport

A dedicated **MCP server** process (stdio) that imports `modules/` directly is the intended approach. It parallels `cli_intake.py` and avoids depending on the FastAPI server or Tauri app being open.

### 6.2 Tools (conceptual)

High-level tools the agent would call — names TBD at implementation:

| Tool | Purpose |
|------|---------|
| `health_check` | ffprobe + environment readiness |
| `list_recent_shows` | Resolve show by friendly name |
| `get_dashboard` | Show health snapshot |
| `get_show_config` / `save_show_config` | Read/update configuration |
| `create_show` | New show + starter config |
| `apply_preset` | Apply playback-system preset |
| `scan_intake` | Plan only |
| `execute_intake` | Copy/route per plan |
| `run_intake` | Scan + execute in one call (convenience for “just run it”) |
| `get_delivery_history` | Past deliveries and logs |

Destructive tools (`execute_intake`, `run_intake`, `save_show_config`, `create_show`) should require explicit user intent in the conversation; implementation may add a `confirm` flag for safety.

### 6.3 What the agent returns to the user

Responses should be **human-first summaries** backed by structured data:

- **Status:** completed / completed with warnings / failed.
- **Counts:** copied, review, skipped, failed.
- **Issues list:** file name → problem → recommended action.
- **Paths:** show root, intake log, review folder if applicable.
- **Next steps:** e.g. “Fix naming on 2 files and re-drop” or “Check `_REVIEW` for spec failures.”

Avoid dumping raw JSON unless the user asks for technical detail.

---

## 7. Constraints and design alignment

Agent integration must honor existing design principles from `DESIGN-V2.md`:

1. **Two-phase execution** — Scan before copy; agent may combine both in one user request but still runs both phases internally.
2. **Never delete; never move active files** — Version coexistence is expected.
3. **Show config is source of truth** — Presets seed config; runtime uses `show_config.json`.
4. **Strict validation, transparent reporting** — Agent reports warnings and failures clearly.
5. **Atomic copy operations** — Unchanged; agent benefits automatically.

### Single-file caveat

Intake operates on **directories**. For “one updated video,” the agent must supply a folder path (e.g. create a temp folder, or use the parent directory). Document this in agent prompts and tool descriptions.

### Long-running work

Scanning many large files with ffprobe can take minutes. For “let me know when it’s ready” workflows, the agent should:

- Set user expectation on duration.
- Run intake to completion before reporting (v1).
- Future: optional progress streaming or job IDs if needed.

---

## 8. Phased delivery (suggested)

| Phase | Deliverable | Covers |
|-------|-------------|--------|
| **A — Goals** | This document | Alignment |
| **B — MVP** | MCP server: health, recent shows, dashboard, scan, execute | §3.1, §4.1, §4.2 |
| **C — Setup** | create show, config read/write, presets | §3.3, §4.9 |
| **D — Polish** | Delivery history, screen files, migration, spec gen | §4.3–4.8, §4.6 |
| **E — Docs** | Cursor MCP config, operator cheat sheet | Adoption |

Implementation plan and tool schemas: separate document when ready to build.

---

## 9. Open questions

1. **Default execute behavior** — When the user says “run intake,” should the agent always execute after scan, or ask if warnings exceed a threshold?
2. **Show name resolution** — Fuzzy match on recent shows vs. require full path?
3. **Single-file UX** — Accept file paths in tool API and normalize to parent folder internally?
4. **Notification** — Is “report in chat when done” sufficient, or integrate Slack/email later?
5. **Concurrent use** — Behavior if GUI and agent intake the same show simultaneously?
6. **Authentication** — Local MCP only (trusted machine) vs. any remote access concerns?

---

## 10. Summary

The feature goal is to let AI agents **run real intake work** — scan, copy, configure shows, and report issues — using the same `modules/` logic as the desktop app, driven by natural language. The highest-value flows are **batch intake**, **single-asset updates with completion notice**, and **show creation/config**. Additional wins include **pre-show health checks**, **scan-only previews**, **delivery history**, and **review triage**, all of which already map to existing code paths.

Next step when approved: implementation spec (MCP tool definitions, schemas, packaging, and Cursor configuration).
