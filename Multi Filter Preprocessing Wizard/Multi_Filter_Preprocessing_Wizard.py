"""
Multi_Filter_Preprocessing_Wizard.py

A Siril Python script (run from inside Siril, via sirilpy) that automates the
first stage of a multi-filter (LRGB / narrowband) preprocessing workflow:

  1. Shows a one-time reminder about how the dataset folder should be laid
     out (and to set Siril's Home/CWD to it before running this script).
  2. Asks whether Siril's Home/CWD is already set to your main dataset
     folder. If so, that becomes the main dataset folder directly. If not,
     shows a folder picker to choose it, and sets Siril's Home/CWD to your
     selection. Either way, once the main dataset folder is known, lets you
     tick which filter subfolders in it to process.
  3. For each selected filter, checks its "darks"/"biases"/"flats"
     subfolders and recommends which Mono_Preprocessing script variant to
     stack it with (see MONO_SSF_VARIANTS/recommend_ssf_variant) -- you can
     confirm or override the recommendation per filter. Then confirms
     whichever variant(s) were actually picked are installed where Siril
     can find them. The phase 3 Python tools (AutoBGE, etc.) are checked
     later, right before phase 3 starts -- see below -- since phase 1/2
     don't use them.
  4. Creates the "1 - Registration", "2 - Pre-process" and "3 - Image
     Processing" working folders inside the main folder. "1 - Registration"
     itself gets three subfolders: "Raw", "Process", and "Output" (see
     phase 2 below for what each is for).
  5. For each selected filter: runs its chosen Mono_Preprocessing variant
     against that filter's "lights" folder (and darks/biases/flats, if
     that variant uses them), renames the resulting stack to
     "<Filter> raw.fit", deletes the leftover "process" folder, copies the
     renamed stack into "1 - Registration/Raw", loads it into Siril so you
     can look at it, and pauses for you to confirm before moving to the
     next filter.

Phase 2 continues from there, working in "1 - Registration":
  6. Asks for a sequence name, then runs Siril's native "convert" (with
     "Raw" as the working directory) on all the "<Filter> raw.fit" files
     sitting there to build a Siril sequence out of them (one frame per
     filter). The resulting sequence files are then moved into "Process",
     which is the working directory for every step below.
  7. Registers that sequence (global star alignment, Siril's "register"
     command) so all filters line up pixel-for-pixel. Still working in
     "Process".
  8. Opens a crop window: a checklist of filters on the left (unchecked =
     excluded from the crop), a preview of the reference frame that you can
     switch to any other frame, zoom in/out/fit-to-window controls (mouse
     wheel zooms too), and an adjustable crop rectangle (draw it, then drag
     its edges/corners to resize or drag inside it to move it, the same
     way Siril's own selection tool works). Clicking "Continue" here is
     final -- there's no separate confirmation step.
  9. Runs Siril's "seqcrop" on the registered sequence (writing into
     "Process"), then copies each checked filter's "cropped_..." output
     into "Output" (renamed to its short initials, e.g. "Blue" -> "B.fit",
     "H-alpha" -> "Ha.fit" -- see FILTER_INITIALS), and copies
     it again from there into "2 - Pre-process/<Filter>/<Initials>.fit"
     (the subfolder keeps the full filter name, only the file is
     shortened). The "cropped_..." file itself is left where "seqcrop"
     wrote it, in "Process".

Phase 3 (right where it would start, once phases 1-2 are done or found
already done, see below) begins with run_phase3_setup_and_tool_check(): it
scans Siril's script directories for every installed Python script, asks how
many extra "Misc/Other" steps you want (see ask_misc_step_count), then opens
configure_phase3_steps() -- a reorderable pipeline of five fixed steps
(Background Extraction, Denoising, Sharpening, Star Removal, Stretching) plus
your Misc/Other steps, where you tick which installed script(s) AND/OR
Siril's own built-in tools (see PY_SCRIPT_CATALOG / BUILTIN_TOOL_CATALOG for
what each one does -- some, like CosmicClarity_Native.py, cover more than one
step) to use for each one, and reorder the whole pipeline with Move Up/Down.
Whichever scripts actually got picked are then checked for real (found/
missing, with the option to locate them manually) the same way phase 1
checks for its .ssf script -- built-in tools never need this since they're
always part of Siril itself. The resulting pipeline is remembered in
wizard_config.json for next time. If a LATER run of this same dataset finds
a remembered pipeline for the exact same step set (same fixed steps, same
Misc/Other count -- run order doesn't matter for this check, only which
steps exist), configure_phase3_steps() shows what was picked for every step
and asks upfront whether to reuse that setup exactly as it was left
(order included, skipping every picker/reorder screen entirely) or step
through it all again to review or change it (see
_confirm_reuse_phase3_choices).

run_phase3_pipeline() then actually runs it, one filter at a time: it loads
that filter's current checkpoint file from "2 - Pre-process/<Filter>/"
(starting from "<Initials>.fit", e.g. "B.fit") and walks the configured
steps in order. This wizard doesn't drive any tool's PARAMETERS itself --
Python scripts are meant to be tuned by hand, and even a built-in tool this
wizard can open for you still needs its own settings chosen by hand in that
dialog -- so for each step it just tells you which tool it is, opens it for
you when it can (a Python script, via "pyscript"; a built-in tool with a
known matching dialog -- see BUILTIN_TOOL_CATALOG -- via sirilpy's
open_dialog()/DialogID), and waits (see run_step_checkpoint). Every image it
loads during phase 3 is switched to Siril's AutoStretch display mode (see
set_display_autostretch) so it's viewable right away instead of
looking flat/black in Linear mode -- a display setting only, the saved
pixel data is never touched. Once you click Done,
it saves a checkpoint copy under a chained filename -- e.g. "B.fit" ->
"B - BE.fit" -> "B - BE, SH.fit" -- with each step's short code appended
(CATEGORY_CODE for the five fixed steps, a user-editable code for Misc/Other
steps). Star Removal is a special case (see handle_star_removal_step): those
tools commonly produce a separate starless image and, optionally, a star
mask, rather than updating the loaded image in place, so this looks for new
files the tool created and renames them into the same scheme (mask files get
an extra "SM" appended, e.g. "B - BE, SH, SR, SM.fit") instead of assuming
there's just one output. You can Skip a step or Abort the whole run from
each checkpoint window. Re-running after an abort resumes each filter from
wherever its checkpoint files show it last got to, rather than starting
over (see find_resume_point). Once a filter's pipeline reaches its last
configured step, finalize_phase3_filter() asks whether to export the
result in a format besides FIT/FITS (TIFF/PNG/JPEG, via ask_final_export_
format), then copies (never moves -- the working folder keeps its full
checkpoint history) that final image, named "<Initials> - Final.<ext>",
into a new "1 - Output" subfolder inside "2 - Pre-process" itself. Once
every selected filter has gone through the pipeline, run_phase3_pipeline()
also copies everything that landed in "1 - Output" into "3 - Image
Processing" in the main dataset folder, so the finished per-filter images
end up somewhere easy to find without digging into "2 - Pre-process".

PHASE 4 (optional): once phase 3 finishes, run_phase4_starmask_pipeline()
offers to build a starmask -- an RGB (Red/Green/Blue) or HOO (H-alpha/OIII)
color composite, with an optional Luminance channel (making it LRGB/LHOO),
built from each contributing filter's ORIGINAL, unprocessed phase 2 output
-- not phase 3's final result (see find_phase2_source_file) -- since phase
4 runs its own separate pipeline against the fresh composite afterwards.
The composite itself is produced with Siril's
"rgbcomp" command (see build_starmask_composite) rather than by trying to
drive its interactive RGB Compositing dialog -- there's no scripting way to
fill in an already-open dialog's fields, but a one-shot "rgbcomp" call with
every channel filename already decided produces the identical result. The
composite is then run through its own pre-process pipeline exactly like a
filter goes through phase 3 (same resume/back/skip/abort behavior, same
checkpoint-chain naming, reusing Phase 3's pipeline as-is or configuring a
separate one under cfg["phase4_steps"]) -- except its Star Removal step
keeps the star MASK output rather than the starless one, since the mask is
the actual point of phase 4 (handle_star_removal_step_for_starmask, the
mirror image of phase 3's handle_star_removal_step). The finished starmask
is copied into "1 - Output" and "3 - Image Processing" the same way every
filter's own final image is. Skippable at any point, and silently skipped
outright if this dataset's selected filters support neither RGB nor HOO.

Once phase 3 (and phase 4, if not skipped) are both done, the whole run
ends with ask_delete_intermediate_folders() offering to delete
"1 - Registration" and "2 - Pre-process" to reclaim disk space now that
every final image already lives in "3 - Image Processing" -- keeping them
(for redundancy, or in case a step needs redoing later) is offered too, but
deleting is the recommended default.

CHECKPOINTING / RESUMING AFTER AN ABORT:
  - TOP-LEVEL checkpoint, checked first, before anything else (even filter
    selection): if "2 - Pre-process" already has at least one final
    "<Initials>.fit" from a previous run of this dataset, the script asks
    whether to re-run phases 1-2 from scratch or skip straight to phase 3
    (entering it the same way described above). Answering "Re-run" falls
    through to the per-phase checkpoints below; nothing is deleted until
    you say so.
  - Phase 1 skips re-stacking any filter that already has a
    "<Filter> raw.fit" in its folder (from a previous run), just making
    sure it's copied into "1 - Registration/Raw" and moving on -- rather
    than crashing trying to rename a new result over the existing file.
    The filter-selection screen marks these "(already stacked)".
  - Phase 2, before running "convert", deletes any leftover sequence/
    registration/crop files it previously generated under the sequence
    name you're about to reuse (never the original "<Filter> raw.fit"
    inputs), so a retry with the same name always starts clean instead of
    depending on how Siril handles overwriting its own files.
  - Phase 2 does NOT resume from partway through an aborted attempt (e.g.
    picking up right after convert but before register) -- that's a much
    harder thing to get right safely. Instead, once you've confirmed a
    redo at the top-level checkpoint above, every phase 2 run starts by
    completely emptying "1 - Registration/Process",
    "1 - Registration/Output", AND "2 - Pre-process" -- so a retry after
    an abort always starts from a clean slate, whatever sequence name was
    used before or is used this time, and an abort mid-phase-2 (or a redo
    with a different crop or filter selection) just means a clean re-run
    from the start, not a crash or a mix of old and new results. Clearing
    Once phase 2 finishes successfully, it also deletes
    "1 - Registration/Process" entirely -- everything phase 3 and any redo
    need from it (the cropped per-filter results) has already been copied
    into "1 - Registration/Output" and "2 - Pre-process", so it's just
    clutter (the sequence, its .seq file, and all the intermediate
    registered/cropped frames) from that point on.
    "2 - Pre-process" too means a filter you uncheck on a redo won't leave
    its previous run's "<Initials>.fit" sitting there stale.
    "1 - Registration/Raw" (the "<Filter> raw.fit" originals from phase 1)
    is a separate folder and is never touched by any of this cleanup.

The UI is a hand-built dark theme (ttk "clam" base + custom colors) styled
to match the look of SyQon's Siril tools: dark card panels, a teal accent
color, and a persistent app-name header. It intentionally does NOT track
Siril's own light/dark theme setting anymore -- it always looks like this,
the same way SyQon's own tools have a fixed look regardless of Siril's
theme. Note: real ttk buttons/panels are rectangular -- Tkinter can't do
SyQon's rounded corners or its fade/segmented preview panel without a lot
more custom canvas-drawn widgets, so this matches the color/typography
language rather than being a pixel-identical clone.

ONE PERSISTENT WINDOW: the whole run happens in a single window that never
closes and reopens between steps (see _ensure_wizard/_new_root) -- it has a
step checklist sidebar on the left (pending "○" / current "➤" / done "✓")
that's always visible, and a content area on the right that gets cleared
and rebuilt for each step's own screen. The ONE exception is the
interactive crop tool (_new_popup_root), which opens as its own separate
window (a Toplevel of the main window, so it still shares the same event
loop) since it's large and benefits from being independently resizable/
positioned -- the persistent window and its checklist stay visible behind
it while it's open.

--------------------------------------------------------------------------
ASSUMPTIONS MADE (please confirm / correct these once you test it):
--------------------------------------------------------------------------
* Mono_Preprocessing_WithoutDBF.ssf is a plain Siril script file (one Siril
  command per line, same syntax you'd type into Siril's console, comments
  start with '#'). This script runs it by reading it line-by-line and
  replaying each line through siril.cmd(), rather than any special "run an
  .ssf" API call -- I could not confirm sirilpy has a dedicated "run this
  .ssf file" method, so this is the safe, generic way to do it. If your
  .ssf uses any syntax that ISN'T valid as a siril.cmd() call, this will
  need adjusting.
* After the .ssf runs, "result.fit" (or "result.fits") ends up either
  directly inside the filter's "lights" folder, or inside a "process"
  subfolder of it. The script checks both locations.
* The tool check no longer asks you where things are installed. It asks
  Siril itself (via siril.get_siril_config("gui", "script_path"), plus
  Siril's user/system data directories) for every folder Siril already
  searches for scripts -- the same folders you set up in Siril's own
  Preferences > Scripts screen -- and searches those automatically. You
  only get asked anything if a tool genuinely can't be found there, and
  even then it's a "Locate manually" button, per missing tool, not a
  general setup step. Found locations are cached in wizard_config.json
  next to this script, but re-verified as still existing every run.
* PHASE 2 assumptions (verified against Siril's docs where possible, but
  please double check on your first real run):
  - "convert basename" always writes into the current working directory --
    "-out=<dir>" was tried to redirect it straight into "Process" while
    reading from "Raw", but Siril silently ignored the flag and wrote into
    the cwd regardless. So this script instead runs "convert" with "Raw"
    as the cwd, then moves the sequence files it created (matched by name
    pattern, never the "<Filter> raw.fit" originals) into "Process" itself
    before continuing. "basename_conversion.txt" maps original filenames
    to sequence frame numbers, but its exact column format isn't
    documented, so this script scans each line for the frame-number
    pattern (_00001.) plus whichever of your original "<Filter> raw.fit"
    filenames also appears on that line, rather than assuming a fixed
    format. This is how it knows which frame is which filter.
  - "register basename" (no extra flags = single-pass global star
    alignment) creates a new sequence "r_basename" immediately, with the
    reference frame being frame 1 (the first frame) since the sequence
    hasn't been registered before.
  - "seqcrop" is told an explicit "-prefix=cropped_" so the output name
    is guaranteed rather than assumed.
  - It's genuinely unclear from Siril's docs whether "unselect"-ing a
    frame before "seqcrop" actually skips it in the crop output, or
    whether seqcrop crops every frame regardless of selection state. To
    be safe either way, this script ALSO enforces the checkbox choice
    itself afterward: it only ever renames/copies "cropped_..." files for
    filters you left checked, even if Siril produced output for an
    unchecked one anyway.
--------------------------------------------------------------------------
"""

import json
import shlex
import shutil
import sys
import threading
import traceback
from pathlib import Path
from typing import Callable

import sirilpy as s

# sirilpy.enums.DialogID + SirilInterface.open_dialog() let a script ask
# Siril to open one of its OWN built-in tool dialogs (GHT, Background
# Extraction, Wavelets, ...) directly -- e.g. siril.open_dialog(DialogID.
# GHT_DIALOG) for "Image Processing > Stretches > Generalized Hyperbolic
# Stretch Transformation". This appears to be a newer addition to sirilpy
# that isn't covered anywhere in Siril's prose scripting docs (only in the
# raw API reference's method/enum listing), so there's no way to be sure
# every Siril install this wizard runs on bundles a new enough sirilpy to
# have it. Importing it defensively here (rather than a bare "from
# sirilpy.enums import DialogID" that would crash this ENTIRE script on an
# older Siril) means BUILTIN_TOOL_CATALOG's "dialog" mappings below (see
# run_step_checkpoint) are used when available and silently skipped
# (falling back to the existing "open it yourself" instructions) when not.
try:
    from sirilpy.enums import DialogID
except ImportError:
    DialogID = None

# sirilpy.enums.STFType + SirilInterface.set_siril_stf() let a script switch
# Siril's DISPLAY mode for the currently loaded image -- e.g. LINEAR_DISPLAY
# vs AUTOSTRETCH_DISPLAY, the same toggle as Siril's own viewer toolbar. This
# only changes how the image is RENDERED on screen; it never touches the
# saved pixel data (unlike the "autostretch"/"mtf" processing commands,
# which permanently stretch and save). Like DialogID above, this only turned
# up in the raw API reference (not Siril's prose docs), so it's imported and
# used defensively -- if an older bundled sirilpy lacks it, phase 3 simply
# leaves Siril's display mode alone instead of erroring.
try:
    from sirilpy.enums import STFType
except ImportError:
    STFType = None

# NOTE: tkinter is part of the Python standard library, not a pip package --
# do NOT call s.ensure_installed("tkinter"); pip has no such package and it
# will fail. If tkinter isn't available in Siril's bundled Python, that's an
# interpreter-level problem, not something installable from here.
try:
    import tkinter as tk
    from tkinter import filedialog, ttk
except ImportError as e:
    print(
        "tkinter is not available in Siril's Python environment. "
        f"Import failed with: {e}\n"
        "This script cannot run without it -- see the chat for how to fix "
        "your Siril Python installation."
    )
    sys.exit(1)

# ttkthemes gives us the "clam" theme, which (unlike Windows' native "vista"
# ttk theme) actually honors custom colors -- that's what lets us build a
# SyQon-style dark theme at all. tksiril.create_tooltip is still used for
# hover tooltips; tksiril.match_theme_to_siril is deliberately NOT used
# (see module docstring).
s.ensure_installed("ttkthemes")
from ttkthemes import ThemedTk
from sirilpy import tksiril

# Pillow is used only to turn a frame's pixel data into something Tkinter's
# Canvas can display, for the crop-preview window in phase 2.
s.ensure_installed("Pillow")
from PIL import Image, ImageTk
import numpy as np
import re

# --------------------------------------------------------------------------
# Dark theme (SyQon-style): colors, fonts, and a ttk.Style setup applied to
# every window this script opens.
# --------------------------------------------------------------------------

BG_MAIN = "#14151c"        # window background
BG_CARD = "#1b1d27"        # card / panel background
BG_CARD_ALT = "#22242f"    # slightly lighter -- inputs, secondary buttons
BORDER = "#2c2f3c"
TEXT_PRIMARY = "#e8e9ee"
TEXT_SECONDARY = "#9a9db2"
ACCENT = "#2dd4c4"         # teal accent
ACCENT_ACTIVE = "#25b8ab"
ACCENT_TEXT = "#0b1220"    # dark text used on top of the accent color
DANGER = "#f0616a"
WARNING = "#e8a33d"        # amber -- a heads-up, not a hard error (DANGER)

FONT_FAMILY = "Segoe UI"


def apply_dark_theme(root: tk.Tk) -> ttk.Style:
    root.configure(background=BG_MAIN)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        ".", background=BG_MAIN, foreground=TEXT_PRIMARY,
        fieldbackground=BG_CARD_ALT, bordercolor=BORDER,
        font=(FONT_FAMILY, 10), borderwidth=0,
    )

    style.configure("TFrame", background=BG_MAIN)
    style.configure("Card.TFrame", background=BG_CARD)

    style.configure("TLabel", background=BG_MAIN, foreground=TEXT_PRIMARY)
    style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT_PRIMARY)
    style.configure(
        "Brand.TLabel", background=BG_MAIN, foreground=TEXT_SECONDARY,
        font=(FONT_FAMILY, 8, "bold"),
    )
    style.configure(
        "Header.TLabel", background=BG_MAIN, foreground=TEXT_PRIMARY,
        font=(FONT_FAMILY, 15, "bold"),
    )
    style.configure(
        "Found.TLabel", background=BG_CARD, foreground=ACCENT,
        font=(FONT_FAMILY, 10, "bold"),
    )
    style.configure(
        "Missing.TLabel", background=BG_CARD, foreground=DANGER,
        font=(FONT_FAMILY, 10, "bold"),
    )
    style.configure(
        "Warning.TLabel", background=BG_CARD, foreground=WARNING,
    )
    # The phase 3 checkpoint window's live status line (e.g. "Launching
    # ..."/"... has been closed.") -- made to stand out on its own since it
    # replaced a progress bar that turned out to be more misleading than
    # informative (there's no real percent-done to show for a step that's
    # really just "waiting for you to finish in Siril").
    style.configure(
        "StatusUpdate.TLabel", background=BG_CARD, foreground=TEXT_PRIMARY,
        font=(FONT_FAMILY, 13, "bold italic"),
    )
    # The "Note:" header above a checkpoint window's reminder text, pinned
    # to the bottom of the window (see run_step_checkpoint).
    style.configure(
        "NoteHeader.TLabel", background=BG_CARD, foreground=TEXT_SECONDARY,
        font=(FONT_FAMILY, 9, "bold"),
    )

    # Sidebar step-checklist rows (see _ensure_wizard / wizard_add_step).
    style.configure(
        "StepPending.TLabel", background=BG_CARD, foreground=TEXT_SECONDARY,
        font=(FONT_FAMILY, 10),
    )
    style.configure(
        "StepCurrent.TLabel", background=BG_CARD, foreground=ACCENT,
        font=(FONT_FAMILY, 10, "bold"),
    )
    style.configure(
        "StepDone.TLabel", background=BG_CARD, foreground=TEXT_PRIMARY,
        font=(FONT_FAMILY, 10),
    )

    style.configure(
        "TLabelframe", background=BG_CARD, bordercolor=BORDER,
        relief="solid", borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label", background=BG_CARD, foreground=ACCENT,
        font=(FONT_FAMILY, 9, "bold"),
    )

    style.configure(
        "TCheckbutton", background=BG_CARD, foreground=TEXT_PRIMARY,
        focuscolor=BG_CARD,
    )
    style.map(
        "TCheckbutton",
        background=[("active", BG_CARD)],
        indicatorcolor=[("selected", ACCENT), ("!selected", BG_CARD_ALT)],
        indicatorforeground=[("selected", ACCENT_TEXT)],
    )

    style.configure(
        "TRadiobutton", background=BG_CARD, foreground=TEXT_PRIMARY,
        focuscolor=BG_CARD,
    )
    style.map(
        "TRadiobutton",
        background=[("active", BG_CARD)],
        indicatorcolor=[("selected", ACCENT), ("!selected", BG_CARD_ALT)],
        indicatorforeground=[("selected", ACCENT_TEXT)],
    )

    style.configure(
        "TButton", background=BG_CARD_ALT, foreground=TEXT_PRIMARY,
        bordercolor=BORDER, focuscolor=BG_CARD_ALT, padding=(16, 9),
        font=(FONT_FAMILY, 10),
    )
    style.map(
        "TButton",
        background=[("active", "#2a2d3d"), ("disabled", BG_CARD)],
        foreground=[("disabled", TEXT_SECONDARY)],
    )

    style.configure(
        "Accent.TButton", background=ACCENT, foreground=ACCENT_TEXT,
        bordercolor=ACCENT, focuscolor=ACCENT, padding=(16, 9),
        font=(FONT_FAMILY, 10, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("active", ACCENT_ACTIVE), ("disabled", BG_CARD)],
        foreground=[("disabled", TEXT_SECONDARY)],
    )

    style.configure(
        "TEntry", fieldbackground=BG_CARD_ALT, foreground=TEXT_PRIMARY,
        insertcolor=TEXT_PRIMARY, bordercolor=BORDER, padding=6,
    )
    style.map("TEntry", fieldbackground=[("disabled", BG_CARD)])

    # ttk.Combobox (used by choose_calibration_scripts): the entry field and
    # arrow button follow the ttk style below, but the dropdown list itself
    # is a plain (non-ttk) Tk Listbox, which only picks up colors via
    # option_add -- both halves need setting or it stays in the OS's native
    # light theme regardless of what theme_use() picked.
    style.configure(
        "TCombobox", fieldbackground=BG_CARD_ALT, background=BG_CARD_ALT,
        foreground=TEXT_PRIMARY, arrowcolor=TEXT_PRIMARY, bordercolor=BORDER,
        selectbackground=BG_CARD_ALT, selectforeground=TEXT_PRIMARY,
        padding=6,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", BG_CARD_ALT), ("disabled", BG_CARD)],
        background=[("readonly", BG_CARD_ALT), ("active", BG_CARD_ALT)],
        foreground=[("disabled", TEXT_SECONDARY)],
        arrowcolor=[("disabled", TEXT_SECONDARY)],
    )
    root.option_add("*TCombobox*Listbox.background", BG_CARD_ALT)
    root.option_add("*TCombobox*Listbox.foreground", TEXT_PRIMARY)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", ACCENT_TEXT)
    root.option_add("*TCombobox*Listbox.font", (FONT_FAMILY, 10))

    # Progress bars shown above the button row on every step (see
    # _button_row) -- one tracks the current step (a looping empty-to-full
    # fill, since Siril doesn't report fine-grained progress for what it's
    # running -- see _animate_fill), the other the overall run (determinate,
    # steps done / steps total). Both are thin, like Siril's own.
    style.configure(
        "Wizard.Horizontal.TProgressbar",
        background=ACCENT, troughcolor=BG_CARD_ALT, bordercolor=BG_CARD_ALT,
        lightcolor=ACCENT, darkcolor=ACCENT, thickness=6,
    )

    return style


def _set_windows_dark_titlebar(root: tk.Tk) -> None:
    """Cosmetic only: on Windows 10 2004+/11 this makes the native title
    bar dark too, so the window doesn't have a bright white bar above a
    dark body. Silently does nothing anywhere else or if it fails."""

    if sys.platform != "win32":
        return
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass

# --------------------------------------------------------------------------
# Configuration persistence
# --------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).resolve().parent / "wizard_config.json"

# Siril's script repository offers four Mono_Preprocessing variants, one
# for each combination of calibration frames it actually supports -- there's
# no standalone "no biases" variant; bias is always paired with whichever of
# darks/flats is present. "full" needs all three; "no_dark"/"no_flat" need
# the other two; "none" (WithoutDBF) needs nothing but lights. See
# recommend_ssf_variant() for how a filter's detected frames map to one of
# these, and choose_calibration_scripts() for the per-filter picker screen.
MONO_SSF_VARIANTS = {
    "full":    ("Mono_Preprocessing.ssf",             "Darks + Biases + Flats"),
    "no_dark": ("Mono_Preprocessing_WithoutDark.ssf", "Biases + Flats (no Darks)"),
    "no_flat": ("Mono_Preprocessing_WithoutFlat.ssf", "Darks + Biases (no Flats)"),
    "none":    ("Mono_Preprocessing_WithoutDBF.ssf",  "Lights only (no calibration)"),
}
MONO_SSF_VARIANT_ORDER = ["full", "no_dark", "no_flat", "none"]

# Which calibration-frame subfolders each variant's .ssf actually "cd"s
# into -- used to warn the user before running if they've picked a variant
# that needs a folder their filter doesn't have (that's exactly what
# crashes the .ssf partway through with a "No such file or directory").
MONO_SSF_REQUIRED_FRAMES = {
    "full": {"darks", "biases", "flats"},
    "no_dark": {"biases", "flats"},
    "no_flat": {"darks", "biases"},
    "none": set(),
}


# Phase 3 pipeline: the five fixed pre-processing steps offered, plus
# however many "Misc/Other" steps the user asks for (see
# ask_misc_step_count/configure_phase3_steps). PY_SCRIPT_CATALOG maps every
# Python script we know about, from Siril's official script-repository
# catalog, to which of these it's used for -- some belong to more than one
# (e.g. CosmicClarity_Native.py covers Sharpening, Denoising, AND Star
# Removal; GraXpert-AI.py covers Background Extraction AND Denoising), so a
# script can legitimately be picked for more than one step. A script found
# on disk but NOT in this catalog isn't offered anywhere in the pipeline
# configurator at all -- including under "Misc/Other" -- since Siril's
# script directories hold every script its repository has ever synced
# (comet finders, catalog fetchers, autofocus helpers, and every other
# "Utility"/non-image-processing category Siril's own Preferences -> Scripts
# screen lists), not just image-processing ones; "Misc/Other" only relaxes
# the CATEGORY restriction (any catalog script, not just ones mapped to
# that step), not the catalog membership itself. Descriptions are taken
# from Siril's own script-repository listing (see
# claude/siril-python-scripting-research.md in this project for sourcing).
CATEGORY_ORDER = [
    "Background Extraction", "Denoising", "Sharpening",
    "Star Removal", "Stretching",
]

# Short codes appended to a filter's working filename as each pipeline step
# finishes (see run_phase3_pipeline) -- e.g. "B.fit" -> "B - BE.fit" ->
# "B - BE, SH.fit". Misc/Other steps get a user-editable code instead
# (default "M1", "M2", ... -- see configure_phase3_steps).
CATEGORY_CODE = {
    "Background Extraction": "BE",
    "Denoising": "DN",
    "Sharpening": "SH",
    "Star Removal": "SR",
    "Stretching": "ST",
}

PY_SCRIPT_CATALOG: dict[str, dict] = {
    # -- Background Extraction / gradient removal --
    "AutoBGE.py": {
        "categories": ["Background Extraction"],
        "desc": "Auto Background Extraction script.",
    },
    "AutoGradientRemoval.py": {
        "categories": ["Background Extraction"],
        "desc": "Auto Gradient Removal tool.",
    },
    "GraXpert-AI.py": {
        "categories": ["Background Extraction", "Denoising"],
        "desc": "GraXpert AI gradient removal, with denoise as well.",
    },
    "GPS_Process.py": {
        "categories": ["Background Extraction", "Denoising", "Sharpening"],
        "desc": "CosmicClarity/GraXpert-based processing (background "
                "extraction, denoise, and/or sharpening).",
    },
    "VeraLux_Nox.py": {
        "categories": ["Background Extraction"],
        "desc": "Physically-faithful photometric gradient reduction.",
    },

    # -- Denoising --
    "Prism.py": {
        "categories": ["Denoising"],
        "desc": "SyQon Prism AI denoise. Paid product.",
    },
    "NoiseXTerminator.py": {
        "categories": ["Denoising"],
        "desc": "RC Astro AI denoise. Paid product.",
    },
    "DeepSNR.py": {
        "categories": ["Denoising"],
        "desc": "DeepSNR AI denoise.",
    },
    "CosmicClarity_Denoise.py": {
        "categories": ["Denoising"],
        "desc": "Cosmic Clarity Denoise.",
    },
    "SCUNet_Denoise.py": {
        "categories": ["Denoising"],
        "desc": "SCUNet AI image denoiser.",
    },
    "VeraLux_Silentium.py": {
        "categories": ["Denoising"],
        "desc": "Linear-phase noise suppression engine.",
    },

    # -- Sharpening / deconvolution --
    "BlurXTerminator.py": {
        "categories": ["Sharpening", "Star Removal"],
        "desc": "RC Astro Deconv AI: aberration correction, star "
                "reduction, and sharpening. Paid product.",
    },
    "Parallax.py": {
        "categories": ["Sharpening", "Star Removal"],
        "desc": "SyQon Parallax AI: aberration correction, star "
                "reduction, and sharpening.",
    },
    "AberrationRemover.py": {
        "categories": ["Sharpening"],
        "desc": "Aberration Remover AI.",
    },
    "CosmicClarity_Superres.py": {
        "categories": ["Sharpening"],
        "desc": "Cosmic Clarity Superres.",
    },
    "CosmicClarity_Native.py": {
        "categories": ["Sharpening", "Denoising", "Star Removal"],
        "desc": "Cosmic Clarity AI-powered sharpening, denoising, super "
                "resolution, and star removal, all in one script.",
    },
    "CosmicClarity_Sharpen.py": {
        "categories": ["Sharpening"],
        "desc": "Cosmic Clarity sharpening process.",
    },

    # -- Star removal / reduction --
    "Starless.py": {
        "categories": ["Star Removal"],
        "desc": "SyQon Starless AI star removal. Paid product.",
    },
    "StarXTerminator.py": {
        "categories": ["Star Removal"],
        "desc": "RC Astro Starless AI star removal. Paid product.",
    },
    "StarNet.py": {
        "categories": ["Star Removal"],
        "desc": "StarNet 2.5 star removal, with optional star mask "
                "generation.",
    },
    "CosmicClarity_Satellite.py": {
        "categories": ["Star Removal"],
        "desc": "Cosmic Clarity Satellite Removal (satellite/aircraft "
                "trail removal).",
    },
    "CosmicClarity_Darkstar.py": {
        "categories": ["Star Removal"],
        "desc": "Cosmic Clarity Darkstar.",
    },
    "ER-Bill_Star_Reduction.py": {
        "categories": ["Star Removal"],
        "desc": "Star reduction via pixel math.",
    },
    "DSA-Star_Reduction.py": {
        "categories": ["Star Removal"],
        "desc": "Star reduction via pixel math.",
    },
    "VeraLux_StarComposer.py": {
        "categories": ["Star Removal"],
        "desc": "High-fidelity star reconstruction engine.",
    },

    # -- Stretching / tone mapping --
    "Statistical_Stretch.py": {
        "categories": ["Stretching"],
        "desc": "Seti Astro Statistical Stretch.",
    },
    "HDR_multiscale.py": {
        "categories": ["Stretching"],
        "desc": "Wavelet-based dynamic range compression.",
    },
    "HDR_Blender.py": {
        "categories": ["Stretching"],
        "desc": "Inverse-variance MLE HDR blender -- blends multiple "
                "images with different exposures.",
    },
    "VeraLux_HyperMetric_Stretch.py": {
        "categories": ["Stretching"],
        "desc": "Photometric hyperbolic stretch engine.",
    },
    "VeraLux_Curves.py": {
        "categories": ["Stretching"],
        "desc": "Spline-based photometric sculpting engine.",
    },
    "AutoStretch_Preview.py": {
        "categories": ["Stretching"],
        "desc": "Interactive AutoStretch preview.",
    },
}


def scan_available_py_scripts(siril: "s.SirilInterface", cfg: dict) -> dict[str, Path]:
    """Finds every .py file Siril can already see (same search directories
    as locate_tools/find_tool), regardless of whether it's in
    PY_SCRIPT_CATALOG -- used to populate the phase 3 pipeline configurator
    with whatever's actually installed. Returns {filename: path}, first
    match wins if the same filename somehow exists in more than one search
    directory. Skips zero-byte files as a stub guard, same reasoning as
    find_tool()."""

    search_dirs = get_search_directories(siril)
    found: dict[str, Path] = {}
    for base in search_dirs:
        for name, path in _scan_dir_files(base).items():
            if name.endswith(".py") and name not in found:
                found[name] = path
    return found


def categorize_available_scripts(available: dict[str, Path]) -> dict[str, list[str]]:
    """Groups the scripts scan_available_py_scripts() found by which of
    CATEGORY_ORDER's five fixed steps they belong to, per PY_SCRIPT_CATALOG
    -- a script in more than one category appears in each. Scripts not in
    the catalog simply don't appear here (they're still offered under a
    Misc/Other step, which isn't filtered by category)."""

    by_category: dict[str, list[str]] = {cat: [] for cat in CATEGORY_ORDER}
    for name in sorted(available):
        info = PY_SCRIPT_CATALOG.get(name)
        if not info:
            continue
        for cat in info["categories"]:
            if cat in by_category:
                by_category[cat].append(name)
    return by_category


