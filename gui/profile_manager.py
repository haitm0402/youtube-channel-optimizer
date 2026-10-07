"""Channel Profile Manager screens; persistence and validation stay in the controller/core."""
import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .platform import open_export_folder
from .widgets import CopyButton, TextArea


class ProfileList(ttk.Frame):
    def __init__(self, master, window):
        super().__init__(master, padding=20)
        self.window = window
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        heading = ttk.Frame(self)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        ttk.Label(heading, text="CHANNEL PROFILES", style="Title.TLabel").pack(side="left")
        ttk.Button(heading, text="+ NEW PROFILE", style="Accent.TButton",
                   command=lambda: window.show_profile_editor(None)).pack(side="right")

        bar = ttk.Frame(self)
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.filter = tk.StringVar(value="Active")
        for label in ("Active", "Archived"):
            ttk.Radiobutton(bar, text=label, value=label, variable=self.filter,
                            command=self.refresh).pack(side="left", padx=(0, 18))
        ttk.Button(bar, text="REFRESH", command=self.refresh).pack(side="right")

        table = ttk.Frame(self)
        table.grid(row=2, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = ("channel", "artist", "market", "language", "genre", "upload", "updated")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        labels = ("Channel", "Artist Direction", "Market", "Language", "Genre", "Upload Time", "Updated (UTC)")
        widths = (190, 150, 110, 110, 130, 100, 190)
        for field, label, width in zip(columns, labels, widths):
            self.tree.heading(field, text=label)
            self.tree.column(field, width=width, minwidth=80)
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
        ttk.Button(actions, text="OPEN PROFILE", command=self.open_selected).pack(side="left")
        self.archive_button = ttk.Button(actions, text="ARCHIVE PROFILE", command=self.toggle_archive)
        self.archive_button.pack(side="left", padx=10)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")
        self.refresh()

    def refresh(self):
        archived = self.filter.get() == "Archived"
        self.archive_button.configure(text="RESTORE PROFILE" if archived else "ARCHIVE PROFILE")
        self.window.run_task(lambda: self.window.controller.list_channel_profiles(archived=archived), self.populate)

    def populate(self, profiles):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in profiles:
            self.tree.insert("", "end", iid=item.profile_id, values=(
                item.channel_name, item.target_artist or "Not set", item.target_market or "Not set",
                item.target_language or "Not set", item.genre or "Not set",
                item.upload_time or "Not set", item.updated_at,
            ))
        self.count.configure(text=f"{len(profiles)} profile(s)" if profiles else "No channel profiles yet.")

    def selected_id(self):
        selection = self.tree.selection()
        if not selection:
            self.window.show_error("Please select a channel profile.")
            return None
        return selection[0]

    def open_selected(self):
        identity = self.selected_id()
        if identity is not None:
            self.window.open_channel_profile(identity)

    def toggle_archive(self):
        identity = self.selected_id()
        if identity is None:
            return
        if self.filter.get() == "Archived":
            self.window.run_task(lambda: self.window.controller.restore_channel_profile(identity),
                                 lambda result: self.refresh())
            return
        if messagebox.askyesno(
            "Archive channel profile",
            "Archive this channel profile? Its data will be kept and can be restored later.",
            parent=self.window,
        ):
            self.window.run_task(lambda: self.window.controller.archive_channel_profile(identity),
                                 lambda result: self.refresh())


class ProfileEditor(ttk.Frame):
    LIST_FIELDS = {
        "competitor_urls", "seo_topics", "channel_keywords", "video_keywords",
        "default_tags", "default_hashtags", "title_templates",
    }

    def __init__(self, master, window, profile=None):
        super().__init__(master, padding=20)
        self.window, self.profile = window, profile
        self.readonly = bool(profile and profile.archived)
        self.controls = {}
        self.destination = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        heading = ttk.Frame(self)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        title = "NEW CHANNEL PROFILE" if profile is None else profile.channel_name
        if self.readonly:
            title += " — ARCHIVED / READ ONLY"
        ttk.Label(heading, text=title, style="Title.TLabel").pack(side="left")
        ttk.Button(heading, text="BACK TO PROFILES", command=window.show_profiles).pack(side="right")

        tabs = ttk.Notebook(self)
        tabs.grid(row=1, column=0, sticky="nsew")
        identity = ttk.Frame(tabs, padding=14)
        music = ttk.Frame(tabs, padding=14)
        branding = ttk.Frame(tabs, padding=14)
        seo = ttk.Frame(tabs, padding=14)
        notes = ttk.Frame(tabs, padding=14)
        tabs.add(identity, text="Identity")
        tabs.add(music, text="Music DNA")
        tabs.add(branding, text="Branding")
        tabs.add(seo, text="SEO")
        tabs.add(notes, text="Notes")

        for tab in (identity, music, branding, seo, notes):
            tab.columnconfigure(1, weight=1)

        self._entry(identity, 0, "channel_name", "Channel Name")
        self._entry(identity, 1, "target_artist", "Artist Direction")
        self._entry(identity, 2, "target_market", "Target Market")
        self._entry(identity, 3, "target_language", "Target Language")
        self._entry(identity, 4, "upload_time", "Default Upload Time")
        self._text(identity, 5, "competitor_urls", "Competitor URLs", height=5)

        self._entry(music, 0, "music_niche", "Music Niche")
        self._entry(music, 1, "genre", "Genre")
        self._entry(music, 2, "subgenre", "Subgenre")
        self._text(music, 3, "vocal_direction", "Vocal Direction", height=4)
        self._text(music, 4, "flow_direction", "Flow Direction", height=4)
        self._text(music, 5, "lyric_rules", "Lyric Rules", height=4)
        self._text(music, 6, "suno_style_rules", "Suno Style Rules", height=4)

        self._text(branding, 0, "channel_positioning", "Channel Positioning", height=4)
        self._text(branding, 1, "channel_description", "Channel Description", height=5)
        self._entry(branding, 2, "slogan", "Slogan")
        self._text(branding, 3, "visual_identity", "Visual Identity", height=4)
        self._text(branding, 4, "thumbnail_rules", "Thumbnail Rules", height=4)
        self._text(branding, 5, "banner_direction", "Banner Direction", height=4)

        self._text(seo, 0, "seo_topics", "SEO Topics — one per line", height=4)
        self._text(seo, 1, "channel_keywords", "Channel Keywords — one per line", height=4)
        self._text(seo, 2, "video_keywords", "Video Keywords — one per line", height=4)
        self._text(seo, 3, "default_tags", "Default Video Tags — one per line", height=4)
        self._text(seo, 4, "default_hashtags", "Default Hashtags — one per line", height=4)
        self._text(seo, 5, "title_templates", "Title Templates — one per line", height=4)

        self._text(notes, 0, "notes", "Internal Notes", height=18)

        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        if not self.readonly:
            ttk.Button(actions, text="SAVE PROFILE", style="Accent.TButton", command=self.save).pack(side="left")
        if profile is not None:
            CopyButton(actions, window, self.profile_json, label="COPY PROFILE JSON").pack(side="left", padx=8)
            ttk.Button(actions, text="EXPORT JSON", command=self.export).pack(side="left")
        self.status = ttk.Label(actions, text="Channel DNA is stored locally and can be reused by future workflows.")
        self.status.pack(side="right")

    def _value(self, field):
        if self.profile is None:
            return [] if field in self.LIST_FIELDS else None
        return getattr(self.profile, field)

    def _entry(self, tab, row, field, label):
        ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=6)
        entry = ttk.Entry(tab, font=("Segoe UI", 10))
        value = self._value(field)
        if value:
            entry.insert(0, value)
        if self.readonly:
            entry.configure(state="disabled")
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        self.controls[field] = entry

    def _text(self, tab, row, field, label, *, height):
        ttk.Label(tab, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 14), pady=6)
        value = self._value(field)
        if isinstance(value, list):
            value = "\n".join(value)
        area = TextArea(tab, text=value or "", readonly=self.readonly, height=height)
        area.grid(row=row, column=1, sticky="nsew", pady=6)
        self.controls[field] = area

    def values(self):
        values = {}
        for field, control in self.controls.items():
            text = control.get().strip()
            if field in self.LIST_FIELDS:
                values[field] = [line.strip() for line in text.splitlines() if line.strip()]
            elif field == "channel_name":
                values[field] = text
            else:
                values[field] = text or None
        return values

    def save(self):
        if self.readonly:
            self.window.show_error("Archived channel profiles are read-only.")
            return
        values = self.values()
        if self.profile is None:
            operation = lambda: self.window.controller.create_channel_profile(**values)
        else:
            identity = self.profile.profile_id
            operation = lambda: self.window.controller.update_channel_profile(identity, **values)
        self.window.run_task(operation, self.window.show_profile_editor)

    def profile_json(self):
        return json.dumps(self.profile.to_prompt_dict(), ensure_ascii=False, indent=2)

    def export(self):
        if self.profile is None:
            return
        identity = self.profile.profile_id
        self.window.run_task(lambda: self.window.controller.export_channel_profile(identity), self.exported)

    def exported(self, path):
        self.destination = Path(path)
        self.status.configure(text=f"Exported: {self.destination}")

    def open_export_folder(self):
        if self.destination is not None:
            open_export_folder(self.destination.parent)
