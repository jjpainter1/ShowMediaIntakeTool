# Pixera Content Delivery & Show Media Organization System

**Version 1.0 — Master Reference**

This is the internal master reference for content intake, organization, and show file management when running shows on Pixera. It covers the full system end-to-end: the spec sent to designers, the intake process, the on-server folder structure, version control, the Pixera project organization that mirrors it, and the fallback playbook for non-compliant deliveries.

A trimmed external-facing version of the delivery spec (sections 2–3 only) is maintained separately as a `.docx` for sending to producers and design agencies.

---

## 1. Guiding Principles

The whole system is built on five principles. When in doubt, fall back to these.

1. **Content identity is durable; cue position is not.** Filenames describe what the content *is*, not where it currently lives in the show. Cue numbers can shift during tech without anything in the media folder needing to change.

2. **The intake gate is non-negotiable.** Nothing enters the working show project until it has been verified, renamed if needed, and filed correctly. The spec is upstream; intake is the enforcement layer.

3. **Never delete; archive instead.** Superseded versions are moved to an `_ARCHIVE` subfolder, never overwritten or deleted. Storage is cheap; recovering a lost asset at 11pm is not.

4. **One active version per content slug per screen.** The active folder shows only the current version. This eliminates "which v02 is loaded in Pixera?" ambiguity.

5. **Tiered enforcement.** A preferred spec is sent upstream; a minimum acceptable standard governs intake. Below the minimum, push back. Above the minimum but below preferred, accept and re-file at intake.

---

## 2. Delivery Specification (External-Facing)

This is what gets sent to producers and design agencies at show kickoff.

### 2.1 Technical File Specs

Resolution, framerate, color space, codec, and bit depth are determined per-show based on screen specs and the Pixera output configuration. These are communicated separately in the show-specific tech spec sheet. The standards below cover *how* files are named and delivered, regardless of the technical specs.

### 2.2 Filename Convention

**Pattern:**

```
SCR##_ContentSlug_v##_YYYYMMDD.ext
```

**Field definitions:**

| Field | Format | Example | Rules |
|---|---|---|---|
| Screen | `SCR` + zero-padded 2-digit number | `SCR01`, `SCR12` | Audience perspective, left to right. SCR01 is farthest stage left. |
| Content Slug | PascalCase, no spaces, no special characters | `OpeningVideo`, `50thAnniversary` | Stable across all versions. The slug is the contract. |
| Version | `v` + zero-padded 2-digit number | `v01`, `v12` | Increments only. Never reset. Never use words like "final", "FINAL", "FINAL2", "REAL_FINAL". |
| Date | `YYYYMMDD` | `20260425` | Date the file was rendered/exported, not delivered. |
| Extension | Per technical spec | `.mov`, `.mp4` | Per show-specific tech spec. |

**Full examples:**

```
SCR01_OpeningVideo_v03_20260425.mov
SCR02_50thAnniversary_v01_20260424.mov
SCR03_Speaker1Lower3rd_v02_20260425.mov
```

**Special cases:**

- **Wide content spanning multiple screens:** Use `SCRwide` followed by the screens it spans, e.g. `SCRwide-01-02-03_KeynoteHero_v01_20260425.mov`.
- **Content for all screens identically:** Use `SCRall`, e.g. `SCRall_HouseLightLogo_v02_20260425.mov`.
- **Audio files:** Use `AUD` prefix instead of `SCR`, e.g. `AUD_OpeningStingBed_v01_20260425.wav`.

### 2.3 Folder Structure for Delivery

Content is delivered organized **by screen first**, then by content. Each screen gets its own folder.

```
ShowName_YYYYMMDD/
├── 01_SCR01_StageLeft/
│   ├── SCR01_OpeningVideo_v03_20260425.mov
│   ├── SCR01_50thAnniversary_v01_20260424.mov
│   └── SCR01_ClosingMontage_v02_20260425.mov
├── 02_SCR02_CenterIMAG/
│   ├── SCR02_OpeningVideo_v03_20260425.mov
│   └── SCR02_50thAnniversary_v01_20260424.mov
├── 03_SCR03_StageRight/
│   └── ...
├── 04_SCRwide/
│   └── SCRwide-01-02-03_KeynoteHero_v01_20260425.mov
├── 05_SCRall/
│   └── SCRall_HouseLightLogo_v02_20260425.mov
└── 06_AUD/
    └── AUD_OpeningStingBed_v01_20260425.wav
```