# Siril's own built-in commands relevant to the same five pipeline steps --
# offered alongside the installed Python scripts in configure_phase3_steps
# so the user isn't limited to third-party scripts. These need no
# "locate"/tool-check step at all -- they're part of Siril itself, so
# they're always available and are excluded from the chosen_scripts set
# run_phase3_setup_and_tool_check() checks for. Command syntax/behavior
# confirmed against Siril's own docs (Commands reference, Background
# Extraction and Deconvolution pages). Star Removal has no entry: Siril's
# old built-in "starnet"/"seqstarnet" commands were removed in favor of the
# StarNet.py script (already in PY_SCRIPT_CATALOG), so there's no separate
# built-in tool for that step anymore.
#
# "dialog" (optional): the sirilpy.enums.DialogID member (by NAME, as a
# string -- resolved via getattr() in run_step_checkpoint so a member that
# doesn't exist in an older sirilpy is simply ignored rather than crashing)
# that opens this tool's actual GUI dialog in Siril via
# SirilInterface.open_dialog(). This is confirmed to exist in Siril's raw
# Python API reference (sirilpy.enums.DialogID, SirilInterface.open_dialog)
# but isn't covered in Siril's prose scripting docs at all, so exactly which
# Siril/sirilpy version introduced it -- and thus whether a given user's
# Siril install has it -- is unconfirmed; run_step_checkpoint tries it and
# falls back to the manual "open it yourself" instructions if it's missing
# or the call fails for any reason. Only mapped where the command and the
# dialog are confidently the same tool; left unmapped (falls back to manual
# instructions, same as before) wherever that's genuinely unclear rather
# than guessing and risking the wrong dialog popping open.
BUILTIN_TOOL_CATALOG: dict[str, dict] = {
    "subsky": {
        "categories": ["Background Extraction"],
        "dialog": "BACKGROUND_EXTRACTION_DIALOG",
        "desc": "Siril built-in: background extraction (\"subsky\") -- "
                "polynomial or RBF synthetic background model, subtracted "
                "or divided out.",
    },
    "denoise": {
        "categories": ["Denoising"],
        "dialog": "DENOISE_DIALOG",
        "desc": "Siril built-in: non-local Bayesian (NL-Bayes) denoise.",
    },
    "atrous": {
        "categories": ["Denoising", "Sharpening"],
        "dialog": "WAVELETS_DIALOG",
        "desc": "Siril built-in: à trous wavelet transform -- can "
                "denoise (per-scale noise reduction) or sharpen (boosting "
                "detail scales), depending on how it's tuned.",
    },
    "unsharp": {
        "categories": ["Sharpening"],
        "desc": "Siril built-in: unsharp mask.",
    },
    "rl": {
        "categories": ["Sharpening"],
        "dialog": "DECONV_DIALOG",
        "desc": "Siril built-in: Richardson-Lucy deconvolution.",
    },
    "sb": {
        "categories": ["Sharpening"],
        "dialog": "DECONV_DIALOG",
        "desc": "Siril built-in: Split Bregman deconvolution.",
    },
    "wiener": {
        "categories": ["Sharpening"],
        "dialog": "DECONV_DIALOG",
        "desc": "Siril built-in: Wiener deconvolution.",
    },
    "ght": {
        "categories": ["Stretching"],
        "dialog": "GHT_DIALOG",
        "desc": "Siril built-in: Generalized Hyperbolic Stretch (GHT).",
    },
    "autoghs": {
        "categories": ["Stretching"],
        "dialog": "GHT_DIALOG",
        "desc": "Siril built-in: GHT with an automatically-picked "
                "symmetry point.",
    },
    "autostretch": {
        "categories": ["Stretching"],
        "dialog": "HISTOGRAM_DIALOG",
        "desc": "Siril built-in: auto-stretch.",
    },
    "asinh": {
        "categories": ["Stretching"],
        "dialog": "ASINH_DIALOG",
        "desc": "Siril built-in: hyperbolic arcsine stretch.",
    },
    "modasinh": {
        "categories": ["Stretching"],
        "dialog": "ASINH_DIALOG",
        "desc": "Siril built-in: modified arcsinh stretch (ghsastro-based).",
    },
    "mtf": {
        "categories": ["Stretching"],
        "dialog": "HISTOGRAM_DIALOG",
        "desc": "Siril built-in: midtones transfer function stretch.",
    },
    "linstretch": {
        "categories": ["Stretching"],
        "dialog": "HISTOGRAM_DIALOG",
        "desc": "Siril built-in: linear stretch to a new black point.",
    },
}


def categorize_builtin_tools() -> dict[str, list[str]]:
    """Same idea as categorize_available_scripts(), but for
    BUILTIN_TOOL_CATALOG -- there's no "available on disk" check needed
    since these are always part of Siril itself."""

    by_category: dict[str, list[str]] = {cat: [] for cat in CATEGORY_ORDER}
    for name, info in BUILTIN_TOOL_CATALOG.items():
        for cat in info["categories"]:
            if cat in by_category:
                by_category[cat].append(name)
    for cat in by_category:
        by_category[cat].sort()
    return by_category


def tool_description(name: str) -> str:
    """Description lookup covering both installed Python scripts
    (PY_SCRIPT_CATALOG) and Siril's own built-in commands
    (BUILTIN_TOOL_CATALOG) -- configure_phase3_steps() offers both kinds in
    the same checklist per step."""

    info = PY_SCRIPT_CATALOG.get(name) or BUILTIN_TOOL_CATALOG.get(name)
    return info["desc"] if info else "Not in the known script catalog -- no description available."


REGISTRATION_DIR_NAME = "1 - Registration"
PREPROCESS_DIR_NAME = "2 - Pre-process"
IMAGE_PROCESSING_DIR_NAME = "3 - Image Processing"

# Subfolders of "1 - Registration": phase 1 copies "<Filter> raw.fit" into
# RAW; phase 2 uses PROCESS as its Siril working directory (converting the
# files that live in RAW); the final cropped output for each filter lands
# in OUTPUT before being copied into "2 - Pre-process".
RAW_SUBDIR_NAME = "Raw"
PROCESS_SUBDIR_NAME = "Process"
OUTPUT_SUBDIR_NAME = "Output"

# Subfolder of "2 - Pre-process" itself (separate from the one above, which
# is under "1 - Registration") -- this is where each filter's phase 3
# FINAL image gets copied (never moved) once its pipeline finishes, named
# "<Initials> - Final.<ext>" -- see finalize_phase3_filter(). Named with a
# "1 - " prefix (unlike the phase 2 Output folder above) so it sorts to the
# top of "2 - Pre-process", above the per-filter subfolders.
PHASE3_OUTPUT_SUBDIR_NAME = "1 - Output"

# Subfolder of "2 - Pre-process" (a sibling of PHASE3_OUTPUT_SUBDIR_NAME and
# every filter's own subfolder) that phase 4 -- building an RGB/HOO starmask
# composite via Siril's "rgbcomp" command -- copies its channel source
# images into and runs its own checkpoint pipeline from. See
# build_starmask_composite/run_phase4_starmask_pipeline.
STARMASK_SUBDIR_NAME = "Starmask"

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    except OSError:
        pass


# --------------------------------------------------------------------------
# A single persistent wizard window: one root window stays open for the
# whole run, with a step checklist sidebar (left) that never goes away, and
# a content area (right) that gets cleared and rebuilt for each step's own
# UI. Only the interactive crop window (_new_popup_root) opens separately.
# --------------------------------------------------------------------------

APP_NAME = "MULTI-FILTER WIZARD"

STEP_GLYPH = {"pending": "○", "current": "➤", "done": "✓"}
STEP_STYLE = {
    "pending": "StepPending.TLabel",
    "current": "StepCurrent.TLabel",
    "done": "StepDone.TLabel",
}

_WIZARD: dict = {}

# Tracks the main dataset folder for this run and whether it reached its
# own real end, so main()'s finally block can put Siril's working
# directory back there if the run instead ended early for any reason (an
# abort, the wizard window closed, an unhandled error) -- see the comment
# where _RUN_STATE["main_folder"] is set inside _run_wizard for why that
# matters. "completed" starts False and is only ever flipped True, never
# reset -- there's exactly one _run_wizard() call per script run.
_RUN_STATE: dict = {"main_folder": None, "completed": False}


class WizardClosed(Exception):
    """Raised when the user closes the persistent wizard window itself
    (the OS window-close "X", not one of its own Continue/Cancel/Abort
    buttons) -- caught once, at the very top of main(), to end the run
    cleanly instead of crashing on whatever widget the rest of the step
    was about to touch next (which the window-close just destroyed)."""


def _on_wizard_window_closed() -> None:
    _WIZARD["closed"] = True
    # Same as any step's own Cancel/Abort button: unblock whatever
    # root.mainloop() call is currently waiting, WITHOUT tearing down the
    # window for real here -- wizard_close() does that once, at the end.
    _WIZARD["root"].quit()


def _check_not_closed() -> None:
    """Called right after every root.mainloop() in every step dialog: if
    the user closed the window itself rather than clicking a button inside
    it, stop right here instead of continuing to work with widgets (the
    window's real .destroy() already tore them all down)."""

    if _WIZARD.get("closed"):
        raise WizardClosed()


# The wizard's window/taskbar icon (a little wizard hat), embedded as base64
# PNG data at three sizes so it stays crisp whether Windows uses it for the
# titlebar, the taskbar, or Alt-Tab -- rather than shipping a separate .ico
# file that could go missing if this script is copied on its own. Built once
# offline with Pillow; nothing here draws it at runtime.
_WIZARD_ICON_16_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACTUlEQVR4nLWSS0jUYRTFz73zn/88"
    "nIbaWFaY9kCZCCIsEhcz2aKFMbsJIog2KRm5iCiM4HOQFhlRrcoWbdpFtZB2FWlFRkiLCtESIikk"
    "MYdyXv/H9902vhKtNt3VWdzf4XDuBf7zkFLC6Yarl5KJ9thyC7wS2dvaGxRR9PlZX8ri6NliidYD"
    "gIL8xqxo0HarzSPKGl+7nQRGNBzfAwD9ya4/G4iARCmWQrrh0Y0LFz2Pk1rKYLb2A0DlwHb5S4IM"
    "96f6GbnQuW01wfOup+H5BVgBaswklH0Xh8zibWsp3pVqp+7n+/zLJ66MTeeqdCTsUm7KE8exazlW"
    "riVgFBAGyCyTQCg70OwbI9aroeqW8S/RgOOB67eWTOvRGbtcthsBILmoh3mhlOJMoiv4te949PHt"
    "zu7VcXtH2dH654xhgS8hGyi5klJKcV1+gua4WaGYOGvEADJ5ZFfxe+T1+IcKuC4zkU8zBcf4IYvf"
    "v7FHT/Zcq59LC5DQrIm07G3bMPIxvvvezalTOw+Um5F3DSwwiAEEgFVaJgbjbvrY2tN2uPDk5ej1"
    "0fkETVs7epitM1qH6XA6jnUb875xGUwBuH4ejlsEWwSnxHz/YYwLJReA+7RcWHPQAgAj8o4EQxwo"
    "1d15QHGtAxYRAxCIhGFMEAIBkUEkWnSY6JMWGfxRMa3nywCAps0d1aGIt0WLroGENol4wswgCZKw"
    "n7Mt+22xwN9ejMVGgOzCP2SQCSwU+m8zyyyFFGcwTJPJBOUXnQoAYrEqqRwYlgQSkkVWAAgA/AL6"
    "PP4tYuSxKgAAAABJRU5ErkJggg=="
)

_WIZARD_ICON_32_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAFW0lEQVR4nO2WXWxURRTH/2fm3r3d"
    "7lJaWhogED6CNelDjVlFvhcCCSJqULNrwKQaGlZS/CBRIPFlqUpIlCeNJi0EJWogXUwMMcb0QWgg"
    "9sXVF9MAVlACaaDdFvaru/femePDttAvyq0QnzzJJnPv3nPmP//5zckADyniiIuHVetBgv7zGSOR"
    "dgkwvbisdeumhkMfAqBwOG54zX9IthGbsnwfCHuXz4+UdXa2uPDoxgMJiETaZSIRVY1rTq21fMEV"
    "StlFq7w+MJ0aD8UBTfr9fDHFgoyAackmAAiFYp624V8JYAa1xlrNRCKqtq0+HjalP+y4eYdICGhU"
    "AuwZxmlTywwiAg+PxbZVX//kt6rCA5nLTnao3ySiPkfzks7uluxwfZ6q3rQdIAL3nd89j3ntI0t9"
    "5x73W8Gw6+YVQEbpf+H327bfa71pCeDfIz6+8uqcWZXpfbi26MuNG68cJGIGEYiImJVjyLKA67d2"
    "AN448CyAOS5wNUMYUh+JgNgJxsod2/7YlCsUiOFK282DSIBANB0OPDPADEEEzd0vzAVVXHUVY8/+"
    "9dSXmiFNs4gbgz1gaBYkSbPqczU8ceB9C86GS98utjcfPR668FnrMrFm1XUq2gJEAFFpLULwtDjw"
    "LIDWn1UAcGDnlu87zsyp7vplnvihYzEFAw60Lk1uSKZcjhyfLAtojxx4FhALtRnMoAs9VbtmBoNz"
    "DdN2XNcgoLR6AqE/ZeDJx/IAiAoFUemFA08C2tvb5cb9VZrout8qoz0FJ8dgNog0iAhFJw+Qi12N"
    "AzjUcs14eWsvrDLVVD/7QCCZbHMwBWueBESjURWNRtWh2LcnisVglSFtLSVISoYhARJZpDPAwgU2"
    "rAU25tTayOYM/4Z1A/flYEoBHI8LZhBfaGzg7PZ9z2y++vysqhTf6AvI22kLt26VfqlBC9m8wLET"
    "1Yg+W0dfnKxyHLs8cPFS9X05mBKQs+sg+hIRjjTwYmR9TfNqis7mjX9K2zGJiIf7skDRycFRWRSL"
    "BsAMaQBbNig6+Z1ZCcQF0HvPOSYTQBFExOVQlVg3oxe0PuFy9yurIf11NbP7nedeuikguHSyR044"
    "EUDi7rNkAzkTpzsWNgHyAwBOfX3E193d7gA0pieMhoPC4bgcvkzciU93757X3HzrN2GIGmWDGDQR"
    "KB7bZ1wFllVM3xyrzu49XF/Xn399jAURRGQCCTVeAAAgXN8cdF1zjSmsZZlc7qlF82euPtF2PWha"
    "DkHR5DyPe8eKQJUuTn1Vywc/CaYqgukjyqUMUfDo+Z5DfeNTCQA3NLwTCOaddwG8QSRqLNNCalDj"
    "rSYD2xt7odIEeQ9kNasJhpBkZNImXnu7FpmshiEZSqs0ILpct3B4wRM3ziQS9UyhUMxMJtucFUvf"
    "PBjw1byXL6YcAEKzq/xWtVw491EhpEuT9xQCs0Iq8xeY1QQrCEBuCDw0dNsFAAYL0/BLpYpg6av4"
    "+eLHGWPJkkGdTALMOFd0bt80pFXLYECTdFQWl/7+1bmzxTT5qWFW4FGTMkMToBmAkEyCyAQRTGFB"
    "swsNfXqmKthAXIyRHKqL1ViqLMaCwhJyuWa3wpR+lNBmuNrGXfwxbnw3BBkQpfsJGAxXFbMA56Xw"
    "HYVG57mewx0jiaOy4wJo0SNPTy+NV6QxsFxS2UrNRaUBPzF2QpCvtLZJnCDWkkyh2e0C0AUiSVoP"
    "GdI8AqNQ6Oz+PDs+Z7x8CoVixnD/nhDh+ubgkH0vFAFDlnGFKqcfe1rSk+aH40ZtZzePHMHJBIx5"
    "P9KQACAYnMvje8RUEQrFzJFxMtnqDpecYN10b8Vev5/yJvx/jI5/ALuMT2VKtFXdAAAAAElFTkSu"
    "QmCC"
)

_WIZARD_ICON_48_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAI/UlEQVR4nO1Za2wc1RX+zr13Zh9O"
    "/AjCFFJMgNBE6xgoTkIaHg7QlDZFRK06EYKoDWprhJSSCFoqWonNUKhKKYEINVVSUAVR+vAUVUUq"
    "jRDQWFQopBipoXYLNSYJFIcAfqy93p2Ze+/pj10TkzhxvGvoj+aT5s/smXPPd8+553wzC5zCtED/"
    "6wCqwYfBL1v2YGqmnIqZcjQFqL21XX2j7S/111285Tfu0NDFAOB5HbJax58IAc/rENu7tmnHxbw5"
    "tU03gMKb2lu3OZlMN1fr+5OqSQLAa68MXsoXP1g8MvauUOn6ul17N+SqdaxmILgpwJTFJnr9is8s"
    "UcJdSgC0jXLPzkDwwCdQQttau5QP3wqIrcyW88VB44hE6gst97QDQDabrSqGj5VAe+s255auxfGa"
    "5TtvSrkN5xWiIR3GI6xkwjFsN3qeJ3fvri6Gj5MAAcCNl+9scKW7CqAGBkAkqHRy7VtBEJhqF/lY"
    "CDBnRanztGvAOS+dqL+xEA3GBDgAyNrYKJFceE1zdsWKFbDVtNMZJ8DsSSLfBsEaCxADZmshHLJE"
    "QgEAEQnL2jgy3QSi1b7vM7q7KyYw412IKDDc/fXm3R3nvvZY54JWwc5SYzUTxISWTbCsGdYeBFDV"
    "LJj5DHSvvTOObHCV72tY2i4oYcFsj7KSxkasVHL15zPZJjQ3m0q70YwQYAZx79pG7vBcbelbzlzb"
    "9ORP7ulkRhMoLxgkAIBofDmS2hStK2vaiLAwCNaYnp7mioZq1QSYQej2HET8FJbWhALmbAyomq+u"
    "673Sv2tPvdYMAAQwYl3A+PAnCMQ2NAzzVjXrz0AGsoTmjIZNrgLRbjHLcaFi3fNKrbn3gaWstYQQ"
    "gLUWubF+CBIAGCAIZi0BtbG1tb1iXVQ1ASLf4s8vObTosYFwON6N1GyBZGS7950hDx2eRalkDOZx"
    "2480G2FtBCmcdinPTPm+byfzPxWq7kKlthmEo6+sW5VYmL/59hsu2k9YNu/ezU9xX1897Xn5LMye"
    "HcMY4NiGQ9A2zu3d61esi2aghAL20CEdZd/etXXh1gNvNg3sP9hgHv5RGw/lklCO/TADE0EEgCxL"
    "UulrWrIV66IZKCHYkfn9KnHhjn2/ePyS+k+d4VySrhk0Xa+eIfr21yOZ0McQIAIsA4UiWSWVAlPF"
    "uqhqAp7XIXf1bghvvvp3mcbTnO8Njb4bsVVuOhXDdTWYx7tjiYUQDGMBRcD8cyJoCxBVrotmgECA"
    "Dq9DFkOzUWujUD5X1tKE4EsHmAgohgIffODg7h+8gy+vzIk3DgiTchMV66KqCaxZE5hbAzedcBLf"
    "jk0RdGRalcEQJDAW9mMoB3zp6hx2PvEGli/JY/mledq59d/GkekmayvTRRUTYM6qp7dsSfDg6nlr"
    "V488by1FwNGSYRyEQlRA7SyNXc/XImkB1BqctaiAPz1Xh6Ecs3Ir00UVEyDy9aoNG0LArmtZoBb3"
    "HxbsOFYIwZjskkLAcRiFogAsYccvG/HmvhTYkgx1xK50K9JF054D5b5vuGftfZjlLMJ70aK2lS/a"
    "2fWN7uO/bkG6RsN+5DgyBCmM5iWiWIEIuPunZ6Lr72mcf04DICDDMNImrmtTNLAwCNYcnM45qGCQ"
    "dVjmTQL/7HsmLnLknK6ufzloNPsPNIhlS96ZjDKIJIbzOcS6CCEIhaLA9dcOoxAS2AILFlgMHlbm"
    "b71y2rpo2gqQOauIfM3dN3ahseYSvDsWI2kdSAtILlXx0V4ZAMkj9wlH7GICGiP7+0eaxF0/O237"
    "b+87sH7xLWca4OSkxbQy0Nra7my6Bc7TW74jIQbzGNMGgoQtqkmn7clAa4KSLIqxxmmzRHtXV8Od"
    "HnpGg5N8fsoMePDk4bYMAcALL/jaWoAP3bQRlH4QAwUNhltZ6EdgLIBZwHfvmDvy8JP31wJAW1tW"
    "AcCKTlj/BNmYJANZ4aGHApQmY4DAoLP0y7UXrV/31n/S5zz3x0MrrvlKLIyGlFV/3QTABKkMiOBc"
    "dt4D94pk71Odnf5eAONLAyhtZoDAYkK7Vcd4AtkAwMoL76gZGbCWUnqzgttiODZjRXtlOjEHQ0O1"
    "0GP7YHRK8sm07inqyxgCxwCIEkqJH+pI3bp8/m37lEi5sSk8zqHckZC1HBzwi+UYP3x2QgllBeDb"
    "ZZ/+5pxkuvGzoc0HAkgSqRSRhBCMoZzmqy+X8eZHD0oMQZ7cFOHyAS6/yByvaqUFRhx88WtnR0PD"
    "edd1XBAI2oYQ5BQsR/9wRPr2ztfv/+uE2Hk8A9TWBmHfvn2ulQhIiEvJlmwsx5ZZM7GF6yhhoxb3"
    "D7+aDVuQOFo0TBY8kUQUjyCMRssvNMfJBpX0E9h1lSyyNqEFEQiQlnWKIJcIoV743PzbHnV7G25d"
    "AVgffkltlWvLXHbubSsTybpnCuFAjoSsPeKbYKzG6Q3nI+3OxchoaSBNVTwMhhIOcvl+DOf7IYWD"
    "qUpuTj1Dm7Ey4Yk7xBaMolLJdD6Xrunq98eA8hnIIMNAVhh6/1BsCu8l3LrTo3g0ZjARQTJAQkgM"
    "5t7GIB2ElHZ6qkUCdbVTmzGAsWJpSBwJni0zWyKhkk5tuqBzLw/XFA3KJSQAwIdvPa+Z9vT9/NU4"
    "Ll7H1v5YCuW4Kq0EKSrlgGBsZI0xJorYRHH50syxZpz4wnGvSLONYpgohok1DHNJiBAIAEEIRySc"
    "WgXmgZhjn115bW/vI2EWWQKOPVHjMxLLL1h/BRnBLHgzkdNiWRtJqkaQ/EgZWNaw1kRUekmcTl6I"
    "wSyF404slfJGwbIdUTLpxDZ8IiFSO0KKhve89tCrxzg5+oYHT/a1Noiuru0xAHieJw93Z1LIQ0fu"
    "wEMKiUWGQwuQYrAlRibh1M2xpT44jfgBQRJhPPIvJn6/3BtjJdMq1oUdrh5+Ik5mnBdf+/7IuH0m"
    "k3V7evwYEzbquCt68CRQHmQnwLIL1i9NiNmronhEg+jkpQmTUU5KJmI89Gzf/cMnMi01mQxPpo+m"
    "tWUTZQU6AbQBnZ2+no6PyTAuG8YxlXyYiKr/5PPgye5MRgI9ADLTeLJk39OzKS59hj+FUziF/0v8"
    "F5zkXBlsXD1uAAAAAElFTkSuQmCC"
)


# Shown in the footer bar of the persistent wizard window.
WIZARD_AUTHOR = "CottonKendy"
WIZARD_VERSION = "Version 0.1a"

# Default size for the persistent wizard window. Set once, right after
# creation below -- without an explicit size, Tk auto-fits the window to
# each step's own content, which is what made it visibly grow/shrink every
# time the wizard moved to a new step. Fixing it here keeps it a consistent
# size across every step, while still leaving it resizable by hand.
WIZARD_DEFAULT_WIDTH = 900
WIZARD_DEFAULT_HEIGHT = 700


def _ensure_wizard() -> dict:
    """Lazily builds the persistent wizard window (root + sidebar + content
    area) the first time it's needed, and returns the same dict on every
    later call. Nothing here talks to Siril -- it's pure Tk state."""

    if _WIZARD.get("root") is not None:
        return _WIZARD

    root = ThemedTk()
    root.title("Siril Multi-Filter Wizard")
    root.geometry(f"{WIZARD_DEFAULT_WIDTH}x{WIZARD_DEFAULT_HEIGHT}")
    root.minsize(640, 480)
    apply_dark_theme(root)
    _set_windows_dark_titlebar(root)
    root.protocol("WM_DELETE_WINDOW", _on_wizard_window_closed)

    # tk.PhotoImage keeps only a weak reference to its pixel data internally,
    # so the PhotoImage objects themselves must be kept alive for as long as
    # the window uses them -- stashed on _WIZARD (never a local variable)
    # for exactly that reason. iconphoto(True, ...) applies to this window
    # and any future Toplevel of it (the crop tool's popup included).
    try:
        icon_images = [
            tk.PhotoImage(data=_WIZARD_ICON_16_B64),
            tk.PhotoImage(data=_WIZARD_ICON_32_B64),
            tk.PhotoImage(data=_WIZARD_ICON_48_B64),
        ]
        root.iconphoto(True, *icon_images)
        _WIZARD["icon_images"] = icon_images
    except tk.TclError as e:
        # Never worth failing the whole wizard over a missing/odd icon.
        pass

    # Footer bar: author/version at the bottom left, and an "Always on top"
    # checkbox that toggles the window's own -topmost attribute live (no
    # need to reopen it). Packed with side="bottom" BEFORE "body" below, so
    # it claims its strip of space first and "body" fills the rest --
    # packing it after "body" (which expands to fill everything) would
    # leave it no room.
    footer = ttk.Frame(root, style="Card.TFrame", padding=(14, 6))
    footer.pack(side="bottom", fill="x")
    ttk.Label(
        footer, text=f"{WIZARD_AUTHOR}    {WIZARD_VERSION}", style="Brand.TLabel",
    ).pack(side="left")

    topmost_var = tk.BooleanVar(value=True)

    def _on_topmost_toggle() -> None:
        root.attributes("-topmost", topmost_var.get())

    ttk.Checkbutton(
        footer, text="Always on top", variable=topmost_var, command=_on_topmost_toggle,
    ).pack(side="right")
    root.attributes("-topmost", topmost_var.get())

    body = ttk.Frame(root)
    body.pack(fill="both", expand=True)

    sidebar = ttk.Frame(body, style="Card.TFrame", padding=(18, 20))
    sidebar.pack(side="left", fill="y")
    ttk.Label(sidebar, text="STEPS", style="Brand.TLabel").pack(anchor="w", pady=(0, 12))
    steps_list = ttk.Frame(sidebar, style="Card.TFrame")
    steps_list.pack(fill="both", expand=True)

    content = ttk.Frame(body)
    content.pack(side="left", fill="both", expand=True)

    _WIZARD.update({
        "root": root,
        "sidebar": sidebar,
        "steps_list": steps_list,
        "content": content,
        "rows": {},     # step key -> {"frame", "glyph", "label", "text"}
        "order": [],    # step keys, in the order they were added
    })
    return _WIZARD


def wizard_add_step(key: str, label: str) -> None:
    """Adds a new row to the sidebar checklist, marked "pending". Safe to
    call again for a key that already exists (does nothing)."""

    wizard = _ensure_wizard()
    if key in wizard["rows"]:
        return

    row = ttk.Frame(wizard["steps_list"], style="Card.TFrame")
    row.pack(fill="x", anchor="w", pady=3)
    glyph = ttk.Label(row, text=STEP_GLYPH["pending"], width=2, style=STEP_STYLE["pending"])
    glyph.pack(side="left")
    text = ttk.Label(row, text=label, style=STEP_STYLE["pending"])
    text.pack(side="left")

    wizard["rows"][key] = {"glyph": glyph, "text": text, "status": "pending"}
    wizard["order"].append(key)


def _wizard_set_row_status(key: str, status: str) -> None:
    wizard = _ensure_wizard()
    row = wizard["rows"].get(key)
    if row is None:
        return
    row["glyph"].configure(text=STEP_GLYPH[status], style=STEP_STYLE[status])
    row["text"].configure(style=STEP_STYLE[status])
    row["status"] = status


def wizard_progress() -> tuple[int, int]:
    """Returns (steps_done, steps_total) across every step registered so
    far in the sidebar -- used to drive the overall-progress bar. The total
    grows over the run as later steps (per-filter stacking, etc.) get added
    once they're known, so the fraction can jump partway through -- same as
    the sidebar list itself does."""

    wizard = _ensure_wizard()
    order = wizard.get("order", [])
    rows = wizard.get("rows", {})
    done = sum(1 for k in order if rows.get(k, {}).get("status") == "done")
    return done, len(order)


def wizard_set_current(key: str) -> None:
    """Marks step `key` as the one in progress right now."""
    _wizard_set_row_status(key, "current")


def wizard_mark_done(key: str) -> None:
    """Marks step `key` as completed."""
    _wizard_set_row_status(key, "done")


def wizard_close() -> None:
    """Really closes the persistent wizard window, at the very end of the
    run (success or abort) -- everything else (".destroy()" calls made by
    individual step dialogs) only ends that step's wait; this is what
    actually tears the window down so it doesn't linger on screen after
    the script itself has finished."""

    root = _WIZARD.get("root")
    if root is not None:
        try:
            root.destroy()
        except tk.TclError:
            pass
    _WIZARD.clear()


def _new_root(siril: "s.SirilInterface", title: str = "Siril Multi-Filter Wizard") -> tk.Widget:
    """Returns the persistent wizard window's content area, cleared and
    ready for this step's widgets, with its title updated. Despite the
    name/signature staying the same as when this created a brand-new
    window each time, it's now the SAME window every call -- every caller
    still does root.mainloop() / root.bind(...) / root.destroy() exactly as
    before; those are transparently redirected to the persistent root (and
    "destroy" to a non-destructive "end this step, keep the window open")
    via the attribute overrides below."""

    wizard = _ensure_wizard()
    real_root = wizard["root"]
    real_root.title(title)

    content = wizard["content"]
    for child in list(content.winfo_children()):
        child.destroy()

    # Some steps (the phase 3 script/tool picker) bind mousewheel scrolling
    # directly on the persistent root itself, not on their own canvas, so
    # scrolling works no matter which child widget the mouse is over -- but
    # that means the binding survives past that step unless it's explicitly
    # cleared here. Left in place, it kept firing on every later screen too,
    # calling back into a canvas this step's cleanup just destroyed above
    # (_tkinter.TclError: invalid command name "...canvas" in Siril's log
    # whenever the wheel was used anywhere afterward). Clearing it on every
    # transition means only a step that rebinds it (because it actually has
    # a scrollable area) has it active at all.
    for _seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        try:
            real_root.unbind(_seq)
        except tk.TclError:
            pass

    # A plain Tk widget's .mainloop()/.quit() already operate on the whole
    # shared Tcl interpreter (not just that widget), so those work as-is.
    # Only ".destroy()" needs overriding: called at the end of every step's
    # dialog, it must end that step's wait WITHOUT tearing down the
    # persistent window the way a real root.destroy() would.
    content.destroy = real_root.quit
    content.bind = real_root.bind

    return content


def _new_popup_root(siril: "s.SirilInterface", title: str) -> tk.Toplevel:
    """A genuinely separate window (its own OS-level window, shown
    alongside the persistent wizard window rather than replacing its
    content) -- used only for the interactive crop tool, which is big and
    benefits from being its own resizable window. It's a Toplevel of the
    wizard's root rather than a whole separate Tk application, so it still
    shares the same underlying event loop -- .mainloop()/.destroy() on it
    behave exactly as a caller expects (mainloop() blocks until this
    window's own "Continue"/"Cancel" closes it; destroy() then both closes
    this window for real AND stops that wait, unlike the persistent
    window's content area, which never really closes until the whole
    script ends)."""

    wizard = _ensure_wizard()
    popup = tk.Toplevel(wizard["root"])
    popup.title(title)
    popup.attributes("-topmost", True)
    popup.geometry(f"{WIZARD_DEFAULT_WIDTH}x{WIZARD_DEFAULT_HEIGHT}")
    popup.minsize(640, 480)
    apply_dark_theme(popup)
    _set_windows_dark_titlebar(popup)

    real_destroy = popup.destroy

    def _close_and_stop_waiting():
        real_destroy()
        wizard["root"].quit()

    popup.destroy = _close_and_stop_waiting

    # Default the OS "X" button to the same safe path as a normal
    # destroy() -- without this, Tk's default WM_DELETE_WINDOW handling
    # destroys the Toplevel at the Tcl level directly, bypassing the
    # Python-level override above, so wizard["root"].quit() would never
    # fire and the caller's mainloop() would hang forever. Callers that
    # need custom "X equals Cancel" behaviour (e.g. clearing a result
    # dict first) can still override this afterward with their own
    # root.protocol("WM_DELETE_WINDOW", ...) call.
    popup.protocol("WM_DELETE_WINDOW", popup.destroy)

    # A modal grab: the persistent wizard window still has its own
    # buttons live underneath this popup (unlike a real dialog, closing
    # the popup doesn't hand control back through the OS), so without
    # this a stray click on the window behind could re-enter that
    # screen's own button handlers while this popup is still open.
    try:
        popup.grab_set()
    except tk.TclError:
        pass

    return popup


def _header(parent, text: str) -> ttk.Frame:
    """SyQon-style brand block: small caps app name, then the step title,
    left-aligned at the top of the window."""

    wrap = ttk.Frame(parent)
    wrap.pack(fill="x", padx=24, pady=(20, 12))
    ttk.Label(wrap, text=APP_NAME, style="Brand.TLabel").pack(anchor="w")
    ttk.Label(wrap, text=text, style="Header.TLabel").pack(anchor="w", pady=(2, 0))
    return wrap


def _card(parent, title: str | None = None) -> ttk.Widget:
    """A dark card panel, optionally with a titled border (ttk.LabelFrame)
    like SyQon's 'Essentials' / 'Advanced' sections, or a plain untitled
    card when title is None."""

    if title:
        frame = ttk.LabelFrame(parent, text=title, padding=14)
    else:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=14)
    frame.pack(fill="both", expand=True, padx=24, pady=(0, 10))
    return frame


def _button_row(parent) -> ttk.Frame:
    """The bottom button area for a step, with a thin "Overall progress" bar
    (steps done out of every step registered in the sidebar so far) stacked
    just above it. There's no per-step bar here anymore -- these dialogs are
    all moments where the script is just waiting on you, not actually doing
    anything, so an animated bar here would be misleading. The per-step
    progress indicator only shows up during actual background work -- see
    run_with_progress()."""

    progress = ttk.Frame(parent)
    progress.pack(fill="x", padx=24, pady=(4, 0))

    done, total = wizard_progress()
    overall_label = f"Overall progress ({done}/{total})" if total else "Overall progress"
    ttk.Label(progress, text=overall_label, style="Card.TLabel").pack(anchor="w")
    overall_bar = ttk.Progressbar(
        progress, style="Wizard.Horizontal.TProgressbar", mode="determinate",
        maximum=max(total, 1), value=done,
    )
    overall_bar.pack(fill="x", pady=(2, 0))

    row = ttk.Frame(parent)
    row.pack(fill="x", padx=24, pady=(6, 20))
    return row


def _wrapping_label(
    parent, text: str, style: str = "Card.TLabel", min_width: int = 200,
    **pack_kwargs,
) -> ttk.Label:
    """A ttk.Label whose wraplength tracks its own current width, so long
    text reflows to fit whenever the window is resized instead of staying
    cut off at a fixed wrap width (or leaving an oddly wide gap if the
    window is wider than a fixed wraplength would use)."""

    label = ttk.Label(parent, text=text, style=style, justify="left")
    pack_kwargs.setdefault("anchor", "w")
    pack_kwargs.setdefault("fill", "x")
    label.pack(**pack_kwargs)

    def _update_wrap(event, lbl=label):
        lbl.configure(wraplength=max(min_width, event.width))

    label.bind("<Configure>", _update_wrap)
    return label


def run_with_progress(
    siril: "s.SirilInterface", title: str, message: str, work_fn,
    status_holder: dict | None = None,
):
    """Runs work_fn() (a zero-argument callable that does actual blocking
    Siril work -- run_ssf(), siril.cmd("convert", ...), etc.) on a
    background thread while showing a step screen with a progress bar, so
    the window stays responsive and the bar keeps moving for the WHOLE
    duration of the real work instead of freezing (Siril's cmd() calls
    block with no progress callback, so there's no true percent-done signal
    to show -- this climbs gradually and slows down the longer it runs, then
    jumps straight to full the instant work_fn() actually finishes, rather
    than looping or guessing at real time remaining).

    status_holder, if given, is a plain dict the CALLER keeps a reference
    to and updates from inside work_fn (e.g. via run_ssf's on_line
    callback) -- its "text" key is polled and mirrored onto a status line
    below the progress bar. This is the closest available stand-in for
    Siril's own progress bar/status text (e.g. "Rejection stacking in
    progress..."): sirilpy has no method to read that back from a script,
    only update_progress()/reset_progress() for a script to report ITS OWN
    progress outward -- so instead this shows the actual .ssf command
    currently executing, which is real information Siril's own bar doesn't
    give you either. Plain dict reads/writes are safe here without a lock;
    CPython's GIL makes a single dict item assignment atomic, and this is
    the only place either thread touches it.

    Returns work_fn()'s return value; re-raises any exception it raised,
    after the window has closed."""

    root = _new_root(siril, title)
    _header(root, title)

    card = _card(root)
    _wrapping_label(card, message)
    status_label = None
    if status_holder is not None:
        status_label = _wrapping_label(
            card, status_holder.get("text", ""), style="Brand.TLabel",
            pady=(6, 0),
        )
    bar = ttk.Progressbar(
        card, style="Wizard.Horizontal.TProgressbar", mode="determinate",
        maximum=100, value=0,
    )
    bar.pack(fill="x", pady=(18, 0))

    outcome: dict = {}

    def _worker():
        try:
            outcome["result"] = work_fn()
        except Exception as e:  # noqa: BLE001 -- re-raised on the main thread below
            outcome["error"] = e
        finally:
            outcome["done"] = True

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    def _tick():
        if not bar.winfo_exists():
            return
        if status_label is not None and status_holder is not None:
            status_label.configure(text=status_holder.get("text", ""))
        if not outcome.get("done"):
            # Ease toward 90% -- slows down the closer it gets, so it never
            # visually finishes on its own without real work actually being
            # done, however long that takes.
            current = bar["value"]
            bar["value"] = current + (90 - current) * 0.04
            bar.after(80, _tick)
        else:
            # The real work just finished -- snap to full immediately, then
            # close this step a moment later so the "full bar" is visible.
            bar["value"] = 100
            root.after(250, root.destroy)

    _tick()
    root.mainloop()
    _check_not_closed()

    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")


