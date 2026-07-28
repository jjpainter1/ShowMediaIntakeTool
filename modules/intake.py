"""Intake mode: two-phase plan + execute workflow."""

import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from collections.abc import Callable
from pathlib import Path

from modules.config import (
    ShowConfig,
    effective_specs_for_screen,
    find_screen,
    is_flat_intake,
    strictness_level,
)
from modules.console_ui import (
    format_filesize,
    print_blank,
    print_error,
    print_header,
    print_info,
    print_subheader,
    print_success,
    print_warning,
    prompt_yes_no,
    pick_folder,
    prompt_menu,
    prompt_path_input,
)
from modules.filename_parser import (
    FullMatch,
    NoMatch,
    ParseResult,
    ParsedFilename,
    PartialMatch,
    is_valid_screen_prefix,
    parse_filename,
)
from modules.ffprobe_wrapper import MediaSpecs, codec_tag_to_identifier, probe_file
from modules.media_formats import (
    is_recognized_still_extension,
    is_still_media_kind,
    normalize_extension,
    partition_image_sequences,
    strip_sequence_frame_suffix,
)
from modules.setup import StaleFolder, detect_stale_folders, ensure_media_structure

from colorama import Fore, Style


# ---------------------------------------------------------------------------
# Enums + data classes
# ---------------------------------------------------------------------------

# Flat intake lands validated files here until the operator assigns them in Pixera.
FLAT_INTAKE_FOLDER = "_INCOMING"


class Action(Enum):
    """Planned action for a single source file during intake."""
    COPY              = auto()
    COPY_WITH_WARNING = auto()
    ROUTE_TO_REVIEW   = auto()
    SKIP_IDENTICAL    = auto()


@dataclass
class ConflictInfo:
    """Details about existing versions of the same slug already in the destination folder."""
    existing_versions: list[ParsedFilename]
    incoming_version:  int


@dataclass
class FilePlan:
    """Proposed action and routing for a single source file."""
    source_path:      Path
    parsed:           ParseResult
    specs:            MediaSpecs | None   # None for NoMatch (ffprobe not run)
    target_screen:    str | None          # SCR## for single-screen files, else None
    destination_path: Path
    action:           Action
    warnings:         list[str] = field(default_factory=list)
    failures:         list[str] = field(default_factory=list)
    infos:            list[str] = field(default_factory=list)
    version_conflict: ConflictInfo | None = None
    sequence_paths:   list[Path] = field(default_factory=list)
    media_kind:       str = "video"


