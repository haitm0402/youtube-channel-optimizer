"""New project form; existing input models perform all domain validation."""
from tkinter import ttk
from .widgets import TextArea


class ProjectForm(ttk.Frame):
    def __init__(self, master, window):
        super().__init__(master, padding=24)
        self.window = window
        self.columnconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)
        ttk.Label(self, text="NEW CHANNEL", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))
        self.entries = {}
        for row, field, label in ((1, "project_name", "Project Name"), (2, "competitor_url", "Competitor YouTube URL"),
                                  (4, "target_artist", "Target Artist (optional)"), (5, "target_market", "Target Market (optional)"),
                                  (6, "target_language", "Target Language (optional)")):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=8)
            entry = ttk.Entry(self, font=("Segoe UI", 11))
            entry.grid(row=row, column=1, sticky="ew", pady=8)
            self.entries[field] = entry
        ttk.Label(self, text="Competitor Description").grid(row=3, column=0, sticky="nw", pady=8)
        self.description = TextArea(self, height=10)
        self.description.grid(row=3, column=1, sticky="nsew", pady=8)
        actions = ttk.Frame(self)
        actions.grid(row=7, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(actions, text="CANCEL", command=window.show_library).pack(side="left", padx=8)
        ttk.Button(actions, text="CREATE PROJECT", style="Accent.TButton", command=self.create).pack(side="left")
        self.entries["project_name"].focus_set()

    def create(self):
        values = {name: entry.get().strip() for name, entry in self.entries.items()}
        values["competitor_description"] = self.description.get()
        for name in ("target_artist", "target_market", "target_language"):
            values[name] = values[name] or None
        self.window.run_task(lambda: self.window.controller.create_project(**values), self.window.show_editor)