def show_message(siril: "s.SirilInterface", title: str, message: str, kind: str = "info") -> None:
    """Themed replacement for tkinter.messagebox so pop-ups match the rest
    of the UI instead of jarring back to a plain OS dialog box."""

    root = _new_root(siril, title)
    _header(root, title)

    card = _card(root)
    style = "Missing.TLabel" if kind == "error" else "Card.TLabel"
    _wrapping_label(card, message, style=style)

    btns = _button_row(root)
    ttk.Button(
        btns, text="OK", style="Accent.TButton", command=root.destroy,
    ).pack(side="right")

    root.mainloop()
    _check_not_closed()


def ask_yes_no(
    siril: "s.SirilInterface", title: str, message: str,
    yes_text: str = "Yes", no_text: str = "No",
) -> bool:
    """Themed Yes/No confirmation dialog."""

    root = _new_root(siril, title)
    _header(root, title)

    card = _card(root)
    _wrapping_label(card, message)

    outcome = {"yes": False}

    def on_yes():
        outcome["yes"] = True
        root.destroy()

    def on_no():
        outcome["yes"] = False
        root.destroy()

    btns = _button_row(root)
    ttk.Button(btns, text=yes_text, style="Accent.TButton", command=on_yes).pack(side="right")
    ttk.Button(btns, text=no_text, command=on_no).pack(side="right", padx=(0, 8))

    root.mainloop()
    _check_not_closed()
    return outcome["yes"]


def show_arrangement_notice(siril: "s.SirilInterface", cfg: dict) -> None:
    if cfg.get("hide_arrangement_notice"):
        return

    root = _new_root(siril, "Dataset folder layout")
    dont_show = tk.BooleanVar(value=False)

    _header(root, "Before we start")

    msg = (
        "Make sure your dataset folder is arranged like this:\n\n"
        "  Main folder\n"
        "    ├─ Red\n"
        "    │    ├─ lights\\*.fit\n"
        "    │    ├─ darks\\*.fit    (opt)\n"
        "    │    ├─ biases\\*.fit   (opt)\n"
        "    │    └─ flats\\*.fit    (opt)\n"
        "    ├─ Green\\lights\\*.fit  (+ darks/biases/flats, same as Red)\n"
        "    ├─ Blue\\lights\\*.fit  (+ darks/biases/flats, same as Red)\n"
        "    ├─ Luminance\\lights\\*.fit  (+ darks/biases/flats, same as Red)\n"
        "    └─ (etc. for H-alpha / OIII / SII or any other filter you have)\n\n"
        "Each filter gets its own folder, and every filter folder must "
        "contain a 'lights' subfolder with that filter's raw sub-exposures "
        "in it. Each filter folder can also have its own 'darks', 'biases', "
        "and 'flats' subfolders (that filter's own calibration sub-"
        "exposures) -- these are optional, so only add the ones you "
        "actually have calibration frames for.\n\n"
        "Before running this script, set Siril's Home/current working "
        "directory to this main folder (top toolbar, or the \"cd\" "
        "command) -- this script uses that as the main dataset folder "
        "instead of asking you to pick it again."
    )

    card = _card(root)
    _wrapping_label(card, msg)
    ttk.Checkbutton(
        card, text="Don't show this message again",
        variable=dont_show, style="TCheckbutton",
    ).pack(anchor="w", pady=(14, 0))

    btns = _button_row(root)
    ttk.Button(btns, text="OK", style="Accent.TButton", command=root.destroy).pack(side="right")

    root.mainloop()
    _check_not_closed()

    if dont_show.get():
        cfg["hide_arrangement_notice"] = True
        save_config(cfg)


def get_main_folder_from_siril_wd(siril: "s.SirilInterface") -> Path | None:
    """Used when the user confirms Siril's Home/CWD is already set to the
    main dataset folder -- the main dataset folder is then just whatever
    Siril's own current working directory already is. Returns None (with a
    message already shown) if Siril's CWD can't be read or doesn't look
    usable."""

    try:
        wd = siril.get_siril_wd()
    except Exception as e:
        show_message(
            siril, "Couldn't read Siril's working directory",
            f"get_siril_wd() failed: {e}\n\n"
            "Set Siril's Home/CWD (top toolbar, or the \"cd\" command) to "
            "your main dataset folder, then run this script again.",
            kind="error",
        )
        return None

    if not wd:
        show_message(
            siril, "No working directory set",
            "Siril didn't report a working directory.\n\n"
            "Set Siril's Home/CWD (top toolbar, or the \"cd\" command) to "
            "your main dataset folder, then run this script again.",
            kind="error",
        )
        return None

    main_folder = Path(wd)
    if not main_folder.is_dir():
        show_message(
            siril, "Working directory not found",
            f"Siril's current working directory doesn't exist on disk:\n{main_folder}\n\n"
            "Set Siril's Home/CWD to your main dataset folder, then run "
            "this script again.",
            kind="error",
        )
        return None

    return main_folder


def choose_filters(siril: "s.SirilInterface", main_folder: Path) -> list[str]:
    """Show a checkbox list of subfolders of main_folder for the user to
    confirm which ones are filter folders to process. Folders that already
    contain a 'lights' subfolder are pre-checked; everything else is
    listed too (unchecked) in case detection misses something."""

    subfolders = sorted(
        p.name for p in main_folder.iterdir()
        if p.is_dir() and p.name not in (
            REGISTRATION_DIR_NAME, PREPROCESS_DIR_NAME, IMAGE_PROCESSING_DIR_NAME
        )
    )

    if not subfolders:
        show_message(
            siril, "No folders found",
            f"No subfolders were found in:\n{main_folder}", kind="error",
        )
        return []

    root = _new_root(siril, "Select filter folders")
    _header(root, "Select filter folders")

    group = _card(root, "Detected folders")

    vars_by_name: dict[str, tk.BooleanVar] = {}

    for name in subfolders:
        has_lights = (main_folder / name / "lights").is_dir()
        already_stacked = find_existing_raw_stack(main_folder / name, name) is not None
        var = tk.BooleanVar(value=has_lights)
        vars_by_name[name] = var
        label = name
        if not has_lights:
            label += "  (no 'lights' subfolder found)"
        elif already_stacked:
            label += "  (already stacked)"
        cb = ttk.Checkbutton(
            group, text=label, variable=var, style="TCheckbutton",
        )
        cb.pack(fill="x", anchor="w", pady=2)
        if not has_lights:
            tksiril.create_tooltip(
                cb, "No 'lights' subfolder was found here -- double check "
                    "this is really a filter folder before ticking it."
            )

    result: dict[str, list[str]] = {"selected": []}

    def on_ok():
        result["selected"] = [n for n, v in vars_by_name.items() if v.get()]
        root.destroy()

    def on_cancel():
        result["selected"] = []
        root.destroy()

    btns = _button_row(root)
    ttk.Button(btns, text="OK", style="Accent.TButton", command=on_ok).pack(side="right")
    ttk.Button(btns, text="Cancel", command=on_cancel).pack(side="right", padx=(0, 8))

    root.mainloop()
    _check_not_closed()
    return result["selected"]


# DSLR/mirrorless raw formats -- these cameras are, for all practical
# purposes, exclusively Bayer/color-sensor bodies (true dedicated
# monochrome camera bodies, like the Leica M Monochrom line, are a tiny
# niche), so the extension alone is a near-certain "this is color camera
# data" signal, no header parsing needed. ".dng" is included since several
# cameras use/convert to it natively, but it's also occasionally used by
# astro cameras, so it's a slightly softer signal than the brand-specific
# ones below.
RAW_CAMERA_EXTENSIONS = {
    ".cr2", ".cr3",   # Canon
    ".nef",           # Nikon
    ".arw",           # Sony
    ".raf",           # Fujifilm
    ".orf",           # Olympus / OM System
    ".rw2",           # Panasonic
    ".pef",           # Pentax
    ".srw",           # Samsung
    ".dng",           # generic/Adobe, also used natively by some cameras
}


def read_fits_header_keys(fit_path: Path, keys: set[str]) -> dict[str, str]:
    """Reads just the primary FITS header (no image data) looking for the
    given keyword names, without needing astropy -- a FITS header is plain
    ASCII, laid out as 80-character "cards" in 2880-byte blocks, terminated
    by an "END" card, so this can stop as soon as it's seen that or found
    everything it's looking for. Returns {keyword: raw_value_string} for
    whichever of `keys` were actually present."""

    found: dict[str, str] = {}
    try:
        with fit_path.open("rb") as f:
            while True:
                block = f.read(2880)
                if len(block) < 2880:
                    break
                for i in range(0, 2880, 80):
                    card = block[i:i + 80].decode("ascii", errors="replace")
                    keyword = card[:8].strip()
                    if keyword == "END":
                        return found
                    if keyword in keys and "=" in card:
                        value = card.split("=", 1)[1].split("/", 1)[0].strip().strip("'").strip()
                        found[keyword] = value
                if len(found) == len(keys):
                    return found
    except OSError:
        pass
    return found


def detect_sensor_type(lights_dir: Path) -> str:
    """Best-effort check of whether a filter's 'lights' subs look like they
    came from a color (Bayer/OSC/DSLR/mirrorless) sensor rather than a
    genuine monochrome one -- used to flag a likely mismatch (e.g. color
    camera data sitting in what's meant to be a mono filter folder) on the
    calibration-frame screen. Checks just one sample light file: a raw
    camera extension (see RAW_CAMERA_EXTENSIONS) means "color" outright;
    for .fit/.fits, the "BAYERPAT" header keyword (present whenever the
    sensor has a Bayer color filter array) or a 3-plane "NAXIS3" (already
    debayered/RGB) both mean "color"; otherwise "mono". Returns "unknown"
    if there's nothing to sample or the extension isn't recognized."""

    if not lights_dir.is_dir():
        return "unknown"

    # Only needs the alphabetically-first file (any sample from this
    # filter's lights works equally well for the header check below, but
    # picking the same one every time keeps this deterministic run to
    # run) -- min() by name does that in one pass instead of sorting
    # every entry in the directory just to look at the first one.
    sample = min(
        (p for p in lights_dir.iterdir() if p.is_file()),
        key=lambda p: p.name, default=None,
    )
    if sample is None:
        return "unknown"

    ext = sample.suffix.lower()
    if ext in RAW_CAMERA_EXTENSIONS:
        return "color"

    if ext in (".fit", ".fits", ".fts"):
        header = read_fits_header_keys(sample, {"BAYERPAT", "NAXIS3"})
        if header.get("BAYERPAT"):
            return "color"
        naxis3 = header.get("NAXIS3", "").strip()
        if naxis3.lstrip("+-").isdigit() and int(naxis3) >= 3:
            return "color"
        return "mono"

    return "unknown"


def detect_calibration_frames(filter_dir: Path) -> dict[str, bool]:
    """Checks which of the optional 'darks'/'biases'/'flats' subfolders
    under a filter folder actually exist and contain at least one file --
    used to recommend which Mono_Preprocessing variant to stack that filter
    with (see recommend_ssf_variant)."""

    result: dict[str, bool] = {}
    for key in ("darks", "biases", "flats"):
        sub = filter_dir / key
        result[key] = sub.is_dir() and any(p.is_file() for p in sub.rglob("*"))
    return result


def recommend_ssf_variant(frames: dict[str, bool]) -> str | None:
    """Maps a filter's detected calibration frames to one of
    MONO_SSF_VARIANTS' keys. Returns None for combinations that don't map
    cleanly to an official script (darks-only, flats-only, biases-only, or
    darks+flats without biases) -- those are left for the user to pick
    explicitly in choose_calibration_scripts()."""

    d, b, f = frames["darks"], frames["biases"], frames["flats"]
    if d and b and f:
        return "full"
    if b and f and not d:
        return "no_dark"
    if d and b and not f:
        return "no_flat"
    if not d and not b and not f:
        return "none"
    return None


def choose_calibration_scripts(
    siril: "s.SirilInterface", main_folder: Path, selected_filters: list[str],
) -> dict[str, str]:
    """For each selected filter, looks at which calibration frames it
    actually has and recommends a Mono_Preprocessing variant to stack it
    with. Shows one screen listing every filter's detected frames and a
    dropdown (preset to the recommendation) so the user can confirm or
    override it -- combinations with no exact match are flagged and left at
    a sensible default, but still need the user to confirm since there's no
    single "correct" answer for those. Returns {filter_name: variant_key},
    using MONO_SSF_VARIANTS' keys."""

    root = _new_root(siril, "Calibration frames")
    _header(root, "Calibration frames")

    card = _card(root, "Detected per filter -- confirm or change the script")

    variant_labels = [MONO_SSF_VARIANTS[k][1] for k in MONO_SSF_VARIANT_ORDER]
    label_to_key = {MONO_SSF_VARIANTS[k][1]: k for k in MONO_SSF_VARIANT_ORDER}

    combos: dict[str, ttk.Combobox] = {}
    frames_by_filter: dict[str, dict[str, bool]] = {}
    any_ambiguous = False

    any_color_sensor = False

    for filter_name in selected_filters:
        frames = detect_calibration_frames(main_folder / filter_name)
        frames_by_filter[filter_name] = frames
        recommended = recommend_ssf_variant(frames)
        found = ", ".join(name for name in ("darks", "biases", "flats") if frames[name]) or "none"

        block = ttk.Frame(card, style="Card.TFrame")
        block.pack(fill="x", anchor="w", pady=5)

        row = ttk.Frame(block, style="Card.TFrame")
        row.pack(fill="x", anchor="w")

        text = f"{filter_name}  --  found: {found}"
        if recommended is None:
            text += "  (no exact match -- please pick one)"
            any_ambiguous = True
        ttk.Label(row, text=text, style="Card.TLabel", anchor="w").pack(
            side="left", fill="x", expand=True
        )

        combo = ttk.Combobox(
            row, state="readonly", width=30, values=variant_labels,
        )
        combo.set(MONO_SSF_VARIANTS[recommended or "full"][1])
        combo.pack(side="right")
        combos[filter_name] = combo

        sensor = detect_sensor_type(main_folder / filter_name / "lights")
        if sensor == "color":
            any_color_sensor = True
            _wrapping_label(
                block,
                f"⚠ '{filter_name}' lights look like they're from "
                "a color camera (Bayer/OSC/DSLR/mirrorless), not a "
                "genuine mono sensor -- double check this is the "
                "right folder.",
                style="Warning.TLabel", pady=(2, 0),
            )

    if any_ambiguous:
        _wrapping_label(
            card,
            "Some filters don't have an exact matching script -- their "
            "calibration frames are an unusual combination (e.g. darks "
            "only, with no biases or flats). Pick whichever variant best "
            "matches what you actually have for those before continuing.",
            pady=(10, 0),
        )

    if any_color_sensor:
        _wrapping_label(
            card,
            "One or more filters flagged above look like they contain "
            "color camera data rather than genuine mono sensor data -- "
            "this is just a heads-up based on the file format/FITS header "
            "of one sample light, not a hard block. Double check those "
            "folders before continuing if that's unexpected.",
            pady=(10, 0),
        )

    result: dict[str, str] = {}

    def on_continue():
        chosen = {filter_name: label_to_key[combo.get()] for filter_name, combo in combos.items()}

        mismatches: dict[str, set[str]] = {}
        for filter_name, variant_key in chosen.items():
            frames = frames_by_filter[filter_name]
            required = MONO_SSF_REQUIRED_FRAMES[variant_key]
            missing = {r for r in required if not frames[r]}
            if missing:
                mismatches[filter_name] = missing

        if mismatches and not confirm_calibration_mismatches(siril, chosen, mismatches):
            return  # stay on this screen so the user can change a dropdown

        result.update(chosen)
        root.destroy()

    btns = _button_row(root)
    ttk.Button(
        btns, text="Continue", style="Accent.TButton", command=on_continue,
    ).pack(side="right")

    root.mainloop()
    _check_not_closed()
    return result


def confirm_calibration_mismatches(
    siril: "s.SirilInterface", chosen: dict[str, str], mismatches: dict[str, set[str]],
) -> bool:
    """Warns before running a chosen script against a filter that's missing
    one or more of the folders that script's own .ssf will "cd" into --
    exactly the situation that crashes the run partway through with a
    "No such file or directory" error. Returns True to run anyway, False to
    go back and pick something else.

    Shown as its own popup window (_new_popup_root), NOT via _new_root --
    this is called from inside choose_calibration_scripts' own on_continue
    handler, while that screen's mainloop() is still running. Reusing
    _new_root here would clear the persistent window's shared content area
    out from under the calibration picker (destroying its dropdowns) and
    rebuild this confirmation in the same spot; if the user then clicked
    "Go back", control would return to on_continue with nothing left on
    screen to interact with -- a stranded window that could cascade into a
    KeyError further downstream. A separate popup leaves the calibration
    picker fully intact underneath, so "Go back" actually gets you back to
    it."""

    root = _new_popup_root(siril, "Are you sure?")
    _header(root, "Are you sure?")

    card = _card(root, "These filters are missing folders their chosen script needs")

    for filter_name, missing in mismatches.items():
        variant_key = chosen[filter_name]
        script_name, variant_label = MONO_SSF_VARIANTS[variant_key]
        _wrapping_label(
            card,
            f"{filter_name}: chose \"{variant_label}\" ({script_name}), but "
            f"couldn't find a '{'/'.join(sorted(missing))}' subfolder here. "
            "This will very likely fail partway through with a "
            "\"directory not found\" error.",
            pady=(0, 8),
        )

    _wrapping_label(
        card,
        "Go back and pick a variant that matches what you actually have, "
        "or continue anyway if you're sure (e.g. you know the folder will "
        "be created before this filter's turn comes up).",
        pady=(4, 0),
    )

    outcome = {"run_anyway": False}

    def on_go_back():
        outcome["run_anyway"] = False
        root.destroy()

    def on_run_anyway():
        outcome["run_anyway"] = True
        root.destroy()

    btns = _button_row(root)
    ttk.Button(
        btns, text="Run anyway", style="Accent.TButton", command=on_run_anyway,
    ).pack(side="right")
    ttk.Button(btns, text="Go back", command=on_go_back).pack(side="right", padx=(0, 8))

    root.mainloop()
    _check_not_closed()
    return outcome["run_anyway"]


def ask_misc_step_count(
    siril: "s.SirilInterface", cfg: dict, config_key: str = "phase3_misc_count",
) -> int:
    """Numeric prompt for how many extra "Misc/Other" steps to add to the
    pipeline being configured (phase 3's, or -- reusing this same screen
    with config_key="phase4_misc_count" -- phase 4's separate starmask
    pipeline), on top of the five fixed steps (Background Extraction/
    Denoising/Sharpening/Star Removal/Stretching). Each Misc/Other step can
    be assigned any installed script, not just ones PY_SCRIPT_CATALOG
    recognizes as belonging to one of the five -- useful for narrowband
    tools, color calibration, satellite trail removal, etc. Remembers the
    last count entered (under config_key) as the default for next time."""

    root = _new_root(siril, "Misc/Other steps")
    _header(root, "Misc/Other steps")

    card = _card(root)
    _wrapping_label(
        card,
        "Besides Background Extraction, Denoising, Sharpening, Star "
        "Removal, and Stretching, how many extra \"Misc/Other\" steps "
        "would you like in your pipeline? These can run any installed "
        "script (narrowband tools, color calibration, satellite trail "
        "removal, etc.), and you can place them anywhere in your process "
        "on the next screen.",
    )

    value = tk.StringVar(value=str(cfg.get(config_key, 0)))
    spin = ttk.Spinbox(card, from_=0, to=10, textvariable=value, width=6)
    spin.pack(anchor="w", pady=(10, 0))

    result = {"count": 0}

    def on_continue():
        try:
            result["count"] = max(0, min(10, int(value.get())))
        except ValueError:
            result["count"] = 0
        root.destroy()

    btns = _button_row(root)
    ttk.Button(
        btns, text="Continue", style="Accent.TButton", command=on_continue,
    ).pack(side="right")

    root.mainloop()
    _check_not_closed()

    cfg[config_key] = result["count"]
    save_config(cfg)
    return result["count"]


def _describe_step_choice(step: dict) -> str:
    """One line for the reuse-confirmation summary: the step's label plus
    whatever tool/script it was last set to (or "None (skip)")."""

    picked = step["scripts"][0] if step["scripts"] else None
    return f"{step['label']}: {picked if picked else 'None (skip this step)'}"


def _confirm_reuse_phase3_choices(
    siril: "s.SirilInterface", steps: list[dict], label_prefix: str = "phase 3",
) -> bool:
    """Shown only when a previous run's pipeline configuration was found for
    the exact same step set (same fixed steps, same Misc/Other count) --
    lists what each step was last set to, and asks whether to reuse that
    configuration as-is (skipping the per-step pickers and the reorder
    screen entirely) or step through every screen again to review/change
    it. label_prefix lets this same screen also serve the phase 4 starmask
    pipeline ("this dataset's starmask pipeline...") without a separate
    near-duplicate function. Returns True for "reuse", False for
    "review"."""

    root = _new_root(siril, f"Reuse previous {label_prefix} setup?")
    _header(root, "Use your previous pipeline setup?")

    card = _card(root)
    _wrapping_label(
        card,
        f"This dataset's {label_prefix} pipeline (same steps, same "
        "Misc/Other count) was already set up in a previous run:",
        pady=(0, 10),
    )

    # Scrollable rather than a plain packed column -- with enough
    # Misc/Other steps in the mix this list can run long enough to grow
    # the persistent wizard window itself past the screen, which is
    # exactly what crashed Tk outright on _choose_scripts_for_step's own
    # script-picker list before IT got a scrollable canvas (see that
    # function's comment). Same fix here: cap this area's height and
    # scroll inside it instead.
    list_area = ttk.Frame(card, style="Card.TFrame")
    list_area.pack(fill="both", expand=True)

    list_canvas = tk.Canvas(
        list_area, background=BG_CARD, highlightthickness=0, height=220,
    )
    list_vbar = ttk.Scrollbar(list_area, orient="vertical", command=list_canvas.yview)
    list_canvas.configure(yscrollcommand=list_vbar.set)
    list_canvas.pack(side="left", fill="both", expand=True)
    list_vbar.pack(side="right", fill="y")

    list_card = ttk.Frame(list_canvas, style="Card.TFrame", padding=(4, 4))
    list_inner_id = list_canvas.create_window((0, 0), window=list_card, anchor="nw")

    def on_inner_configure(event=None):
        list_canvas.configure(scrollregion=list_canvas.bbox("all"))

    list_card.bind("<Configure>", on_inner_configure)
    list_canvas.bind(
        "<Configure>", lambda event: list_canvas.itemconfigure(list_inner_id, width=event.width)
    )

    for step in steps:
        ttk.Label(
            list_card, text=_describe_step_choice(step), style="Card.TLabel",
        ).pack(anchor="w", pady=2)

    def on_mousewheel(event):
        delta = getattr(event, "delta", 0)
        if delta == 0:
            delta = 120 if getattr(event, "num", 0) == 4 else -120
        try:
            list_canvas.yview_scroll(int(-delta / 120), "units")
        except tk.TclError:
            # This screen's canvas is already gone (a queued wheel event
            # arriving right as the screen changed) -- _new_root() also
            # clears this binding on every transition, so this is just a
            # belt-and-braces guard against that timing gap.
            pass

    # Bound on the window itself (not just the canvas) so scrolling works
    # no matter which child widget the mouse happens to be over -- same
    # reasoning as _choose_scripts_for_step's identical binding.
    root.bind("<MouseWheel>", on_mousewheel)
    root.bind("<Button-4>", on_mousewheel)
    root.bind("<Button-5>", on_mousewheel)

    _wrapping_label(
        card,
        "You can reuse this exactly as it was left (including the run "
        "order), or go through every step again to review or change it.",
        pady=(10, 0),
    )

    outcome = {"reuse": True}

    def on_reuse():
        outcome["reuse"] = True
        root.destroy()

    def on_review():
        outcome["reuse"] = False
        root.destroy()

    btns = _button_row(root)
    ttk.Button(btns, text="Use previous setup", style="Accent.TButton", command=on_reuse).pack(side="right")
    ttk.Button(btns, text="Review each step", command=on_review).pack(side="right", padx=(0, 8))

    root.mainloop()
    _check_not_closed()
    return outcome["reuse"]


def configure_phase3_steps(
    siril: "s.SirilInterface", available: dict[str, Path],
    by_category: dict[str, list[str]], builtin_by_category: dict[str, list[str]],
    misc_count: int, cfg: dict, config_key: str = "phase3_steps",
    label_prefix: str = "phase 3", title_prefix: str = "Phase 3 setup",
) -> list[dict]:
    """The phase 3 pipeline configurator: the five fixed steps
    (Background Extraction/Denoising/Sharpening/Star Removal/Stretching)
    plus `misc_count` "Misc/Other" steps, each assignable to any number of
    installed scripts -- a script can be used in more than one step (e.g.
    CosmicClarity_Native.py covers Sharpening, Denoising, AND Star
    Removal). Rather than one window with a run-order list on the left and
    a checkbox panel on the right that rebuilds itself every time a
    different step is selected (which felt laggy with a real script
    catalog), this walks through each step in its own screen one at a time
    (_choose_scripts_for_step, with Back/Continue), and only opens a
    reorder-only screen (_rearrange_phase3_steps) at the very end once
    every step's picks are already known -- the five fixed steps offer
    both Siril's own built-in tools (BUILTIN_TOOL_CATALOG) mapped to that
    category and installed scripts PY_SCRIPT_CATALOG maps to it, while
    Misc/Other steps offer every installed PY_SCRIPT_CATALOG script (any
    category, not just one) and every built-in tool, plus their own
    editable filename code -- a script Siril has on disk but that isn't in
    PY_SCRIPT_CATALOG at all (plate-solving, cataloging, and other
    non-image-processing tools Siril's repository also syncs) is never
    offered, in any step. Returns the
    final ordered list of {"id", "label", "category", "code",
    "scripts": [...]} dicts (category is None for a Misc/Other step); also
    saved into cfg["phase3_steps"] so it's remembered next run (only reused
    if the step set is identical -- same fixed steps, same misc count --
    otherwise everyone starts unselected). When a matching previous
    configuration IS found, this asks up front whether to reuse it as-is
    (including whatever order it was last left in) or step through
    everything again -- see _confirm_reuse_phase3_choices below."""

    steps: list[dict] = [
        {"id": cat, "label": cat, "category": cat, "code": CATEGORY_CODE[cat], "scripts": []}
        for cat in CATEGORY_ORDER
    ]
    for i in range(1, misc_count + 1):
        steps.append({
            "id": f"misc{i}", "label": f"Misc/Other #{i}", "category": None,
            "code": f"M{i}", "scripts": [],
        })

    saved = cfg.get(config_key)
    # Compared as SETS of ids, not order -- a step set is "the same" even if
    # you'd previously dragged it into a different run order via
    # _rearrange_phase3_steps. When it matches, "steps" is then rebuilt in
    # the SAVED order (not the fixed CATEGORY_ORDER built above) so a reused
    # configuration really does come back exactly as it was left, order
    # included.
    restored_from_previous = bool(saved) and (
        {s["id"] for s in saved} == {s["id"] for s in steps}
    )
    if restored_from_previous:
        by_id = {s["id"]: s for s in steps}
        steps = [by_id[saved_step["id"]] for saved_step in saved]
        for step, saved_step in zip(steps, saved):
            step["scripts"] = [
                n for n in saved_step.get("scripts", [])
                if n in available or n in BUILTIN_TOOL_CATALOG
            ]
            # Fixed steps keep their category code always; only a
            # Misc/Other step's code is user-editable and worth restoring.
            if step["category"] is None:
                saved_code = "".join(ch for ch in str(saved_step.get("code", "")).upper() if ch.isalnum())
                if saved_code:
                    step["code"] = saved_code[:6]

    if restored_from_previous and any(step["scripts"] for step in steps):
        if _confirm_reuse_phase3_choices(siril, steps, label_prefix=label_prefix):
            cfg[config_key] = steps
            save_config(cfg)
            return steps

    # One step at a time (its own window, built fresh and only once) rather
    # than a single window that rebuilds a whole checkbox panel on every
    # listbox click -- that dynamic rebuild (destroying and recreating every
    # row and its tooltip binding each time) was what made the old combined
    # screen feel laggy. Reordering only happens at the very end, once every
    # step's picks are already known, in its own lightweight screen.
    index = 0
    while 0 <= index < len(steps):
        outcome = _choose_scripts_for_step(
            siril, steps[index], index, len(steps),
            available, by_category, builtin_by_category,
            title_prefix=title_prefix,
        )
        if outcome == "back":
            index -= 1
        else:
            index += 1

    steps = _rearrange_phase3_steps(siril, steps, title_prefix=title_prefix)

    cfg[config_key] = steps
    save_config(cfg)
    return steps