@dataclass
class ExecutionResult:
    """Tally of outcomes after executing an intake plan."""
    copied:           list[Path] = field(default_factory=list)
    skipped:          list[Path] = field(default_factory=list)
    routed_to_review: list[Path] = field(default_factory=list)
    copy_failures:    list[tuple[Path, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 7A: Source discovery
# ---------------------------------------------------------------------------

def walk_source(source: Path) -> list[Path]:
    """Recursively find all non-hidden files under source."""
    files: list[Path] = []
    for path in source.rglob("*"):
        if path.is_file() and not any(part.startswith(".") for part in path.parts):
            files.append(path)
    return sorted(files)


def _source_paths_for_plan(plan: FilePlan) -> list[Path]:
    if plan.sequence_paths:
        return list(plan.sequence_paths)
    return [plan.source_path]


def _path_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _plan_total_bytes(plan: FilePlan) -> int:
    return sum(_path_size(path) for path in _source_paths_for_plan(plan))


def _validate_delivery_extension(
    source_path: Path,
    config: ShowConfig,
    warnings: list[str],
    failures: list[str],
    *,
    flat_mode: bool = False,
) -> None:
    ext = source_path.suffix
    if config.expected_media.is_allowed_extension(ext):
        return
    normalized = normalize_extension(ext)
    if is_recognized_still_extension(normalized) and not config.expected_media.accept_stills:
        message = (
            "Still images are not enabled — turn on "
            "'Accept still images' in Expected Specs"
        )
    elif is_recognized_still_extension(normalized):
        message = (
            f"Still image extension '{ext}' is not in the accepted formats list "
            f"(Expected Specs → Still images)"
        )
    elif config.expected_media.is_video_extension(ext):
        message = f"Video extension '{ext}' is not in the accepted delivery formats"
    else:
        message = f"Extension '{ext}' is not an accepted delivery format"
    _apply_validation_level(
        strictness_level(config, "codec"),
        message,
        warnings,
        failures,
        flat_mode=flat_mode,
    )


def _validate_still_image_specs(
    specs: MediaSpecs,
    config: ShowConfig,
    warnings: list[str],
    failures: list[str],
    *,
    parsed: ParsedFilename | None = None,
    target_screen_id: str | None = None,
    flat_mode: bool = False,
) -> None:
    """Validate resolution only for still images and image sequences."""
    strictness = config.validation_strictness

    def _apply(level: str, message: str) -> None:
        if level == "ignore":
            return
        if flat_mode:
            if level in ("strict", "warn", "info"):
                warnings.append(message)
            return
        if level == "strict":
            failures.append(message)
        else:
            warnings.append(message)

    if target_screen_id is not None:
        screen_cfg = find_screen(config, target_screen_id)
        if screen_cfg is None:
            _apply(strictness["screen_id"], f"Screen '{target_screen_id}' is not in config")
        elif screen_cfg.resolution and specs.width and specs.height:
            expected_w, expected_h = (int(x) for x in screen_cfg.resolution.split("x"))
            if specs.width != expected_w or specs.height != expected_h:
                _apply(
                    strictness["resolution"],
                    f"Resolution is {specs.width}x{specs.height}, "
                    f"{target_screen_id} expects {screen_cfg.resolution}",
                )
    elif parsed is not None and parsed.screen_prefix:
        prefix = parsed.screen_prefix
        if re.match(r"^SCR\d{2}$", prefix):
            screen_cfg = find_screen(config, prefix)
            if screen_cfg is None:
                _apply(strictness["screen_id"], f"Screen '{prefix}' is not in config")
            elif screen_cfg.resolution and specs.width and specs.height:
                expected_w, expected_h = (int(x) for x in screen_cfg.resolution.split("x"))
                if specs.width != expected_w or specs.height != expected_h:
                    _apply(
                        strictness["resolution"],
                        f"Resolution is {specs.width}x{specs.height}, expected {screen_cfg.resolution}",
                    )
        elif prefix == "SCRall" and specs.width and specs.height:
            match = any(
                s.resolution
                and int(s.resolution.split("x")[0]) == specs.width
                and int(s.resolution.split("x")[1]) == specs.height
                for s in config.screens
                if s.resolution
            )
            if not match:
                _apply(
                    strictness["resolution"],
                    f"Resolution {specs.width}x{specs.height} does not match any configured screen",
                )
    elif flat_mode and specs.width and specs.height:
        if not _screens_matching_resolution(specs, config):
            _apply(
                strictness["resolution"],
                f"Resolution {specs.width}x{specs.height} does not match any configured screen",
            )


# ---------------------------------------------------------------------------
# 7B: Per-file planning
# ---------------------------------------------------------------------------

def plan_file(
    source_path: Path,
    config: ShowConfig,
    show_root: Path,
    *,
    parse_filename_as: str | None = None,
) -> FilePlan:
    """Determine the action and destination for a single source file."""
    filename = source_path.name
    parse_name = parse_filename_as or filename
    parsed = parse_filename(parse_name, config)
    review_path = show_root / "Media" / "_REVIEW" / filename
    warnings: list[str] = []
    failures: list[str] = []

    _validate_delivery_extension(source_path, config, warnings, failures)
    validate_filename(parsed, config, warnings, failures)

    if isinstance(parsed, NoMatch):
        specs = probe_file(source_path, config)
        if specs.probe_succeeded:
            validate_file_specs(specs, config, warnings, failures)
        else:
            failures.append(f"Could not read file metadata: {specs.probe_error}")
        plan = FilePlan(
            source_path=source_path,
            parsed=parsed,
            specs=specs if specs.probe_succeeded else None,
            target_screen=None,
            destination_path=review_path,
            action=Action.ROUTE_TO_REVIEW,
            failures=failures,
            warnings=warnings,
        )
        return _apply_existing_file_check(plan, source_path, show_root)

    if isinstance(parsed, PartialMatch):
        screen_prefix = parsed.screen_prefix
    else:
        screen_prefix = parsed.parsed.screen_prefix

    screen_routable = is_valid_screen_prefix(screen_prefix, config)
    screen_cfg = find_screen(config, screen_prefix)
    dest_path = (
        _dest_folder(screen_prefix, show_root) / filename
        if screen_routable
        else review_path
    )
    target_screen = screen_prefix if screen_cfg else None

    if isinstance(parsed, PartialMatch):
        specs = probe_file(source_path, config)
        if not specs.probe_succeeded:
            failures.append(f"Could not read file metadata: {specs.probe_error}")
            return FilePlan(
                source_path=source_path,
                parsed=parsed,
                specs=specs,
                target_screen=None,
                destination_path=review_path,
                action=Action.ROUTE_TO_REVIEW,
                failures=failures,
                warnings=warnings,
            )
        validate_file_specs(
            specs,
            config,
            warnings,
            failures,
            target_screen_id=screen_prefix if screen_cfg else None,
        )
        action = _filename_action(failures, warnings, screen_routable)
        if failures or not screen_routable:
            dest_path = review_path
        plan = FilePlan(
            source_path=source_path,
            parsed=parsed,
            specs=specs,
            target_screen=target_screen if screen_routable else None,
            destination_path=dest_path,
            action=action,
            warnings=warnings,
            failures=failures,
        )
        return _apply_existing_file_check(plan, source_path, show_root)

    specs = probe_file(source_path, config)
    if not specs.probe_succeeded:
        return FilePlan(
            source_path=source_path,
            parsed=parsed,
            specs=specs,
            target_screen=target_screen,
            destination_path=review_path,
            action=Action.ROUTE_TO_REVIEW,
            failures=[f"Could not read file metadata: {specs.probe_error}"],
            warnings=warnings,
        )

    validate_file_specs(
        specs,
        config,
        warnings,
        failures,
        parsed=parsed.parsed,
    )

    if failures:
        action = Action.ROUTE_TO_REVIEW
        dest_path = review_path
    elif warnings:
        action = Action.COPY_WITH_WARNING
    else:
        action = Action.COPY

    plan = FilePlan(
        source_path=source_path,
        parsed=parsed,
        specs=specs,
        target_screen=target_screen,
        destination_path=dest_path,
        action=action,
        warnings=warnings,
        failures=failures,
    )
    return _apply_existing_file_check(plan, source_path, show_root)


def plan_file_flat(
    source_path: Path,
    config: ShowConfig,
    show_root: Path,
    *,
    parse_filename_as: str | None = None,
) -> FilePlan:
    """Plan a file for flat intake: union spec validation; copy to Media/_INCOMING."""
    filename = source_path.name
    parse_name = parse_filename_as or filename
    parsed = parse_filename(parse_name, config)
    incoming_folder = _flat_dest_folder(show_root)
    dest_path = incoming_folder / filename
    review_path = show_root / "Media" / "_REVIEW" / filename
    warnings: list[str] = []
    failures: list[str] = []

    if not config.screens:
        return FilePlan(
            source_path=source_path,
            parsed=parsed,
            specs=None,
            target_screen=None,
            destination_path=review_path,
            action=Action.ROUTE_TO_REVIEW,
            failures=["Flat intake requires at least one screen in config"],
        )

    _validate_delivery_extension(
        source_path, config, warnings, failures, flat_mode=True,
    )
    validate_filename(parsed, config, warnings, failures, flat_mode=True)

    specs = probe_file(source_path, config)
    if not specs.probe_succeeded:
        failures.append(f"Could not read file metadata: {specs.probe_error}")
        return FilePlan(
            source_path=source_path,
            parsed=parsed,
            specs=specs,
            target_screen=None,
            destination_path=review_path,
            action=Action.ROUTE_TO_REVIEW,
            failures=failures,
        )

    validate_file_specs_flat(specs, config, warnings, failures)

    if failures:
        action = Action.ROUTE_TO_REVIEW
        dest_path = review_path
    elif warnings:
        action = Action.COPY_WITH_WARNING
    else:
        action = Action.COPY

    plan = FilePlan(
        source_path=source_path,
        parsed=parsed,
        specs=specs,
        target_screen=None,
        destination_path=dest_path,
        action=action,
        warnings=warnings,
        failures=failures,
    )
    return _apply_existing_file_check(plan, source_path, show_root)


def plan_image_sequence(
    sequence_paths: list[Path],
    config: ShowConfig,
    show_root: Path,
    *,
    flat: bool,
) -> FilePlan:
    """Plan a numbered image sequence as one logical asset (validate once, copy all frames)."""
    representative = sequence_paths[0]
    logical_name = strip_sequence_frame_suffix(representative.name)
    if flat:
        plan = plan_file_flat(
            representative,
            config,
            show_root,
            parse_filename_as=logical_name,
        )
    else:
        plan = plan_file(
            representative,
            config,
            show_root,
            parse_filename_as=logical_name,
        )
    plan.sequence_paths = list(sequence_paths)
    plan.media_kind = "image_sequence"
    if plan.specs is not None:
        plan.specs.media_kind = "image_sequence"
    plan.infos.insert(0, f"Image sequence: {len(sequence_paths)} frames")
    return plan


ProgressCallback = Callable[[int, int, str], None]


def build_intake_plan(
    source: Path,
    config: ShowConfig,
    show_root: Path,
    *,
    progress: ProgressCallback | None = None,
) -> tuple[list[FilePlan], list[StaleFolder]]:
    """Walk source, plan each file, detect conflicts and stale folders.

    progress(current, total, filename) is called after each file is planned.
    """
    if is_flat_intake(config) and not config.screens:
        raise ValueError("Flat intake requires at least one screen in config")

    ensure_media_structure(show_root, config)
    files = walk_source(source)
    sequences, singletons = partition_image_sequences(files, config)
    flat = is_flat_intake(config)
    plans: list[FilePlan] = []
    logical_total = len(sequences) + len(singletons)
    index = 0
    for sequence_paths in sequences:
        index += 1
        plans.append(plan_image_sequence(sequence_paths, config, show_root, flat=flat))
        if progress is not None:
            progress(index, logical_total, sequence_paths[0].name)
    for file_path in singletons:
        index += 1
        if flat:
            plans.append(plan_file_flat(file_path, config, show_root))
        else:
            plans.append(plan_file(file_path, config, show_root))
        if progress is not None:
            progress(index, logical_total, file_path.name)
    if not flat:
        plans = detect_version_conflicts(plans, show_root, config)
    stale = detect_stale_folders(show_root, config)
    return plans, stale


def detect_version_conflicts(
    plans: list[FilePlan],
    show_root: Path,
    config: ShowConfig,
) -> list[FilePlan]:
    """Populate version_conflict on plans where an older version already exists."""
    if config.filename_convention.enabled and "version" not in config.filename_convention.tokens:
        return plans

    for plan in plans:
        if plan.action not in (Action.COPY, Action.COPY_WITH_WARNING):
            continue
        if not isinstance(plan.parsed, FullMatch):
            continue

        incoming = plan.parsed.parsed
        dest_folder = plan.destination_path.parent
        if not dest_folder.exists():
            continue

        existing: list[ParsedFilename] = []
        for existing_file in dest_folder.iterdir():
            if not existing_file.is_file():
                continue
            result = parse_filename(existing_file.name, config)
            if not isinstance(result, FullMatch):
                continue
            ep = result.parsed
            if ep.screen_prefix == incoming.screen_prefix and ep.slug == incoming.slug:
                if ep.version != incoming.version:
                    existing.append(ep)

        if existing:
            plan.version_conflict = ConflictInfo(
                existing_versions=existing,
                incoming_version=incoming.version,
            )

    return plans


# ---------------------------------------------------------------------------
# 7C: Plan display
# ---------------------------------------------------------------------------

def display_plan(
    plans: list[FilePlan],
    stale_folders: list[StaleFolder],
    config: ShowConfig,
    source: Path,
) -> None:
    """Print the full plan report to the console (DESIGN.md §8.7)."""
    show_label = f"{config.show_name} ({config.show_date})"
    total_files = len(plans)

    print_header("INTAKE DELIVERY — PLAN PHASE")
    print(f"  Show:    {show_label}")
    print(f"  Source:  {source}")
    print(f"  Files:   {total_files} file{'s' if total_files != 1 else ''} found in source")
    print_blank()

    print_subheader("PROPOSED ACTIONS")
    print_blank()

    for plan in plans:
        _print_file_plan_line(plan)

    print_blank()

    # --- Warnings section (stale folders + version conflicts) ---
    conflicts = [p for p in plans if p.version_conflict]
    if stale_folders or conflicts:
        print_subheader("WARNINGS")
        print_blank()

        for sf in stale_folders:
            print_warning(f"Stale folder: Media\\{sf.name}\\ ({sf.file_count} file{'s' if sf.file_count != 1 else ''})")
            print(f"      Not listed in config. Verify if needed.")

        if conflicts:
            print(f"  {Style.BRIGHT}Version conflicts:{Style.RESET_ALL}")
            for plan in conflicts:
                assert isinstance(plan.parsed, FullMatch)
                ci = plan.version_conflict
                assert ci is not None
                prefix = plan.parsed.parsed.screen_prefix
                slug   = plan.parsed.parsed.slug
                active_versions = ", ".join(f"v{p.version:02d}" for p in ci.existing_versions)
                print(f"      {prefix}_{slug}: {active_versions} (active) and v{ci.incoming_version:02d} (incoming)")

        print_blank()

    # --- Summary ---
    copy_plans  = [p for p in plans if p.action in (Action.COPY, Action.COPY_WITH_WARNING)]
    review_plans = [p for p in plans if p.action == Action.ROUTE_TO_REVIEW]
    skip_plans  = [p for p in plans if p.action == Action.SKIP_IDENTICAL]
    total_bytes = sum(p.source_path.stat().st_size for p in copy_plans)

    print_subheader("SUMMARY")
    print_blank()
    print(f"    {len(copy_plans)} file{'s' if len(copy_plans) != 1 else ''} to copy ({format_filesize(total_bytes)})")
    print(f"    {len(review_plans)} file{'s' if len(review_plans) != 1 else ''} to route to _REVIEW")
    print(f"    {len(skip_plans)} file{'s' if len(skip_plans) != 1 else ''} to skip (already present)")
    if conflicts:
        print(f"    {len(conflicts)} version conflict{'s' if len(conflicts) != 1 else ''} detected")
    if stale_folders:
        print(f"    {len(stale_folders)} stale folder{'s' if len(stale_folders) != 1 else ''} detected")
    print_blank()


def prompt_proceed() -> bool:
    """Ask the operator whether to execute the plan."""
    return prompt_yes_no("Proceed with copy?", default="N")


# ---------------------------------------------------------------------------
# 7D: Execution
# ---------------------------------------------------------------------------

CopyByteProgressCallback = Callable[[int, int], None]

_COPY_PROGRESS_INTERVAL_SEC = 0.12
_COPY_CHUNK_SIZE = 8 * 1024 * 1024


def atomic_copy(
    source: Path,
    destination: Path,
    *,
    progress: CopyByteProgressCallback | None = None,
) -> bool:
    """Copy source → destination atomically via a .tmp intermediate.

    progress(bytes_copied, bytes_total) is called during the transfer (throttled).
    Returns True on success, False on failure (temp file cleaned up on failure).
    """
    tmp_path = destination.parent / (destination.name + ".tmp")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        total_bytes = _path_size(source)
        copied_bytes = 0
        last_report = 0.0

        def _report(force: bool = False) -> None:
            if progress is None:
                return
            nonlocal last_report
            now = time.monotonic()
            if not force and copied_bytes < total_bytes:
                if now - last_report < _COPY_PROGRESS_INTERVAL_SEC:
                    return
            last_report = now
            progress(copied_bytes, total_bytes)

        with source.open("rb") as src_file, tmp_path.open("wb") as dst_file:
            while True:
                chunk = src_file.read(_COPY_CHUNK_SIZE)
                if not chunk:
                    break
                dst_file.write(chunk)
                copied_bytes += len(chunk)
                _report()

        _report(force=True)
        shutil.copystat(source, tmp_path)
        tmp_path.replace(destination)
        return True
    except Exception as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        print_error(f"Copy failed: {exc}")
        return False


@dataclass
class CopyProgressEvent:
    files_done: int
    files_total: int
    filename: str
    status: str  # copying | done | failed | skipped
    bytes_copied: int = 0
    bytes_total: int = 0
    job_bytes_copied: int = 0
    job_bytes_total: int = 0


ExecuteProgressCallback = Callable[[CopyProgressEvent], None]


def execute_plan(
    plans: list[FilePlan],
    show_root: Path,
    *,
    progress: ExecuteProgressCallback | None = None,
) -> ExecutionResult:
    """Execute the file plan: copy, skip, or route to review. Returns a summary.

    progress(current, total, filename, status) is called after each actionable file,
    where status is ``done``, ``failed``, or ``skipped``. During each file copy,
    status ``copying`` events include byte counts for the file and overall job.
    """
    result = ExecutionResult()

    # Clean up any leftover .tmp files from a previous interrupted run
    media_dir = show_root / "Media"
    if media_dir.exists():
        for tmp_file in media_dir.rglob("*.tmp"):
            try:
                tmp_file.unlink()
            except OSError:
                pass

    actionable = [p for p in plans if p.action != Action.SKIP_IDENTICAL]
    file_total = sum(len(_source_paths_for_plan(p)) for p in actionable)
    job_bytes_total = sum(
        _path_size(path)
        for plan in actionable
        for path in _source_paths_for_plan(plan)
    )
    files_done = 0
    job_bytes_copied = 0

    def _emit(event: CopyProgressEvent) -> None:
        if progress is not None:
            progress(event)

    for plan in plans:
        if plan.action == Action.SKIP_IDENTICAL:
            for src in _source_paths_for_plan(plan):
                result.skipped.append(plan.destination_path.parent / src.name)
            _emit(
                CopyProgressEvent(
                    files_done=files_done,
                    files_total=file_total,
                    filename=plan.source_path.name,
                    status="skipped",
                    job_bytes_copied=job_bytes_copied,
                    job_bytes_total=job_bytes_total,
                )
            )
            continue

        sources = _source_paths_for_plan(plan)
        label = plan.source_path.name
        if len(sources) > 1:
            label = f"{label} ({len(sources)} frames)"
        size_str = format_filesize(_plan_total_bytes(plan))
        print(f"  Copying {label} ({size_str})...", end=" ", flush=True)

        copy_ok = True
        for src in sources:
            file_bytes = _path_size(src)

            def _on_bytes(copied: int, total: int) -> None:
                _emit(
                    CopyProgressEvent(
                        files_done=files_done,
                        files_total=file_total,
                        filename=src.name,
                        status="copying",
                        bytes_copied=copied,
                        bytes_total=total,
                        job_bytes_copied=job_bytes_copied + copied,
                        job_bytes_total=job_bytes_total,
                    )
                )

            dest = plan.destination_path.parent / src.name
            if not atomic_copy(src, dest, progress=_on_bytes):
                copy_ok = False
                result.copy_failures.append((src, "copy error"))
                _emit(
                    CopyProgressEvent(
                        files_done=files_done,
                        files_total=file_total,
                        filename=src.name,
                        status="failed",
                        bytes_copied=0,
                        bytes_total=file_bytes,
                        job_bytes_copied=job_bytes_copied,
                        job_bytes_total=job_bytes_total,
                    )
                )
                break

            files_done += 1
            job_bytes_copied += file_bytes
            _emit(
                CopyProgressEvent(
                    files_done=files_done,
                    files_total=file_total,
                    filename=src.name,
                    status="done",
                    bytes_copied=file_bytes,
                    bytes_total=file_bytes,
                    job_bytes_copied=job_bytes_copied,
                    job_bytes_total=job_bytes_total,
                )
            )

        if copy_ok:
            print(f"{Fore.GREEN}done{Style.RESET_ALL}")
            for src in sources:
                dest = plan.destination_path.parent / src.name
                if plan.action == Action.ROUTE_TO_REVIEW:
                    result.routed_to_review.append(dest)
                else:
                    result.copied.append(dest)
        else:
            print(f"{Fore.RED}FAILED{Style.RESET_ALL}")

    return result


# ---------------------------------------------------------------------------
# 7E: Logging
# ---------------------------------------------------------------------------

def append_to_delivery_log(
    show_root: Path,
    source: Path,
    result: ExecutionResult,
    conflicts_count: int,
    intake_log_path: Path | None = None,
) -> None:
    """Append a one-line summary to Media/_LOGS/DeliveryLog.txt."""
    log_path = show_root / "Media" / "_LOGS" / "DeliveryLog.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    notes_parts = []
    if conflicts_count:
        notes_parts.append(f"{conflicts_count} version conflict{'s' if conflicts_count != 1 else ''}")
    if result.copy_failures:
        notes_parts.append(f"{len(result.copy_failures)} copy failure{'s' if len(result.copy_failures) != 1 else ''}")

    stats = (
        f"{len(result.copied)} copied, "
        f"{len(result.routed_to_review)} review, "
        f"{len(result.skipped)} skip"
    )
    segments = [ts, str(source), stats]
    if intake_log_path is not None:
        segments.append(str(intake_log_path))
    if notes_parts:
        segments.append(f"Notes: {', '.join(notes_parts)}")

    line = " | ".join(segments) + "\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


def write_intake_log(
    show_root: Path,
    plans: list[FilePlan],
    stale_folders: list[StaleFolder],
    result: ExecutionResult,
    source: Path,
    config: ShowConfig,
    proceeded: bool,
) -> Path:
    """Write a full intake transcript to Media/_LOGS/intake_YYYYMMDD_HHMMSS.txt."""
    ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = show_root / "Media" / "_LOGS" / f"intake_{ts_file}.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    ts_human = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    intake_label = "flat" if is_flat_intake(config) else "routed"
    lines += [
        "=" * 70,
        f"  SHOW MEDIA INTAKE LOG",
        f"  Generated: {ts_human}",
        f"  Show:      {config.show_name} ({config.show_date})",
        f"  Intake:    {intake_label}"
        + (f" → Media\\{FLAT_INTAKE_FOLDER}\\" if is_flat_intake(config) else ""),
        f"  Source:    {source}",
        f"  Files:     {len(plans)} found",
        "=" * 70,
        "",
        "PROPOSED ACTIONS",
        "-" * 70,
    ]

    for plan in plans:
        action_label = {
            Action.COPY:              "COPY",
            Action.COPY_WITH_WARNING: "COPY (warnings)",
            Action.ROUTE_TO_REVIEW:   "REVIEW",
            Action.SKIP_IDENTICAL:    "SKIP",
        }[plan.action]
        size_str = format_filesize(_plan_total_bytes(plan))
        rel_dest = plan.destination_path.relative_to(show_root / "Media")
        lines.append(f"  [{action_label:16s}] {plan.source_path.name:50s} ({size_str:>8s})  ->  Media\\{rel_dest.parent.name}\\")
        for info in plan.infos:
            lines.append(f"                       INFO: {info}")
        for w in plan.warnings:
            lines.append(f"                       WARN: {w}")
        for f_ in plan.failures:
            lines.append(f"                       FAIL: {f_}")
        if plan.version_conflict:
            ci = plan.version_conflict
            active = ", ".join(f"v{p.version:02d}" for p in ci.existing_versions)
            lines.append(f"                       VERSION CONFLICT: {active} active, v{ci.incoming_version:02d} incoming")

    lines += ["", "OPERATOR DECISION", "-" * 70]
    lines.append(f"  Proceed: {'YES' if proceeded else 'NO (aborted)'}")
    lines.append("")

    if proceeded:
        lines += ["EXECUTION RESULTS", "-" * 70]
        for p in result.copied:
            lines.append(f"  OK      {p.name}")
        for p in result.routed_to_review:
            lines.append(f"  REVIEW  {p.name}")
        for p in result.skipped:
            lines.append(f"  SKIP    {p.name}")
        for src, reason in result.copy_failures:
            lines.append(f"  FAILED  {src.name}  ({reason})")
        lines.append("")

    lines += [
        "SUMMARY",
        "-" * 70,
        f"  {len(result.copied)} copied",
        f"  {len(result.routed_to_review)} routed to _REVIEW",
        f"  {len(result.skipped)} skipped (identical)",
        f"  {len(result.copy_failures)} copy failure(s)",
    ]
    if stale_folders:
        lines.append(f"  {len(stale_folders)} stale folder(s) detected")

    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


# ---------------------------------------------------------------------------
# 7F: Mode entry point
# ---------------------------------------------------------------------------

def run_intake(show_root: Path, config: ShowConfig) -> None:
    """Full intake workflow: pick source, plan, confirm, execute, log."""
    print_blank()
    if is_flat_intake(config) and not config.screens:
        print_error("Flat intake requires at least one screen in config.")
        return

    print("  Select the source folder containing the delivery.")
    source = pick_folder("Select delivery source folder")
    if source is None:
        print_blank()
        print_warning("No folder selected. Intake cancelled.")
        return
    if not source.exists() or not source.is_dir():
        print_error(f"Source folder not found: {source}")
        return

    print_blank()
    print(f"  Scanning {source} ...")

    try:
        plans, stale = build_intake_plan(
            source,
            config,
            show_root,
        )
    except ValueError as exc:
        print_error(str(exc))
        return

    if not plans:
        print_warning("No files found in source folder.")
        return

    print_blank()
    display_plan(plans, stale, config, source)

    proceeded = prompt_proceed()
    print_blank()

    conflicts_count = sum(1 for p in plans if p.version_conflict)

    if not proceeded:
        write_intake_log(show_root, plans, stale, ExecutionResult(), source, config, proceeded=False)
        print_info("Intake aborted. No files were copied.")
        return

    result = execute_plan(plans, show_root)
    print_blank()

    log_path = write_intake_log(show_root, plans, stale, result, source, config, proceeded=True)
    append_to_delivery_log(show_root, source, result, conflicts_count, log_path)

    # Summary
    print_subheader("INTAKE COMPLETE")
    print_blank()
    if result.copied:
        print_success(f"{len(result.copied)} file{'s' if len(result.copied) != 1 else ''} copied")
    if result.routed_to_review:
        print_warning(f"{len(result.routed_to_review)} file{'s' if len(result.routed_to_review) != 1 else ''} routed to _REVIEW")
    if result.skipped:
        print_info(f"{len(result.skipped)} file{'s' if len(result.skipped) != 1 else ''} skipped (already present)")
    if result.copy_failures:
        print_error(f"{len(result.copy_failures)} copy failure{'s' if len(result.copy_failures) != 1 else ''}")
    print_info(f"Log written: {log_path}")
    print_blank()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dest_folder(screen_prefix: str, show_root: Path) -> Path:
    return show_root / "Media" / screen_prefix


def _flat_dest_folder(show_root: Path) -> Path:
    return show_root / "Media" / FLAT_INTAKE_FOLDER


def _unique_review_path(dest: Path) -> Path:
    """Return dest unchanged if it doesn't exist, else append _2/_3/... until clear."""
    if not dest.exists():
        return dest
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _apply_existing_file_check(plan: FilePlan, source_path: Path, show_root: Path) -> FilePlan:
    """Prevent overwrites: skip identical screen-folder files; rename _REVIEW duplicates."""
    if plan.specs and not plan.sequence_paths:
        plan.media_kind = plan.specs.media_kind

    dest = plan.destination_path
    review_dir = show_root / "Media" / "_REVIEW"

    # Files going to _REVIEW: skip if identical, rename if same name but different size
    if dest.parent == review_dir:
        if not dest.exists():
            return plan
        src_size  = source_path.stat().st_size
        dest_size = dest.stat().st_size
        if src_size == dest_size:
            plan.action = Action.SKIP_IDENTICAL
        else:
            plan.destination_path = _unique_review_path(dest)
            plan.warnings.append(f"Renamed to avoid overwrite: {plan.destination_path.name}")
        return plan

    # Files going to screen folders: skip identical, re-route conflicts to _REVIEW
    if not dest.exists():
        return plan

    src_size  = source_path.stat().st_size
    dest_size = dest.stat().st_size

    if src_size == dest_size:
        plan.action = Action.SKIP_IDENTICAL
    else:
        plan.action = Action.ROUTE_TO_REVIEW
        plan.destination_path = _unique_review_path(review_dir / source_path.name)
        plan.failures.append("Name conflict: file already exists with different size")

    return plan


def _apply_validation_level(
    level: str,
    message: str,
    warnings: list[str],
    failures: list[str],
    *,
    flat_mode: bool = False,
) -> None:
    """Apply a strictness level to warnings/failures lists."""
    if level == "ignore":
        return
    if flat_mode:
        if level in ("strict", "warn", "info"):
            warnings.append(message)
        return
    if level == "strict":
        failures.append(message)
    else:
        warnings.append(message)


def _is_show_token_problem(message: str) -> bool:
    lower = message.lower()
    return "show token" in lower


def _is_screen_problem(message: str) -> bool:
    lower = message.lower()
    return (
        "not a valid screen" in lower
        or "not a valid prefix" in lower
        or "no recognisable screen" in lower
        or "unrecognised scr prefix" in lower
    )


def validate_filename(
    parsed: ParseResult,
    config: ShowConfig,
    warnings: list[str],
    failures: list[str],
    *,
    flat_mode: bool = False,
) -> None:
    """Apply filename strictness rules. Modifies warnings/failures in place."""
    if isinstance(parsed, NoMatch):
        level = strictness_level(config, "filename_convention")
        _apply_validation_level(
            level,
            "Filename does not match convention",
            warnings,
            failures,
            flat_mode=flat_mode,
        )
        for problem in parsed.problems:
            _apply_validation_level(
                level,
                problem,
                warnings,
                failures,
                flat_mode=flat_mode,
            )
        return

    if isinstance(parsed, PartialMatch):
        screen_prefix = parsed.screen_prefix
        screen_valid = is_valid_screen_prefix(screen_prefix, config)
        for problem in parsed.problems:
            if _is_show_token_problem(problem):
                level = strictness_level(config, "show_token")
            elif _is_screen_problem(problem) or not screen_valid:
                level = strictness_level(config, "screen_id")
            else:
                level = strictness_level(config, "filename_format")
            _apply_validation_level(
                level,
                problem,
                warnings,
                failures,
                flat_mode=flat_mode,
            )
        if not screen_valid and not any(_is_screen_problem(p) for p in parsed.problems):
            _apply_validation_level(
                strictness_level(config, "screen_id"),
                f"'{screen_prefix}' is not a valid screen token for this show",
                warnings,
                failures,
                flat_mode=flat_mode,
            )
        return

    if isinstance(parsed, FullMatch):
        screen_prefix = parsed.parsed.screen_prefix
        if re.match(r"^SCR\d{2}$", screen_prefix) and find_screen(config, screen_prefix) is None:
            _apply_validation_level(
                strictness_level(config, "screen_id"),
                f"Screen '{screen_prefix}' is not in config",
                warnings,
                failures,
                flat_mode=flat_mode,
            )


def _filename_action(
    failures: list[str],
    warnings: list[str],
    screen_routable: bool,
) -> Action:
    """Choose copy action for a partial filename match with routable screen."""
    if failures or not screen_routable:
        return Action.ROUTE_TO_REVIEW
    if warnings:
        return Action.COPY_WITH_WARNING
    return Action.COPY


def _screens_matching_resolution(
    specs: MediaSpecs,
    config: ShowConfig,
) -> list[str]:
    """Return screen ids whose configured resolution matches the probed file dimensions."""
    if not specs.width or not specs.height:
        return []
    matches: list[str] = []
    for screen in config.screens:
        if not screen.resolution:
            continue
        try:
            expected_w, expected_h = (int(x) for x in screen.resolution.split("x"))
        except ValueError:
            continue
        if specs.width == expected_w and specs.height == expected_h:
            matches.append(screen.id)
    return matches


def validate_file_specs_flat(
    specs: MediaSpecs,
    config: ShowConfig,
    warnings: list[str],
    failures: list[str],
) -> None:
    """Validate specs against the union of all configured screen profiles."""
    if is_still_media_kind(specs.media_kind):
        _validate_still_image_specs(
            specs, config, warnings, failures, flat_mode=True,
        )
        return

    strictness = config.validation_strictness

    def _apply(level: str, message: str) -> None:
        if level == "ignore":
            return
        if level == "strict":
            failures.append(message)
        else:
            warnings.append(message)

    if not config.screens:
        _apply(strictness["screen_id"], "No screens configured")
        return

    if specs.width and specs.height:
        if not _screens_matching_resolution(specs, config):
            _apply(
                strictness["resolution"],
                f"Resolution {specs.width}x{specs.height} does not match any configured screen",
            )

    screen_specs = [
        (screen, effective_specs_for_screen(screen, config))
        for screen in config.screens
    ]

    if specs.framerate is not None:
        valid_rates = [
            eff.framerate for _, eff in screen_specs if eff.framerate is not None
        ]
        if valid_rates and not any(
            abs(specs.framerate - rate) <= 0.01 for rate in valid_rates
        ):
            rates_label = ", ".join(f"{rate:g}" for rate in sorted(set(valid_rates)))
            _apply(
                strictness["framerate"],
                f"Framerate is {specs.framerate:.3f}; configured screens expect "
                f"one of ({rates_label})",
            )

    if specs.color_space:
        valid_spaces = [
            eff.color_space for _, eff in screen_specs if eff.color_space is not None
        ]
        if valid_spaces and specs.color_space not in valid_spaces:
            spaces_label = ", ".join(sorted(set(valid_spaces)))
            _apply(
                strictness["color_space"],
                f"Color space is '{specs.color_space}'; configured screens allow "
                f"one of ({spaces_label})",
            )

    if specs.color_range:
        valid_ranges = [
            eff.color_range for _, eff in screen_specs if eff.color_range is not None
        ]
        if valid_ranges and specs.color_range not in valid_ranges:
            ranges_label = ", ".join(sorted(set(valid_ranges)))
            _apply(
                strictness["color_range"],
                f"Color range is '{specs.color_range}'; configured screens allow "
                f"one of ({ranges_label})",
            )

    if specs.audio_sample_rate is not None:
        valid_rates = [
            eff.audio_sample_rate
            for _, eff in screen_specs
            if eff.audio_sample_rate is not None
        ]
        if valid_rates and specs.audio_sample_rate not in valid_rates:
            rates_label = ", ".join(str(rate) for rate in sorted(set(valid_rates)))
            _apply(
                strictness["audio_sample_rate"],
                f"Audio sample rate is {specs.audio_sample_rate} Hz; configured screens "
                f"expect one of ({rates_label}) Hz",
            )

    if specs.audio_channels is not None:
        valid_channels = [
            eff.audio_channels
            for _, eff in screen_specs
            if eff.audio_channels is not None
        ]
        if valid_channels and specs.audio_channels not in valid_channels:
            channels_label = ", ".join(str(ch) for ch in sorted(set(valid_channels)))
            _apply(
                strictness["audio_channels"],
                f"Audio channels: {specs.audio_channels}; configured screens expect "
                f"one of ({channels_label})",
            )

    if specs.codec_tag:
        identifier = codec_tag_to_identifier(specs.codec_tag)
        if identifier is None or identifier not in config.expected_codecs:
            codec_label = identifier or specs.codec_tag
            _apply(
                strictness["codec"],
                f"Codec '{codec_label}' is not in expected_codecs",
            )
        elif identifier not in config.preferred_codecs:
            _apply(
                strictness["codec_flavor"],
                f"Codec '{identifier}' is acceptable but not preferred",
            )
    elif specs.codec_name:
        _apply(
            strictness["codec"],
            f"Unknown codec: {specs.codec_name} (no recognised ProRes tag)",
        )


def validate_file_specs(
    specs: MediaSpecs,
    config: ShowConfig,
    warnings: list[str],
    failures: list[str],
    *,
    parsed: ParsedFilename | None = None,
    target_screen_id: str | None = None,
) -> None:
    """Fill warnings/failures based on spec comparison. Modifies lists in place."""
    if is_still_media_kind(specs.media_kind):
        _validate_still_image_specs(
            specs,
            config,
            warnings,
            failures,
            parsed=parsed,
            target_screen_id=target_screen_id,
        )
        return

    strictness = config.validation_strictness

    def _apply(level: str, message: str) -> None:
        if level == "ignore":
            return
        if level == "strict":
            failures.append(message)
        else:
            warnings.append(message)

    if target_screen_id is not None:
        screen_cfg = find_screen(config, target_screen_id)
        label = target_screen_id
        if screen_cfg is None:
            _apply(strictness["screen_id"], f"Screen '{target_screen_id}' is not in config")
            expected = config.expected_specs
        else:
            expected = effective_specs_for_screen(screen_cfg, config)
            if screen_cfg.resolution and specs.width and specs.height:
                expected_w, expected_h = (int(x) for x in screen_cfg.resolution.split("x"))
                if specs.width != expected_w or specs.height != expected_h:
                    _apply(
                        strictness["resolution"],
                        f"Resolution is {specs.width}x{specs.height}, {label} expects {screen_cfg.resolution}",
                    )
    elif parsed is not None:
        prefix = parsed.screen_prefix
        if re.match(r"^SCR\d{2}$", prefix):
            screen_cfg = find_screen(config, prefix)
            if screen_cfg is None:
                _apply(strictness["screen_id"], f"Screen '{prefix}' is not in config")
                expected = config.expected_specs
            else:
                expected = effective_specs_for_screen(screen_cfg, config)
                if screen_cfg.resolution and specs.width and specs.height:
                    expected_w, expected_h = (int(x) for x in screen_cfg.resolution.split("x"))
                    if specs.width != expected_w or specs.height != expected_h:
                        _apply(
                            strictness["resolution"],
                            f"Resolution is {specs.width}x{specs.height}, expected {screen_cfg.resolution}",
                        )
        elif prefix == "SCRall":
            expected = config.expected_specs
            if specs.width and specs.height:
                match = any(
                    s.resolution and int(s.resolution.split("x")[0]) == specs.width
                    and int(s.resolution.split("x")[1]) == specs.height
                    for s in config.screens
                    if s.resolution
                )
                if not match:
                    _apply(
                        strictness["resolution"],
                        f"Resolution {specs.width}x{specs.height} does not match any configured screen",
                    )
        else:
            expected = config.expected_specs
    else:
        expected = config.expected_specs

    # Framerate
    if specs.framerate is not None and expected.framerate is not None:
        if abs(specs.framerate - expected.framerate) > 0.01:
            label = target_screen_id or (parsed.screen_prefix if parsed else "show")
            _apply(
                strictness["framerate"],
                f"Framerate is {specs.framerate:.3f}, {label} expects {expected.framerate}",
            )

    # Codec (show-level)
    if specs.codec_tag:
        identifier = codec_tag_to_identifier(specs.codec_tag)
        if identifier is None or identifier not in config.expected_codecs:
            codec_label = identifier or specs.codec_tag
            _apply(
                strictness["codec"],
                f"Codec '{codec_label}' is not in expected_codecs",
            )
        elif identifier not in config.preferred_codecs:
            _apply(
                strictness["codec_flavor"],
                f"Codec '{identifier}' is acceptable but not preferred",
            )
    elif specs.codec_name:
        _apply(strictness["codec"], f"Unknown codec: {specs.codec_name} (no recognised ProRes tag)")

    if specs.color_space and expected.color_space is not None and specs.color_space != expected.color_space:
        _apply(
            strictness["color_space"],
            f"Color space is '{specs.color_space}', expected '{expected.color_space}'",
        )

    if specs.color_range and expected.color_range is not None and specs.color_range != expected.color_range:
        _apply(
            strictness["color_range"],
            f"Color range is '{specs.color_range}', expected '{expected.color_range}'",
        )

    if specs.audio_sample_rate is not None and expected.audio_sample_rate is not None \
            and specs.audio_sample_rate != expected.audio_sample_rate:
        _apply(
            strictness["audio_sample_rate"],
            f"Audio sample rate is {specs.audio_sample_rate} Hz, expected {expected.audio_sample_rate} Hz",
        )

    if specs.audio_channels is not None and expected.audio_channels is not None \
            and specs.audio_channels != expected.audio_channels:
        _apply(
            strictness["audio_channels"],
            f"Audio channels: {specs.audio_channels}, expected {expected.audio_channels}",
        )


def _validate_specs(
    parsed: ParsedFilename,
    specs: MediaSpecs,
    config: ShowConfig,
    warnings: list[str],
    failures: list[str],
) -> None:
    """Backward-compatible wrapper for routed intake validation."""
    validate_file_specs(specs, config, warnings, failures, parsed=parsed)


def _print_file_plan_line(plan: FilePlan) -> None:
    """Print one color-coded line for a file in the plan report."""
    filename = plan.source_path.name
    size_str = format_filesize(plan.source_path.stat().st_size)

    try:
        rel_dest = plan.destination_path.relative_to(plan.destination_path.parents[2])
        dest_label = f"Media\\{plan.destination_path.parent.name}\\"
    except (ValueError, IndexError):
        dest_label = str(plan.destination_path.parent)

    if plan.action == Action.COPY:
        prefix = f"{Fore.GREEN}  ✓ COPY    {Style.RESET_ALL}"
    elif plan.action == Action.COPY_WITH_WARNING:
        prefix = f"{Fore.YELLOW}  ⚠ COPY    {Style.RESET_ALL}"
    elif plan.action == Action.ROUTE_TO_REVIEW:
        prefix = f"{Fore.RED}  ✗ REVIEW  {Style.RESET_ALL}"
    else:  # SKIP_IDENTICAL
        prefix = f"{Fore.CYAN}{Style.DIM}  • SKIP    {Style.RESET_ALL}"

    print(f"{prefix}{filename:50s} ({size_str:>8s})  {dest_label}")

    indent = "               "
    for info in plan.infos:
        print(f"{Fore.CYAN}{indent}INFO: {info}{Style.RESET_ALL}")
    for w in plan.warnings:
        print(f"{Fore.YELLOW}{indent}WARN: {w}{Style.RESET_ALL}")
    for f_ in plan.failures:
        print(f"{Fore.RED}{indent}FAIL: {f_}{Style.RESET_ALL}")
    if plan.version_conflict:
        ci = plan.version_conflict
        active = ", ".join(f"v{p.version:02d}" for p in ci.existing_versions)
        print(f"{Style.DIM}{indent}Replaces {active} (will coexist){Style.RESET_ALL}")
