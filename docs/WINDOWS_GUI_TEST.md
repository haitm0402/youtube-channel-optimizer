# Windows GUI manual test

Use Windows 10/11, Python 3.11+ with **Tcl/Tk and IDLE** enabled in the Python
installer. Tkinter/ttk ships with this installation; no GUI pip package is needed.
Record Windows/Python versions, display scaling (100%, 125%, 150%), results and
any error messages. Automated controller checks and Linux Tk smoke tests do not
replace this Windows checklist.

From PowerShell in the repository:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe app.py --gui
```

Use a temporary local TOML with custom `data_dir` and `exports_dir` if you want
isolated test projects: `python app.py --gui --config config/local.toml`.
Relative paths are resolved relative to that TOML file. Keep `prompts_dir`
pointing to the existing prompts directory.

- [ ] Launch: MY CHANNELS and NEW CHANNEL are visible; no traceback.
- [ ] Create: enter `Música — Dự án Việt`, a valid channel URL, multiline
  competitor description and optional artist/market/language. CANCEL saves
  nothing; CREATE PROJECT saves a session and opens analysis.
- [ ] Validation: blank name/invalid URL shows a readable error and preserves form.
- [ ] COPY PROMPT: paste into Notepad/ChatGPT; verify full Unicode prompt and
  brief `Copied` feedback. Prompt is read-only, selectable and scrollable.
- [ ] JSON paste: Ctrl+V, Ctrl+A and multiline scrolling work without END_JSON.
  Paste invalid JSON, then a schema-invalid object: text stays unchanged,
  error is readable, workflow does not advance.
- [ ] REGENERATE DISPLAY: prompt stays exactly the same and pasted JSON remains.
- [ ] Valid analysis: paste UTF-8 contents of `examples/analysis_response.json`.
  Successful validation automatically displays the names prompt.
- [ ] Close/reopen while waiting for a response: open the saved project and
  verify its exact pending prompt. Unsubmitted textbox contents are not saved.
- [ ] Names: paste `examples/names_response.json`. All 12 names, category,
  score, reason and best recommendation are visible; no name is auto-selected.
  Continue with no selection shows a friendly error. Select `Mây Âm Nhạc`.
- [ ] Resume: close/reopen at NAMES_READY and WAITING_FOR_PACKAGE; existing
  names and package prompt are retained. No completed AI work is regenerated.
- [ ] Package: paste `examples/package_v1_response.json`; inspect all ten
  text sections and their COPY buttons. Resize to 900×660 and larger;
  lists/text remain scrollable and workflow controls accessible.
- [ ] Export: path is shown; nine UTF-8 files are present. Repeat export:
  a different folder is created and the first export is unchanged.
- [ ] OPEN EXPORT FOLDER: Windows Explorer opens the displayed folder.
- [ ] COMPLETE resume: close/reopen; completed package appears immediately.
- [ ] Filters: Active lists unfinished projects; Completed lists completed
  nonarchived projects; Archived lists only archived projects.
- [ ] Archive: cancelling confirmation changes nothing. Confirming preserves
  session data; Archived opens a read-only view, with no import/name-selection
  controls. A completed archived package can still be copied/exported.
- [ ] Unicode: Vietnamese, Spanish and Italian text survive copy/paste,
  restart, session files, export files and Unicode directory paths.
- [ ] Responsiveness: refresh, resume, validation and export show Working…
  while local I/O runs; window remains repaintable. Closing during I/O leaves
  a valid atomic session or a recoverable prior state.
- [ ] Conflict: if the CLI/another window updates this session, stale GUI
  submissions show a reload error; RELOAD PROJECT retrieves saved state.
- [ ] CLI regression: `python app.py --manual` and `python app.py --sessions`
  still work. END_JSON remains a CLI convention only.

Cloud validation is performed on Linux. Actual Windows Explorer behavior, DPI
scaling, fonts and Windows clipboard integration require the checks above.