def _choose_scripts_for_step(
    siril: "s.SirilInterface", step: dict, index: int, total: int,
    available: dict[str, Path], by_category: dict[str, list[str]],
    builtin_by_category: dict[str, list[str]], title_prefix: str = "Phase 3 setup",
) -> str:
    """One step's own script/tool picker screen (built once, no dynamic
    rebuilding) -- shows Siril's built-in tools for this step's category
    (if any) plus installed scripts mapped to it, or every built-in/
    installed script with no filtering for a Misc/Other step, which also
    gets an editable short filename code here. Only ONE tool can be picked
    per step (radio buttons, plus a "None" option) -- a step is one process
    in the pipeline, so wanting two Background Extraction passes, say,
    means adding a second Misc/Other step for the other one rather than
    ticking two scripts into the same step. Returns "continue" or "back"
    (there's no explicit abort button -- closing the window aborts the
    whole wizard, same as everywhere else)."""

    root = _new_root(siril, f"{title_prefix} ({index + 1}/{total}): {step['label']}")
    _header(root, step["label"])

    card = _card(root)

    code_var = None
    if step["category"] is None:
        # Misc/Other steps have no fixed category code, so let the user
        # pick their own short filename code (default "M1", "M2", ...).
        code_row = ttk.Frame(card, style="Card.TFrame")
        code_row.pack(fill="x", anchor="w", pady=(0, 12))
        ttk.Label(code_row, text="Filename code:", style="Card.TLabel").pack(side="left")
        code_var = tk.StringVar(value=step["code"])
        code_entry = ttk.Entry(code_row, textvariable=code_var, width=8)
        code_entry.pack(side="left", padx=(6, 0))
        tksiril.create_tooltip(
            code_entry,
            "Short code appended to the filename when this step "
            "finishes, e.g. \"B - BE, M1.fit\". Letters/numbers only.",
        )

    if step["category"]:
        script_names = by_category.get(step["category"], [])
        builtin_names = builtin_by_category.get(step["category"], [])
    else:
        # Misc/Other -- every installed script AND every built-in tool
        # that's actually relevant to image pre-processing, not tied to
        # one specific category. Siril's script directories hold every
        # script its repository has ever synced (every category: Utility,
        # Sequence pre-processing, Astrometry, etc. -- not just image
        # processing), regardless of that script's "Sel" checkbox in
        # Preferences -> Scripts, so scanning the filesystem for "*.py"
        # picks up plenty of unrelated tools too (comet finders, catalog
        # fetchers, autofocus helpers...). Restricting this to
        # PY_SCRIPT_CATALOG -- the researched set of actual pre-processing
        # scripts -- is what keeps this list relevant; a script that isn't
        # in the catalog yet won't show up here even if it's genuinely
        # useful, but that's a much better default than showing everything
        # Siril has ever downloaded.
        script_names = sorted(name for name in available if name in PY_SCRIPT_CATALOG)
        builtin_names = sorted(BUILTIN_TOOL_CATALOG)

    NONE_VALUE = "__none__"
    current = step["scripts"][0] if step["scripts"] else NONE_VALUE
    choice_var = tk.StringVar(value=current)

    if not script_names and not builtin_names:
        _wrapping_label(
            card,
            "No installed scripts were found for this step, and Siril "
            "has no built-in tool for it either. Install a script via "
            "Siril's script repository manager, then re-open this "
            "screen. You can just click Continue for now.",
        )
    else:
        none_row = ttk.Frame(card, style="Card.TFrame")
        none_row.pack(fill="x", anchor="w", pady=(0, 8))
        ttk.Radiobutton(
            none_row, text="None (skip this step)", variable=choice_var,
            value=NONE_VALUE, style="TRadiobutton",
        ).pack(side="left")

        # The rest of the list lives in a scrollable, multi-column grid
        # rather than one long packed column -- with a Misc/Other step
        # offering EVERY installed script plus every built-in tool (easily
        # 40-60+ entries), a single tall column had no way to scroll and,
        # worse, made the persistent wizard window itself grow to match
        # that height -- which is what crashed Tk entirely when toggling
        # full-screen on it. Capping this area's height and scrolling
        # inside it keeps the window itself a normal, fixed size no matter
        # how many entries there are.
        list_area = ttk.Frame(card, style="Card.TFrame")
        list_area.pack(fill="both", expand=True)

        list_canvas = tk.Canvas(
            list_area, background=BG_CARD, highlightthickness=0, height=280,
        )
        list_vbar = ttk.Scrollbar(list_area, orient="vertical", command=list_canvas.yview)
        list_canvas.configure(yscrollcommand=list_vbar.set)
        list_canvas.pack(side="left", fill="both", expand=True)
        list_vbar.pack(side="right", fill="y")

        list_inner = ttk.Frame(list_canvas, style="Card.TFrame")
        list_inner_id = list_canvas.create_window((0, 0), window=list_inner, anchor="nw")

        def on_inner_configure(event=None):
            list_canvas.configure(scrollregion=list_canvas.bbox("all"))

        list_inner.bind("<Configure>", on_inner_configure)

        # (widget, is_header) in display order -- headers get their own row
        # spanning every column; everything else flows left-to-right,
        # wrapping into as many columns as currently fit.
        entries: list[tuple[tk.Widget, bool]] = []

        def add_header(text: str):
            label = ttk.Label(list_inner, text=text, style="Brand.TLabel")
            entries.append((label, True))

        def add_row(name: str, tag: str | None = None):
            label = f"{name}  ({tag})" if tag else name
            rb = ttk.Radiobutton(
                list_inner, text=label, variable=choice_var, value=name, style="TRadiobutton",
            )
            entries.append((rb, False))

        if builtin_names:
            add_header("Siril built-in")
            for name in builtin_names:
                add_row(name, tag="built-in")
        if script_names:
            add_header("Installed scripts")
            for name in script_names:
                add_row(name)

        MIN_COL_WIDTH = 260
        reflow_state = {"cols": 0}

        def reflow(event=None):
            width = list_canvas.winfo_width()
            cols = max(1, width // MIN_COL_WIDTH)
            if cols == reflow_state["cols"]:
                return
            reflow_state["cols"] = cols
            for c in range(cols):
                list_inner.columnconfigure(c, weight=1)
            row_idx = 0
            col_idx = 0
            for widget, is_header in entries:
                widget.grid_forget()
                if is_header:
                    if col_idx != 0:
                        row_idx += 1
                        col_idx = 0
                    widget.grid(row=row_idx, column=0, columnspan=cols, sticky="w", pady=(10, 2))
                    row_idx += 1
                else:
                    widget.grid(row=row_idx, column=col_idx, sticky="w", padx=(0, 16), pady=2)
                    col_idx += 1
                    if col_idx >= cols:
                        col_idx = 0
                        row_idx += 1

        def on_canvas_configure(event):
            list_canvas.itemconfigure(list_inner_id, width=event.width)
            reflow(event)

        list_canvas.bind("<Configure>", on_canvas_configure)

        def on_mousewheel(event):
            delta = getattr(event, "delta", 0)
            if delta == 0:
                delta = 120 if getattr(event, "num", 0) == 4 else -120
            try:
                list_canvas.yview_scroll(int(-delta / 120), "units")
            except tk.TclError:
                # This step's canvas is already gone (a queued wheel event
                # arriving right as the screen changed) -- _new_root() also
                # clears this binding on every transition, so this is just
                # a belt-and-braces guard against that timing gap.
                pass

        # Bound on the window itself (not just the canvas) so scrolling
        # works no matter which child widget the mouse happens to be over
        # -- every widget in this window shares its toplevel as a bindtag.
        root.bind("<MouseWheel>", on_mousewheel)
        root.bind("<Button-4>", on_mousewheel)
        root.bind("<Button-5>", on_mousewheel)

        _wrapping_label(
            card,
            "Only one tool per step -- want two Background Extraction "
            "passes, say? Add a second Misc/Other step for the other one "
            "instead of picking two here.",
            pady=(10, 0),
        )

    outcome = {"result": "continue"}

    def apply_choice():
        step["scripts"] = [] if choice_var.get() == NONE_VALUE else [choice_var.get()]
        if code_var is not None:
            cleaned = "".join(ch for ch in code_var.get().upper() if ch.isalnum())[:6]
            step["code"] = cleaned or step["code"]

    def on_continue():
        apply_choice()
        outcome["result"] = "continue"
        root.destroy()

    def on_back():
        apply_choice()
        outcome["result"] = "back"
        root.destroy()

    btns = _button_row(root)
    ttk.Button(btns, text="Continue", style="Accent.TButton", command=on_continue).pack(side="right")
    if index > 0:
        ttk.Button(btns, text="Back", command=on_back).pack(side="left")

    root.mainloop()
    _check_not_closed()
    return outcome["result"]


def _rearrange_phase3_steps(
    siril: "s.SirilInterface", steps: list[dict], title_prefix: str = "Phase 3 setup",
) -> list[dict]:
    """The final, lightweight reorder-only screen -- every step's scripts
    are already chosen by this point, so this is just the run-order
    listbox and Move Up/Move Down, no per-step rebuild involved."""

    root = _new_root(siril, f"{title_prefix}: pipeline order")
    _header(root, "Arrange your pipeline order")
    _wrapping_label(
        _card(root),
        "This is the order steps will run in (top runs first). Select a "
        "step and use Move Up/Move Down to rearrange it -- for example, "
        "to sharpen before denoising instead of after.",
    )

    left = ttk.LabelFrame(root, text="Pipeline order", padding=10)
    left.pack(fill="both", expand=True, padx=24, pady=(0, 10))

    listbox = tk.Listbox(
        left, height=12, background=BG_CARD_ALT, foreground=TEXT_PRIMARY,
        selectbackground=ACCENT, selectforeground=ACCENT_TEXT,
        highlightthickness=0, borderwidth=0, activestyle="none",
        font=(FONT_FAMILY, 10), exportselection=False,
    )
    listbox.pack(fill="both", expand=True)

    def step_summary(step: dict) -> str:
        n = len(step["scripts"])
        suffix = f"  ({n} selected)" if n else "  (none selected)"
        return step["label"] + suffix

    def refresh_listbox(select_index: int | None = None) -> None:
        listbox.delete(0, "end")
        for step in steps:
            listbox.insert("end", step_summary(step))
        if select_index is not None:
            listbox.selection_set(select_index)

    def move(delta: int) -> None:
        sel = listbox.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + delta
        if 0 <= j < len(steps):
            steps[i], steps[j] = steps[j], steps[i]
            refresh_listbox(select_index=j)

    move_row = ttk.Frame(left)
    move_row.pack(fill="x", pady=(8, 0))
    ttk.Button(move_row, text="Move Up", command=lambda: move(-1)).pack(side="left")
    ttk.Button(move_row, text="Move Down", command=lambda: move(1)).pack(side="left", padx=(6, 0))

    refresh_listbox(select_index=0)

    btns = _button_row(root)
    ttk.Button(btns, text="Continue", style="Accent.TButton", command=root.destroy).pack(side="right")

    root.mainloop()
    _check_not_closed()
    return steps


def run_pipeline_setup_and_tool_check(
    siril: "s.SirilInterface", cfg: dict,
    misc_count_key: str = "phase3_misc_count",
    steps_config_key: str = "phase3_steps",
    tool_paths_config_key: str = "phase3_tool_paths",
    label_prefix: str = "phase 3",
    title_prefix: str = "Phase 3 setup",
    log_prefix: str = "phase 3 setup",
    tools_notice_title: str = "Required tools for Pre-processing",
    setup_step_id: str | None = "phase3_setup",
    setup_step_label: str = "Configure Phase 3 pipeline",
    tools_step_id: str | None = "phase3_tools",
    tools_step_label: str = "Check Python tools (phase 3)",
) -> bool:
    """The full pipeline setup flow: scan for installed Python scripts, ask
    how many Misc/Other steps to add, let the user build/reorder the
    pipeline and pick scripts per step (configure_phase3_steps), then check
    that every script actually picked (across all steps -- the same script
    picked for two steps is only checked once) is genuinely findable,
    exactly the way the phase 1 stacking-script check works. The resulting
    pipeline is left in cfg[steps_config_key] either way (even if aborted
    at the tool check) since it's still worth remembering for next time.

    Originally phase 3 only ever had one of these (hardcoded to phase 3's
    own config keys/wizard step ids), and phase 4's starmask pipeline
    (when the user chooses to set up a separate one rather than reusing
    phase 3's) had its own separately-maintained near-duplicate of this
    same flow inline in run_phase4_starmask_pipeline. Generalized here so
    both share one implementation -- every parameter defaults to phase 3's
    own original values, so phase 3's call site needed no changes at all;
    phase 4 passes its own config keys/prefixes/titles instead.

    setup_step_id/tools_step_id control whether this manages its OWN
    wizard sidebar rows for the setup/tool-check steps (phase 3's own
    "phase3_setup"/"phase3_tools" rows, added/marked done here exactly as
    before) or leaves that to the caller (pass None for either/both) --
    phase 4 has just ONE "phase4_run" sidebar row spanning its whole
    setup+run+finalize span (a deliberate difference from phase 3's
    per-stage rows, since phase 4 is a single composite rather than a
    per-filter loop), and manages that row itself around this call, so it
    passes None for both here rather than getting two new phase-4-only
    sidebar rows it never had before.

    Returns True to continue, False to abort the run here."""

    if setup_step_id:
        wizard_add_step(setup_step_id, setup_step_label)
        wizard_set_current(setup_step_id)

    available = scan_available_py_scripts(siril, cfg)
    by_category = categorize_available_scripts(available)
    builtin_by_category = categorize_builtin_tools()
    misc_count = ask_misc_step_count(siril, cfg, config_key=misc_count_key)
    steps = configure_phase3_steps(
        siril, available, by_category, builtin_by_category, misc_count, cfg,
        config_key=steps_config_key, label_prefix=label_prefix, title_prefix=title_prefix,
    )
    for step in steps:
        siril.log(f"[{log_prefix}] {step['label']}: {', '.join(step['scripts']) or '(none selected)'}")
    if setup_step_id:
        wizard_mark_done(setup_step_id)

    # Siril's own built-in commands (GHT, subsky, denoise, etc.) are always
    # part of Siril itself -- they never need a "found on disk?" tool check
    # the way Python scripts do, so exclude them here.
    chosen_scripts = sorted({
        name for step in steps for name in step["scripts"]
        if name not in BUILTIN_TOOL_CATALOG
    })

    if tools_step_id:
        wizard_add_step(tools_step_id, tools_step_label)
        wizard_set_current(tools_step_id)

    if not chosen_scripts:
        siril.log(f"[{log_prefix}] No scripts selected for any step -- nothing to check.")
        if tools_step_id:
            wizard_mark_done(tools_step_id)
        return True

    py_tools = locate_tools(siril, cfg, kinds=("py",), py_names=chosen_scripts)
    if not show_tool_check_notice(
        siril, cfg, py_tools, kinds=("py",), title=tools_notice_title,
        py_names=chosen_scripts,
    ):
        siril.log(f"Aborted at {label_prefix} tool check.")
        if tools_step_id:
            wizard_mark_done(tools_step_id)
        return False

    # Re-resolve after the notice closes (rather than trusting py_tools as
    # first computed) since "Re-check"/"Locate manually" inside the notice
    # may have updated cfg["tool_paths"] with a freshly-picked location --
    # this is what run_phase3_pipeline()/run_phase4_starmask_pipeline()
    # will actually use to launch each script.
    final_py_tools = locate_tools(siril, cfg, kinds=("py",), py_names=chosen_scripts)
    cfg[tool_paths_config_key] = {
        name: str(path) for name, path in final_py_tools["py"].items() if path
    }
    save_config(cfg)

    if tools_step_id:
        wizard_mark_done(tools_step_id)
    return True


def run_phase3_setup_and_tool_check(siril: "s.SirilInterface", cfg: dict) -> bool:
    """Phase 3's own call into run_pipeline_setup_and_tool_check, using
    every one of its defaults (phase 3's config keys/wizard step ids) --
    kept as a separate, unparameterized function purely so phase 3's own
    call site (in _run_wizard) reads the same as it always has."""

    return run_pipeline_setup_and_tool_check(siril, cfg)


def prompt_for_file(siril: "s.SirilInterface", title: str) -> Path | None:
    """Native OS file picker. Doesn't need a window of its own -- the
    persistent wizard window (see _ensure_wizard) already exists as the
    Tk application by the time this is called."""

    _ensure_wizard()
    picked = filedialog.askopenfilename(title=title)
    return Path(picked) if picked else None


def choose_main_folder_dialog(siril: "s.SirilInterface") -> Path | None:
    """Native OS folder picker for the main dataset folder -- used only
    when the user says Siril's working directory isn't already set to it.
    Returns None if the user cancels."""

    _ensure_wizard()
    picked = filedialog.askdirectory(title="Select your main dataset folder")
    return Path(picked) if picked else None


def prompt_text(
    siril: "s.SirilInterface", title: str, label: str, default: str = "",
) -> str | None:
    """A themed text-entry dialog. Returns the entered text, or None if
    cancelled."""

    root = _new_root(siril, title)
    _header(root, title)

    card = _card(root)
    _wrapping_label(card, label)

    value = tk.StringVar(value=default)
    entry = ttk.Entry(card, textvariable=value, width=32)
    entry.pack(anchor="w", pady=(8, 0), fill="x")
    entry.focus_set()
    entry.select_range(0, "end")

    result: dict[str, str | None] = {"value": None}

    def on_ok():
        result["value"] = value.get().strip()
        root.destroy()

    def on_cancel():
        result["value"] = None
        root.destroy()

    root.bind("<Return>", lambda e: on_ok())

    btns = _button_row(root)
    ttk.Button(btns, text="Continue", style="Accent.TButton", command=on_ok).pack(side="right")
    ttk.Button(btns, text="Cancel", command=on_cancel).pack(side="right", padx=(0, 8))

    root.mainloop()
    _check_not_closed()
    return result["value"] or None


# Both caches below exist purely to avoid re-walking the filesystem/
# re-querying Siril's own config over and over for something that doesn't
# change within a single run of this wizard -- get_search_directories()
# used to re-ask Siril for its script path config and re-stat every
# candidate directory on EVERY call (locate_tools() alone calls it up to
# half a dozen times across phase 1/3/4's tool checks), and find_tool()/
# scan_available_py_scripts() used to separately re-walk (rglob) the same
# search directories for every single tool name checked, rather than
# scanning each directory once and looking names up in the result.
# Invalidated (see _invalidate_tool_scan_cache) at the exact points where
# something could genuinely have changed underneath them within a run --
# right before show_tool_check_notice's "Re-check"/"Locate manually"
# re-scan, since that button's whole purpose is to notice a script the
# user just installed or pointed to. Never invalidated otherwise, since
# Siril's own config and installed scripts don't change on their own
# mid-run.
_SEARCH_DIRS_CACHE: list[Path] | None = None
_DIR_FILE_SCAN_CACHE: dict[Path, dict[str, Path]] = {}


def _invalidate_tool_scan_cache() -> None:
    """Clears both caches above so the next get_search_directories()/
    find_tool()/scan_available_py_scripts() call does a genuinely fresh
    filesystem scan. Called right before show_tool_check_notice's "Re-
    check"/"Locate manually" re-scan -- the only points within a run where
    the user has just done something (installed a script, pointed to one
    by hand) that a cached scan wouldn't reflect."""

    global _SEARCH_DIRS_CACHE
    _SEARCH_DIRS_CACHE = None
    _DIR_FILE_SCAN_CACHE.clear()


def _scan_dir_files(base: Path) -> dict[str, Path]:
    """{filename: path} for every non-empty file anywhere under `base`
    (recursively), scanned once and cached in _DIR_FILE_SCAN_CACHE --
    shared by find_tool() (exact-name lookups) and
    scan_available_py_scripts() (".py" lookups) so a search directory
    with, say, a hundred installed scripts gets walked once per run
    instead of once per tool name checked against it. First occurrence of
    a given filename within this one base directory wins, same as the
    per-name rglob() this replaces would have found first (directory walk
    order isn't guaranteed either way, but a filename collision within a
    single search directory is already an edge case neither version
    specially handles)."""

    cached = _DIR_FILE_SCAN_CACHE.get(base)
    if cached is not None:
        return cached

    found: dict[str, Path] = {}
    try:
        for h in base.rglob("*"):
            if h.name in found:
                continue
            try:
                if h.is_file() and h.stat().st_size > 0:
                    found[h.name] = h
            except OSError:
                continue
    except OSError:
        pass
    _DIR_FILE_SCAN_CACHE[base] = found
    return found


def get_search_directories(siril: "s.SirilInterface") -> list[Path]:
    """Directories Siril itself already knows about: everywhere the user has
    told Siril (via Preferences > Scripts) to look for scripts, plus Siril's
    own data directories where core/repository scripts and the bundled
    Python tool scripts live. No manual setup required for a normal Siril
    install. Cached for the run -- see _SEARCH_DIRS_CACHE above."""

    global _SEARCH_DIRS_CACHE
    if _SEARCH_DIRS_CACHE is not None:
        return _SEARCH_DIRS_CACHE

    raw_dirs: list[str] = []

    try:
        configured = siril.get_siril_config("gui", "script_path")
        if configured:
            raw_dirs.extend(configured)
    except Exception:
        pass

    for getter_name in ("get_siril_userdatadir", "get_siril_systemdatadir"):
        try:
            d = getattr(siril, getter_name)()
            if d:
                raw_dirs.append(d)
        except Exception:
            pass

    seen: set[Path] = set()
    dirs: list[Path] = []
    for raw in raw_dirs:
        p = Path(raw)
        if p.is_dir() and p not in seen:
            seen.add(p)
            dirs.append(p)
    _SEARCH_DIRS_CACHE = dirs
    return dirs


def find_tool(
    siril: "s.SirilInterface", cfg: dict, name: str, search_dirs: list[Path]
) -> Path | None:
    """Looks for a previously-remembered path first (re-verified that it
    still exists), then searches Siril's known script directories
    (recursively, since scripts are often grouped into subfolders), and
    only returns None if it truly can't be found anywhere. Logs what it
    checked to Siril's log so you can see exactly why something was or
    wasn't found.

    Note: Siril's own Preferences > Scripts screen has a separate "Sel"
    (selected) checkbox per repository script, which only controls whether
    that script shows up in SIRIL'S OWN Scripts menu -- it has nothing to
    do with whether the file itself is present/complete on disk in one of
    these search_dirs (repository scripts are synced to disk as soon as
    the catalog updates, selected or not). This wizard reads the .ssf file
    directly and replays it (see run_ssf()) rather than invoking it through
    Siril's Scripts menu, so a script can be perfectly usable here even
    while it shows as un-selected/"not installed" in that Preferences
    screen. We only skip a hit if it's a suspiciously empty/stub file."""

    cached = cfg.get("tool_paths", {}).get(name)
    if cached and Path(cached).is_file() and Path(cached).stat().st_size > 0:
        siril.log(f"[tool check] {name}: using remembered path {cached}")
        return Path(cached)

    for base in search_dirs:
        found = _scan_dir_files(base).get(name)
        if found is not None:
            siril.log(f"[tool check] {name}: found at {found}")
            cfg.setdefault("tool_paths", {})[name] = str(found)
            save_config(cfg)
            return found

    siril.log(
        f"[tool check] {name}: NOT found (or only empty/stub files) in any "
        "of: " + ", ".join(str(d) for d in search_dirs)
    )
    return None


def locate_tools(
    siril: "s.SirilInterface", cfg: dict,
    kinds: tuple[str, ...] = ("ssf", "py"),
    ssf_names: list[str] | None = None,
    py_names: list[str] | None = None,
) -> dict:
    """Checks which required tools Siril can already find on its own.
    Returns {"ssf": {name: path_or_None}, "py": {name: path_or_None}} --
    only the requested kinds are actually searched for; the other one comes
    back as an empty dict. "ssf" covers whichever Mono_Preprocessing
    variant(s) are actually needed for this run (see MONO_SSF_VARIANTS) --
    pass ssf_names to restrict the search to a specific set (the ones
    choose_calibration_scripts() actually picked); "py" is the phase 3/4
    Python tools (AutoBGE, etc.), similarly restricted by py_names. Every
    call site always passes explicit names for whichever kind it requests,
    so an omitted ssf_names/py_names for a requested kind searches for
    nothing rather than guessing a default list."""

    search_dirs = get_search_directories(siril)
    siril.log(
        "[tool check] Searching these directories (from Siril's own "
        "config): " + ", ".join(str(d) for d in search_dirs)
    )
    results = {"ssf": {}, "py": {}}

    if "ssf" in kinds:
        for name in (ssf_names or []):
            results["ssf"][name] = find_tool(siril, cfg, name, search_dirs)

    if "py" in kinds:
        for name in (py_names or []):
            results["py"][name] = find_tool(siril, cfg, name, search_dirs)

    return results


def show_tool_check_notice(
    siril: "s.SirilInterface", cfg: dict, results: dict,
    kinds: tuple[str, ...] = ("ssf", "py"),
    title: str = "Required tools check",
    ssf_names: list[str] | None = None,
    py_names: list[str] | None = None,
) -> bool:
    """Shows the found/missing list. Returns True to continue, False to
    abort. The popup is skipped only if everything is present AND the user
    previously chose to hide it -- if anything is missing we always show
    it, since the pipeline can't run without these tools. Missing tools are
    checked for automatically in Siril's own script directories, so this
    should normally just be a quick confirmation, not something the user
    has to configure. kinds is only used to re-run locate_tools() with the
    same restricted scope on "Re-check"/"Locate manually"."""

    all_ssf = results["ssf"]
    all_py = results["py"]
    missing = [name for name, path in {**all_ssf, **all_py}.items() if not path]
    all_present = not missing

    if all_present and cfg.get("hide_tool_check_notice"):
        return True

    root = _new_root(siril, title)
    _header(root, title)

    group = _card(root, "This pipeline uses the following tools")

    for name, path in {**all_ssf, **all_py}.items():
        row = ttk.Frame(group, style="Card.TFrame")
        row.pack(fill="x", anchor="w", pady=3)
        mark_style = "Found.TLabel" if path else "Missing.TLabel"
        mark = "✓ found" if path else "✗ missing"
        ttk.Label(row, text=mark, width=10, style=mark_style).pack(side="left")
        label = ttk.Label(row, text=name, style="Card.TLabel", anchor="w")
        label.pack(side="left", fill="x", expand=True)
        if path:
            tksiril.create_tooltip(label, str(path))

    if "ssf" in kinds and any(all_ssf.values()):
        _wrapping_label(
            group,
            "Note: this checks that the script file itself exists where "
            "Siril looks for scripts -- it's separate from the \"Sel\" "
            "checkbox in Siril's own Preferences → Scripts screen (that "
            "only controls Siril's own Scripts menu). This wizard reads "
            "and runs the file directly, so \"found\" here is enough even "
            "if a script shows as unselected there.",
            pady=(10, 0),
        )

    dont_show = tk.BooleanVar(value=False)
    if all_present:
        ttk.Checkbutton(
            group, text="Don't show this message again (I'll always check "
                        "silently)", variable=dont_show, style="TCheckbutton",
        ).pack(anchor="w", pady=(10, 0))
    else:
        _wrapping_label(
            group,
            "One or more tools couldn't be found automatically. Make "
            "sure they're installed where Siril looks for scripts "
            "(Preferences → Scripts), or click 'Locate manually' "
            "to point to them yourself.",
            pady=(10, 0),
        )

    outcome = {"continue": False}

    def on_continue():
        outcome["continue"] = True
        root.destroy()

    def on_abort():
        outcome["continue"] = False
        root.destroy()

    def on_recheck():
        outcome["continue"] = "recheck"
        root.destroy()

    def on_locate():
        outcome["continue"] = "locate"
        root.destroy()

    btns = _button_row(root)
    ttk.Button(
        btns, text="Continue", style="Accent.TButton", command=on_continue,
        state="normal" if all_present else "disabled",
    ).pack(side="right")
    if not all_present:
        ttk.Button(btns, text="Locate manually", command=on_locate).pack(side="right", padx=8)
        ttk.Button(btns, text="Re-check", command=on_recheck).pack(side="right")
    ttk.Button(btns, text="Abort", command=on_abort).pack(side="left")

    root.mainloop()
    _check_not_closed()

    if outcome["continue"] == "recheck":
        # The whole point of "Re-check" is to notice a script the user
        # just installed since the last scan -- without this, the cached
        # directory scans (see _scan_dir_files/get_search_directories)
        # would just hand back the same stale "not found" result.
        _invalidate_tool_scan_cache()
        new_results = locate_tools(siril, cfg, kinds=kinds, ssf_names=ssf_names, py_names=py_names)
        return show_tool_check_notice(siril, cfg, new_results, kinds=kinds, title=title, ssf_names=ssf_names, py_names=py_names)

    if outcome["continue"] == "locate":
        for name in missing:
            picked = prompt_for_file(siril, f"Locate {name}")
            if picked and picked.is_file():
                cfg.setdefault("tool_paths", {})[name] = str(picked)
                save_config(cfg)
        # A manually-located file is found again via cfg["tool_paths"]
        # regardless (find_tool checks that before any directory scan), but
        # invalidate here too for the same reason as "Re-check" above --
        # this re-scan should reflect anything that changed on disk, not a
        # stale cached listing.
        _invalidate_tool_scan_cache()
        new_results = locate_tools(siril, cfg, kinds=kinds, ssf_names=ssf_names, py_names=py_names)
        return show_tool_check_notice(siril, cfg, new_results, kinds=kinds, title=title, ssf_names=ssf_names, py_names=py_names)

    if outcome["continue"] is True and all_present and dont_show.get():
        cfg["hide_tool_check_notice"] = True
        save_config(cfg)

    return outcome["continue"] is True


def checkpoint_dialog(siril: "s.SirilInterface", message: str) -> bool:
    """Full-review checkpoint: the caller has already loaded the relevant
    image into Siril's own view before calling this, so the user can look
    at it there. Returns True to continue, False to abort the whole run."""

    root = _new_root(siril, "Review checkpoint")
    _header(root, "Review checkpoint")

    card = _card(root)
    _wrapping_label(card, message)

    outcome = {"continue": False}

    def on_continue():
        outcome["continue"] = True
        root.destroy()

    def on_abort():
        outcome["continue"] = False
        root.destroy()

    btns = _button_row(root)
    ttk.Button(
        btns, text="Continue", style="Accent.TButton", command=on_continue,
    ).pack(side="right")
    ttk.Button(btns, text="Abort run", command=on_abort).pack(side="left")

    root.mainloop()
    _check_not_closed()
    return outcome["continue"]


# --------------------------------------------------------------------------
# Siril / filesystem work
# --------------------------------------------------------------------------

def siril_quote(value: str) -> str:
    """Siril's command parser splits arguments on whitespace, same as a
    shell would, so any argument containing a space (paths, most of all)
    has to be wrapped in double quotes before being handed to siril.cmd() --
    that function does not add quoting for you. Already-quoted values are
    left alone."""

    value = str(value)
    if value.startswith('"') and value.endswith('"'):
        return value
    if any(ch.isspace() for ch in value):
        return f'"{value}"'
    return value


def run_ssf(
    siril: "s.SirilInterface", ssf_path: Path,
    on_line: Callable[[str], None] | None = None,
) -> None:
    """Replays a Siril .ssf script line-by-line through siril.cmd().
    See the module docstring for why this approach was used.

    on_line, if given, is called with each command line just before it's
    run -- sirilpy has no way to read Siril's own progress bar/status text
    back out (only update_progress()/reset_progress(), for a script to
    report ITS OWN progress, not to read Siril's), so run_with_progress
    uses this to show the actual command currently executing as live
    status text instead, as the nearest equivalent."""

    for raw_line in ssf_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # shlex.split() strips the quotes from any quoted argument in the
        # .ssf line (e.g. a path with spaces) -- re-quote anything that
        # needs it before replaying it through siril.cmd().
        parts = shlex.split(line)
        cmd, args = parts[0], [siril_quote(a) for a in parts[1:]]
        siril.log(f"  > {line}")
        if on_line:
            on_line(line)
        siril.cmd(cmd, *args)


def find_result_file(filter_dir: Path) -> Path | None:
    """filter_dir is the filter's own folder (e.g. ".../Blue"), the folder
    the .ssf was actually cd'd into and run from -- it does its own "cd
    lights" internally. Since we don't know for certain where this
    particular .ssf leaves its final stack, this checks every combination
    of {filter_dir, filter_dir/lights} x {itself, its "process" subfolder}."""

    search_dirs = [
        filter_dir,
        filter_dir / "process",
        filter_dir / "lights",
        filter_dir / "lights" / "process",
    ]

    for d in search_dirs:
        for filename in ("result.fit", "result.fits"):
            c = d / filename
            if c.is_file():
                return c

    # Fallback: anything that looks like a result file, case-insensitive
    for d in search_dirs:
        if d.is_dir():
            for pattern in ("*result*.fit", "*result*.fits"):
                hits = list(d.glob(pattern))
                if hits:
                    return hits[0]
    return None


def find_existing_raw_stack(filter_dir: Path, filter_name: str) -> Path | None:
    """Checkpoint helper for phase 1: if '<filter> raw.fit' (or .fits)
    already sits in the filter's own folder, that filter has already been
    stacked in a previous run -- used to skip re-stacking on a resume."""

    for ext in (".fit", ".fits"):
        candidate = filter_dir / f"{filter_name} raw{ext}"
        if candidate.is_file():
            return candidate
    return None


def process_filter(
    siril: "s.SirilInterface",
    main_folder: Path,
    filter_name: str,
    ssf_path: Path,
    raw_dir: Path,
    review_each_stack: bool = True,
) -> bool:
    """Returns True to keep going, False if the user aborted.

    If review_each_stack is False, the per-stack "take a look, then
    Continue/Abort" checkpoint is skipped and the run proceeds straight
    to the next filter automatically."""

    filter_dir = main_folder / filter_name
    lights_dir = filter_dir / "lights"
    if not lights_dir.is_dir():
        siril.log(f"[{filter_name}] No 'lights' folder found, skipping.")
        show_message(
            siril, "Skipped",
            f"'{filter_name}' has no 'lights' subfolder -- skipped.",
        )
        return True

    # Checkpoint: if this filter was already stacked in a previous run
    # (aborted partway through, or just run again), don't redo the stack --
    # that would also crash trying to rename the new result over the
    # existing "<filter> raw.fit". Just make sure it made it into
    # "1 - Registration/Raw" too, and move on.
    existing_raw = find_existing_raw_stack(filter_dir, filter_name)
    if existing_raw is not None:
        siril.log(f"[{filter_name}] Already stacked -- found {existing_raw.name}, skipping.")
        dest = raw_dir / existing_raw.name
        if not dest.is_file():
            shutil.copy2(existing_raw, dest)
            siril.log(f"[{filter_name}] Copied existing stack to {dest} (it was missing there).")
        return True

    # Pre-clean: a "process" folder left over from an earlier attempt that
    # was interrupted mid-stack could confuse the .ssf when it tries to
    # (re)create it.
    for process_dir in (filter_dir / "process", lights_dir / "process"):
        if process_dir.is_dir():
            shutil.rmtree(process_dir)
            siril.log(f"[{filter_name}] Removed leftover 'process' folder from a previous attempt ({process_dir}).")

    siril.log(f"[{filter_name}] Stacking via {ssf_path.name} ...")
    # cd into the filter folder itself, NOT "lights" -- the .ssf does its
    # own "cd lights" as its first real step, since these preprocessing
    # script templates are written to be run from the session's parent
    # folder (which also holds darks/flats/biases when calibration is used).
    siril.cmd("cd", siril_quote(filter_dir))
    status_holder: dict = {"text": ""}
    run_with_progress(
        siril, f"Stacking: {filter_name}",
        f"Running {ssf_path.name} on '{filter_name}'... this can take a "
        "while depending on how many sub-exposures you have.",
        lambda: run_ssf(
            siril, ssf_path,
            on_line=lambda line: status_holder.__setitem__("text", f"> {line}"),
        ),
        status_holder=status_holder,
    )

    result_file = find_result_file(filter_dir)
    if result_file is None:
        show_message(
            siril, "Stacking result not found",
            f"Couldn't find a result.fit/result.fits for '{filter_name}' "
            f"in:\n{filter_dir}\n(or its 'lights'/'process' subfolders).\n\n"
            "The run will stop here so nothing gets renamed/deleted "
            "incorrectly.",
            kind="error",
        )
        return False

    new_path = filter_dir / f"{filter_name} raw{result_file.suffix}"
    result_file.rename(new_path)
    siril.log(f"[{filter_name}] Renamed {result_file.name} -> {new_path.name}")

    for process_dir in (filter_dir / "process", lights_dir / "process"):
        if process_dir.is_dir():
            shutil.rmtree(process_dir)
            siril.log(f"[{filter_name}] Deleted leftover 'process' folder ({process_dir}).")

    dest = raw_dir / new_path.name
    shutil.copy2(new_path, dest)
    siril.log(f"[{filter_name}] Copied stack to {dest}")

    # Full review: load the freshly copied stack into Siril's own view.
    siril.cmd("load", siril_quote(dest))

    if not review_each_stack:
        siril.log(f"[{filter_name}] Stacked -- continuing automatically (review not requested).")
        return True

    return checkpoint_dialog(
        siril,
        f"'{filter_name}' is stacked and now loaded in Siril as:\n\n"
        f"{new_path.name}\n\n"
        "Take a look at it in Siril, then click Continue to move on to "
        "the next filter, or Abort to stop the whole run here."
    )


# --------------------------------------------------------------------------
# Phase 2: convert + register the per-filter stacks into one sequence, then
# an interactive crop applied to that sequence.
# --------------------------------------------------------------------------

def parse_conversion_map(conversion_txt: Path, known_originals: list[str]) -> dict[int, str]:
    """Reads Siril's "<basename>_conversion.txt" and works out which
    sequence frame number (0-based) each of our known original filenames
    ("Blue raw.fit", etc.) ended up as. The exact column layout of this
    file isn't documented, so rather than assume one, this just looks for
    a "_00001." style frame-number pattern and one of our known filenames
    on the same line -- works regardless of the file's exact format."""

    mapping: dict[int, str] = {}
    if not conversion_txt.is_file():
        return mapping

    frame_pattern = re.compile(r"_0*([1-9][0-9]*)\.")

    for line in conversion_txt.read_text(errors="replace").splitlines():
        match = frame_pattern.search(line)
        if not match:
            continue
        frame_number_1based = int(match.group(1))
        for original in known_originals:
            if original in line:
                mapping[frame_number_1based - 1] = original
                break

    return mapping


def filter_name_from_raw_filename(raw_filename: str) -> str:
    """'Blue raw.fit' -> 'Blue'. Falls back to the bare filename stem if
    it doesn't match the " raw" convention phase 1 uses."""

    stem = Path(raw_filename).stem
    if stem.lower().endswith(" raw"):
        return stem[: -len(" raw")]
    return stem


# Short codes used for the FINAL cropped image filenames (in "Output" and
# "2 - Pre-process") instead of the full filter name -- the folder names
# stay full ("2 - Pre-process/Blue/", etc.), only the file inside is
# shortened, e.g. "2 - Pre-process/Blue/B.fit".
FILTER_INITIALS = {
    "luminance": "L", "lum": "L", "l": "L",
    "red": "R", "r": "R",
    "green": "G", "g": "G",
    "blue": "B", "b": "B",
    "hydrogen": "Ha", "h-alpha": "Ha", "halpha": "Ha", "h alpha": "Ha", "ha": "Ha",
    "oxygen": "OIII", "oiii": "OIII", "o3": "OIII",
    "sulfur": "SII", "sulphur": "SII", "sii": "SII", "s2": "SII",
}


def filter_initials(filter_name: str) -> str:
    """Looks up filter_name's short code in FILTER_INITIALS (case-
    insensitive). Anything not recognized falls back to its own first
    three letters, e.g. "Clear" -> "Cle"."""

    key = filter_name.strip().lower()
    if key in FILTER_INITIALS:
        return FILTER_INITIALS[key]
    letters = "".join(ch for ch in filter_name if ch.isalnum())
    if not letters:
        return filter_name
    abbr = letters[:3]
    return abbr[0].upper() + abbr[1:].lower()


def filters_by_initials(
    siril: "s.SirilInterface", selected_filters: list[str],
) -> dict[str, str]:
    """{filter_initials(name): name} for every selected filter -- used by
    both ask_channel_assignment and build_starmask_composite to look up
    "whichever selected filter matches this channel's usual initials" for
    the RGB/HOO default pre-fill. Two differently-named filters can share
    the same initials (e.g. two custom/unrecognized names whose first
    three letters happen to collide, or simply two filters this wizard
    doesn't specifically recognize), and a plain dict comprehension would
    silently let the later one in selected_filters win with no sign
    anything was lost -- whichever channel that initials code maps to
    would then silently default to the wrong filter. Logs a loud warning
    for every collision found (rather than picking one silently) so it's
    at least visible in Siril's log if a starmask's auto-filled channel
    looks wrong; the manual channel-assignment screens remain the way to
    actually fix it, since every dropdown there lists every selected
    filter regardless of this default."""

    by_initials: dict[str, str] = {}
    for name in selected_filters:
        code = filter_initials(name)
        if code in by_initials and by_initials[code] != name:
            siril.log(
                f"[phase 4] Warning: both '{by_initials[code]}' and '{name}' "
                f"share the initials '{code}' -- defaulting to '{name}' for "
                f"any channel that auto-matches '{code}'. Check the manual "
                "channel assignment screen if a starmask channel looks like "
                "it picked the wrong filter."
            )
        by_initials[code] = name
    return by_initials


def clean_previous_sequence_artifacts(process_dir: Path, basename: str) -> list[str]:
    """Checkpoint helper for phase 2: if a previous, aborted run already
    used this sequence name, its leftover generated files (never the
    original "<Filter> raw.fit" inputs, only Siril's own generated
    sequence/registration/crop output) are deleted first, so re-running
    "convert" always starts from a clean, predictable state instead of
    relying on however Siril happens to handle overwriting its own files."""

    patterns = [
        f"{basename}_.seq",
        f"{basename}_conversion.txt",
        f"{basename}_[0-9][0-9][0-9][0-9][0-9].*",
        f"r_{basename}_.seq",
        f"r_{basename}_[0-9][0-9][0-9][0-9][0-9].*",
        f"cropped_r_{basename}_[0-9][0-9][0-9][0-9][0-9].*",
    ]
    removed: list[str] = []
    for pattern in patterns:
        for f in process_dir.glob(pattern):
            f.unlink()
            removed.append(f.name)
    return removed


def move_sequence_files(raw_dir: Path, process_dir: Path, basename: str) -> list[str]:
    """"convert" only ever writes into the current working directory --
    passing it "-out=<dir>" was tried and confirmed to have no effect
    (Siril silently ignores it), so after running "convert" with raw_dir as
    the cwd, this moves just the sequence files it created (never the
    "<Filter> raw.fit" originals, which don't match these name patterns)
    out of raw_dir and into process_dir."""

    patterns = [
        f"{basename}_.seq",
        f"{basename}_conversion.txt",
        f"{basename}_[0-9][0-9][0-9][0-9][0-9].*",
    ]
    moved: list[str] = []
    for pattern in patterns:
        for f in raw_dir.glob(pattern):
            shutil.move(str(f), process_dir / f.name)
            moved.append(f.name)
    return moved


def preprocess_dir_has_output(preprocess_dir: Path) -> bool:
    """True if "2 - Pre-process" already has at least one final
    "<Initials>.fit"/".fits" sitting in any filter subfolder -- i.e. a
    previous run got at least partway through phase 2 for this dataset.
    Used as the top-level, whole-pipeline checkpoint at the very start of a
    re-run, before main_folder's filters have even been picked again."""

    if not preprocess_dir.is_dir():
        return False
    return any(preprocess_dir.glob("*/*.fit")) or any(preprocess_dir.glob("*/*.fits"))


def clean_process_and_output_dirs(
    process_dir: Path, output_dir: Path, siril: "s.SirilInterface | None" = None,
) -> list[str]:
    """Phase 2 doesn't resume from partway through (see module docstring)
    -- every non-skipped run starts fresh. "Process" and "Output" only ever
    hold things this script/Siril generated during phase 2 (leftover
    sequence files, registered frames, conversion.txt, cropped_ output,
    Siril's own "cache" folder from a previous registration, etc.), so this
    just empties both folders completely, whatever sequence name was used
    last time. The "Raw" folder (the "<Filter> raw.fit" stacks from phase 1)
    is a separate sibling folder and is never touched here.

    A file/folder that's locked by another process (most often Siril itself
    still having something loaded from it -- see the "close" call before
    this is invoked) is skipped with a warning logged instead of crashing
    the whole run with a PermissionError."""

    removed: list[str] = []
    for d in (process_dir, output_dir):
        for f in d.iterdir():
            try:
                if f.is_file():
                    f.unlink()
                    removed.append(f"{d.name}/{f.name}")
                elif f.is_dir():
                    shutil.rmtree(f)
                    removed.append(f"{d.name}/{f.name}/")
            except OSError as e:
                if siril is not None:
                    siril.log(f"[phase 2] WARNING: couldn't remove {d.name}/{f.name} (still in use?): {e}")

    return removed


def clean_preprocess_dir(preprocess_dir: Path, siril: "s.SirilInterface | None" = None) -> list[str]:
    """Phase 2 doesn't resume from partway through -- a redo should leave
    "2 - Pre-process" reflecting exactly the current run's crop and filter
    selection, not a mix of it and a previous run's leftovers (e.g. a
    filter that was included before but gets unchecked this time, which
    would otherwise leave its old "<Filter>.fit" sitting there forever).
    This clears everything out of "2 - Pre-process" before phase 2
    regenerates it.

    A file/folder that's locked by another process (most often Siril itself
    still having something loaded from it -- see the "close" call before
    this is invoked) is skipped with a warning logged instead of crashing
    the whole run with a PermissionError."""

    removed: list[str] = []
    for f in preprocess_dir.iterdir():
        try:
            if f.is_dir():
                shutil.rmtree(f)
                removed.append(f.name + "/")
            elif f.is_file():
                f.unlink()
                removed.append(f.name)
        except OSError as e:
            if siril is not None:
                siril.log(f"[phase 2] WARNING: couldn't remove {f.name} (still in use?): {e}")

    return removed


def convert_and_register(
    siril: "s.SirilInterface", cfg: dict, raw_dir: Path, process_dir: Path,
) -> dict | None:
    """Prompts for a sequence name, converts the "<Filter> raw.fit" files
    sitting in raw_dir into a Siril sequence built inside process_dir (which
    becomes the working directory for every step from here on), registers
    it, and works out which frame number is which filter. Returns None if
    the user cancels or something goes wrong (with a message already
    shown), otherwise:
    {"basename": str, "registered_seqname": str,
     "frame_filter_map": {0-based frame index: filter name}}."""

    raw_files = sorted(raw_dir.glob("* raw.fit")) + sorted(raw_dir.glob("* raw.fits"))
    if not raw_files:
        show_message(
            siril, "Nothing to convert",
            f"No '<Filter> raw.fit' files were found in:\n{raw_dir}",
            kind="error",
        )
        return None

    default_name = cfg.get("last_sequence_basename", "Orion_Nebula")
    basename = prompt_text(
        siril, "Name this sequence",
        "Siril needs a base name for the sequence it will build from your "
        f"{len(raw_files)} stacked filter file(s) "
        "(e.g. \"Orion_Nebula\", \"Andromeda_Galaxy\"):",
        default=default_name,
    )
    if not basename:
        siril.log("Sequence naming cancelled -- aborting phase 2.")
        return None
    cfg["last_sequence_basename"] = basename
    save_config(cfg)

    removed = clean_previous_sequence_artifacts(process_dir, basename)
    if removed:
        siril.log(
            f"[phase 2] Cleaned up {len(removed)} leftover file(s) from a "
            f"previous attempt with this sequence name: {', '.join(removed)}"
        )

    siril.log(f"[phase 2] Converting {len(raw_files)} file(s) into sequence '{basename}' ...")
    # "convert" only ever writes into the current working directory --
    # "-out=<dir>" was tried and confirmed to have no effect (Siril quietly
    # ignored it and wrote into the cwd regardless). So: convert with "Raw"
    # as the cwd (where the "<Filter> raw.fit" originals actually are),
    # then move just the newly-created sequence files into "Process"
    # ourselves, and cd there for every step from here on (load_seq,
    # register, seqcrop).
    siril.cmd("cd", siril_quote(raw_dir))
    run_with_progress(
        siril, "Converting",
        f"Converting {len(raw_files)} file(s) into sequence '{basename}'...",
        lambda: siril.cmd("convert", basename),
    )
    moved = move_sequence_files(raw_dir, process_dir, basename)
    siril.log(f"[phase 2] Moved {len(moved)} sequence file(s) from '{RAW_SUBDIR_NAME}' into '{PROCESS_SUBDIR_NAME}'.")
    siril.cmd("cd", siril_quote(process_dir))
    # "convert" names the sequence "<basename>_" (with a trailing underscore --
    # frames come out as "<basename>_00001.fit" etc), NOT just "<basename>".
    # Loading it back under the wrong name is what produced Siril's vague
    # "Generic error" the first time this was tried.
    siril.cmd("load_seq", f"{basename}_")

    known_originals = [f.name for f in raw_files]
    conversion_txt = process_dir / f"{basename}_conversion.txt"
    frame_filter_map = parse_conversion_map(conversion_txt, known_originals)

    if len(frame_filter_map) != len(raw_files):
        missing = set(known_originals) - set(frame_filter_map.values())
        siril.log(
            f"[phase 2] WARNING: only matched {len(frame_filter_map)} of "
            f"{len(raw_files)} files from {conversion_txt.name}. "
            f"Unmatched: {', '.join(missing) or 'none listed'}"
        )
        show_message(
            siril, "Couldn't fully verify frame order",
            f"Only matched {len(frame_filter_map)} of {len(raw_files)} "
            f"filter files to their sequence frame number by reading "
            f"{conversion_txt.name}.\n\n"
            "Continuing would risk mislabeling a filter later on, so this "
            "stops here. Check Siril's log for exactly what was found.",
            kind="error",
        )
        return None

    for idx in sorted(frame_filter_map):
        siril.log(f"[phase 2] Frame {idx + 1} -> {frame_filter_map[idx]} ({filter_name_from_raw_filename(frame_filter_map[idx])})")

    siril.log(f"[phase 2] Registering sequence '{basename}' ...")
    run_with_progress(
        siril, "Registering",
        f"Registering sequence '{basename}' (global star alignment)...",
        lambda: siril.cmd("register", basename),
    )

    registered_seqname = f"r_{basename}_"
    # Same trailing-underscore naming as above: "register" writes out
    # "r_<basename>_.seq", not "r_<basename>.seq".
    siril.cmd("load_seq", registered_seqname)

    filter_map_by_name = {
        idx: filter_name_from_raw_filename(fname) for idx, fname in frame_filter_map.items()
    }

    return {
        "basename": basename,
        "registered_seqname": registered_seqname,
        "frame_filter_map": filter_map_by_name,
    }


def get_frame_reference_index(siril: "s.SirilInterface") -> int:
    """0-based index of the currently loaded sequence's reference frame,
    falling back to 0 (the first frame) if it can't be read."""

    try:
        seq = siril.get_seq()
        if seq is not None and getattr(seq, "reference_image", None) is not None:
            return int(seq.reference_image)
    except Exception:
        pass
    return 0


def render_frame_preview(siril: "s.SirilInterface", frame_index: int, max_dim: int | None = None) -> tuple[Image.Image, float] | None:
    """Fetches a frame's pixel data and turns it into a display-ready PIL
    Image. With max_dim=None (the default), returns the image at its full
    resolution (scale 1.0) so the caller can do its own zoom/fit scaling.
    Passing a max_dim instead pre-scales the image to fit within it, plus
    returns the scale factor used (so canvas coordinates can be mapped back
    to real pixel coordinates)."""

    try:
        fit = siril.get_seq_frame(frame_index, with_pixels=True, preview=True)
    except TypeError:
        # Older sirilpy without a "preview" kwarg -- fall back and stretch ourselves.
        fit = siril.get_seq_frame(frame_index, with_pixels=True)
    if fit is None or fit.data is None:
        return None

    data = np.asarray(fit.data)

    # FFit pixel data is (channels, height, width); collapse to a single
    # 2D array (mono) or (h, w, 3) for display.
    if data.ndim == 3:
        if data.shape[0] in (1, 3):
            data = np.moveaxis(data, 0, -1)
            if data.shape[-1] == 1:
                data = data[:, :, 0]

    # FITS pixel data is stored bottom-up (row 0 = the bottom of the image),
    # but Siril's own viewer -- and "crop"/"seqcrop"'s x/y, documented as
    # "the top left corner" of the selection -- both work in normal
    # top-down, top-left-origin coordinates, flipping the raw data for
    # display. Without this flip here, this preview showed each frame
    # upside-down relative to Siril's own window, so a crop box drawn to
    # match what you saw in Siril landed in the wrong place once "seqcrop"
    # applied it -- confirmed from a reference frame that displayed
    # reversed here but got cropped as if it hadn't been.
    data = np.ascontiguousarray(np.flipud(data))

    if data.dtype != np.uint8:
        # Not already an 8-bit preview -- do a simple percentile stretch
        # purely for on-screen display. Never touches the saved data.
        lo, hi = np.percentile(data, (0.5, 99.5))
        if hi <= lo:
            hi = lo + 1
        data = np.clip((data.astype(np.float32) - lo) / (hi - lo), 0, 1)
        data = (data * 255).astype(np.uint8)

    mode = "L" if data.ndim == 2 else "RGB"
    image = Image.fromarray(data, mode=mode)

    if max_dim is None:
        return image, 1.0

    scale = min(max_dim / image.width, max_dim / image.height)
    scale = min(scale, 1.0) if scale > 0 else 1.0
    display_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    resample = getattr(getattr(Image, "Resampling", Image), "BILINEAR")
    display_image = image.resize(display_size, resample)

    return display_image, scale


def run_crop_window(
    siril: "s.SirilInterface",
    frame_filter_map: dict[int, str],
    reference_index: int,
) -> dict | None:
    """The interactive crop window. Returns None if cancelled, otherwise
    {"x": int, "y": int, "width": int, "height": int,
     "included_frames": [0-based frame indices left checked]}
    (coordinates are in the ORIGINAL image's pixel space, not canvas
    pixels)."""

    root = _new_popup_root(siril, "Crop the aligned sequence")
    _header(root, "Crop the aligned sequence")

    body = ttk.Frame(root)
    body.pack(fill="both", expand=True, padx=24, pady=(0, 6))

    list_card = ttk.LabelFrame(body, text="Filters", padding=10)
    list_card.pack(side="left", fill="y", padx=(0, 12))

    preview_card = ttk.Frame(body, style="Card.TFrame", padding=10)
    preview_card.pack(side="left", fill="both", expand=True)

    _wrapping_label(
        root,
        "Drag on the preview to draw the crop box, then drag its edges/"
        "corners to resize it or drag inside it to move it. Scroll the "
        "mouse wheel over the preview to zoom in/out, and hold the "
        "middle mouse button to pan around. Click a filter name to "
        "check how the crop looks on that frame too.",
        padx=24, pady=(0, 8),
    )

    # Zoom in / zoom out / fit-to-window toolbar, top-left above the preview.
    toolbar = ttk.Frame(preview_card, style="Card.TFrame")
    toolbar.pack(fill="x", pady=(0, 8))

    zoom_pct_label = ttk.Label(toolbar, style="Card.TLabel", text="100%")

    canvas_frame = ttk.Frame(preview_card, style="Card.TFrame")
    canvas_frame.pack(fill="both", expand=True)
    canvas_frame.rowconfigure(0, weight=1)
    canvas_frame.columnconfigure(0, weight=1)

    canvas = tk.Canvas(
        canvas_frame, background=BG_CARD_ALT, highlightthickness=0,
        width=480, height=480,
    )
    canvas.grid(row=0, column=0, sticky="nsew")
    vbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
    vbar.grid(row=0, column=1, sticky="ns")
    hbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
    hbar.grid(row=1, column=0, sticky="ew")
    canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

    MIN_ZOOM, MAX_ZOOM, ZOOM_STEP = 0.05, 8.0, 1.25
    HANDLE_R = 4     # half-size (canvas px) of each drag handle square, fixed regardless of zoom
    HANDLE_HIT = 8   # how close (canvas px) a click needs to be to grab a handle
    MIN_BOX = 4      # smallest crop box side, in canvas px, before a drag is ignored

    CURSOR_FOR_HANDLE = {
        "nw": "size_nw_se", "se": "size_nw_se",
        "ne": "size_ne_sw", "sw": "size_ne_sw",
        "n": "size_ns", "s": "size_ns",
        "e": "size_we", "w": "size_we",
    }

    state = {
        "current_frame": reference_index,
        "base_image": None,   # full-resolution PIL image for current_frame
        "photo": None,        # keep a reference so Tk doesn't garbage-collect it
        "scale": 1.0,         # current display scale relative to base_image pixels
        "fit_mode": True,     # True = auto-refit scale whenever the window resizes
        "rect_id": None,
        "handle_ids": {},     # name -> canvas item id, for the 8 drag handles
        "rect_image": None,   # (ix0, iy0, ix1, iy1) in ORIGINAL image pixel space
        "drag_mode": None,    # None | "draw" | "move" | "resize"
        "resize_handle": None,
        "drag_start_canvas": None,
        "drag_rect_canvas": None,   # live [x0, y0, x1, y1] canvas coords during a drag
        "move_origin_rect": None,   # rect_canvas as it was when a "move" drag started
        "included": {idx: tk.BooleanVar(value=True) for idx in frame_filter_map},
        "result": None,
        "panning": False,   # True while the middle mouse button is held/dragged
        "offset": (0.0, 0.0),  # canvas-space (x, y) the image's top-left is
                                # drawn at -- keeps it centered when it's
                                # smaller than the canvas, instead of stuck
                                # at the top-left corner
    }

    def overlay_handle_positions(rect_canvas):
        x0, y0, x1, y1 = rect_canvas
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        return {
            "nw": (x0, y0), "n": (mx, y0), "ne": (x1, y0),
            "e": (x1, my), "se": (x1, y1), "s": (mx, y1),
            "sw": (x0, y1), "w": (x0, my),
        }

    def current_rect_canvas():
        if not state["rect_image"]:
            return None
        scale = state["scale"] or 1.0
        off_x, off_y = state["offset"]
        ix0, iy0, ix1, iy1 = state["rect_image"]
        return (ix0 * scale + off_x, iy0 * scale + off_y, ix1 * scale + off_x, iy1 * scale + off_y)

    def draw_overlay(rect_canvas):
        """(Re)creates the crop rectangle + its 8 drag handles at rect_canvas
        (canvas coords). Only called right after a full canvas.delete("all")
        redraw (render_canvas / frame switch / zoom)."""
        x0, y0, x1, y1 = rect_canvas
        state["rect_id"] = canvas.create_rectangle(x0, y0, x1, y1, outline=ACCENT, width=2)
        state["handle_ids"] = {}
        for name, (hx, hy) in overlay_handle_positions(rect_canvas).items():
            state["handle_ids"][name] = canvas.create_rectangle(
                hx - HANDLE_R, hy - HANDLE_R, hx + HANDLE_R, hy + HANDLE_R,
                fill=ACCENT, outline=BG_MAIN, width=1,
            )

    def update_overlay_coords(rect_canvas):
        """Cheap reposition of the existing rect + handle canvas items while
        dragging -- no full redraw/flicker."""
        if state["rect_id"] is None:
            return
        x0, y0, x1, y1 = rect_canvas
        canvas.coords(state["rect_id"], x0, y0, x1, y1)
        for name, (hx, hy) in overlay_handle_positions(rect_canvas).items():
            hid = state["handle_ids"].get(name)
            if hid is not None:
                canvas.coords(hid, hx - HANDLE_R, hy - HANDLE_R, hx + HANDLE_R, hy + HANDLE_R)

    def hit_test(cx, cy, rect_canvas):
        for name, (hx, hy) in overlay_handle_positions(rect_canvas).items():
            if abs(cx - hx) <= HANDLE_HIT and abs(cy - hy) <= HANDLE_HIT:
                return "handle", name
        x0, y0, x1, y1 = rect_canvas
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return "body", None
        return None, None

    def compute_fit_scale() -> float:
        image = state["base_image"]
        if image is None:
            return 1.0
        # Use the canvas widget's OWN size, not canvas_frame's -- the frame
        # also contains the scrollbars (grid cols/rows 1), so its width/
        # height is bigger than what the canvas can actually show. Fitting
        # to the frame's size instead of the canvas's meant the "fit" image
        # was always slightly too large, leaving its bottom/right edge
        # hidden behind the scrollbars.
        canvas.update_idletasks()
        avail_w = canvas.winfo_width()
        avail_h = canvas.winfo_height()
        if avail_w <= 1 or avail_h <= 1:
            avail_w, avail_h = 480, 480
        scale = min(avail_w / image.width, avail_h / image.height)
        return scale if scale > 0 else 1.0

    def render_canvas():
        image = state["base_image"]
        if image is None:
            return
        scale = state["scale"]
        display_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        resample = getattr(getattr(Image, "Resampling", Image), "BILINEAR")
        display_image = image.resize(display_size, resample)
        state["photo"] = ImageTk.PhotoImage(display_image)

        # Center the image in the canvas when it's smaller than the visible
        # area (instead of leaving it pinned to the top-left corner). When
        # zoomed in past the canvas size there's no room to center in that
        # dimension, so the offset there is just 0 and normal scrolling
        # takes over. update_idletasks() first, so canvas.winfo_width()/
        # height() reflect the widget's real, current on-screen size rather
        # than a stale pre-layout placeholder (which is what was causing the
        # image to render pinned to the top-left despite the centering
        # logic below).
        canvas.update_idletasks()
        canvas_w = canvas.winfo_width() or 480
        canvas_h = canvas.winfo_height() or 480
        off_x = max(0.0, (canvas_w - display_size[0]) / 2)
        off_y = max(0.0, (canvas_h - display_size[1]) / 2)
        state["offset"] = (off_x, off_y)

        canvas.delete("all")
        canvas.create_image(off_x, off_y, anchor="nw", image=state["photo"])
        canvas.configure(scrollregion=(
            0, 0,
            max(canvas_w, display_size[0] + off_x),
            max(canvas_h, display_size[1] + off_y),
        ))
        state["rect_id"] = None
        state["handle_ids"] = {}
        rect_canvas = current_rect_canvas()
        if rect_canvas is not None:
            draw_overlay(rect_canvas)
        zoom_pct_label.config(text=f"{round(scale * 100)}%")

    def apply_zoom(factor: float | None = None, fit: bool = False):
        if fit:
            state["fit_mode"] = True
            state["scale"] = compute_fit_scale()
        else:
            state["fit_mode"] = False
            new_scale = state["scale"] * factor
            state["scale"] = max(MIN_ZOOM, min(MAX_ZOOM, new_scale))
        render_canvas()

    ttk.Button(toolbar, text="Zoom In", command=lambda: apply_zoom(factor=ZOOM_STEP)).pack(side="left")
    ttk.Button(toolbar, text="Zoom Out", command=lambda: apply_zoom(factor=1 / ZOOM_STEP)).pack(side="left", padx=(6, 0))
    ttk.Button(toolbar, text="Fit to Window", command=lambda: apply_zoom(fit=True)).pack(side="left", padx=(6, 0))
    zoom_pct_label.pack(side="left", padx=(10, 0))

    def on_canvas_frame_resize(event):
        if state["base_image"] is None:
            return
        if state["fit_mode"]:
            state["scale"] = compute_fit_scale()
        # Re-render even when not fitting to window, so the centering
        # offset stays correct as the window/canvas is resized.
        render_canvas()

    canvas_frame.bind("<Configure>", on_canvas_frame_resize)

    def on_mousewheel(event):
        if state["base_image"] is None:
            return
        delta = getattr(event, "delta", 0)
        if delta == 0:
            # X11 sends Button-4 (up/zoom in) / Button-5 (down/zoom out)
            # instead of a MouseWheel event with .delta.
            delta = 120 if getattr(event, "num", 0) == 4 else -120
        factor = ZOOM_STEP if delta > 0 else (1 / ZOOM_STEP)

        old_scale = state["scale"] or 1.0
        new_scale = max(MIN_ZOOM, min(MAX_ZOOM, old_scale * factor))
        if new_scale == old_scale:
            return

        # Keep the image point under the cursor fixed on screen while
        # zooming, the way most image viewers handle wheel-zoom.
        old_off_x, old_off_y = state["offset"]
        cx, cy = canvas.canvasx(event.x), canvas.canvasy(event.y)
        ix, iy = (cx - old_off_x) / old_scale, (cy - old_off_y) / old_scale

        state["fit_mode"] = False
        state["scale"] = new_scale
        render_canvas()

        new_off_x, new_off_y = state["offset"]
        region = canvas.cget("scrollregion").split()
        total_w = float(region[2]) if len(region) == 4 else 1.0
        total_h = float(region[3]) if len(region) == 4 else 1.0
        new_cx, new_cy = ix * new_scale + new_off_x, iy * new_scale + new_off_y
        left, top = new_cx - event.x, new_cy - event.y
        if total_w > 0:
            canvas.xview_moveto(max(0.0, min(1.0, left / total_w)))
        if total_h > 0:
            canvas.yview_moveto(max(0.0, min(1.0, top / total_h)))

    canvas.bind("<MouseWheel>", on_mousewheel)  # Windows / macOS
    canvas.bind("<Button-4>", on_mousewheel)    # Linux scroll up
    canvas.bind("<Button-5>", on_mousewheel)    # Linux scroll down

    def load_preview(frame_index: int):
        rendered = render_frame_preview(siril, frame_index)
        if rendered is None:
            siril.log(f"[phase 2] Could not render a preview for frame {frame_index + 1}.")
            return
        image, _ = rendered
        state["base_image"] = image
        if state["fit_mode"]:
            state["scale"] = compute_fit_scale()
        render_canvas()

    def select_frame(frame_index: int):
        state["current_frame"] = frame_index
        load_preview(frame_index)

    for idx in sorted(frame_filter_map):
        row = ttk.Frame(list_card, style="Card.TFrame")
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=state["included"][idx]).pack(side="left")
        name = frame_filter_map[idx] + ("  (reference)" if idx == reference_index else "")
        link = ttk.Label(row, text=name, style="Card.TLabel", cursor="hand2")
        link.pack(side="left", padx=(4, 0))
        link.bind("<Button-1>", lambda e, i=idx: select_frame(i))

    # Adjustable crop box, the same way Siril's own selection tool works:
    # drag to draw a new box; once one exists, drag inside it to move it, or
    # drag one of its 8 handles to resize from that edge/corner -- no need
    # to get it perfect on the first try.

    def clamp_to_image(cx, cy):
        """Keeps a canvas coordinate from going past the displayed image's
        own borders -- the crop box can never be drawn/resized/moved larger
        than the actual image."""
        image = state["base_image"]
        if image is None:
            return cx, cy
        scale = state["scale"] or 1.0
        off_x, off_y = state["offset"]
        min_x, min_y = off_x, off_y
        max_x, max_y = off_x + image.width * scale, off_y + image.height * scale
        return min(max(min_x, cx), max_x), min(max(min_y, cy), max_y)

    def on_press(event):
        cx, cy = canvas.canvasx(event.x), canvas.canvasy(event.y)
        cx, cy = clamp_to_image(cx, cy)
        rect_canvas = current_rect_canvas()
        kind, handle = hit_test(cx, cy, rect_canvas) if rect_canvas else (None, None)

        if kind == "handle":
            state["drag_mode"] = "resize"
            state["resize_handle"] = handle
            state["drag_rect_canvas"] = list(rect_canvas)
        elif kind == "body":
            state["drag_mode"] = "move"
            state["drag_start_canvas"] = (cx, cy)
            state["move_origin_rect"] = rect_canvas
            state["drag_rect_canvas"] = list(rect_canvas)
        else:
            # Start a brand-new box, replacing any existing one.
            if state["rect_id"] is not None:
                canvas.delete(state["rect_id"])
                for hid in state["handle_ids"].values():
                    canvas.delete(hid)
                state["rect_id"] = None
                state["handle_ids"] = {}
            state["drag_mode"] = "draw"
            state["drag_start_canvas"] = (cx, cy)
            state["drag_rect_canvas"] = [cx, cy, cx, cy]
            state["rect_id"] = canvas.create_rectangle(cx, cy, cx, cy, outline=ACCENT, width=2)

    def on_drag(event):
        mode = state["drag_mode"]
        if mode is None:
            return
        cx, cy = canvas.canvasx(event.x), canvas.canvasy(event.y)
        cx, cy = clamp_to_image(cx, cy)

        if mode == "draw":
            x0, y0 = state["drag_start_canvas"]
            state["drag_rect_canvas"] = [x0, y0, cx, cy]
            canvas.coords(state["rect_id"], x0, y0, cx, cy)
        elif mode == "move":
            x0, y0 = state["drag_start_canvas"]
            dx, dy = cx - x0, cy - y0
            ox0, oy0, ox1, oy1 = state["move_origin_rect"]
            w, h = ox1 - ox0, oy1 - oy0
            image = state["base_image"]
            scale = state["scale"] or 1.0
            off_x, off_y = state["offset"]
            max_w = image.width * scale if image else ox1 - off_x
            max_h = image.height * scale if image else oy1 - off_y
            nx0 = min(max(off_x, ox0 + dx), max(off_x, off_x + max_w - w))
            ny0 = min(max(off_y, oy0 + dy), max(off_y, off_y + max_h - h))
            rect = [nx0, ny0, nx0 + w, ny0 + h]
            state["drag_rect_canvas"] = rect
            update_overlay_coords(rect)
        elif mode == "resize":
            x0, y0, x1, y1 = state["drag_rect_canvas"]
            handle = state["resize_handle"]
            if "n" in handle:
                y0 = cy
            if "s" in handle:
                y1 = cy
            if "w" in handle:
                x0 = cx
            if "e" in handle:
                x1 = cx
            state["drag_rect_canvas"] = [x0, y0, x1, y1]
            update_overlay_coords([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)])

    def on_release(event):
        mode = state["drag_mode"]
        if mode is None:
            return
        x0, y0, x1, y1 = state["drag_rect_canvas"]
        nx0, nx1 = sorted((x0, x1))
        ny0, ny1 = sorted((y0, y1))
        scale = state["scale"] or 1.0
        off_x, off_y = state["offset"]
        if (nx1 - nx0) >= MIN_BOX and (ny1 - ny0) >= MIN_BOX:
            state["rect_image"] = (
                (nx0 - off_x) / scale, (ny0 - off_y) / scale,
                (nx1 - off_x) / scale, (ny1 - off_y) / scale,
            )
        state["drag_mode"] = None
        state["resize_handle"] = None
        state["drag_start_canvas"] = None
        state["move_origin_rect"] = None
        render_canvas()

    def on_motion(event):
        if state["panning"] or state["drag_mode"] is not None:
            return
        cx, cy = canvas.canvasx(event.x), canvas.canvasy(event.y)
        rect_canvas = current_rect_canvas()
        cursor = "cross"
        if rect_canvas is not None:
            kind, handle = hit_test(cx, cy, rect_canvas)
            if kind == "handle":
                cursor = CURSOR_FOR_HANDLE.get(handle, "cross")
            elif kind == "body":
                cursor = "fleur"
        try:
            canvas.config(cursor=cursor)
        except tk.TclError:
            pass

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<Motion>", on_motion)

    # Middle-mouse-button panning, the same way Siril's own image view works:
    # hold the middle button and drag to pan around when zoomed in, with a
    # hand cursor while doing so.
    def on_pan_start(event):
        if state["base_image"] is None:
            return
        state["panning"] = True
        canvas.scan_mark(event.x, event.y)
        canvas.config(cursor="hand2")

    def on_pan_drag(event):
        if not state["panning"]:
            return
        canvas.scan_dragto(event.x, event.y, gain=1)

    def on_pan_end(event):
        state["panning"] = False
        on_motion(event)

    canvas.bind("<ButtonPress-2>", on_pan_start)
    canvas.bind("<B2-Motion>", on_pan_drag)
    canvas.bind("<ButtonRelease-2>", on_pan_end)

    # Force Tk to finish laying out the window before computing the initial
    # fit-to-window scale/centering -- otherwise canvas_frame/canvas still
    # report their small pre-layout placeholder size (e.g. the 480x480 the
    # canvas was created with) instead of the real, much larger window size,
    # which is what caused the very first render to come out tiny (e.g. an
    # 8% "fit") and pinned to the top-left instead of centered.
    root.update_idletasks()
    load_preview(reference_index)

    def compute_image_rect() -> tuple[int, int, int, int] | None:
        if not state["rect_image"]:
            return None
        ix0, iy0, ix1, iy1 = state["rect_image"]
        iw, ih = ix1 - ix0, iy1 - iy0
        if iw <= 0 or ih <= 0:
            return None
        return int(ix0), int(iy0), int(iw), int(ih)

    def on_continue():
        rect = compute_image_rect()
        if rect is None:
            show_message(siril, "No crop drawn", "Drag a rectangle on the preview first.", kind="error")
            return
        included = [idx for idx, var in state["included"].items() if var.get()]
        if not included:
            show_message(siril, "Nothing selected", "At least one filter needs to stay checked.", kind="error")
            return
        state["result"] = {
            "x": rect[0], "y": rect[1], "width": rect[2], "height": rect[3],
            "included_frames": included,
        }
        root.destroy()

    def on_cancel():
        state["result"] = None
        root.destroy()

    # Closing this window via the OS "X" is the same as clicking Cancel.
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    btns = _button_row(root)
    ttk.Button(btns, text="Continue", style="Accent.TButton", command=on_continue).pack(side="right")
    ttk.Button(btns, text="Cancel", command=on_cancel).pack(side="right", padx=(0, 8))

    root.mainloop()
    # Edge case: the PERSISTENT wizard window (this popup's parent) got
    # closed while this crop window was open, tearing this one down too.
    _check_not_closed()
    return state["result"]