Folder names use a 2-digit prefix so they sort correctly in any file browser, followed by the screen identifier and a short descriptive name.

### 2.4 Versioning Rules

- Each new version is a new file with an incremented version number. **Never overwrite a previous version.**
- The content slug must remain identical across versions. `OpeningVideo_v01` and `OpeningVid_v02` are not the same content as far as the system is concerned.
- The word "final" (in any form, casing, or punctuation) is prohibited. Versioning is numeric only.
- Version numbers do not reset between deliveries. If v04 was the last delivered version, the next version is v05, even if it's been weeks.

### 2.5 Delivery Methods

- **Cloud delivery** (Frame.io, WeTransfer, Dropbox, Aspera, etc.) is preferred for initial deliveries and pre-show revisions.
- **Physical drives** are accepted for on-site changes, but the folder structure inside the drive must still match Section 2.3.
- Mixed deliveries (some files cloud, some drive) are acceptable as long as each individual delivery follows the spec.

---

## 3. Receiving & Intake Process

This is the gate. No file enters the working show project until it has passed this checklist.

### 3.1 Intake Checklist

For every delivery (cloud or drive), in order:

1. **Quarantine.** Copy the entire delivery as-received into `_INTAKE/YYYYMMDD_HHMM_DeliverySource/` on the working drive. Never work directly off a delivery drive or cloud download folder. Always work from a local copy.

2. **Manifest check.** Compare files received against any delivery manifest provided. Note missing files immediately and flag the producer.

