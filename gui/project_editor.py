"""Workflow screens render existing sessions and delegate every transition."""
from pathlib import Path
from tkinter import ttk
from .controller import EditorScreen, package_sections, screen_for_state
from .platform import open_export_folder
from .widgets import CopyButton, TextArea


class ProjectEditor(ttk.Frame):
    def __init__(self, master, window, session):
        super().__init__(master, padding=20)
        self.window, self.session = window, session
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        heading = ttk.Frame(self)
        heading.grid(row=0, column=0, sticky="ew")
        ttk.Label(heading, text=session.display_name + (" — ARCHIVED / READ ONLY" if session.archived else ""), style="Title.TLabel", wraplength=850).pack(side="left")
        ttk.Button(heading, text="RELOAD PROJECT", command=lambda: window.open_project(session.session_id)).pack(side="right")
        screen = screen_for_state(session.state)
        stage = {EditorScreen.ANALYSIS: 2, EditorScreen.NAMES_PROMPT: 3, EditorScreen.NAME_SELECTION: 3,
                 EditorScreen.PACKAGE_PROMPT: 4, EditorScreen.PACKAGE: 5}[screen]
        progress = ttk.Frame(self)
        progress.grid(row=1, column=0, sticky="ew", pady=(12, 16))
        for index, name in enumerate(("Competitor", "Analysis", "Channel Name", "Package", "Export"), start=1):
            label = f"{index}  {name}"
            ttk.Label(progress, text=label, style="Current.TLabel" if index == stage else "Muted.TLabel").pack(side="left", padx=(0, 24))
        self.body = ttk.Frame(self)
        self.body.grid(row=2, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(1, weight=1)
        if session.archived:
            self.render_archive(screen)
        elif screen == EditorScreen.NAME_SELECTION:
            self.render_names()
        elif screen == EditorScreen.PACKAGE:
            self.render_package()
        else:
            self.render_prompt(screen)

    def render_prompt(self, screen):
        titles = {EditorScreen.ANALYSIS: "STEP 1 — COMPETITOR ANALYSIS", EditorScreen.NAMES_PROMPT: "CHANNEL NAME PROMPT",
                  EditorScreen.PACKAGE_PROMPT: "CHANNEL PACKAGE PROMPT"}
        bar = ttk.Frame(self.body)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(bar, text=titles[screen], style="Section.TLabel").pack(side="left")
        CopyButton(bar, self.window, lambda: self.prompt.get(), label="COPY PROMPT").pack(side="right")
        ttk.Button(bar, text="REGENERATE DISPLAY", command=self.refresh_prompt).pack(side="right", padx=8)
        panes = ttk.Panedwindow(self.body, orient="vertical")
        panes.grid(row=1, column=0, sticky="nsew")
        self.prompt = TextArea(panes, text=self.session.pending_prompt or "Use RELOAD PROJECT to prepare this step.", readonly=True, height=12)
        lower = ttk.Frame(panes)
        lower.columnconfigure(0, weight=1)
        lower.rowconfigure(1, weight=1)
        ttk.Label(lower, text="PASTE CHATGPT JSON RESULT", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(12, 6))
        self.response = TextArea(lower, height=10)
        self.response.grid(row=1, column=0, sticky="nsew")
        panes.add(self.prompt, weight=1)
        panes.add(lower, weight=1)
        ttk.Button(self.body, text="VALIDATE & CONTINUE", style="Accent.TButton", command=self.submit).grid(row=2, column=0, sticky="e", pady=(12, 0))

    def refresh_prompt(self):
        self.window.run_task(self.window.controller.pending_prompt,
                             lambda text: self.prompt.set(text, readonly=True))

    def submit(self):
        value = self.response.get()  # Capture on the Tk thread; no END_JSON delimiter.
        self.window.run_task(lambda: self.window.controller.submit_json(value), self.window.show_editor)
        # Error callbacks leave this entire screen and pasted text intact.

    def render_names(self):
        ttk.Label(self.body, text="SELECT ONE CHANNEL NAME — recommendation is highlighted, never auto-selected",
                  style="Section.TLabel", wraplength=950).grid(row=0, column=0, sticky="w", pady=(0, 12))
        frame = ttk.Frame(self.body)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = ("name", "category", "score", "recommendation", "reason")
        self.names_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", height=12)
        for field, title, width in zip(columns, ("Name", "Category", "Score", "Recommendation", "Short Reason"), (240, 120, 65, 155, 390)):
            self.names_tree.heading(field, text=title)
            self.names_tree.column(field, width=width, minwidth=60)
        self.names_tree.tag_configure("best", background="#eef0ff")
        self.candidates = {}
        for index, candidate in enumerate(self.session.names.names):
            identity = str(index)
            self.candidates[identity] = candidate
            best = candidate.name == self.session.names.best_recommendation
            self.names_tree.insert("", "end", iid=identity, values=(candidate.name, candidate.category.value, candidate.score,
                                   "BEST RECOMMENDATION" if best else "", candidate.short_reason), tags=("best",) if best else ())
        vertical = ttk.Scrollbar(frame, orient="vertical", command=self.names_tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=self.names_tree.xview)
        self.names_tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.names_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.reason = TextArea(self.body, text="Select a row to read the full reason.", readonly=True, height=3)
        self.reason.grid(row=2, column=0, sticky="ew", pady=10)
        self.names_tree.bind("<<TreeviewSelect>>", self.name_changed)
        ttk.Button(self.body, text="SELECT NAME & CONTINUE", style="Accent.TButton", command=self.select_name).grid(row=3, column=0, sticky="e")

    def name_changed(self, event=None):
        selection = self.names_tree.selection()
        if selection:
            candidate = self.candidates[selection[0]]
            self.reason.set(f"{candidate.name} — {candidate.category.value} — {candidate.score}/10\n{candidate.short_reason}", readonly=True)

    def select_name(self):
        selection = self.names_tree.selection()
        name = self.candidates[selection[0]].name if selection else None
        self.window.run_task(lambda: self.window.controller.select_name(name), self.window.show_editor)

    def render_package(self):
        header = ttk.Frame(self.body)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(header, text=self.session.selected_name, style="Section.TLabel").pack(side="left")
        ttk.Button(header, text="EXPORT CHANNEL PACKAGE", style="Accent.TButton", command=self.export).pack(side="right")
        content = ttk.Frame(self.body)
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        navigation = ttk.Frame(content)
        navigation.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        viewer = ttk.Frame(content)
        viewer.grid(row=0, column=1, sticky="nsew")
        viewer.columnconfigure(0, weight=1)
        viewer.rowconfigure(1, weight=1)
        self.section_label = ttk.Label(viewer, style="Section.TLabel")
        self.section_label.grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.section_text = TextArea(viewer, readonly=True, height=16)
        self.section_text.grid(row=1, column=0, sticky="nsew")
        sections = package_sections(self.session)
        for row, section in enumerate(sections):
            ttk.Button(navigation, text=section.label, command=lambda item=section: self.show_section(item)).grid(row=row, column=0, sticky="ew", pady=3)
            CopyButton(navigation, self.window, lambda item=section: item.text).grid(row=row, column=1, padx=(6, 0))
        self.show_section(sections[0])
        footer = ttk.Frame(self.body)
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        self.export_path = ttk.Label(footer, text="Export creates a new folder and keeps previous exports.", wraplength=750)
        self.export_path.grid(row=0, column=0, sticky="w")
        self.folder_button = ttk.Button(footer, text="OPEN EXPORT FOLDER", command=self.open_folder, state="disabled")
        self.folder_button.grid(row=0, column=1, padx=(12, 0))
        self.destination = None

    def show_section(self, section):
        self.section_label.configure(text=section.label)
        self.section_text.set(section.text, readonly=True)

    def export(self):
        self.window.run_task(self.window.controller.export_project, self.exported)

    def exported(self, path):
        self.destination = Path(path)
        self.export_path.configure(text=f"Export folder: {self.destination}")
        self.folder_button.configure(state="normal")

    def open_folder(self):
        if self.destination is not None:
            path = self.destination
            self.window.run_task(lambda: open_export_folder(path), lambda result: None)

    def render_archive(self, screen):
        if screen == EditorScreen.PACKAGE:
            self.render_package()  # Export is a read-only operation on session data.
            return
        ttk.Label(self.body, text="ARCHIVED PROJECT — READ ONLY", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        tabs = ttk.Notebook(self.body)
        tabs.grid(row=1, column=0, sticky="nsew")
        import json
        sections = [("Competitor", self.session.competitor.to_prompt_dict())]
        if self.session.analysis is not None:
            sections.append(("Analysis", self.session.analysis.to_ai_dict()))
        if self.session.names is not None:
            sections.append(("Names", self.session.names.to_ai_dict()))
        for title, data in sections:
            tabs.add(TextArea(tabs, text=json.dumps(data, ensure_ascii=False, indent=2), readonly=True), text=title)
        if self.session.pending_prompt is not None:
            tabs.add(TextArea(tabs, text=self.session.pending_prompt, readonly=True), text="Saved Prompt")