def run_registration_and_crop_phase(
    siril: "s.SirilInterface", cfg: dict, registration_dir: Path, preprocess_dir: Path,
) -> bool:
    """Phase 2 end to end. Returns True on success, False if the user
    backed out or something failed (message already shown/logged)."""

    raw_dir = registration_dir / RAW_SUBDIR_NAME
    process_dir = registration_dir / PROCESS_SUBDIR_NAME
    output_dir = registration_dir / OUTPUT_SUBDIR_NAME
    for d in (raw_dir, process_dir, output_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Whether to even get here at all (vs. skipping straight to phase 3) is
    # decided by the top-level checkpoint in main(), before filters were
    # even picked again -- by the time this runs, redoing phase 2 has
    # already been confirmed. Phase 2 itself doesn't resume from partway
    # through an aborted attempt -- it always starts fresh, so clear out
    # anything it generated last time first (never the "<Filter> raw.fit"
    # originals from phase 1, which live in "Raw" -- a separate folder this
    # never touches). This also clears "2 - Pre-process" itself, so a redo
    # can't leave a stale "<Filter>.fit" behind for a filter that was
    # included before but gets unchecked this time.
    # Siril may still have an image loaded from an earlier run -- most
    # commonly a checkpoint file from a previous phase 3 run (see
    # run_phase3_pipeline), which lives inside "2 - Pre-process".
    # Windows won't let a folder be deleted while Siril still has a file
    # inside it open, which is exactly what caused a PermissionError /
    # WinError 32 here before this was added. Closing whatever's currently
    # loaded releases that lock; if nothing was loaded this just logs
    # Siril's own "nothing to close" complaint and moves on.
    try:
        siril.cmd("close")
    except Exception as e:
        siril.log(f"[phase 2] Nothing to close before cleanup (or close failed): {e}")

    removed = clean_process_and_output_dirs(process_dir, output_dir, siril)
    removed += [f"{PREPROCESS_DIR_NAME}/{name}" for name in clean_preprocess_dir(preprocess_dir, siril)]
    if removed:
        siril.log(
            f"[phase 2] Starting fresh: removed {len(removed)} leftover "
            f"file(s)/folder(s): {', '.join(removed)}"
        )

    wizard_set_current("convert_register")
    conversion = convert_and_register(siril, cfg, raw_dir, process_dir)
    if conversion is None:
        return False
    wizard_mark_done("convert_register")

    frame_filter_map = conversion["frame_filter_map"]
    registered_seqname = conversion["registered_seqname"]
    reference_index = get_frame_reference_index(siril)

    wizard_set_current("crop")
    crop = run_crop_window(siril, frame_filter_map, reference_index)
    if crop is None:
        siril.log("[phase 2] Crop cancelled -- aborting phase 2.")
        return False
    wizard_mark_done("crop")
    wizard_set_current("copy_preprocess")

    excluded_frames = [i for i in frame_filter_map if i not in crop["included_frames"]]
    if excluded_frames:
        for idx in excluded_frames:
            # 1-based, inclusive range for Siril's select/unselect commands.
            siril.cmd("unselect", registered_seqname, str(idx + 1), str(idx + 1))
        siril.log(
            "[phase 2] Unselected frame(s) before cropping: "
            + ", ".join(str(i + 1) for i in excluded_frames)
        )

    siril.log(
        f"[phase 2] Cropping '{registered_seqname}' to "
        f"x={crop['x']} y={crop['y']} width={crop['width']} height={crop['height']} ..."
    )
    run_with_progress(
        siril, "Cropping",
        f"Cropping '{registered_seqname}' to "
        f"{crop['width']}x{crop['height']}...",
        lambda: siril.cmd(
            "seqcrop", registered_seqname,
            str(crop["x"]), str(crop["y"]), str(crop["width"]), str(crop["height"]),
            "-prefix=cropped_",
        ),
    )

    any_failed = False
    for idx in crop["included_frames"]:
        filter_name = frame_filter_map[idx]
        # registered_seqname already ends in "_" (e.g. "r_ngc_3372_"), matching
        # how Siril names the frame files themselves -- no extra "_" here.
        # "seqcrop" writes into the current working directory, i.e. "Process".
        cropped_path = process_dir / f"cropped_{registered_seqname}{idx + 1:05d}.fit"
        if not cropped_path.is_file():
            # Be defensive about the exact numbering/extension in case
            # Siril's convention differs slightly from what's assumed here.
            candidates = list(process_dir.glob(f"cropped_{registered_seqname}{idx + 1:05d}.*"))
            cropped_path = candidates[0] if candidates else None

        if not cropped_path or not cropped_path.is_file():
            siril.log(f"[phase 2] WARNING: no cropped output found for '{filter_name}' (frame {idx + 1}).")
            any_failed = True
            continue

        # Phase 2's own final result for this filter is COPIED (not moved --
        # the "cropped_..." file stays in "Process" too) into "Output",
        # renamed to its short initials (e.g. "Blue" -> "B.fit",
        # "H-alpha" -> "Ha.fit") instead of the full filter name.
        initials = filter_initials(filter_name)
        output_path = output_dir / f"{initials}{cropped_path.suffix}"
        shutil.copy2(cropped_path, output_path)
        siril.log(f"[phase 2] '{filter_name}': copied {cropped_path.name} -> '{OUTPUT_SUBDIR_NAME}/{output_path.name}'")

        # ... and copied again (same "<Initials>.fit" name) into
        # "2 - Pre-process/<Filter>/" for the next phase -- the subfolder
        # itself keeps the full filter name, only the file is shortened.
        filter_subdir = preprocess_dir / filter_name
        filter_subdir.mkdir(parents=True, exist_ok=True)
        dest = filter_subdir / f"{initials}{output_path.suffix}"
        shutil.copy2(output_path, dest)
        siril.log(f"[phase 2] '{filter_name}': copied {output_path.name} -> {dest}")

    if any_failed:
        show_message(
            siril, "Some filters didn't get a cropped output",
            "Check Siril's log for which filter(s) were skipped -- their "
            "cropped file wasn't found where expected.",
            kind="error",
        )
        return False

    # Everything phase 2 needed out of "Process" (the per-filter cropped
    # files) has now been copied into "Output" and "2 - Pre-process" --
    # "Process" itself (the raw conversion/registration/crop working files:
    # the sequence, its .seq file, the registered/cropped frames, etc.) is
    # just clutter from here on, so remove it. Close whatever Siril still
    # has loaded from in there first and "cd" out of it, same as the
    # cleanup above -- Windows won't delete a folder Siril still has a
    # handle into.
    try:
        siril.cmd("close")
    except Exception as e:
        siril.log(f"[phase 2] Nothing to close before removing '{PROCESS_SUBDIR_NAME}' (or close failed): {e}")
    try:
        siril.cmd("cd", siril_quote(registration_dir))
    except Exception as e:
        siril.log(f"[phase 2] Couldn't 'cd' out of '{PROCESS_SUBDIR_NAME}' before removing it: {e}")
    try:
        shutil.rmtree(process_dir)
        siril.log(f"[phase 2] Removed '{PROCESS_SUBDIR_NAME}' folder -- no longer needed now that its output is in '{PREPROCESS_DIR_NAME}'.")
    except Exception as e:
        siril.log(f"[phase 2] WARNING: couldn't remove '{PROCESS_SUBDIR_NAME}' folder ({e}) -- you can delete it by hand.")

    wizard_mark_done("copy_preprocess")
    show_message(
        siril, "Phase 2 complete",
        "Cropped images have been copied into "
        f"'{PREPROCESS_DIR_NAME}', one subfolder per filter.",
    )
    return True


# --------------------------------------------------------------------------
# Phase 3: running the configured pipeline.
#
# This wizard does NOT drive any tool's parameters -- built-in Siril tools
# (GHT, subsky, denoise, ...) have no scripting API to pop their own GUI
# dialog open, and Python scripts are meant to be tuned interactively by
# the user too. So this wizard's job is purely to load the right working
# file, tell the user which tool this step is, launch it for them when it
# can (Python scripts, via "pyscript"), and then wait -- once the user says
# they're done, it saves a checkpoint copy under the filter's chained
# filename (e.g. "B.fit" -> "B - BE.fit" -> "B - BE, SH.fit") and moves on
# to the next step. Star Removal is a special case: those scripts commonly
# produce two output files (a starless image and, optionally, a star mask)
# rather than just updating the loaded image in place -- see
# handle_star_removal_step().
# --------------------------------------------------------------------------

def find_filter_subfolder(preprocess_dir: Path, filter_name: str) -> Path | None:
    """Case-insensitive lookup of filter_name's subfolder inside
    "2 - Pre-process"."""

    if not preprocess_dir.is_dir():
        return None
    for d in preprocess_dir.iterdir():
        if d.is_dir() and d.name.lower() == filter_name.lower():
            return d
    return None


def find_working_file(folder: Path, stem: str) -> Path | None:
    """Looks for "<stem>.fit" or "<stem>.fits" directly inside folder."""

    for ext in (".fit", ".fits"):
        candidate = folder / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    return None


def chained_filename(initials: str, chain: list[str]) -> str:
    """Builds the checkpoint filename stem (no extension) for a filter's
    initials and its list of completed step codes so far, e.g. "B" +
    ["BE", "SH"] -> "B - BE, SH". Assumes chain is non-empty -- the very
    first file (before any step has run) is just "<initials>.fit" with no
    " - " at all, so this is only used once at least one step is done."""

    return f"{initials} - {', '.join(chain)}"


def find_resume_point(
    folder: Path, initials: str, active_steps: list[dict],
) -> tuple[int, list[str], Path | None]:
    """Checks how far a filter's pipeline already got in a previous run of
    this same folder, by looking for the checkpoint file each step would
    have produced, in order, and stopping at the first one that isn't
    there. This is what lets an aborted run pick back up instead of
    starting every filter over from "<initials>.fit" -- e.g. if
    Background Extraction, a Misc/Other step, and Sharpening all already
    have their checkpoint files but Denoising doesn't, this returns
    resume_index=3 so the pipeline continues from Denoising onward. Only
    works cleanly if the pipeline configuration (steps, order, codes)
    hasn't changed since the aborted run -- reconfiguring between runs can
    throw off which file matches which step. Returns
    (resume_index, chain_so_far, most_recent_checkpoint_file); the third
    element is None only if even the very first "<initials>.fit" is
    missing, meaning there's nothing to resume OR start from at all."""

    current = find_working_file(folder, initials)
    if current is None:
        return 0, [], None

    chain: list[str] = []
    resume_index = 0
    for i, step in enumerate(active_steps):
        candidate_chain = chain + [step["code"]]
        candidate = find_working_file(folder, chained_filename(initials, candidate_chain))
        if candidate is None:
            break
        chain = candidate_chain
        current = candidate
        resume_index = i + 1

    return resume_index, chain, current


def find_final_output_file(output_dir: Path, initials: str) -> Path | None:
    """Checks whether this filter (or, reused for phase 4, the starmask's
    own pseudo-"initials") already has a finished final image sitting in
    output_dir (see finalize_phase3_filter -- it always names that file
    "<initials> - Final.<ext>", whatever export format was chosen last
    time), meaning a PREVIOUS run already carried this one all the way
    through. Matched by glob rather than find_working_file since the
    extension can be .fit/.fits/.tif/.png/etc depending on which export
    format was picked. Returns the first match, or None if there isn't
    one yet."""

    matches = sorted(output_dir.glob(f"{initials} - Final.*"))
    return matches[0] if matches else None


def save_phase3_checkpoint(
    siril: "s.SirilInterface", folder: Path, initials: str, chain: list[str],
) -> Path:
    """Saves Siril's currently loaded image as the next checkpoint file for
    this chain (e.g. "B - BE, SH.fit"), then resolves and returns the
    actual path Siril wrote (in case it picked a different extension than
    ".fit" -- mirrors the same .fit/.fits fallback used for phase 2's
    cropped output)."""

    stem = chained_filename(initials, chain)
    siril.cmd("save", siril_quote(folder / stem))
    for ext in (".fit", ".fits"):
        candidate = folder / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    candidates = list(folder.glob(f"{stem}.*"))
    return candidates[0] if candidates else folder / f"{stem}.fit"


def set_display_autostretch(siril: "s.SirilInterface") -> None:
    """Switches Siril's display mode for the currently loaded image to
    AutoStretch (STF) instead of Linear, so every image phase 3 (and phase
    4's starmask pipeline) loads shows up already stretched for easy
    viewing -- purely a viewer setting (see the STFType import comment
    above), never touches the saved pixel data. Best-effort: silently does
    nothing if this sirilpy is too old to have STFType/set_siril_stf, or if
    the call fails for any reason."""

    if STFType is None:
        return
    try:
        siril.set_siril_stf(STFType.AUTOSTRETCH_DISPLAY)
    except Exception as e:
        siril.log(f"[phase 3] Couldn't switch display to AutoStretch ({e}) -- leaving Siril's display mode as-is.")


def undo_phase3_checkpoint(folder: Path, initials: str, chain: list[str]) -> None:
    """The "Back" button's undo: deletes whichever checkpoint file(s) this
    exact chain produced, so a discarded step doesn't linger as orphaned
    clutter (and so find_resume_point() doesn't later think that step is
    still done). Matched by exact stem (not by prefix) against both the
    main checkpoint name and its Star Removal sibling "..., SM" mask file
    (see handle_star_removal_step) -- exact matching avoids accidentally
    deleting an unrelated checkpoint whose chain code happens to start
    with the same characters (e.g. undoing "M1" must not also delete
    "M10"). Does nothing if chain is empty (there's no "<initials>.fit"
    to undo -- that original starting file is never touched)."""

    if not chain:
        return
    prefix = chained_filename(initials, chain)
    sibling = f"{prefix}, SM"
    for f in list(folder.iterdir()):
        if f.is_file() and f.stem in (prefix, sibling):
            try:
                f.unlink()
            except OSError:
                pass


def delete_all_phase3_checkpoints(folder: Path, initials: str) -> int:
    """Removes every checkpoint file this filter's phase 3 pipeline has
    produced so far in `folder` -- anything named "<initials> - ..."
    (any extension), which covers every completed step's saved checkpoint
    AND any star-mask sidecar file (see handle_star_removal_step) -- but
    leaves the very first "<initials>.fit"/".fits" starting file untouched,
    since that's what the freshly-restarted pipeline resumes from. Used
    when the user chooses to start a filter's pipeline over from scratch
    (see run_phase3_pipeline) rather than resume, so the previous, now-
    discarded run's checkpoints don't linger as clutter or trick a LATER
    find_resume_point() call into thinking steps are already done that are
    about to be redone with possibly different results. Returns how many
    files were removed."""

    prefix = f"{initials} - "
    removed = 0
    for f in list(folder.iterdir()):
        if f.is_file() and f.name.startswith(prefix):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def handle_star_removal_step(
    siril: "s.SirilInterface", folder: Path, initials: str, chain: list[str],
    code: str, before_names: set[str],
) -> tuple[Path, list[str]]:
    """Star removal tools commonly write their own output files (rather
    than just updating Siril's loaded image) -- typically a starless image
    and, if the user asked for one, a star mask. This looks at what new
    files appeared in the working folder while the tool was open, and
    renames whichever look like a starless/mask result into this
    pipeline's naming scheme, always starting with the filter's initials as
    requested. If nothing new turns up (the tool updated the loaded image
    in place instead), falls back to saving the current checkpoint the
    normal way. Returns (new_current_file, new_chain) -- the mask, if any,
    is saved alongside but doesn't continue the chain."""

    after_names = {f.name for f in folder.iterdir() if f.is_file()}
    new_names = sorted(after_names - before_names)

    starless_src = None
    starmask_src = None
    for name in new_names:
        lower = name.lower()
        if starless_src is None and ("starless" in lower or "nostar" in lower or "no_star" in lower):
            starless_src = folder / name
        elif starmask_src is None and ("starmask" in lower or "star_mask" in lower or ("mask" in lower and "star" in lower)):
            starmask_src = folder / name

    new_chain = chain + [code]

    if starless_src is not None:
        dest = folder / f"{chained_filename(initials, new_chain)}{starless_src.suffix}"
        starless_src.rename(dest)
        siril.cmd("load", siril_quote(dest))
        set_display_autostretch(siril)
        siril.log(f"[phase 3] Star removal: '{starless_src.name}' -> '{dest.name}'.")
        current = dest
    else:
        siril.log(
            "[phase 3] Star removal: no separate starless file appeared -- "
            "assuming the loaded image was updated in place."
        )
        current = save_phase3_checkpoint(siril, folder, initials, new_chain)

    if starmask_src is not None:
        mask_chain = new_chain + ["SM"]
        mask_dest = folder / f"{chained_filename(initials, mask_chain)}{starmask_src.suffix}"
        starmask_src.rename(mask_dest)
        siril.log(f"[phase 3] Star mask: '{starmask_src.name}' -> '{mask_dest.name}'.")

    return current, new_chain


def handle_star_removal_step_for_starmask(
    siril: "s.SirilInterface", folder: Path, initials: str, chain: list[str],
    code: str, before_names: set[str],
) -> tuple[Path, list[str]]:
    """Phase 4's own variant of handle_star_removal_step, with the
    starless/star-mask roles SWAPPED: phase 4's whole subject is a
    starmask, so when a star removal tool produces both a starless image
    and a separate star mask file, THIS pipeline continues its chain with
    the star MASK (that's the actual result phase 4 is after), while the
    starless image is just logged and renamed alongside as a sidecar
    rather than continuing on -- the mirror image of phase 3's
    handle_star_removal_step, where the starless image continues and the
    mask is the sidecar. If no separate mask file turns up (the tool
    updated the loaded image in place, or doesn't produce a distinct mask
    file at all), falls back to saving the current checkpoint the normal
    way, same as phase 3. Returns (new_current_file, new_chain)."""

    after_names = {f.name for f in folder.iterdir() if f.is_file()}
    new_names = sorted(after_names - before_names)

    starless_src = None
    starmask_src = None
    for name in new_names:
        lower = name.lower()
        if starless_src is None and ("starless" in lower or "nostar" in lower or "no_star" in lower):
            starless_src = folder / name
        elif starmask_src is None and ("starmask" in lower or "star_mask" in lower or ("mask" in lower and "star" in lower)):
            starmask_src = folder / name

    new_chain = chain + [code]

    if starmask_src is not None:
        dest = folder / f"{chained_filename(initials, new_chain)}{starmask_src.suffix}"
        starmask_src.rename(dest)
        siril.cmd("load", siril_quote(dest))
        set_display_autostretch(siril)
        siril.log(f"[phase 4] Star removal: '{starmask_src.name}' (the star mask) -> '{dest.name}'.")
        current = dest
    else:
        siril.log(
            "[phase 4] Star removal: no separate star mask file appeared -- "
            "assuming the loaded image was updated in place."
        )
        current = save_phase3_checkpoint(siril, folder, initials, new_chain)

    if starless_src is not None:
        starless_chain = new_chain + ["SL"]
        starless_dest = folder / f"{chained_filename(initials, starless_chain)}{starless_src.suffix}"
        starless_src.rename(starless_dest)
        siril.log(
            f"[phase 4] Starless (byproduct, not continued): "
            f"'{starless_src.name}' -> '{starless_dest.name}'."
        )

    return current, new_chain


# Windows constant for a graceful "please close" request -- the exact same
# message sent when a user clicks a window's own X button (its close
# handler, unsaved-changes prompt, etc. all still run normally). Never a
# force-kill.
_WM_CLOSE = 0x0010


def _enum_visible_non_wizard_windows() -> dict[int, str]:
    """{window handle: title} for every visible top-level window on
    Windows, excluding this wizard's own windows (always titled "Siril
    Multi-Filter Wizard" or starting with "Phase 3 --"/"Phase 4 --" --
    see run_step_checkpoint's phase_label) so it can never mistake or
    close one of its own. Windows-only; returns {} on any other OS or if
    anything about the API call goes wrong."""

    if not sys.platform.startswith("win"):
        return {}
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        windows: dict[int, str] = {}

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value or ""
            lower = title.lower()
            if (
                "siril multi-filter wizard" in lower
                or lower.startswith("phase 3 --")
                or lower.startswith("phase 4 --")
            ):
                return True
            windows[hwnd] = title
            return True

        user32.EnumWindows(_enum, 0)
        return windows
    except Exception:
        return {}


def _post_close_to_window(hwnd: int) -> bool:
    """Sends the graceful WM_CLOSE request to one specific window handle,
    after checking it's still a real, open window. Windows-only; returns
    False on any other OS, an already-gone window, or any API error."""

    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        if not user32.IsWindow(hwnd):
            return False
        user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
        return True
    except Exception:
        return False


def try_close_launched_window(tool_name: str, tracked_hwnd: int | None) -> bool:
    """Best-effort: asks Windows to close the launched script's window, so
    clicking Done can close it automatically instead of asking the user to
    do it by hand -- this wizard has no real handle back to a script it
    launched via Siril's "pyscript" (Siril runs it, not this wizard, so
    there's no subprocess/PID of its own to hold onto).

    Tries, in order:
    1. tracked_hwnd -- the window run_step_checkpoint's launch-watcher
       thread already identified as "whatever new window appeared right
       after this script was launched" (see the launch-time snapshot/diff
       below). This is the reliable path: it doesn't depend on guessing
       what the window's title looks like at all.
    2. A title-substring fallback (tool_name appearing somewhere in a
       window's title), only used if step 1 never found anything -- this
       still catches simple cases (a script that titles its window exactly
       its own name) but is unreliable in general: many scripts show a
       human-friendly title plus their own version number (e.g.
       "AberrationRemover.py" opening a window titled "Aberrations Remover
       - v1.1.4") that doesn't line up with the script's filename at all,
       which is exactly why step 1 exists.

    Windows-only throughout; returns False immediately on any other OS,
    or if neither approach finds a window, so callers fall back to asking
    the user to close it by hand. Returns True if a window was found and
    sent the close request (not a guarantee it actually closed -- the
    caller still waits and confirms via launch_status)."""

    if not sys.platform.startswith("win"):
        return False

    if tracked_hwnd is not None and _post_close_to_window(tracked_hwnd):
        return True

    needle = tool_name.strip().lower()
    if not needle:
        return False
    found = [
        hwnd for hwnd, title in _enum_visible_non_wizard_windows().items()
        if needle in title.lower()
    ]
    for hwnd in found:
        _post_close_to_window(hwnd)
    return bool(found)


def run_step_checkpoint(
    siril: "s.SirilInterface", tool_paths: dict[str, str], filter_name: str,
    step_label: str, tool_name: str, can_go_back: bool = False,
    category: str | None = None, phase_label: str = "Phase 3",
) -> str:
    """The "working on this step" window for one tool run within phase 3.
    This wizard never guesses parameters or auto-applies anything -- for a
    Python script it launches it via Siril's own "pyscript" command ON A
    BACKGROUND THREAD (that call turns out to BLOCK until the launched
    script's own window is closed, confirmed by it visibly freezing this
    window if called directly on the main thread -- a background thread
    keeps this checkpoint window itself responsive and visible the whole
    time the script is open, exactly when you need to see it); for a Siril
    built-in tool, a handful (see BUILTIN_TOOL_CATALOG's "dialog" entries)
    can be opened the same way you'd click them in Siril's own Image
    Processing menu, via sirilpy's SirilInterface.open_dialog()/DialogID --
    tried first, and only falling back to a manual "open it yourself"
    message (Siril's own Image Processing menu, or typing the command with
    your own parameters straight into Siril's console) if that's not
    mapped for this tool, isn't available in this sirilpy, or fails for any
    reason. Either way the user does the actual editing themselves, at
    their own pace, in Siril -- a "Currently open: <tool name>" line and a
    live status line (bold/italic and enlarged so it's easy to spot -- see
    "StatusUpdate.TLabel") keep the window showing that this step is still
    active while they do it. There's deliberately no progress bar here
    (there used to be one, the same climb-and-hover fake bar
    run_with_progress uses for phase 1, but it turned out to be more
    misleading than useful in real use -- there's no real percent-done to
    show for a step that's really just "waiting for you to finish in
    Siril"). A reminder of what to actually do, plus the tweak-before-
    finalizing note for a launched script, sits under a "Note:" header
    pinned to the bottom of the window instead. can_go_back shows a "Back" button (hidden on a filter's very first
    step this run, since there's nothing before it to undo) -- returning
    "back" tells run_phase3_pipeline to undo the PREVIOUS step's saved
    checkpoint file and re-open that step instead of this one. There's no
    handle back to a launched script's own window, and Siril has no "stop
    this script" command -- but on Windows, clicking Done while it's still
    open now asks Windows itself to close that window (a graceful WM_CLOSE,
    the same as clicking its own X button -- see try_close_launched_window),
    then briefly waits to see it actually close before continuing. If that
    can't be done (not Windows, no matching window found, or it doesn't
    close in time -- e.g. it's waiting on a save prompt of its own) this
    falls back to asking for confirmation instead of silently risking two
    commands hitting Siril at once. category (the step's category, e.g.
    "Stretching") adds a standing reminder to the live status text for
    steps where it matters -- currently just Stretching, reminding the
    user to switch Siril's viewer back to Linear first since phase 3 keeps
    it in AutoStretch otherwise (see set_display_autostretch/
    category_reminder). phase_label controls only the window title's
    prefix ("Phase 3" by default; run_phase4_starmask_pipeline passes
    "Phase 4" since it reuses this same checkpoint window for the
    starmask pipeline, and filter_name there is actually the composite's
    stem, e.g. "RGB Starmask", not a real filter name) -- everything else
    about the step behaves identically either way. Returns "done", "skip",
    "back", or "abort"."""

    is_builtin = tool_name in BUILTIN_TOOL_CATALOG
    launch_status: dict = {}

    # Every image loaded in phase 3 is switched to AutoStretch display for
    # easy viewing (see set_display_autostretch) -- great for most
    # steps, but a stretching tool's own effect is judged against whatever
    # Siril is currently showing, so an already-autostretched preview would
    # make it look wrong. Appended to the status text (whatever it says at
    # any given moment -- see where category_reminder is used below) only
    # for the Stretching category, as a standing reminder to flip the
    # viewer back to Linear first.
    category_reminder = (
        "\n\nReminder: switch Siril's image viewer back to Linear before "
        "stretching -- it's currently showing AutoStretch (for easy "
        "viewing), which would make this step's actual effect look wrong."
        if category == "Stretching" else ""
    )

    if is_builtin:
        # A handful of built-in tools have a matching entry in sirilpy's
        # DialogID enum (see BUILTIN_TOOL_CATALOG's "dialog" comment) --
        # when one does, and this sirilpy actually has open_dialog/DialogID
        # (an older bundled sirilpy might not), try asking Siril to open
        # that tool's real dialog directly, exactly like clicking it in the
        # Image Processing menu. Any failure here (missing attribute,
        # unknown enum member, Siril refusing for some reason) just falls
        # back to the manual instructions below rather than risking a
        # half-broken message.
        opened_automatically = False
        dialog_name = BUILTIN_TOOL_CATALOG[tool_name].get("dialog")
        if dialog_name and DialogID is not None:
            dialog_id = getattr(DialogID, dialog_name, None)
            if dialog_id is not None:
                try:
                    opened_automatically = bool(siril.open_dialog(dialog_id))
                except Exception as e:
                    siril.log(f"[phase 3] Couldn't auto-open \"{tool_name}\"'s dialog ({e}) -- falling back to manual instructions.")
                    opened_automatically = False

        if opened_automatically:
            launch_note = (
                f"\"{tool_name}\" is open right in Siril -- go ahead and "
                "apply it to the image that's currently loaded, at your "
                "own pace."
            )
        else:
            launch_note = (
                f"This one's built right into Siril, so it's over to you: open "
                f"it from Siril's Image Processing menu (or, if you'd rather "
                f"set its options that way, type \"{tool_name}\" with your own "
                "parameters straight into Siril's console) and apply it to the "
                "image that's currently loaded.\n\n"
                "(A quick reason this wizard can't just open it for you like it "
                "does a Python script: called from a script, a Siril built-in "
                "tool only understands a one-shot command with every setting "
                "already filled in -- it can't hand back the same interactive "
                "dialog you get from Siril's own menu, so there's simply "
                "nothing here for this wizard to pop open on your behalf.)"
            )
    else:
        path = tool_paths.get(tool_name)
        if path:
            # "Launching ..." only describes the instant before the
            # script's own window actually appears -- siril.cmd("pyscript",
            # ...) opens it almost immediately and then BLOCKS until that
            # window is closed, so for the entire time you're actually
            # using the script, this text was stuck saying "Launching",
            # which read as if it hadn't opened yet even while its window
            # was sitting right there open. On Windows this is solved
            # properly instead: start with an "Opening ..." status, then
            # flip it to "is open and ready" only once _watch_for_new_window
            # (below) actually detects the script's window appearing --
            # rather than just assuming it's already open the instant this
            # label is drawn, which could show up before the script (or a
            # slow-loading model inside it) has actually finished opening
            # its window. Platforms without that window-detection (non-
            # Windows) fall back to the old "assume it's open" wording
            # immediately, same as before. launch_status["note"] is also
            # what flips this text again once the window actually closes.
            watches_for_window = sys.platform.startswith("win")
            ready_note = f"\"{tool_name}\" is open and ready for you -- go ahead and do your editing there."
            launch_note = f"Opening \"{tool_name}\" ..." if watches_for_window else ready_note

            # window_track["hwnd"] lets try_close_launched_window() (see
            # above) close this exact window later without having to guess
            # its title -- a plain title match can't be trusted in general
            # (a script's window title often doesn't match its filename at
            # all, e.g. "AberrationRemover.py" opening a window titled
            # "Aberrations Remover - v1.1.4"). Instead: snapshot every
            # visible window right before launching, then have a
            # background thread watch for whichever NEW window shows up
            # right after -- that's almost certainly this script's own
            # window, whatever it happens to be titled. That same
            # detection now also drives the "Opening .../is open" status
            # switch above.
            window_track: dict = {"hwnd": None}
            windows_before = _enum_visible_non_wizard_windows()

            def _launch():
                try:
                    siril.cmd("pyscript", siril_quote(Path(path)))
                    launch_status["note"] = f"Nice, \"{tool_name}\" is closed. Ready to move on whenever you are."
                except Exception as e:
                    launch_status["note"] = (
                        f"Hmm, \"{tool_name}\" didn't launch on its own ({e}) -- "
                        "no worries, just open it yourself from Siril's Scripts menu."
                    )
                finally:
                    launch_status["done"] = True

            def _watch_for_new_window():
                import time
                # The script's window normally appears almost immediately,
                # but give it a few seconds (e.g. a slow model load) before
                # giving up -- try_close_launched_window() still has the
                # title-substring fallback if this never finds anything.
                for _ in range(50):  # ~10s at 200ms
                    if launch_status.get("done"):
                        return
                    after = _enum_visible_non_wizard_windows()
                    new_hwnds = set(after) - set(windows_before)
                    if new_hwnds:
                        window_track["hwnd"] = next(iter(new_hwnds))
                        break
                    time.sleep(0.2)
                # Found the window (or gave up waiting) -- either way, flip
                # the status from "Opening ..." to "is open and ready" now,
                # unless the script already closed in the meantime (done).
                if not launch_status.get("done") and not launch_status.get("note"):
                    launch_status["note"] = ready_note

            threading.Thread(target=_launch, daemon=True).start()
            if watches_for_window:
                threading.Thread(target=_watch_for_new_window, daemon=True).start()
        else:
            window_track = {"hwnd": None}
            launch_note = f"Just open \"{tool_name}\" yourself from Siril's Scripts menu -- couldn't find it on disk to launch it for you."

    root = _new_root(siril, f"{phase_label} -- {filter_name}: {step_label}")
    _header(root, f"{filter_name}: {step_label}")

    card = _card(root)

    # The note (below) is pinned to the very bottom of the card via
    # side="bottom", packed FIRST so it claims that space before anything
    # else -- everything else below flows top-down as usual and fills
    # whatever's left above it.
    is_launched_script = not is_builtin and bool(tool_paths.get(tool_name))
    tweak_note = (
        f" Not happy with the result yet? Siril's own Undo still works, "
        f"and you can click \"{tool_name}\"'s own Run/Process button again "
        "as many times as you like before closing it -- nothing here is "
        "final until you click Done."
        if is_launched_script else ""
    )
    note_area = ttk.Frame(card, style="Card.TFrame")
    note_area.pack(side="bottom", fill="x", pady=(10, 0))
    ttk.Label(note_area, text="Note:", style="NoteHeader.TLabel").pack(anchor="w")
    _wrapping_label(
        note_area,
        "Nothing is applied automatically -- do the actual editing in "
        "Siril yourself, at your own pace. Click Done once you're happy "
        "with the result, so this wizard can save a checkpoint here and "
        "move on to the next step." + tweak_note,
        pady=(2, 0),
    )

    status_row = ttk.Frame(card, style="Card.TFrame")
    status_row.pack(fill="x", anchor="w")
    ttk.Label(status_row, text="Currently open:", style="Card.TLabel").pack(side="left")
    ttk.Label(status_row, text=tool_name, style="Brand.TLabel").pack(side="left", padx=(6, 0))

    _wrapping_label(card, tool_description(tool_name), pady=(4, 10))

    # The live status update ("Launching ..." / "... has been closed.", or
    # the built-in-tool instructions) -- enlarged, bold and italic so it
    # stands out on its own. This used to sit next to a progress bar, but
    # that bar turned out to be more misleading than useful after actual
    # use: there's no real percent-done to show for a step that's really
    # just "waiting for you to finish in Siril", so it's gone -- this label
    # (plus the "Currently open" line above) is now the only status
    # indicator for the step. It sits in the leftover space between the
    # fixed content above and the "Note:" block pinned to the bottom (see
    # note_area above), centered horizontally and just above vertical
    # center of THAT space via place()'s relative coordinates -- which,
    # unlike pack, keep recomputing that position (and, via the <Configure>
    # binding below, the wrap width) as the window is resized, rather than
    # only being placed once.
    status_area = ttk.Frame(card, style="Card.TFrame")
    status_area.pack(fill="both", expand=True)

    launch_label = ttk.Label(
        status_area, text=launch_note + category_reminder, style="StatusUpdate.TLabel",
        justify="center", anchor="center",
    )
    launch_label.place(relx=0.5, rely=0.42, anchor="center", relwidth=0.92)

    def _update_status_wrap(event, lbl=launch_label):
        lbl.configure(wraplength=max(200, int(event.width * 0.92)))

    status_area.bind("<Configure>", _update_status_wrap)

    if not is_builtin and tool_paths.get(tool_name):
        # Only a launched Python script has a background thread updating
        # launch_status -- poll it just long enough to mirror that one
        # eventual change ("Launching ..." -> "... has been closed.") onto
        # the label, then stop; nothing else here depends on a timer.
        def _poll_launch_status():
            if not launch_label.winfo_exists():
                return
            if launch_status.get("note"):
                launch_label.configure(text=launch_status["note"] + category_reminder)
            if not launch_status.get("done"):
                launch_label.after(200, _poll_launch_status)

        _poll_launch_status()

    outcome = {"result": "abort"}

    def finish(result: str) -> None:
        outcome["result"] = result
        root.destroy()

    def _wait_for_script_to_close(attempts_left: int) -> None:
        # Polls the same launch_status the label already watches (see
        # _poll_launch_status above) -- "done" only flips True once
        # siril.cmd("pyscript", ...) actually returns, i.e. the window is
        # really closed, not just asked to close.
        if not root.winfo_exists():
            return
        if launch_status.get("done"):
            finish("done")
            return
        if attempts_left <= 0:
            proceed = ask_yes_no(
                siril, f"\"{tool_name}\" still looks open",
                f"Asked \"{tool_name}\" to close, but it doesn't seem to "
                "have closed yet -- it may be waiting on a save/unsaved-"
                "changes prompt of its own. Take a look, close it "
                "yourself if needed, then continue.",
                yes_text="Continue anyway", no_text="Go back",
            )
            if proceed:
                finish("done")
            return
        root.after(150, lambda: _wait_for_script_to_close(attempts_left - 1))

    def on_done() -> None:
        # Siril has no "stop this script" command, and this wizard has no
        # real handle back to a script it launched via "pyscript" (Siril
        # runs it, not this wizard) -- so on Windows it asks the OS itself
        # to close that script's window (a graceful WM_CLOSE, exactly like
        # clicking its own X button), identified either by window_track's
        # launch-time snapshot/diff (see above -- the reliable path,
        # doesn't care what the window is titled) or, failing that, a
        # title-substring guess (see try_close_launched_window), then waits
        # briefly to see it actually close before moving on. If neither
        # finds a window (or this isn't Windows), falls back to nudging the
        # user to close it themselves, same as before.
        if is_launched_script and not launch_status.get("done"):
            if try_close_launched_window(tool_name, window_track.get("hwnd")):
                note = f"Closing \"{tool_name}\" ..."
                launch_status["note"] = note
                if launch_label.winfo_exists():
                    launch_label.configure(text=note + category_reminder)
                _wait_for_script_to_close(attempts_left=40)  # ~6s at 150ms
                return
            proceed = ask_yes_no(
                siril, f"\"{tool_name}\" still looks open",
                f"\"{tool_name}\" doesn't seem to have been closed yet, "
                "and this wizard couldn't find its window to close it for "
                "you. It's best to close it yourself first, so Siril "
                "isn't handling two commands at once. Continue anyway?",
                yes_text="Continue anyway", no_text="Go back",
            )
            if not proceed:
                return
        finish("done")

    btns = _button_row(root)
    ttk.Button(btns, text="Done -- save & continue", style="Accent.TButton", command=on_done).pack(side="right")
    ttk.Button(btns, text="Skip this step", command=lambda: finish("skip")).pack(side="right", padx=(0, 8))
    ttk.Button(btns, text="Abort run", command=lambda: finish("abort")).pack(side="left")
    if can_go_back:
        ttk.Button(btns, text="Back (undo previous step)", command=lambda: finish("back")).pack(side="left", padx=(8, 0))

    root.mainloop()
    _check_not_closed()
    return outcome["result"]


# Export format choices offered at the end of each filter's pipeline (see
# ask_final_export_format/finalize_phase3_filter) -- value -> (label,
# Siril save command, file extension it writes). "fit" isn't a real Siril
# command entry here since it just means "keep the last checkpoint as-is".
FINAL_EXPORT_FORMATS: dict[str, tuple[str, str, str]] = {
    "fit": ("Keep as FIT/FITS (no conversion)", "", ""),
    "tif16": ("16-bit TIFF", "savetif", ".tif"),
    "tif32": ("32-bit TIFF", "savetif32", ".tif"),
    "png": ("PNG", "savepng", ".png"),
    "jpg": ("JPEG", "savejpg", ".jpg"),
}


def ask_final_export_format(
    siril: "s.SirilInterface", filter_name: str, current: Path,
    phase_label: str = "Phase 3",
) -> str:
    """Shown once a filter's (or, reused for phase 4, the starmask's own)
    pipeline reaches its last configured step -- asks whether the final
    image should be saved in a different format besides FIT/FITS before
    it's copied into the Output subfolder. Returns one of
    FINAL_EXPORT_FORMATS's keys (default "fit")."""

    root = _new_root(siril, f"{phase_label} -- {filter_name}: final image")
    _header(root, f"{filter_name}: this is the last step")

    card = _card(root)
    _wrapping_label(
        card,
        f"'{current.name}' is the final result of {filter_name}'s "
        "pipeline. Would you like to save it in a different format "
        "besides FIT/FITS before it's copied into this dataset's Output "
        "folder?",
    )

    choice_var = tk.StringVar(value="fit")
    options_row = ttk.Frame(card, style="Card.TFrame")
    options_row.pack(fill="x", anchor="w", pady=(12, 0))
    for key, (label, _cmd, _ext) in FINAL_EXPORT_FORMATS.items():
        ttk.Radiobutton(
            options_row, text=label, variable=choice_var, value=key, style="TRadiobutton",
        ).pack(anchor="w", pady=2)

    outcome = {"result": "fit"}

    def on_continue():
        outcome["result"] = choice_var.get()
        root.destroy()

    btns = _button_row(root)
    ttk.Button(btns, text="Continue", style="Accent.TButton", command=on_continue).pack(side="right")

    root.mainloop()
    _check_not_closed()
    return outcome["result"]


def finalize_phase3_filter(
    siril: "s.SirilInterface", folder: Path, output_dir: Path, initials: str,
    filter_name: str, current: Path, log_prefix: str = "phase 3",
) -> Path | None:
    """Runs once a filter's (or, reused for phase 4, the starmask's own)
    pipeline has gone through every configured step (or resume found it
    already had): offers a non-FIT/FITS export (ask_final_export_format),
    then names the true final image "<Initials> - Final.<ext>" and copies
    (never moves -- the working folder keeps its full checkpoint history,
    including the original "<Initials> - Final" file itself) it into
    "2 - Pre-process/Output/". The last chain checkpoint file itself is
    left untouched either way, so find_resume_point() still works if this
    filter's pipeline gets reconfigured and re-run later. Returns the path
    it was copied to inside output_dir, or None if the export/copy
    couldn't be completed."""

    phase_label = "Phase 4" if log_prefix == "phase 4" else "Phase 3"
    export_format = ask_final_export_format(siril, filter_name, current, phase_label=phase_label)
    label, cmd_name, ext = FINAL_EXPORT_FORMATS[export_format]
    final_stem = f"{initials} - Final"

    if export_format == "fit":
        final_local = folder / f"{final_stem}{current.suffix}"
        shutil.copy2(current, final_local)
    else:
        siril.cmd(cmd_name, siril_quote(folder / final_stem))
        final_local = folder / f"{final_stem}{ext}"
        if not final_local.is_file():
            # Siril's actual written extension didn't match what's
            # expected -- fall back to whatever it actually produced.
            candidates = list(folder.glob(f"{final_stem}.*"))
            final_local = candidates[0] if candidates else final_local

    if not final_local.is_file():
        siril.log(
            f"[{log_prefix}] '{filter_name}': couldn't find the exported final "
            f"image ('{label}') to copy into '{PHASE3_OUTPUT_SUBDIR_NAME}' "
            "-- check Siril's log for the save command's own output."
        )
        return None

    output_dest = output_dir / final_local.name
    shutil.copy2(final_local, output_dest)
    siril.log(
        f"[{log_prefix}] '{filter_name}': final image ({label}) saved as "
        f"'{final_local.name}', copied into "
        f"'{PREPROCESS_DIR_NAME}/{PHASE3_OUTPUT_SUBDIR_NAME}'."
    )
    return output_dest


def ask_skip_phase3_entirely(
    siril: "s.SirilInterface", preprocess_dir: Path, filters: list[str],
) -> bool:
    """Checked right before phase 3 actually starts (both call sites --
    the normal flow, and the "skip straight to phase 3" checkpoint path),
    before even phase 3's own pipeline setup/tool check: if EVERY one of
    filters already has a final image sitting in "1 - Output" (see
    find_final_output_file) -- meaning an earlier run already carried all
    of them through phase 3's pipeline already -- there's nothing left
    for phase 3 to do at all, not even the per-filter Skip/Redo prompt
    run_phase3_pipeline would otherwise show for each one (see that
    function). Offers a "Skip to Phase 4" button in that case, bypassing
    phase 3's setup screens and pipeline entirely. Returns False -- with
    no screen shown at all -- the moment even ONE filter is still missing
    its final image, since phase 3 genuinely still has work to do."""

    if not filters:
        return False

    output_dir = preprocess_dir / PHASE3_OUTPUT_SUBDIR_NAME
    all_finalized = all(
        find_final_output_file(output_dir, filter_initials(f)) is not None
        for f in filters
    )
    if not all_finalized:
        return False

    root = _new_root(siril, "Phase 3 -- already finished?")
    _header(root, "Every filter is already finished")

    card = _card(root)
    _wrapping_label(
        card,
        "Every selected filter already has a final image in "
        f"'{PREPROCESS_DIR_NAME}/{PHASE3_OUTPUT_SUBDIR_NAME}' from an "
        "earlier run -- there's nothing left for phase 3 to do. Skip "
        "straight to phase 4 (the optional starmask step), or go through "
        "phase 3 anyway (you'll still get a Skip/Redo choice for each "
        "filter there)?",
    )

    outcome = {"skip": False}

    def on_skip():
        outcome["skip"] = True
        root.destroy()

    def on_continue():
        outcome["skip"] = False
        root.destroy()

    btns = _button_row(root)
    ttk.Button(btns, text="Skip to Phase 4", style="Accent.TButton", command=on_skip).pack(side="right")
    ttk.Button(btns, text="Go through Phase 3 anyway", command=on_continue).pack(side="right", padx=(0, 8))

    root.mainloop()
    _check_not_closed()
    return outcome["skip"]


def run_pipeline_steps(
    siril: "s.SirilInterface", tool_paths: dict[str, str],
    remaining_steps: list[dict], chain: list[str], current: Path,
    folder: Path, initials: str, display_name: str,
    log_prefix: str, phase_label: str,
    star_removal_handler,
) -> tuple[bool, list[str], Path]:
    """The shared "run each configured step, one checkpoint window at a
    time" loop -- originally two separately-maintained near-identical
    copies inside run_phase3_pipeline (a real filter) and
    run_phase4_starmask_pipeline (the starmask composite, standing in for
    a "filter" via its stem as initials), now unified here since the two
    had already quietly drifted apart in small ways (see below) despite
    doing the exact same job. Handles a step's "abort"/"back"/"skip"/
    (implicit) "done" outcome from run_step_checkpoint, keeping `history`
    (the chain/current-file state going INTO each remaining step) so
    "Back" can undo whichever step's checkpoint produced the CURRENT
    state and re-open the step before it -- see run_phase3_pipeline's
    own (preserved) docstring for the full behavior this implements.

    log_prefix ("phase 3"/"phase 4") tags every log line the way each
    caller already did; phase_label ("Phase 3"/"Phase 4") is passed
    straight through to run_step_checkpoint for its window title; folder
    is the filter's own subfolder (phase 3) or the starmask's own
    subfolder (phase 4); initials is the filter's real initials or the
    starmask's stem standing in for them; display_name is what shows up
    in log lines and the checkpoint window's title (a real filter name,
    or the starmask's stem); star_removal_handler is
    handle_star_removal_step or handle_star_removal_step_for_starmask,
    whichever this caller needs for a Star Removal step's special
    starless-vs-mask output handling.

    One small behavior difference between the two original copies is
    fixed here rather than preserved: phase 3's "Back" branch logged a
    line even when there was nothing to actually undo (the previous step
    had been skipped, so there's no checkpoint file to remove) --
    phase 4's copy silently did nothing in that case. Both now log it,
    since it's genuinely useful information either way, not a
    phase-specific choice.

    Returns (aborted, chain, current) -- the final chain/current-file
    state, and whether a step's checkpoint window was aborted partway
    through (the caller still needs to know this to decide whether it's
    safe to finalize/return True, or must return False without doing
    so)."""

    aborted = False
    history: list[tuple[list[str], Path]] = [(list(chain), current)]
    i = 0
    while i < len(remaining_steps):
        step = remaining_steps[i]
        is_star_removal = step["category"] == "Star Removal"
        # Single-select (see _choose_scripts_for_step) -- a step has at
        # most one tool now, never several to run in sequence.
        tool_name = step["scripts"][0]

        # Snapshotted BEFORE the checkpoint window opens (and thus before
        # the user runs the tool), so star_removal_handler can tell
        # exactly which files the tool itself created.
        before_names = (
            {f.name for f in folder.iterdir() if f.is_file()}
            if is_star_removal else None
        )

        outcome = run_step_checkpoint(
            siril, tool_paths, display_name, step["label"], tool_name,
            can_go_back=(i > 0), category=step["category"], phase_label=phase_label,
        )

        if outcome == "abort":
            siril.log(f"[{log_prefix}] '{display_name}': run aborted during '{step['label']}' ({tool_name}).")
            aborted = True
            break

        if outcome == "back":
            # i > 0 is guaranteed here since the button is hidden
            # otherwise, but guard anyway in case that ever changes.
            if i == 0:
                continue
            prev_chain, prev_current = history[i]
            target_chain, target_current = history[i - 1]
            if prev_current != target_current:
                undo_phase3_checkpoint(folder, initials, prev_chain)
                siril.log(
                    f"[{log_prefix}] '{display_name}': undid "
                    f"'{remaining_steps[i - 1]['label']}' -- removed "
                    f"checkpoint(s) for '{chained_filename(initials, prev_chain)}', "
                    f"reloaded {target_current.name}."
                )
            else:
                siril.log(
                    f"[{log_prefix}] '{display_name}': going back to redo "
                    f"'{remaining_steps[i - 1]['label']}' (it was "
                    "skipped last time, nothing to undo)."
                )
            chain, current = target_chain, target_current
            siril.cmd("load", siril_quote(current))
            set_display_autostretch(siril)
            history.pop()
            i -= 1
            continue

        if outcome == "skip":
            siril.log(f"[{log_prefix}] '{display_name}': skipped '{tool_name}' ({step['label']}).")
            history.append((list(chain), current))
            i += 1
            continue

        if is_star_removal:
            current, chain = star_removal_handler(
                siril, folder, initials, chain, step["code"], before_names,
            )
        else:
            chain = chain + [step["code"]]
            current = save_phase3_checkpoint(siril, folder, initials, chain)

        siril.log(f"[{log_prefix}] '{display_name}': completed '{tool_name}' ({step['label']}) -> {current.name}")
        history.append((list(chain), current))
        i += 1

    return aborted, chain, current


def run_phase3_pipeline(
    siril: "s.SirilInterface", cfg: dict, preprocess_dir: Path,
    selected_filters: list[str], image_processing_dir: Path,
) -> bool:
    """Runs the configured Phase 3 pipeline (cfg["phase3_steps"]) against
    every selected filter's checkpoint file in "2 - Pre-process/<Filter>/",
    one step at a time, saving a chained checkpoint filename after each
    tool the user completes (see save_phase3_checkpoint/
    handle_star_removal_step). Each filter is checked for a final image in
    "1 - Output" FIRST (see find_final_output_file) -- if one's already
    there from an earlier run, "resume" wouldn't make sense (there's no
    unfinished pipeline left to resume into), so the choice offered is
    Skip (leave that final image alone) or Redo from scratch instead.
    Only when there's no final image yet is the filter resumed from
    wherever its checkpoint files show it last got to (see
    find_resume_point) -- if an earlier run was aborted partway through,
    re-running this only asks whether to pick back up from there or start
    that filter over, rather than redoing already-completed steps
    unconditionally. Either "start over" path also deletes every old
    checkpoint file that earlier run already produced (see
    delete_all_phase3_checkpoints), so redone steps aren't sitting
    alongside stale leftovers from the discarded run -- and so a LATER
    run can't misread those leftovers as already-done progress via
    find_resume_point. Within a single
    run, each checkpoint window (past the first step) also offers a "Back"
    button that undoes the previous step's checkpoint file(s) (see
    undo_phase3_checkpoint) and reloads the state before it, so a step can
    be redone with different settings instead of only ever moving forward.
    Once every selected filter has finished (i.e. this isn't returning early
    because of an abort), every file finalize_phase3_filter() copied into
    "2 - Pre-process/1 - Output" is ALSO copied (never moved -- that folder
    stays the authoritative one) into "3 - Image Processing" in the main
    dataset folder, so the final images for every filter end up sitting
    right where you'd actually go looking to start combining/processing
    them, without having to dig into "2 - Pre-process" for it. Siril's
    working directory is then also set to "3 - Image Processing", so
    whatever you do next in Siril starts right there instead of wherever
    the last filter's own folder happened to leave it.
    Returns True if every filter finished (or was cleanly skipped for
    having no starting file); False if the user chose to abort partway
    through."""

    phase3_steps = cfg.get("phase3_steps") or []
    active_steps = [step for step in phase3_steps if step["scripts"]]
    if not active_steps:
        siril.log("[phase 3] No pipeline steps configured -- nothing to run.")
        show_message(
            siril, "Nothing configured",
            "No Phase 3 steps had any script or tool selected, so there's "
            "nothing to run. Re-open the Phase 3 setup screen to configure "
            "a pipeline.",
        )
        return True

    tool_paths = cfg.get("phase3_tool_paths", {})

    output_dir = preprocess_dir / PHASE3_OUTPUT_SUBDIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)

    for filter_name in selected_filters:
        wizard_add_step(f"phase3_run:{filter_name}", f"Pre-process: {filter_name}")

    for filter_name in selected_filters:
        wizard_set_current(f"phase3_run:{filter_name}")

        folder = find_filter_subfolder(preprocess_dir, filter_name)
        if folder is None:
            siril.log(f"[phase 3] '{filter_name}': no subfolder in '{PREPROCESS_DIR_NAME}' -- skipping.")
            wizard_mark_done(f"phase3_run:{filter_name}")
            continue

        initials = filter_initials(filter_name)

        # Checked BEFORE find_resume_point/checkpoints: if a previous run
        # already carried this filter all the way through to a final
        # image in "1 - Output", there's nothing left to "resume" -- that
        # option only makes sense partway through a still-unfinished
        # pipeline. Offer Skip (leave the existing final image alone) or
        # Redo (wipe this filter's checkpoints and run it again from
        # scratch) instead of the usual resume-vs-start-over question.
        final_output_file = find_final_output_file(output_dir, initials)
        if final_output_file is not None:
            keep_existing = ask_yes_no(
                siril, f"'{filter_name}' already finished",
                f"'{filter_name}' already has a final image in "
                f"'{PREPROCESS_DIR_NAME}/{PHASE3_OUTPUT_SUBDIR_NAME}' "
                f"('{final_output_file.name}') from an earlier run -- "
                "resuming isn't the right choice here since there's no "
                "unfinished pipeline left to resume into. Skip this "
                "filter and keep that final image as-is, or redo its "
                "whole pipeline from scratch?",
                yes_text="Skip (keep existing)", no_text="Redo from scratch",
            )
            if keep_existing:
                siril.log(
                    f"[phase 3] '{filter_name}': already has a final image "
                    f"('{final_output_file.name}') -- skipping, kept as-is."
                )
                wizard_mark_done(f"phase3_run:{filter_name}")
                continue

            removed = delete_all_phase3_checkpoints(folder, initials)
            siril.log(
                f"[phase 3] '{filter_name}': redoing from scratch by user "
                f"choice (it already had a final image) -- removed "
                f"{removed} old checkpoint file(s)."
            )
            resume_index, chain, remaining_steps = 0, [], active_steps
            current = find_working_file(folder, initials)
            if current is None:
                siril.log(
                    f"[phase 3] '{filter_name}': no '{initials}.fit'/'.fits' "
                    f"found in '{folder}' to redo from -- skipping."
                )
                wizard_mark_done(f"phase3_run:{filter_name}")
                continue

        else:
            resume_index, chain, current = find_resume_point(folder, initials, active_steps)
            if current is None:
                siril.log(
                    f"[phase 3] '{filter_name}': no '{initials}.fit'/'.fits' "
                    f"found in '{folder}' -- skipping."
                )
                wizard_mark_done(f"phase3_run:{filter_name}")
                continue

            remaining_steps = active_steps[resume_index:]
            if resume_index > 0:
                resume = ask_yes_no(
                    siril, f"Resume '{filter_name}'?",
                    f"'{filter_name}' already has progress from an earlier run "
                    f"-- through '{active_steps[resume_index - 1]['label']}' "
                    f"({current.name}). Resume from there, or start this "
                    "filter's pipeline over from the beginning?\n\n"
                    "(This only lines up correctly if the pipeline hasn't been "
                    "reconfigured since that earlier run.)",
                    yes_text="Resume", no_text="Start over",
                )
                if resume:
                    siril.log(
                        f"[phase 3] '{filter_name}': resuming after "
                        f"'{active_steps[resume_index - 1]['label']}' -> {current.name}"
                    )
                else:
                    resume_index = 0
                    chain = []
                    remaining_steps = active_steps
                    current = find_working_file(folder, initials) or current
                    removed = delete_all_phase3_checkpoints(folder, initials)
                    siril.log(
                        f"[phase 3] '{filter_name}': starting the pipeline over from the "
                        f"beginning by user choice -- removed {removed} old checkpoint "
                        "file(s) from the previous run."
                    )

        siril.cmd("cd", siril_quote(folder))
        siril.cmd("load", siril_quote(current))
        set_display_autostretch(siril)
        siril.log(f"[phase 3] '{filter_name}': working directory set to '{folder}', loaded {current.name}.")

        # The actual "run each configured step, one checkpoint window at a
        # time" loop -- shared with run_phase4_starmask_pipeline, see
        # run_pipeline_steps.
        aborted, chain, current = run_pipeline_steps(
            siril, tool_paths, remaining_steps, chain, current, folder, initials,
            display_name=filter_name, log_prefix="phase 3", phase_label="Phase 3",
            star_removal_handler=handle_star_removal_step,
        )

        if aborted:
            wizard_mark_done(f"phase3_run:{filter_name}")
            return False

        finalize_phase3_filter(siril, folder, output_dir, initials, filter_name, current)
        wizard_mark_done(f"phase3_run:{filter_name}")

        siril.log(f"[phase 3] '{filter_name}': pipeline complete -> {current.name}")

    # Every selected filter is done -- copy the finished "1 - Output" files
    # (the "<Initials> - Final.<ext>" images finalize_phase3_filter() wrote
    # there for each filter) into "3 - Image Processing" too, so they're
    # sitting somewhere convenient right in the main dataset folder instead
    # of nested inside "2 - Pre-process". Copied, not moved -- "1 - Output"
    # remains the authoritative copy (and stays correct as the source of
    # truth if this wizard is ever re-run against this dataset).
    image_processing_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in output_dir.iterdir():
        if f.is_file():
            shutil.copy2(f, image_processing_dir / f.name)
            copied += 1
    if copied:
        siril.log(
            f"[phase 3] Copied {copied} final image(s) from "
            f"'{PREPROCESS_DIR_NAME}/{PHASE3_OUTPUT_SUBDIR_NAME}' into "
            f"'{IMAGE_PROCESSING_DIR_NAME}' for easy access."
        )

    # The whole run is done -- leave Siril's working directory sitting in
    # "3 - Image Processing" rather than wherever the last filter's folder
    # happened to be, since that's where the finished images just landed
    # and almost certainly where you'd want to keep working from next.
    siril.cmd("cd", siril_quote(image_processing_dir))
    siril.log(f"[phase 3] Working directory set to '{image_processing_dir}'.")

    show_message(
        siril, "Phase 3 complete",
        "Every selected filter has gone through its configured pipeline. "
        "Final checkpoint files are in "
        f"'{PREPROCESS_DIR_NAME}', inside each filter's own subfolder, and "
        f"the finished image(s) have also been copied into "
        f"'{IMAGE_PROCESSING_DIR_NAME}' for easy access -- Siril's working "
        "directory has been set there too.",
    )
    return True