3. **Filename compliance check.** Verify each file matches the naming convention. Files that don't comply go to one of three buckets:
   - **Auto-fixable** (typo in screen number, wrong date format, missing version number): rename at intake, log the change.
   - **Ambiguous** (unclear which screen it's for, or which content it supersedes): hold and query the producer before filing.
   - **Wrong content** (file appears to be for a different show, or technical spec doesn't match): reject and request redelivery.

4. **Technical QC.** Spot-check resolution, framerate, codec, color space, and duration for each file. Confirm files actually open and play.

5. **Version conflict resolution.** If a new version of an existing slug arrives, the previous version is **moved** (not copied) from the active folder into the screen's `_ARCHIVE` subfolder. The new version replaces it as the active file.

6. **File into Show Media folder.** Once the file passes all checks, move it from `_INTAKE` into the appropriate Show Media screen folder (see Section 4).

7. **Update Pixera.** Re-link the resource in Pixera if it was already imported under the same slug. (See Section 5.3.)

8. **Log the delivery.** Add an entry to the show delivery log (see Section 3.2).

### 3.2 Show Delivery Log

A simple text or CSV log per show, kept in the show root folder. One line per delivery batch:

```
2026-04-25 14:30 | Cloud (Frame.io) | 8 files | Notes: Updated opening video v03, new closing montage v02
2026-04-25 19:15 | Drive (WD black, "AGENCY_DELIVERY_4") | 3 files | Notes: SCR02 50thAnniversary v01 (new asset, replaces placeholder)
2026-04-26 09:45 | Cloud (WeTransfer) | 1 file | Notes: SCR01 OpeningVideo v04 (color correction pass)
```

This log is the answer to "when did we get the last update?" and is invaluable in postmortems.

---

## 4. Show Media Folder Structure (On-Server)

This is the structure that lives on the Pixera workstation's working drive. It mirrors the delivery structure but adds archive subfolders and intake/log scaffolding.

```
ShowName_YYYYMMDD/
├── _INTAKE/                          # Quarantine landing zone
│   └── (timestamped delivery folders, cleared after successful filing)
├── _LOGS/
│   ├── DeliveryLog.txt
│   └── _RunOfShow_Map.csv            # Optional, see Section 4.3
├── _REFERENCE/                       # Run of show, tech specs, screen diagrams
│   ├── RunOfShow_v##.pdf
│   ├── ScreenDiagram.pdf
│   └── TechSpec.pdf
├── 01_SCR01_StageLeft/
│   ├── SCR01_OpeningVideo_v03_20260425.mov     # Active version only
│   ├── SCR01_50thAnniversary_v01_20260424.mov
│   └── _ARCHIVE/
│       ├── SCR01_OpeningVideo_v01_20260420.mov
│       └── SCR01_OpeningVideo_v02_20260423.mov
├── 02_SCR02_CenterIMAG/
│   ├── ...
│   └── _ARCHIVE/
├── 03_SCR03_StageRight/
│   └── ...
├── 04_SCRwide/
│   └── _ARCHIVE/
├── 05_SCRall/
│   └── _ARCHIVE/
└── 06_AUD/
    └── _ARCHIVE/
```

### 4.1 Folder Behavior Rules

- Active folders contain **exactly one file per content slug** — the current version.
- `_ARCHIVE` contains every superseded version, never deleted.
- Underscore-prefixed folders (`_INTAKE`, `_LOGS`, `_REFERENCE`, `_ARCHIVE`) sort to the top in most file browsers, keeping screen folders together.
- The entire `ShowName_YYYYMMDD/` folder is the unit of show portability. Copying it copies the entire show state, including all archived versions.

### 4.2 Show Lifecycle

- **Pre-show through show day:** Active folder is the working state.
- **Post-show:** Entire show folder gets archived to long-term storage as-is, including `_INTAKE` (if any leftovers) and all `_ARCHIVE` folders. No cleanup. The show is preserved exactly as it was run.

### 4.3 Run of Show Map (Optional, Above Threshold)

For shows with **more than ~20 cues OR more than 4 screens**, maintain a `_RunOfShow_Map.csv` file at `_LOGS/_RunOfShow_Map.csv`:

```csv
Cue,Screen,ContentSlug,Filename,Version,DeliveredDate,Notes
100,SCR01,OpeningVideo,SCR01_OpeningVideo_v03_20260425.mov,v03,2026-04-25,
100,SCR02,OpeningVideo,SCR02_OpeningVideo_v03_20260425.mov,v03,2026-04-25,
100,SCR03,OpeningVideo,SCR03_OpeningVideo_v02_20260424.mov,v02,2026-04-24,Pending v03
120,SCR02,Speaker1Lower3rd,SCR02_Speaker1Lower3rd_v01_20260424.mov,v01,2026-04-24,
145,SCR01,50thAnniversary,SCR01_50thAnniversary_v04_20260425.mov,v04,2026-04-25,
145,SCR02,50thAnniversary,SCR02_50thAnniversary_v04_20260425.mov,v04,2026-04-25,
```

For smaller shows, a lighter plain-text version is acceptable:

```
100 | OpeningVideo    | SCR01,SCR02,SCR03 | v03/v03/v02
120 | Speaker1Lower3rd| SCR02              | v01
145 | 50thAnniversary | SCR01,SCR02        | v04/v04
```

The map is updated when new content is delivered or when the run of show changes. Cue renumbers only require editing the cue column — no file renames.

---

## 5. Pixera Project Organization

The on-server folder structure is designed to mirror how Pixera thinks about resources. This section covers how to set up the Pixera project so it stays in sync with the file system.

### 5.1 Resource Pool Organization

When importing content into Pixera:

- Drag in **whole screen folders at a time**, not individual files. This creates a logical grouping in the resource pool that matches the file system.
- Use Pixera's resource pool folders/groups to mirror the screen folders (`SCR01_StageLeft`, `SCR02_CenterIMAG`, etc.). One Pixera resource folder per screen folder on disk.
- Wide content (`SCRwide`) and all-screen content (`SCRall`) get their own resource folders.
- Audio gets its own resource folder.

### 5.2 Cue Naming in Pixera

Cue names in Pixera continue to follow the existing convention: `100 - opening video` matches show cue 100. The cue number lives in the Pixera cue label, not in the filename. This is the deliberate decoupling that lets cue numbers shift without filename churn.

The Pixera cue references the resource by content slug. When cue 100 becomes cue 95, the cue label changes (`95 - opening video`) but the resource it points to does not.

### 5.3 Re-Linking After Version Updates

When a new version arrives and the old version is archived:

- Because the new file has a different filename (different version number and date), Pixera will not auto-relink.
- Workflow: re-import the new file into the same resource pool folder, then update the affected cues to reference the new resource. Delete the old (archived) resource from the pool to keep it clean.
- Alternative for repeat updates of the same slug: some ops prefer to keep a stable Pixera resource name (without version/date in the resource name, even though the file has it) and use Pixera's "replace media" function to swap the underlying file. Either approach works; pick one and stick with it for the show.

### 5.4 Compositions vs. Timeline vs. Pixera Control

The folder structure works regardless of whether the show is built on the timeline or as Pixera Control buttons. The resource pool organization is the constant; how those resources are arranged into playable cues is a per-show creative/operational decision.

---

## 6. Fallback Playbook (When Deliveries Don't Follow the Spec)

The spec is the ideal. Reality often isn't. Here's what to do when it isn't.

### 6.1 Triage Levels

When a non-compliant delivery arrives, sort it into one of three levels:

**Level 1 — Cosmetic non-compliance.** Filename has wrong casing, wrong date format, or missing zero-padding, but the screen, content, and version are unambiguous.
- **Action:** Rename at intake. File normally. Note in delivery log.
- **Pushback:** None on this delivery. Send a friendly reminder of the spec for next time.

**Level 2 — Structural non-compliance.** Files are flat in a folder with no screen organization, or named with words like "final" or "FINAL2", or use ambiguous slugs ("video1", "the new one").
- **Action:** Hold the delivery in `_INTAKE`. Identify each file's intended screen and content slug by cross-referencing the run of show. Rename and re-file. Note all renames in the delivery log.
- **Pushback:** Email the producer with a clear list of what was renamed and why. Reference the spec.

**Level 3 — Critical non-compliance.** Wrong technical specs (resolution, framerate, codec), files won't play, or content appears to be for a different show.
- **Action:** Reject the delivery. Do not file. Notify producer immediately with specific reason.
- **Pushback:** Required. The file does not enter the project until it's redelivered correctly.

### 6.2 The "Surprise Drive at Load-In" Scenario

When a drive shows up unexpectedly with content that has to be in the show:

1. Copy entire drive contents to `_INTAKE/YYYYMMDD_HHMM_OnSiteDelivery/` immediately. Do not work off the drive.
2. Quick triage: are these new assets, updates to existing assets, or a mix?
3. For updates: identify by content slug, archive the existing version, file the new one.
4. For new assets: confirm with the producer which cue(s) they're for before filing. Do not assume.
5. If the run of show map is being maintained, update it.
6. If there's no time for proper intake before showtime: file what you can verify, hold what you can't, and program from the verified files only. Anything held does not go in the show until verified.

### 6.3 The "It's Different Now" Scenario

Producer says "we changed cue 100" but no new file has been delivered.

1. Confirm: is the change a content swap (different file plays) or a cue change (same file, different position in show)?
2. **Content swap without new delivery:** the file they want already exists somewhere. Identify it by slug, point the cue at it. No file system change.
3. **Cue position change:** edit the cue number in Pixera and update the run of show map. No file system change.
4. **New content needed:** request delivery, refuse to fake it. Note in delivery log when promised and when received.

---

## 7. Show Setup Checklist (Pre-Kickoff)

Before content starts arriving for a new show:

- [ ] Create the show root folder: `ShowName_YYYYMMDD/`
- [ ] Create scaffolding: `_INTAKE/`, `_LOGS/`, `_REFERENCE/`
- [ ] Create screen folders based on the show's screen count, with `_ARCHIVE` subfolders
- [ ] Initialize `DeliveryLog.txt` with show name, date, and screen mapping
- [ ] If above threshold (>20 cues or >4 screens), initialize `_RunOfShow_Map.csv`
- [ ] Confirm screen numbering and naming with producer; document in `_REFERENCE/ScreenDiagram.pdf`
- [ ] Send delivery spec (the external `.docx`) to producer and any direct-contact agencies
- [ ] Confirm technical specs (resolution, framerate, codec, color space) per screen and document in `_REFERENCE/TechSpec.pdf`
- [ ] Confirm delivery method(s) and expected delivery dates with producer

---

## 8. Quick Reference Card

For the wall of the booth or the back of a clipboard.

**Filename:** `SCR##_ContentSlug_v##_YYYYMMDD.ext`

**Screens:** SCR01 = farthest stage left (audience POV), counting up to stage right.

**Special prefixes:** `SCRwide-XX-YY` (multi-screen), `SCRall` (all screens), `AUD` (audio).

**Versioning:** Numbers only. Never "final". Never reset. Never overwrite.

**Intake gate:** Quarantine → Manifest → Filename → Tech QC → Version conflict → File → Pixera → Log.

**Archive, never delete:** Old versions move to `_ARCHIVE`, never get overwritten.

**Cue numbers live in Pixera, not in filenames.** Cues can renumber freely without touching files.
