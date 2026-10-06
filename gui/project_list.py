"""Saved project table; actions are delegated to the controller."""
import tkinter as tk
from tkinter import messagebox, ttk
from .controller import ProjectFilter


class ProjectList(ttk.Frame):
    def __init__(self, master, window):
        super().__init__(master, padding=20)
        self.window = window
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        heading = ttk.Frame(self)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        ttk.Label(heading, text="MY CHANNELS", style="Title.TLabel").pack(side="left")
        ttk.Button(heading, text="+ NEW CHANNEL", style="Accent.TButton", command=window.show_new).pack(side="right")
        bar = ttk.Frame(self)
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.filter = tk.StringVar(value=window.library_filter)
        for value in ProjectFilter:
            ttk.Radiobutton(bar, text=value.value, value=value.value, variable=self.filter,
                            command=self.refresh).pack(side="left", padx=(0, 18))
        ttk.Button(bar, text="REFRESH", command=self.refresh).pack(side="right")
        table = ttk.Frame(self)
        table.grid(row=2, column=0, sticky="nsew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        columns = ("project", "channel", "url", "market", "status", "updated")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        for name, label, width in zip(columns, ("Project", "Channel Name", "Competitor URL", "Market", "Status", "Updated (UTC)"),
                                      (190, 185, 270, 100, 190, 180)):
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, minwidth=80)
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Double-1>", lambda event: self.open_selected())
        self.tree.bind("<Return>", lambda event: self.open_selected())
        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(actions, text="OPEN PROJECT", command=self.open_selected).pack(side="left")
        self.archive_button = ttk.Button(actions, text="ARCHIVE PROJECT", command=self.archive)
        self.archive_button.pack(side="left", padx=10)
        self.empty = ttk.Label(actions, text="")
        self.empty.pack(side="right")
        self.refresh()

    def refresh(self):
        self.window.library_filter = self.filter.get()
        self.archive_button.configure(state="disabled" if self.filter.get() == "Archived" else "normal")
        filter_name = self.filter.get()
        self.window.run_task(lambda: self.window.controller.list_projects(filter_name), self.populate)

    def populate(self, projects):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in projects:
            self.tree.insert("", "end", iid=item.session_id, values=(
                item.display_name, item.selected_channel_name or "NO CHANNEL NAME YET", item.competitor_url,
                item.target_market or "Not specified", item.status, item.updated_at))
        self.empty.configure(text=f"{len(projects)} project(s)" if projects else "No projects in this view. Create a channel to begin.")

    def open_selected(self):
        selection = self.tree.selection()
        if not selection:
            self.window.show_error("Please select a project to open.")
            return
        self.window.open_project(selection[0])

    def archive(self):
        selection = self.tree.selection()
        if not selection:
            self.window.show_error("Please select a project to archive.")
            return
        if messagebox.askyesno("Archive project", "Archive this project? Its data will be kept and available in Archived.", parent=self.window):
            identity = selection[0]
            self.window.run_task(lambda: self.window.controller.archive_project(identity, confirmed=True), lambda result: self.refresh())