# --------------------------------------------------------------------------
# Phase 4: an optional RGB/HOO starmask composite (Siril's "rgbcomp"
# command), run through its own (possibly reused) pre-process pipeline the
# same way each filter's own image goes through phase 3.
# --------------------------------------------------------------------------

def determine_starmask_capabilities(selected_filters: list[str]) -> tuple[bool, bool, bool]:
    """Which starmask recipes this dataset's selected filters can actually
    support: RGB needs Red+Green+Blue, HOO needs H-alpha+OIII, and
    Luminance is an optional add-on offered alongside either one if a
    Luminance filter was ALSO selected. Matched via filter_initials, so
    differently-spelled filter names ("Red"/"red"/"R") all resolve the
    same way they do everywhere else in this wizard."""

    initials = {filter_initials(f) for f in selected_filters}
    can_rgb = {"R", "G", "B"} <= initials
    can_hoo = {"Ha", "OIII"} <= initials
    can_lum = "L" in initials
    return can_rgb, can_hoo, can_lum


def find_phase2_source_file(preprocess_dir: Path, filter_name: str) -> Path | None:
    """Locates filter_name's ORIGINAL, untouched Phase 2 output -- the
    plain "<Initials>.fit"/".fits" that landed in its own "2 - Pre-process"
    subfolder straight out of registration/cropping, before Phase 3's
    pipeline has done anything to it. This is deliberately NOT Phase 3's
    final result: a starmask composite needs to be built from the raw,
    unprocessed channel images (not already background-extracted,
    stretched, or -- worst of all -- already star-removed by Phase 3's own
    pipeline), since Phase 4 runs its OWN separate pipeline against the
    fresh composite afterwards. Phase 3 never renames or deletes this
    original file (its checkpoints are always saved under new chained
    names alongside it -- see chained_filename/delete_all_phase3_
    checkpoints), so it's still sitting there even after Phase 3 has fully
    finished. Returns None if the filter has no subfolder or no starting
    file at all."""

    folder = find_filter_subfolder(preprocess_dir, filter_name)
    if folder is None:
        return None
    return find_working_file(folder, filter_initials(filter_name))


