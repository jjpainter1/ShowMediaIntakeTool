"""Spec document generation from show config."""

from pathlib import Path

import docx
from docx.oxml.ns import qn

from modules.config import ShowConfig

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Maps ffprobe / config color_space strings to human-friendly spec names
_COLOR_SPACE_NAMES: dict[str, str] = {
    "bt709": "Rec.709",
    "bt2020": "Rec.2020",
    "smpte170m": "Rec.601",
    "bt470bg": "Rec.601",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_spec(show_root: Path, config: ShowConfig) -> Path:
    """Generate a delivery spec docx from config and save it in show_root.

    Returns the path to the generated file.
    """
    template_path = _TEMPLATES_DIR / "spec_template.docx"
    if not template_path.exists():
        raise FileNotFoundError(f"Spec template not found: {template_path}")

    doc = docx.Document(str(template_path))

    color_space_label = _COLOR_SPACE_NAMES.get(
        config.expected_specs.color_space,
        config.expected_specs.color_space,
    )
    framerate_label = f"{config.expected_specs.framerate:g} fps"

    # --- Paragraph-level replacements ---
    # Standard replacements applied to every paragraph
    standard = {
        "[Project Name]":          config.show_name,
        "[##]":                    str(len(config.screens)),
        "[Operator Name]":         config.operator.name,
        "[email@prestigeav.com]":  config.operator.email,
    }

    for para in doc.paragraphs:
        # Show date: replace only the FIRST [YYYY-MM-DD] (delivery target stays as bracket)
        if "[YYYY-MM-DD]" in para.text:
            _replace_in_paragraph(para, {"[YYYY-MM-DD]": config.show_date}, count=1)
        _replace_in_paragraph(para, standard)

    # --- Table 0: screens table ---
    screens_table = doc.tables[0]
    _rebuild_screens_table(screens_table, config)

    # --- Table 1: spec values ---
    spec_table = doc.tables[1]
    spec_replacements = {
        "[e.g. 30 / 60 fps]": framerate_label,
        "[Rec.709]":           color_space_label,
    }
    for row in spec_table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                _replace_in_paragraph(para, spec_replacements)

    # Apply standard replacements to all table cells in every table
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    _replace_in_paragraph(para, standard)

    # --- Save ---
    output_path = show_root / f"{config.show_name}_DeliverySpec.docx"
    doc.save(str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _replace_in_paragraph(para, replacements: dict[str, str], count: int = 0) -> None:
    """Replace placeholder text in a paragraph, handling cross-run splits.

    When count > 0, only the first `count` occurrences of each key are replaced.
    Formatting of the first run is preserved; subsequent runs are cleared.
    """
    full_text = para.text
    if not any(k in full_text for k in replacements):
        return

    for old, new in replacements.items():
        if count:
            full_text = full_text.replace(old, new, count)
        else:
            full_text = full_text.replace(old, new)

    if not para.runs:
        return

    # Put the full replaced text in the first run; blank the rest.
    # This preserves the first run's character formatting (bold, font, size).
    para.runs[0].text = full_text
    for run in para.runs[1:]:
        run.text = ""


def _rebuild_screens_table(table, config: ShowConfig) -> None:
    """Replace example rows in the screens table with one row per config screen."""
    # Remove all rows except the header (row 0)
    header_row = table.rows[0]
    rows_to_remove = list(table.rows[1:])
    for row in rows_to_remove:
        table._tbl.remove(row._tr)

    # Copy the header row's style for new rows by referencing the table's XML
    for screen in config.screens:
        new_row = table.add_row()
        cells = new_row.cells

        cells[0].text = screen.id
        cells[1].text = screen.name or ""
        cells[2].text = screen.resolution or ""
        cells[3].text = ""  # notes — operator fills in manually

        # Match font size / style from the header cells where possible
        _copy_cell_style(header_row.cells[0], cells[0])
        _copy_cell_style(header_row.cells[1], cells[1])
        _copy_cell_style(header_row.cells[2], cells[2])
        _copy_cell_style(header_row.cells[3], cells[3])


def _copy_cell_style(source_cell, dest_cell) -> None:
    """Copy basic paragraph style from source cell to the newly written dest cell."""
    if not source_cell.paragraphs or not dest_cell.paragraphs:
        return
    src_para  = source_cell.paragraphs[0]
    dest_para = dest_cell.paragraphs[0]

    # Copy paragraph style name
    if src_para.style:
        try:
            dest_para.style = src_para.style
        except Exception:
            pass

    # Copy run-level font properties from first run of source
    if src_para.runs and dest_para.runs:
        src_run  = src_para.runs[0]
        dest_run = dest_para.runs[0]
        dest_run.font.size    = src_run.font.size
        dest_run.font.bold    = src_run.font.bold
        dest_run.font.italic  = src_run.font.italic
        dest_run.font.name    = src_run.font.name