def ask_manual_recipe_layout(siril: "s.SirilInterface") -> str:
    """Only shown when the user picked "Manual" on ask_starmask_mode's
    screen AND this dataset's selected filters support BOTH RGB and HOO
    (see determine_starmask_capabilities) -- manual channel assignment
    still needs a starting layout (rgbcomp's plain three-channel R/G/B, or
    its H-alpha/OIII bicolor palette) before ask_channel_assignment can
    show the right channel rows to fill in. Skipped entirely (the one
    supported layout is used automatically) when the dataset only
    supports RGB or only HOO. Returns "rgb" or "hoo"."""

    root = _new_root(siril, "Phase 4 -- Manual layout")
    _header(root, "Which channel layout?")

    card = _card(root)
    _wrapping_label(
        card,
        "Manual assignment still starts from one of rgbcomp's two channel "
        "layouts -- RGB's three plain channels, or HOO's H-alpha/OIII "
        "bicolor palette -- before you can pick which filter feeds each "
        "one.",
    )

    choice_var = tk.StringVar(value="rgb")
    options_row = ttk.Frame(card, style="Card.TFrame")
    options_row.pack(fill="x", anchor="w", pady=(12, 0))
    ttk.Radiobutton(
        options_row, text="RGB (Red, Green, Blue)", variable=choice_var,
        value="rgb", style="TRadiobutton",
    ).pack(anchor="w", pady=2)
    ttk.Radiobutton(
        options_row, text="HOO (H-alpha, OIII)", variable=choice_var,
        value="hoo", style="TRadiobutton",
    ).pack(anchor="w", pady=2)

    outcome = {"result": "rgb"}

    def on_continue():
        outcome["result"] = choice_var.get()
        root.destroy()

    btns = _button_row(root)
    ttk.Button(btns, text="Continue", style="Accent.TButton", command=on_continue).pack(side="right")

    root.mainloop()
    _check_not_closed()
    return outcome["result"]


def ask_starmask_mode(siril: "s.SirilInterface", can_rgb: bool, can_hoo: bool) -> tuple[str, bool] | None:
    """Phase 4's first screen: which channel combination to build the
    starmask composite from, limited to whichever recipe(s) this dataset's
    selected filters can actually support (see
    determine_starmask_capabilities), plus a "Manual" choice that skips
    the normal automatic Red/Green/Blue (or H-alpha/OIII) matching by
    filter name and shows ask_channel_assignment afterwards instead, so
    the user can pick exactly which selected filter feeds each channel.
    RGB, HOO, and Manual are one single mutually-exclusive choice here --
    not a separate "manually assign" checkbox alongside the RGB/HOO pick --
    since picking Manual is a genuinely different path through this
    screen, not a modifier on top of RGB or HOO. If Manual is picked and
    the dataset supports BOTH RGB and HOO, ask_manual_recipe_layout asks
    which of the two layouts to manually fill in; with only one supported,
    that one is used automatically with no extra prompt. Always offers a
    Skip button (with a confirmation, since it's easy to click by
    accident) -- a starmask is entirely optional. Returns
    (mode, manual_channels) where mode is "rgb" or "hoo" (manual_channels
    is True whenever Manual was picked, whichever layout it resolved to),
    or None if the user chose to skip phase 4 and confirmed it."""

    if not can_rgb and not can_hoo:
        siril.log(
            "[phase 4] Neither RGB (needs Red+Green+Blue) nor HOO (needs "
            "H-alpha+OIII) is possible with this dataset's selected "
            "filters -- skipping the starmask step entirely."
        )
        return None

    while True:
        root = _new_root(siril, "Phase 4 -- Starmask")
        _header(root, "Generate a starmask?")

        card = _card(root)
        _wrapping_label(
            card,
            "Combine some of this dataset's finished filters into a color "
            "composite (via Siril's RGB Compositing) purely to use as a "
            "starmask reference. Choose which channel recipe to build it "
            "from -- matched automatically by filter name, or picked "
            "yourself -- or skip this step entirely -- it's optional.",
        )

        default_mode = "rgb" if can_rgb else "hoo"
        choice_var = tk.StringVar(value=default_mode)
        options_row = ttk.Frame(card, style="Card.TFrame")
        options_row.pack(fill="x", anchor="w", pady=(12, 0))
        if can_rgb:
            ttk.Radiobutton(
                options_row, text="RGB (Red, Green, Blue)", variable=choice_var,
                value="rgb", style="TRadiobutton",
            ).pack(anchor="w", pady=2)
        if can_hoo:
            ttk.Radiobutton(
                options_row, text="HOO (H-alpha, OIII)", variable=choice_var,
                value="hoo", style="TRadiobutton",
            ).pack(anchor="w", pady=2)
        ttk.Radiobutton(
            options_row, text="Manual (choose which filter feeds each channel yourself)",
            variable=choice_var, value="manual", style="TRadiobutton",
        ).pack(anchor="w", pady=2)

        outcome = {"result": "skip"}

        def on_continue():
            outcome["result"] = choice_var.get()
            root.destroy()

        def on_skip():
            outcome["result"] = "skip"
            root.destroy()

        btns = _button_row(root)
        ttk.Button(btns, text="Continue", style="Accent.TButton", command=on_continue).pack(side="right")
        ttk.Button(btns, text="Skip phase 4", command=on_skip).pack(side="right", padx=(0, 8))

        root.mainloop()
        _check_not_closed()

        if outcome["result"] == "manual":
            if can_rgb and can_hoo:
                mode = ask_manual_recipe_layout(siril)
            else:
                mode = "rgb" if can_rgb else "hoo"
            return mode, True

        if outcome["result"] != "skip":
            return outcome["result"], False

        confirm_skip = ask_yes_no(
            siril, "Skip the starmask?",
            "Skip phase 4 (generating a starmask) entirely? You can "
            "always run this wizard again later against this same dataset "
            "to build one.",
            yes_text="Yes, skip it", no_text="Go back",
        )
        if confirm_skip:
            siril.log("[phase 4] Skipped by user choice.")
            return None
        # "Go back" -- loop and show the mode-choice screen again.


def ask_channel_assignment(
    siril: "s.SirilInterface", selected_filters: list[str], mode: str, use_luminance: bool,
) -> dict[str, str]:
    """Shown instead of relying on automatic name matching, when the user
    picked "Manual" on ask_starmask_mode's screen. Lists one dropdown per channel this
    starmask needs -- R/G/B for RGB, or three rows for HOO (H-alpha for
    red, plus a separate row each for the green and blue channels, since
    the classic HOO palette reuses the same OIII image for both but there's
    no reason to force that if the user wants something else there) --
    plus a Luminance row if use_luminance. Every dropdown lists ALL of this
    dataset's selected filters (not just the one that would normally
    auto-match that channel), pre-filled with the usual automatic match
    when one exists so confirming with no changes reproduces the same
    result build_starmask_composite would have picked on its own. Returns
    {channel_code: filter_name} -- channel codes are "R"/"G"/"B" for RGB,
    "Ha"/"OIII_G"/"OIII_B" for HOO, plus "L" if use_luminance -- ready to
    hand straight to build_starmask_composite's channel_assignment
    parameter."""

    by_initials = filters_by_initials(siril, selected_filters)

    if mode == "rgb":
        channels = [("R", "Red channel"), ("G", "Green channel"), ("B", "Blue channel")]
        auto_default = {"R": by_initials.get("R"), "G": by_initials.get("G"), "B": by_initials.get("B")}
    else:
        channels = [
            ("Ha", "Red channel (H-alpha)"),
            ("OIII_G", "Green channel (OIII)"),
            ("OIII_B", "Blue channel (OIII)"),
        ]
        auto_default = {
            "Ha": by_initials.get("Ha"),
            "OIII_G": by_initials.get("OIII"),
            "OIII_B": by_initials.get("OIII"),
        }
    if use_luminance:
        channels.append(("L", "Luminance channel"))
        auto_default["L"] = by_initials.get("L")

    root = _new_root(siril, "Phase 4 -- Channel assignment")
    _header(root, "Assign filters to channels")

    # _card()'s second argument is a LabelFrame TITLE, not a body
    # paragraph -- a title never wraps or reflows on resize the way
    # _wrapping_label's text does, so this sentence is added as an actual
    # wrapping label inside a plain (untitled) card instead, matching
    # every other phase 4 screen.
    card = _card(root)
    _wrapping_label(
        card,
        "Each row is pre-filled with the usual match by filter name -- "
        "change any dropdown to use a different one of this dataset's "
        "filters for that channel instead.",
        pady=(0, 10),
    )

    combos: dict[str, ttk.Combobox] = {}
    for code, label in channels:
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x", anchor="w", pady=5)
        ttk.Label(row, text=label, style="Card.TLabel", anchor="w").pack(
            side="left", fill="x", expand=True
        )
        combo = ttk.Combobox(row, state="readonly", width=30, values=selected_filters)
        default = auto_default.get(code)
        combo.set(default if default in selected_filters else selected_filters[0])
        combo.pack(side="right")
        combos[code] = combo

    result: dict[str, str] = {}

    def on_continue():
        result.update({code: combo.get() for code, combo in combos.items()})
        root.destroy()

    btns = _button_row(root)
    ttk.Button(btns, text="Continue", style="Accent.TButton", command=on_continue).pack(side="right")

    root.mainloop()
    _check_not_closed()
    return result


def ask_use_luminance(siril: "s.SirilInterface", mode: str) -> bool:
    """Second phase 4 screen (only asked when a Luminance filter is
    actually available): whether to fold it in as a fourth channel,
    turning an RGB composite into LRGB (or HOO into LHOO)."""

    label = "RGB" if mode == "rgb" else "HOO"
    return ask_yes_no(
        siril, "Use a Luminance image?",
        f"Also use this dataset's Luminance filter as a fourth channel, "
        f"making this an L{label} composite instead of plain {label}?",
        yes_text="Yes, use Luminance", no_text="No, just " + label,
    )


def build_starmask_composite(
    siril: "s.SirilInterface", preprocess_dir: Path,
    selected_filters: list[str], mode: str, use_luminance: bool,
    channel_assignment: dict[str, str] | None = None,
) -> tuple[Path, str] | None:
    """Gathers this starmask's source channel images -- each filter's
    ORIGINAL, unprocessed Phase 2 output, not Phase 3's final result (see
    find_phase2_source_file for why) -- copies them into a fresh
    "2 - Pre-process/Starmask" subfolder, makes that folder Siril's
    working directory, then runs the composite as a single one-shot
    "rgbcomp" command with every channel already filled in by name.

    Each copy is named after the assigned FILTER's own initials (e.g.
    "OIII.fit"), never a generic "R"/"G"/"B" or "Ha"/"OIII_G"/"OIII_B"
    channel-role name (see the comment on _gather, below) -- this matters
    once channel_assignment is involved, since a file literally called
    "Ha.fit" that isn't actually H-alpha data would look like the wizard
    ignored a manual pick even when it didn't. rgbcomp only cares about
    each filename's POSITION in its argument list to know which channel
    it feeds, so naming them after the real filter instead of the role is
    purely cosmetic from Siril's point of view -- it's here for the
    Starmask folder to make sense to a person looking at it. A filter
    that feeds more than one channel (the classic HOO palette reusing
    OIII for both green and blue, or any other repeat via manual
    assignment) is only copied once; rgbcomp is just pointed at that same
    filename twice.

    channel_assignment, when given (see ask_channel_assignment), overrides
    the normal automatic Red/Green/Blue (or H-alpha/OIII) matching by
    filter name -- it maps each channel ROLE ("R"/"G"/"B" for RGB,
    "Ha"/"OIII_G"/"OIII_B" for HOO, plus "L") straight to whichever
    selected filter the user picked for that channel, letting an unusual
    filter stand in for a channel it wouldn't otherwise auto-match. Left
    as None, every channel is matched the old way, by filter_initials.

    This deliberately does NOT try to open Siril's interactive RGB
    Compositing dialog and drive it by hand -- there's no scripting way to
    fill in an already-open dialog's own fields or tick its own checkboxes
    (the same limitation documented on BUILTIN_TOOL_CATALOG's "dialog"
    mapping elsewhere in this file, for other built-in tools). Running
    "rgbcomp" with the R/G/B(/lum) filenames already decided produces
    exactly the same result as a person filling in that same dialog by
    hand and clicking Compose -- just without needing to click through it.

    Since phase 4 can be re-run against this same dataset with a
    different recipe/assignment every time, and every run shares this one
    "Starmask" subfolder, this also cleans up whatever the PREVIOUS
    run(s) left behind that doesn't belong to this run: any channel image
    (R/G/B, Ha/OIII_G/OIII_B, L) not part of this run's recipe, and every
    file belonging to a different stem entirely (e.g. leftover "HOO
    Starmask.*" files after switching to RGB, or after a manual
    reassignment changes the stem's own name -- see where "label" is
    built above). This run's OWN stem's files are always left alone.

    Also tracks exactly which filter fed each channel in a small
    "<stem>.sources.json" sidecar file, and wipes any of "stem"'s old
    per-step checkpoints if that assignment has changed since the last
    time this same stem was built here (e.g. re-picking different filters
    via channel_assignment after an earlier attempt, that happens to land
    on the same stem name by coincidence) -- otherwise a later resume
    could apply/skip pipeline steps against an image that no longer
    matches what's actually sitting in "stem.fit" now. Re-running
    with the exact same sources leaves existing checkpoints alone, so
    resuming after a plain abort still works.

    Loads the finished composite into Siril in AutoStretch display mode
    once done. Returns (composite_fit_path, stem) -- stem (e.g. "RGB
    Starmask" or "LHOO Starmask" for a standard automatic assignment, or
    something like "RGS Starmask" if channel_assignment substituted a
    non-standard filter into one of the channels -- see the comment where
    "label" is built, right before stem itself) is the base name this
    starmask's OWN checkpoint chain uses from here on, exactly the way
    each filter's initials drive its own chain in phase 3 -- or None if
    any required source image is missing or "rgbcomp" didn't produce a
    result."""

    by_initials = filters_by_initials(siril, selected_filters)
    starmask_dir = preprocess_dir / STARMASK_SUBDIR_NAME
    starmask_dir.mkdir(parents=True, exist_ok=True)

    # Recorded as each channel is actually gathered below, then compared
    # against whatever was recorded the LAST time "stem" was built (see
    # the sources_file check further down) -- this is what lets a changed
    # channel_assignment (or a different auto-match, if the dataset's
    # filters changed) be told apart from simply re-running against the
    # exact same sources as before.
    sources_used: dict[str, str] = {}

    # channel_code -> the destination filename (no extension) rgbcomp
    # should actually be pointed at for that channel -- see _gather just
    # below for why this is the assigned FILTER's own initials, not a
    # generic channel-role name.
    channel_filenames: dict[str, str] = {}

    def _gather(channel_code: str, initials_code: str) -> str | None:
        # Copies under the assigned filter's OWN initials (e.g. "OIII.fit"),
        # never a generic channel-role name like "Ha.fit"/"OIII_G.fit" --
        # with manual channel_assignment able to put ANY filter into ANY
        # channel, naming the copy after the channel role instead of the
        # actual filter would leave a file called "Ha.fit" sitting in the
        # Starmask folder that isn't H-alpha data at all, which is exactly
        # the kind of thing that looks like the wizard ignored a manual
        # pick even though it didn't. Copied only once per distinct
        # filter (checked via "dest.is_file()") even if that SAME filter
        # feeds more than one channel -- the classic HOO palette reusing
        # OIII for both green and blue, or any other repeat via manual
        # assignment -- rgbcomp is simply pointed at that one file's name
        # twice rather than keeping two identical copies around. Returns
        # the destination filename (no extension) to use in rgbcomp's
        # argument list for this channel, or None if the assigned filter
        # (or its phase 2 source image) couldn't be found.
        if channel_assignment is not None:
            filter_name = channel_assignment.get(channel_code)
        else:
            filter_name = by_initials.get(initials_code)
        if filter_name is None:
            return None
        src = find_phase2_source_file(preprocess_dir, filter_name)
        if src is None or not src.is_file():
            return None
        dest_stem = filter_initials(filter_name)
        dest = starmask_dir / f"{dest_stem}{src.suffix}"
        if not dest.is_file():
            shutil.copy2(src, dest)
        sources_used[channel_code] = filter_name
        return dest_stem

    missing: list[str] = []

    def _require(channel_code: str, initials_code: str, missing_label: str) -> None:
        filename = _gather(channel_code, initials_code)
        if filename is None:
            missing.append(missing_label)
        else:
            channel_filenames[channel_code] = filename

    if mode == "rgb":
        _require("R", "R", "Red")
        _require("G", "G", "Green")
        _require("B", "B", "Blue")
    else:
        _require("Ha", "Ha", "H-alpha")
        _require("OIII_G", "OIII", "OIII (green)")
        _require("OIII_B", "OIII", "OIII (blue)")
    if use_luminance:
        _require("L", "L", "Luminance")

    if missing:
        show_message(
            siril, "Missing starmask source image(s)",
            "Couldn't find a Phase 2 image for: " +
            ", ".join(missing) +
            f". Phase 4 (starmask) can't continue -- check that each of "
            f"those filters actually finished Phase 2 and has its original "
            f"checkpoint file under '{PREPROCESS_DIR_NAME}'.",
            kind="error",
        )
        return None

    siril.cmd("cd", siril_quote(starmask_dir))

    prefix = "L" if use_luminance else ""
    if channel_assignment is not None:
        # Manual assignment can point a channel at an unusual filter (a
        # different narrowband filter standing in for a "channel" it
        # wouldn't normally represent) -- keeping the generic "RGB"/"HOO"
        # name regardless would silently collide with a completely
        # different manual combination that happens to share the same
        # mode, tricking a LATER run's checkpoint/resume logic (see
        # find_resume_point) into treating them as the exact same
        # starmask even though the actual source pixels differ. Instead,
        # the key is built from each actually-assigned filter's own first
        # letter, in the same R/G/B or Ha/OIII_G/OIII_B channel order
        # "rgbcomp" uses -- a standard Red/Green/Blue (or H-alpha/OIII)
        # assignment still comes out as the familiar "RGB"/"HOO", but any
        # non-standard substitution naturally earns its own distinct name
        # instead of colliding with anything else.
        channel_order = ["R", "G", "B"] if mode == "rgb" else ["Ha", "OIII_G", "OIII_B"]
        label = "".join(
            sources_used[code][0].upper() for code in channel_order if sources_used.get(code)
        ) or ("RGB" if mode == "rgb" else "HOO")
    else:
        label = "RGB" if mode == "rgb" else "HOO"
    stem = f"{prefix}{label} Starmask"

    # Phase 4 can be re-run against this same dataset any number of times
    # with different choices each time -- a different recipe (RGB vs
    # HOO), the Luminance toggle flipped, or a different manual channel
    # assignment -- and every one of those runs shares this same
    # "Starmask" subfolder. Left alone, it would just keep accumulating
    # every previous attempt's leftovers forever. Two kinds of leftovers
    # are cleaned up now, right before this run actually writes anything
    # of its own:
    #
    # 1. Channel source images -- now named after whichever FILTER was
    #    actually assigned (e.g. "OIII.fit"), not a fixed channel-role
    #    name -- that aren't part of THIS run's recipe. Any bare
    #    "<Initials>.fit"/".fits" sitting directly in the Starmask folder
    #    (i.e. not one of THIS run's own composite/checkpoint files,
    #    which all have " Starmask" in their name -- see step 2 below) is
    #    a channel image from some earlier run; if it isn't one of the
    #    filenames this run just gathered into channel_filenames, it's
    #    left over from a different recipe or manual assignment (e.g.
    #    switching from HOO to RGB leaves "Ha.fit"/"OIII.fit" behind, or
    #    dropping Luminance leaves a stale "L.fit"'s worth of whatever
    #    filter that was) and gets removed.
    needed_channel_filenames = set(channel_filenames.values())
    unused_channel_files = 0
    for f in list(starmask_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() not in (".fit", ".fits"):
            continue
        if "Starmask" in f.stem or f.stem in needed_channel_filenames:
            continue
        try:
            f.unlink()
            unused_channel_files += 1
        except OSError:
            pass
    if unused_channel_files:
        siril.log(
            f"[phase 4] Removed {unused_channel_files} channel image "
            "file(s) left over from a different recipe/assignment on an "
            "earlier run (not used by this one)."
        )

    # 2. Everything belonging to a DIFFERENT stem than this run's own --
    #    e.g. "HOO Starmask.fit" and its whole checkpoint chain, sitting
    #    around from an earlier attempt, after this run's manual
    #    reassignment or recipe change produced a different stem like
    #    "RGB Starmask" instead. Matched by stripping each file's own
    #    " - <chain>"/".sources.json"/".fit"/".fits" suffix back down to
    #    its stem and comparing that to THIS run's stem -- anything that
    #    doesn't match gets removed; this run's own stem's files (its raw
    #    composite, per-step checkpoints, and sources.json) are left
    #    completely alone so resuming still works.
    other_stem_pattern = re.compile(r"^(?P<stem>.+ Starmask)(?:\.(?:fit|fits)|\.sources\.json| - .*)$")
    removed_other_stem = 0
    for f in list(starmask_dir.iterdir()):
        if not f.is_file():
            continue
        match = other_stem_pattern.match(f.name)
        if match and match.group("stem") != stem:
            try:
                f.unlink()
                removed_other_stem += 1
            except OSError:
                pass
    if removed_other_stem:
        siril.log(
            f"[phase 4] Removed {removed_other_stem} file(s) left over "
            f"from a different starmask (not '{stem}') built here on an "
            "earlier run."
        )

    # If an earlier run already built a "stem" composite (e.g. this same
    # "HOO Starmask" from a previous, aborted attempt) from a DIFFERENT
    # set of source filters -- most likely because "manually choose which
    # filter goes to each channel" picked something different this time --
    # any of its old per-step checkpoint files (chained off "stem",
    # exactly like a filter's own chain in phase 3) describe a pipeline
    # applied to THAT earlier composite's actual pixels, not this one,
    # even though they'd share the exact same filenames. Letting
    # find_resume_point() see those and offer to "resume" would silently
    # skip steps as already done against an image that no longer exists.
    # A small sidecar JSON file records exactly which filter fed each
    # channel the last time "stem" was built here; if this run's sources
    # don't match that record, every old checkpoint for "stem" is wiped
    # now, before rebuilding, so there's nothing stale left to resume
    # from -- this run starts that pipeline fresh, same as a manual
    # "start over" would. Re-running with the exact same sources (the
    # common case -- just continuing after an abort) leaves everything
    # alone, so resuming mid-pipeline still works as expected.
    sources_file = starmask_dir / f"{stem}.sources.json"
    previous_sources: dict[str, str] | None = None
    if sources_file.is_file():
        try:
            previous_sources = json.loads(sources_file.read_text())
        except (OSError, ValueError):
            previous_sources = None

    if previous_sources is not None and previous_sources != sources_used:
        removed = delete_all_phase3_checkpoints(starmask_dir, stem)
        siril.log(
            f"[phase 4] '{stem}': source filter(s) changed since this "
            f"starmask was last built ({previous_sources} -> "
            f"{sources_used}) -- removed {removed} old checkpoint "
            "file(s) so this run's pipeline starts fresh instead of "
            "resuming against the wrong image."
        )

    try:
        sources_file.write_text(json.dumps(sources_used))
    except OSError as e:
        siril.log(
            f"[phase 4] Couldn't record '{stem}''s source filter(s) ({e}) "
            "-- if they change on a later run, stale checkpoints might "
            "not get cleared automatically."
        )

    # Remove any leftover "<stem>.fit"/".fits" from an earlier attempt
    # FIRST -- Siril's "rgbcomp" refuses to overwrite an existing output
    # file ("failed to create new file (already exists?)"), which would
    # otherwise make this fail every time phase 4 is re-run against the
    # same dataset (e.g. after fixing a pipeline choice, or just trying
    # again) instead of simply rebuilding the composite fresh, which is
    # exactly what this function is meant to do each time it's called.
    for ext in (".fit", ".fits"):
        stale = starmask_dir / f"{stem}{ext}"
        if stale.is_file():
            try:
                stale.unlink()
            except OSError:
                pass

    # Bare filenames (no extension, no path) since Siril's working
    # directory is already the starmask folder -- same convention "load"/
    # "save" use everywhere else in this wizard. "-out=..." needs quoting
    # via siril_quote() (wrapping the WHOLE "-out=value" token in double
    # quotes, not just the value after "=") since Siril's own command-line
    # tokenizer only treats a token as quoted when the quote is its very
    # first character -- quoting just the value half, e.g.
    # -out="HOO Starmask", left the tokenizer splitting on the space
    # anyway and silently truncating the name to "HOO".
    args: list[str] = []
    if use_luminance:
        args.append(f"-lum={channel_filenames['L']}")
    if mode == "rgb":
        args += [channel_filenames["R"], channel_filenames["G"], channel_filenames["B"]]
    else:
        args += [channel_filenames["Ha"], channel_filenames["OIII_G"], channel_filenames["OIII_B"]]
    args.append(siril_quote(f"-out={stem}"))

    siril.log(f"[phase 4] Building '{stem}' via Siril's RGB Compositing (\"rgbcomp\"): {' '.join(args)}")
    try:
        siril.cmd("rgbcomp", *args)
    except Exception as e:
        show_message(
            siril, "RGB Compositing failed",
            f"Siril's \"rgbcomp\" command failed: {e}\n\nCheck Siril's log "
            "above for its own error output. Phase 4 (starmask) stops "
            "here -- nothing else has been touched.",
            kind="error",
        )
        return None

    result = find_working_file(starmask_dir, stem)
    if result is None:
        show_message(
            siril, "RGB Compositing failed",
            f"Siril's \"rgbcomp\" command didn't produce '{stem}.fit'/"
            "'.fits' as expected -- check Siril's log for its own error "
            "output. Phase 4 (starmask) stops here.",
            kind="error",
        )
        return None

    siril.cmd("load", siril_quote(result))
    set_display_autostretch(siril)
    siril.log(f"[phase 4] '{stem}' created and loaded (AutoStretch display).")
    return result, stem


def run_phase4_starmask_pipeline(
    siril: "s.SirilInterface", cfg: dict, preprocess_dir: Path,
    image_processing_dir: Path, selected_filters: list[str],
) -> bool:
    """Phase 4, in full: asks which starmask recipe to build (or to skip
    entirely -- see ask_starmask_mode), builds the RGB/HOO(/L) composite
    (build_starmask_composite), then asks whether to run it through Phase
    3's own pre-process pipeline as-is or set up a separate one just for
    the starmask (configure_phase3_steps, saved under cfg["phase4_steps"]
    rather than cfg["phase3_steps"] so the two never overwrite each
    other), then runs that pipeline step by step exactly the way
    run_phase3_pipeline does for a filter -- same resume/back/skip/abort
    behavior, same checkpoint-chain naming (via the composite's own "stem"
    standing in for a filter's initials) -- except a Star Removal step
    keeps the star MASK output rather than the starless one (see
    handle_star_removal_step_for_starmask, the mirror image of phase 3's
    handling). Finishes with the same final-export prompt phase 3 uses
    (ask_final_export_format, via finalize_phase3_filter), copying the
    result into "1 - Output" and "3 - Image Processing" alongside every
    filter's own final image.

    Returns True only if phase 4 reached a clean end -- skipped right from
    ask_starmask_mode's very first screen (before anything was touched),
    already had a final image for this exact recipe/stem from an earlier
    run and the user chose to keep it (see find_final_output_file below),
    or its pipeline ran all the way through to completion just now.
    Returns False for every OTHER way this can end early: none of this
    dataset's filters support a starmask at all, the composite couldn't be
    built, the pipeline's own tool check was aborted, or the pipeline
    itself was aborted partway through a step. The caller uses this to
    decide whether it's safe to offer deleting "1 - Registration"/
    "2 - Pre-process" afterwards (see ask_delete_intermediate_folders) --
    an aborted-partway-through phase 4 still needs those folders, so that
    question shouldn't pop up in that case."""

    wizard_add_step("phase4_choice", "Phase 4: choose starmask")
    wizard_set_current("phase4_choice")

    can_rgb, can_hoo, can_lum = determine_starmask_capabilities(selected_filters)
    mode_choice = ask_starmask_mode(siril, can_rgb, can_hoo)
    if mode_choice is None:
        wizard_mark_done("phase4_choice")
        return True  # skipped right from the start -- a clean, complete outcome.
    mode, manual_channels = mode_choice

    use_luminance = ask_use_luminance(siril, mode) if can_lum else False

    channel_assignment = (
        ask_channel_assignment(siril, selected_filters, mode, use_luminance)
        if manual_channels else None
    )
    wizard_mark_done("phase4_choice")

    wizard_add_step("phase4_build", "Phase 4: build starmask composite")
    wizard_set_current("phase4_build")
    built = build_starmask_composite(
        siril, preprocess_dir, selected_filters, mode, use_luminance, channel_assignment,
    )
    if built is None:
        wizard_mark_done("phase4_build")
        return False
    composite_path, stem = built
    starmask_dir = composite_path.parent
    wizard_mark_done("phase4_build")

    wizard_add_step("phase4_run", f"Phase 4: pre-process ({stem})")
    wizard_set_current("phase4_run")

    # Mirrors run_phase3_pipeline's equivalent check (see find_final_output_file):
    # if an earlier run already carried THIS EXACT starmask (same stem, so the
    # same recipe/manual channel picks -- a different combination gets its own
    # stem and so isn't matched here) all the way through to a final image in
    # "1 - Output", there's nothing left to resume into, and asking about a
    # pipeline to run would be a pointless detour. Offer Skip/Redo instead,
    # before even asking which pipeline to use.
    output_dir = preprocess_dir / PHASE3_OUTPUT_SUBDIR_NAME
    final_output_file = find_final_output_file(output_dir, stem)
    if final_output_file is not None:
        keep_existing = ask_yes_no(
            siril, f"'{stem}' already finished",
            f"'{stem}' already has a final image in "
            f"'{PREPROCESS_DIR_NAME}/{PHASE3_OUTPUT_SUBDIR_NAME}' "
            f"('{final_output_file.name}') from an earlier run -- "
            "resuming isn't the right choice here since there's no "
            "unfinished pipeline left to resume into. Skip and keep that "
            "final image as-is, or redo this starmask's whole pipeline "
            "from scratch?",
            yes_text="Skip (keep existing)", no_text="Redo from scratch",
        )
        if keep_existing:
            siril.log(
                f"[phase 4] '{stem}': already has a final image "
                f"('{final_output_file.name}') -- skipping, kept as-is."
            )
            # Mirrors the normal completion path's tail below (copy into
            # "3 - Image Processing" + leave Siril sitting on it) so a
            # skipped-as-already-finished starmask ends up in the exact
            # same state a freshly-completed one would, rather than only
            # being reachable if this happened to survive from the run
            # that originally finished it.
            image_processing_dir.mkdir(parents=True, exist_ok=True)
            image_processing_copy = image_processing_dir / final_output_file.name
            shutil.copy2(final_output_file, image_processing_copy)
            siril.log(f"[phase 4] Copied '{final_output_file.name}' into '{IMAGE_PROCESSING_DIR_NAME}' too.")
            siril.cmd("cd", siril_quote(image_processing_dir))
            siril.cmd("load", siril_quote(image_processing_copy))
            set_display_autostretch(siril)
            siril.log(f"[phase 4] Working directory set to '{image_processing_dir}', loaded '{image_processing_copy.name}'.")
            wizard_mark_done("phase4_run")
            return True

        removed = delete_all_phase3_checkpoints(starmask_dir, stem)
        siril.log(
            f"[phase 4] '{stem}': redoing from scratch by user choice (it "
            f"already had a final image) -- removed {removed} old "
            "checkpoint file(s)."
        )

    use_same_pipeline = ask_yes_no(
        siril, "Starmask pipeline",
        "Run this starmask through the SAME pre-process pipeline configured "
        "for Phase 3, or set up a separate one just for the starmask?",
        yes_text="Use Phase 3's pipeline", no_text="Choose a new one",
    )

    if use_same_pipeline:
        active_steps = [step for step in (cfg.get("phase3_steps") or []) if step["scripts"]]
        tool_paths = cfg.get("phase3_tool_paths", {})
        siril.log("[phase 4] Reusing Phase 3's configured pipeline as-is.")
    else:
        # Shared with phase 3's own setup+tool-check flow (see
        # run_pipeline_setup_and_tool_check) -- this used to be a
        # separately-maintained near-duplicate of run_phase3_setup_and_
        # tool_check inline right here. setup_step_id/tools_step_id=None
        # since phase 4 manages its own single "phase4_run" sidebar row
        # around this whole call rather than getting phase 3's separate
        # per-stage rows.
        if not run_pipeline_setup_and_tool_check(
            siril, cfg,
            misc_count_key="phase4_misc_count", steps_config_key="phase4_steps",
            tool_paths_config_key="phase4_tool_paths", label_prefix="phase 4 starmask",
            title_prefix="Phase 4 setup", log_prefix="phase 4 setup",
            tools_notice_title="Required tools for the starmask pipeline",
            setup_step_id=None, tools_step_id=None,
        ):
            siril.log("[phase 4] Aborted at the starmask pipeline's tool check.")
            wizard_mark_done("phase4_run")
            return False

        active_steps = [step for step in (cfg.get("phase4_steps") or []) if step["scripts"]]
        tool_paths = cfg.get("phase4_tool_paths", {})

    if not active_steps:
        siril.log("[phase 4] No pipeline steps configured for the starmask -- exporting it as-is.")

    initials = stem  # chained_filename/find_resume_point don't care that this isn't a real filter's initials.
    resume_index, chain, current = find_resume_point(starmask_dir, initials, active_steps)
    if current is None:
        current = find_working_file(starmask_dir, initials)
    if current is None:
        # Mirrors run_phase3_pipeline's equivalent guard -- without this,
        # siril_quote(None) below would silently stringify to "None" and
        # hand Siril a "load None" command instead of failing loudly here.
        # In practice this means build_starmask_composite's own output
        # file has gone missing (deleted or renamed outside the wizard)
        # between building it and reaching this pipeline.
        siril.log(
            f"[phase 4] '{stem}': no starting image found in '{starmask_dir}' "
            "to run the pipeline on -- aborting the starmask pipeline."
        )
        wizard_mark_done("phase4_run")
        return False

    remaining_steps = active_steps[resume_index:]
    if resume_index > 0:
        resume = ask_yes_no(
            siril, f"Resume '{stem}'?",
            f"'{stem}' already has progress from an earlier run -- through "
            f"'{active_steps[resume_index - 1]['label']}' ({current.name}). "
            "Resume from there, or start this starmask's pipeline over "
            "from the beginning?",
            yes_text="Resume", no_text="Start over",
        )
        if resume:
            siril.log(f"[phase 4] '{stem}': resuming after '{active_steps[resume_index - 1]['label']}' -> {current.name}")
        else:
            resume_index = 0
            chain = []
            remaining_steps = active_steps
            current = find_working_file(starmask_dir, initials) or current
            removed = delete_all_phase3_checkpoints(starmask_dir, initials)
            siril.log(
                f"[phase 4] '{stem}': starting over -- removed {removed} old "
                "checkpoint file(s) from the previous attempt."
            )

    siril.cmd("cd", siril_quote(starmask_dir))
    siril.cmd("load", siril_quote(current))
    set_display_autostretch(siril)

    # The actual "run each configured step, one checkpoint window at a
    # time" loop -- shared with run_phase3_pipeline, see run_pipeline_steps.
    aborted, chain, current = run_pipeline_steps(
        siril, tool_paths, remaining_steps, chain, current, starmask_dir, initials,
        display_name=stem, log_prefix="phase 4", phase_label="Phase 4",
        star_removal_handler=handle_star_removal_step_for_starmask,
    )

    if aborted:
        wizard_mark_done("phase4_run")
        return False

    output_dir = preprocess_dir / PHASE3_OUTPUT_SUBDIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = finalize_phase3_filter(
        siril, starmask_dir, output_dir, initials, stem, current, log_prefix="phase 4",
    )
    if final_path is not None:
        image_processing_dir.mkdir(parents=True, exist_ok=True)
        image_processing_copy = image_processing_dir / final_path.name
        shutil.copy2(final_path, image_processing_copy)
        siril.log(f"[phase 4] Copied '{final_path.name}' into '{IMAGE_PROCESSING_DIR_NAME}' too.")

        # Leave Siril sitting on the finished starmask in
        # "3 - Image Processing" -- the same "working directory + loaded
        # image" state phase 3 leaves things in at its own completion --
        # so it's right there to look at/keep working from without having
        # to dig back into "2 - Pre-process" for it.
        siril.cmd("cd", siril_quote(image_processing_dir))
        siril.cmd("load", siril_quote(image_processing_copy))
        set_display_autostretch(siril)
        siril.log(f"[phase 4] Working directory set to '{image_processing_dir}', loaded '{image_processing_copy.name}'.")

    wizard_mark_done("phase4_run")
    siril.log(f"[phase 4] '{stem}': pipeline complete -> {current.name}")
    show_message(
        siril, "Phase 4 complete",
        f"'{stem}' has gone through its configured pipeline. The final "
        f"checkpoint files are in '{PREPROCESS_DIR_NAME}/{STARMASK_SUBDIR_NAME}', "
        f"and the finished starmask has also been copied into "
        f"'{PREPROCESS_DIR_NAME}/{PHASE3_OUTPUT_SUBDIR_NAME}' and "
        f"'{IMAGE_PROCESSING_DIR_NAME}' -- Siril's working directory has "
        "been set there too, with the starmask loaded.",
    )
    return True


def ask_delete_intermediate_folders(
    siril: "s.SirilInterface", registration_dir: Path, preprocess_dir: Path,
    image_processing_dir: Path | None = None,
) -> None:
    """The very last step of the whole run: now that every finished image
    (every filter's, and phase 4's starmask if one was built) has already
    been copied into "3 - Image Processing", offers to delete
    "1 - Registration" and "2 - Pre-process" to free up the disk space
    their intermediate stacking/pre-processing files take up -- or to keep
    them around for redundancy/backups (e.g. in case a step needs
    re-checking or redoing later). Deletion is the RECOMMENDED choice
    (the accented button), but keeping them is offered right alongside it,
    with a clear reminder that deleting can't be undone. Does nothing if
    neither folder actually exists.

    If image_processing_dir is given, Siril's working directory is moved
    there FIRST, right before actually deleting anything -- phase 4 already
    leaves things there on its own successful completion, but this is also
    the safety net for every other path (phase 4 skipped, aborted, or
    failed to build a composite at all), so Siril is never sitting inside
    a folder this function is about to remove out from under it."""

    existing = [d for d in (registration_dir, preprocess_dir) if d.is_dir()]
    if not existing:
        return

    proceed = ask_yes_no(
        siril, "Clean up intermediate folders?",
        f"Every finished image has already been copied into "
        f"'{IMAGE_PROCESSING_DIR_NAME}'. Delete "
        f"'{REGISTRATION_DIR_NAME}' and '{PREPROCESS_DIR_NAME}' now to "
        "free up disk space, or keep them around for redundancy/backups "
        "(e.g. in case you want to redo a step later)?\n\n"
        "This can't be undone once deleted.",
        yes_text="Delete them (recommended)", no_text="Keep them",
    )
    if not proceed:
        siril.log("[cleanup] Keeping intermediate folders by user choice.")
        return

    if image_processing_dir is not None:
        try:
            siril.cmd("cd", siril_quote(image_processing_dir))
        except Exception as e:
            siril.log(f"[cleanup] Couldn't move Siril's working directory out of the way first ({e}) -- deleting anyway.")

    removed = []
    for d in existing:
        try:
            shutil.rmtree(d)
            removed.append(d.name)
        except Exception as e:
            siril.log(f"[cleanup] Couldn't remove '{d}': {e} -- you can delete it by hand.")
    if removed:
        siril.log(f"[cleanup] Removed: {', '.join(removed)}.")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def _run_wizard(siril: "s.SirilInterface") -> None:
    cfg = load_config()

    wizard_add_step("arrange", "Dataset layout reminder")
    wizard_add_step("checkpoint", "Check for existing output")
    wizard_add_step("filters", "Select filters")
    wizard_add_step("calibration", "Check calibration frames")
    wizard_add_step("tools", "Check stacking script (phase 1)")
    # Per-filter stacking steps, plus "convert_register"/"crop"/
    # "copy_preprocess"/"phase3_tools", are added once selected_filters is
    # known below (or, on the "skip straight to phase 3" checkpoint path,
    # right before that check itself runs) -- so it shows up in the sidebar
    # in the right spot: right before phase 3 actually starts, not up here
    # next to the phase 1 tool check.

    wizard_set_current("arrange")
    show_arrangement_notice(siril, cfg)
    wizard_mark_done("arrange")

    already_set = ask_yes_no(
        siril, "Main dataset folder",
        "Have you already set Siril's Home/current working directory to "
        "your main dataset folder?",
        yes_text="Yes, already set", no_text="No, let me choose",
    )
    if already_set:
        main_folder = get_main_folder_from_siril_wd(siril)
        if not main_folder:
            siril.log("Couldn't determine the main dataset folder from Siril's working directory -- aborting.")
            return
        siril.log(f"Using Siril's current working directory as the main dataset folder: {main_folder}")
    else:
        main_folder = choose_main_folder_dialog(siril)
        if not main_folder:
            siril.log("No main dataset folder selected -- aborting.")
            return
        siril.cmd("cd", siril_quote(main_folder))
        siril.log(f"Set Siril's working directory to the selected main dataset folder: {main_folder}")

    # Recorded here (as soon as it's known) so main()'s finally block can
    # reset Siril's working directory back to it if this run ends early --
    # aborted mid-phase, the wizard window closed, or an unhandled error --
    # with Siril's cwd possibly left sitting somewhere deep inside
    # "2 - Pre-process/<Filter>" (or phase 4's "Starmask" subfolder) from
    # whatever step was in progress. Left as-is, a LATER run's "Yes,
    # already set" would treat that leftover subfolder as the main dataset
    # folder itself and go looking for filter subfolders/etc. inside IT --
    # not a good time. _RUN_STATE["completed"] only flips True once this
    # run actually reaches its own real end (see the two ask_delete_
    # intermediate_folders() call sites below); anything short of that
    # leaves it False, so main() knows to reset the cwd on the way out.
    _RUN_STATE["main_folder"] = main_folder

    # Top-level checkpoint, checked before anything else (even filter
    # selection): if this dataset already has phase 2 output sitting in
    # "2 - Pre-process" from a previous run, ask before redoing phases 1-2
    # at all rather than assuming a rerun means starting over.
    wizard_set_current("checkpoint")
    preprocess_dir = main_folder / PREPROCESS_DIR_NAME
    if preprocess_dir_has_output(preprocess_dir):
        # yes_text/no_text are swapped from ask_yes_no's usual "yes is the
        # affirmative/accent choice" convention on purpose here -- Skip to
        # phase 3 is the far more common choice on a re-run (the whole
        # point of this checkpoint existing), so it gets the accent
        # button in the normal rightmost/primary spot, with Re-run as the
        # plain secondary button to its left. skip_to_phase3 (rather than
        # "redo") is named to match which button is actually the "yes".
        skip_to_phase3 = ask_yes_no(
            siril, "Phases 1-2 already completed",
            f"'{PREPROCESS_DIR_NAME}' already has final image(s) from a "
            "previous run of this dataset. Re-run stacking and "
            "registration (phases 1-2) again, or skip straight to phase 3?",
            yes_text="Skip to phase 3", no_text="Re-run",
        )
        if skip_to_phase3:
            siril.log("[checkpoint] Phases 1-2 already complete -- skipping straight to phase 3.")
            wizard_mark_done("checkpoint")

            # Filter selection was skipped on this path (straight to phase
            # 3), so the filter list comes from whichever subfolders
            # "2 - Pre-process" already has, one per filter processed last
            # time -- EXCLUDING "1 - Output" and "Starmask" themselves,
            # since those are subfolders this wizard creates for its own
            # bookkeeping (phase 3's final-image folder, and phase 4's
            # composite-building folder respectively), never an actual
            # filter's own subfolder. Left in, either one would get
            # treated as a bogus extra "filter" -- showing up in the
            # sidebar as its own "Pre-process: ..." step, and (since
            # neither has an "<initials> - Final.*" of its own) tricking
            # ask_skip_phase3_entirely below into thinking phase 3 still
            # has work left even when every REAL filter is already
            # finished. Determined BEFORE phase 3's own setup/tool check
            # (not after, like before) so ask_skip_phase3_entirely can
            # bypass that setup entirely too when there's nothing left to
            # configure a pipeline for.
            phase3_filters = sorted(
                d.name for d in preprocess_dir.iterdir()
                if d.is_dir() and d.name not in (PHASE3_OUTPUT_SUBDIR_NAME, STARMASK_SUBDIR_NAME)
            ) if preprocess_dir.is_dir() else []
            if not phase3_filters:
                siril.log(f"[phase 3] '{PREPROCESS_DIR_NAME}' has no filter subfolders -- nothing to run.")
                return
            image_processing_dir = main_folder / IMAGE_PROCESSING_DIR_NAME

            if ask_skip_phase3_entirely(siril, preprocess_dir, phase3_filters):
                siril.log(
                    "[phase 3] Every filter already has a final image -- "
                    "skipping phase 3 (and its setup) entirely by user choice."
                )
                phase3_ok = True
            else:
                if not run_phase3_setup_and_tool_check(siril, cfg):
                    return
                phase3_ok = run_phase3_pipeline(
                    siril, cfg, preprocess_dir, phase3_filters, image_processing_dir,
                )

            if phase3_ok:
                # Only reachable if phase 3 actually finished (not aborted
                # partway through). run_phase4_starmask_pipeline() returns
                # True only if phase 4 also reached a clean end -- skipped
                # right from its very first screen, or its pipeline ran
                # all the way through -- and False for every other way it
                # can end early (tool check aborted, pipeline aborted
                # partway through a step, no supported starmask recipe,
                # composite build failed). Only in the True case does it
                # make sense to offer deleting "1 - Registration"/
                # "2 - Pre-process" -- an aborted phase 4 still needs
                # those folders just as much as an aborted phase 3 would.
                phase4_ok = run_phase4_starmask_pipeline(
                    siril, cfg, preprocess_dir, image_processing_dir, phase3_filters,
                )
                if phase4_ok:
                    ask_delete_intermediate_folders(
                        siril, main_folder / REGISTRATION_DIR_NAME, preprocess_dir,
                        image_processing_dir,
                    )
                    _RUN_STATE["completed"] = True
            return
        siril.log("[checkpoint] Re-running phases 1-2 by user choice.")
    wizard_mark_done("checkpoint")

    wizard_set_current("filters")
    selected_filters = choose_filters(siril, main_folder)
    if not selected_filters:
        siril.log("No filters selected -- aborting.")
        return
    wizard_mark_done("filters")

    # Now that the filter list is known, fill in the rest of the checklist.
    for filter_name in selected_filters:
        wizard_add_step(f"stack:{filter_name}", f"Stack: {filter_name}")
    wizard_add_step("convert_register", "Convert & register")
    wizard_add_step("crop", "Crop")
    wizard_add_step("copy_preprocess", "Copy to Pre-process")
    # "phase3_setup"/"phase3_tools" are registered inside
    # run_phase3_setup_and_tool_check() itself, right before phase 3 -- not
    # here -- so they show up in the sidebar in the right spot (see the
    # comment on the "tools" step above for why this matters).

    # If every selected filter already has its "<filter> raw.fit"/".fits"
    # from an earlier run, there's no actual stacking left to do -- so
    # there's nothing for a calibration-frame recipe or a stacking script
    # to apply to. Skip choosing/checking either one entirely; the
    # per-filter loop below will just fast-forward every filter through
    # its "already stacked" checkpoint (see find_existing_raw_stack /
    # process_filter) straight into phase 2.
    all_already_stacked = all(
        find_existing_raw_stack(main_folder / filter_name, filter_name) is not None
        for filter_name in selected_filters
    )

    if all_already_stacked:
        siril.log(
            "Every selected filter is already stacked from an earlier run "
            "-- skipping the calibration-frame picker and stacking-script "
            "check entirely, since there's no stacking left to do."
        )
        wizard_set_current("calibration")
        wizard_mark_done("calibration")
        wizard_set_current("tools")
        wizard_mark_done("tools")
        filter_ssf_path: dict[str, Path | None] = {name: None for name in selected_filters}
    else:
        wizard_set_current("calibration")
        filter_variant = choose_calibration_scripts(siril, main_folder, selected_filters)
        for filter_name, variant_key in filter_variant.items():
            siril.log(
                f"[{filter_name}] Calibration script chosen: "
                f"{MONO_SSF_VARIANTS[variant_key][0]} ({MONO_SSF_VARIANTS[variant_key][1]})"
            )
        wizard_mark_done("calibration")

        needed_ssf_names = sorted({MONO_SSF_VARIANTS[k][0] for k in filter_variant.values()})

        wizard_set_current("tools")
        tools = locate_tools(siril, cfg, kinds=("ssf",), ssf_names=needed_ssf_names)
        if not show_tool_check_notice(
            siril, cfg, tools, kinds=("ssf",), title="Required tools for Stacking",
            ssf_names=needed_ssf_names,
        ):
            siril.log("Aborted at tool check.")
            wizard_mark_done("tools")
            return
        wizard_mark_done("tools")

        # Re-resolve rather than trusting the pre-notice "tools" dict --
        # "Re-check"/"Locate manually" inside the notice may have just
        # found (or been pointed to) a script that showed as missing when
        # "tools" was first computed above; without this, a successfully
        # fixed script would still show as missing here and wrongly abort
        # the run right below (mirrors the same re-resolve already done
        # for phase 3/4's own tool checks, see run_phase3_setup_and_tool_check).
        tools = locate_tools(siril, cfg, kinds=("ssf",), ssf_names=needed_ssf_names)

        filter_ssf_path = {}
        missing_scripts: list[str] = []
        for filter_name, variant_key in filter_variant.items():
            script_name = MONO_SSF_VARIANTS[variant_key][0]
            path = tools["ssf"].get(script_name)
            if path is None:
                missing_scripts.append(script_name)
            else:
                filter_ssf_path[filter_name] = path

        if missing_scripts:
            show_message(
                siril, "Missing script",
                "These recommended scripts still aren't found, so the run "
                "can't continue:\n\n" + "\n".join(sorted(set(missing_scripts))) +
                "\n\nInstall them via Siril's script repository manager, then "
                "run this wizard again.",
                kind="error",
            )
            return

    registration_dir = main_folder / REGISTRATION_DIR_NAME
    raw_dir = registration_dir / RAW_SUBDIR_NAME
    process_dir = registration_dir / PROCESS_SUBDIR_NAME
    output_dir = registration_dir / OUTPUT_SUBDIR_NAME
    # preprocess_dir was already computed above, for the top-level checkpoint.
    image_processing_dir = main_folder / IMAGE_PROCESSING_DIR_NAME
    for d in (registration_dir, raw_dir, process_dir, output_dir, preprocess_dir, image_processing_dir):
        d.mkdir(parents=True, exist_ok=True)
    siril.log(
        f"Created working folders: '{REGISTRATION_DIR_NAME}' (with "
        f"'{RAW_SUBDIR_NAME}'/'{PROCESS_SUBDIR_NAME}'/'{OUTPUT_SUBDIR_NAME}'), "
        f"'{PREPROCESS_DIR_NAME}', '{IMAGE_PROCESSING_DIR_NAME}'."
    )

    # all_already_stacked was already computed above (before the
    # calibration-frame/tool-check skip) -- reused here since nothing
    # about stacking status changes in between. If every selected filter
    # already has its "<filter> raw.fit"/".fits" from an earlier run,
    # there's no actual stacking left to do this time -- process_filter
    # would just skip every one of them straight through anyway. Asking
    # whether to review each stack would be a pointless question in that
    # case (nothing will ever pause for review), so skip it entirely and
    # go straight into the loop below, which fast-forwards through phase 1
    # into phase 2.
    if all_already_stacked:
        # Value is inconsequential here (not truly "unused" -- it's still
        # passed to process_filter() below) since every filter will hit
        # process_filter's own "already stacked" skip before it ever
        # checks this flag.
        review_each_stack = True
        siril.log(
            "Every selected filter is already stacked from an earlier run "
            "-- skipping the stack-review question and going straight "
            "through to phase 2."
        )
    else:
        review_each_stack = ask_yes_no(
            siril, "Review stacks?",
            "Would you like to check each filter's stack before moving on to "
            "the next one, or let the script stack all selected filters "
            "automatically and go straight through to phase 2?",
            yes_text="Check each stack", no_text="Run automatically",
        )
        siril.log(
            "Reviewing each stack before continuing." if review_each_stack
            else "Stacking all filters automatically -- no per-stack review."
        )

    for filter_name in selected_filters:
        wizard_set_current(f"stack:{filter_name}")
        keep_going = process_filter(
            siril, main_folder, filter_name, filter_ssf_path[filter_name],
            raw_dir, review_each_stack,
        )
        if not keep_going:
            siril.log("Run aborted by user.")
            return
        wizard_mark_done(f"stack:{filter_name}")

    siril.log("Phase 1 complete: all selected filters stacked and reviewed.")

    proceed = checkpoint_dialog(
        siril,
        "All selected filters have been stacked, renamed, and copied into "
        f"'{REGISTRATION_DIR_NAME}'.\n\n"
        "Continue into phase 2 -- converting, registering, and cropping "
        "them into a common frame?"
    )
    if not proceed:
        siril.log("Stopping after phase 1 (user choice).")
        return

    if not run_registration_and_crop_phase(siril, cfg, registration_dir, preprocess_dir):
        siril.log("Phase 2 did not complete.")
        return

    siril.log("Phase 2 complete.")

    if ask_skip_phase3_entirely(siril, preprocess_dir, selected_filters):
        siril.log(
            "[phase 3] Every filter already has a final image -- skipping "
            "phase 3 (and its setup) entirely by user choice."
        )
        phase3_ok = True
    else:
        if not run_phase3_setup_and_tool_check(siril, cfg):
            return
        phase3_ok = run_phase3_pipeline(siril, cfg, preprocess_dir, selected_filters, image_processing_dir)

    if phase3_ok:
        # See the matching comment on the other call site (the "skip
        # straight to phase 3" path above) for why the cleanup prompt is
        # nested inside "if phase4_ok" too, not just "if phase3_ok" --
        # an aborted phase 4 still needs "1 - Registration"/
        # "2 - Pre-process" just as much as an aborted phase 3 would.
        phase4_ok = run_phase4_starmask_pipeline(
            siril, cfg, preprocess_dir, image_processing_dir, selected_filters,
        )
        if phase4_ok:
            ask_delete_intermediate_folders(siril, registration_dir, preprocess_dir, image_processing_dir)
            _RUN_STATE["completed"] = True


def show_fatal_error(siril: "s.SirilInterface", exc: BaseException) -> None:
    """Shown when _run_wizard raises anything not already handled somewhere
    more specific (a genuine bug, an unexpected Siril command failure that
    wasn't warned about beforehand, etc.). Without this, an unhandled
    exception just gets dumped as a scary traceback into Siril's log and
    the Python process silently exits -- this explains what happened in
    the wizard's own window instead, and keeps the full traceback visible
    (in case it needs to be reported/debugged) without it being the only
    thing shown."""

    tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    siril.log("Unhandled error -- the wizard stopped. Full traceback:\n" + tb_text)

    try:
        root = _new_root(siril, "Something went wrong")
        _header(root, "Something went wrong")

        card = _card(root)
        _wrapping_label(
            card,
            "The wizard hit an unexpected error and had to stop here. "
            "Nothing past this point ran, and phase 1's per-filter "
            "checkpoints mean any filters already stacked won't be redone "
            "-- so it's safe to fix the issue below (or just try again) "
            "and re-run the wizard.\n\n"
            f"Error: {exc}",
        )

        text = tk.Text(
            card, height=10, wrap="word",
            background=BG_CARD_ALT, foreground=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY, relief="flat", padx=8, pady=8,
            font=(FONT_FAMILY, 9),
        )
        text.insert("1.0", tb_text)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, pady=(14, 0))

        btns = _button_row(root)
        ttk.Button(
            btns, text="Close", style="Accent.TButton", command=root.destroy,
        ).pack(side="right")

        root.mainloop()
    except Exception:
        # If even the error window itself can't be shown, the traceback is
        # still in Siril's log above -- nothing more we can do here.
        pass


def main() -> None:
    siril = s.SirilInterface()
    try:
        siril.connect()
    except Exception as e:
        print(f"Could not connect to Siril: {e}")
        sys.exit(1)

    try:
        _run_wizard(siril)
    except WizardClosed:
        siril.log("Wizard window closed by user -- aborting run.")
    except Exception as e:
        show_fatal_error(siril, e)
    finally:
        # Whatever happened -- success, an abort, or an unhandled error --
        # make sure the wizard window actually closes rather than lingering
        # on screen after the script itself has finished.
        wizard_close()

        # If this run ended anywhere short of its own real completion (an
        # abort mid-phase, the wizard window closed, an unhandled error),
        # Siril's working directory could be sitting deep inside
        # "2 - Pre-process/<Filter>" or phase 4's "Starmask" subfolder --
        # wherever the step in progress last "cd"'d to. Put it back to the
        # main dataset folder itself (see where _RUN_STATE["main_folder"]
        # is set, inside _run_wizard) so a LATER run's "Yes, already set"
        # doesn't mistake that leftover subfolder for the main dataset
        # folder and go looking for filter subfolders inside IT instead.
        # A no-op if main_folder was never even determined yet (e.g. the
        # very first screen was aborted) or the run actually did complete.
        if not _RUN_STATE["completed"] and _RUN_STATE["main_folder"] is not None:
            try:
                siril.cmd("cd", siril_quote(_RUN_STATE["main_folder"]))
                siril.log(
                    "[cleanup] Run ended early -- reset Siril's working "
                    f"directory back to the main dataset folder "
                    f"('{_RUN_STATE['main_folder']}')."
                )
            except Exception as e:
                siril.log(
                    "[cleanup] Couldn't reset Siril's working directory "
                    f"back to the main dataset folder ({e})."
                )


if __name__ == "__main__":
    main()
