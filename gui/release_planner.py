"""Desktop Release Planner views and forms."""
from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk

from models.release_planner import ReleaseStatus
from core.release_planner import WEEKDAY_NAMES


class ReleasePlannerView(ttk.Frame):
    def __init__(self, master, window):
        super().__init__(master, padding=20)
        self.window = window
        self.channel_map = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        heading = ttk.Frame(self)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(heading, text="RELEASE PLANNER", style="Title.TLabel").pack(side="left")
        ttk.Button(heading, text="+ NEW RELEASE", style="Accent.TButton", command=self.new_release).pack(side="right")
        ttk.Button(heading, text="+ CHANNEL", command=self.new_channel).pack(side="right", padx=8)

        self.summary_text = tk.StringVar(value="Loading release plan…")
        ttk.Label(self, textvariable=self.summary_text, style="Section.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 12))

        tabs = ttk.Notebook(self)
        tabs.grid(row=2, column=0, sticky="nsew")
        self.schedule_tab = ttk.Frame(tabs, padding=12)
        self.channels_tab = ttk.Frame(tabs, padding=12)
        tabs.add(self.schedule_tab, text="Schedule")
        tabs.add(self.channels_tab, text="Channels")
        self._build_schedule()
        self._build_channels()
        self.refresh_all()

    def _build_schedule(self):
        tab = self.schedule_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        filters = ttk.Frame(tab)
        filters.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(filters, text="Range").pack(side="left")
        self.range_var = tk.StringVar(value="Next 7 Days")
        ttk.Combobox(filters, textvariable=self.range_var, state="readonly",
                     values=("Today", "Next 7 Days", "Next 30 Days", "All"), width=14).pack(side="left", padx=(6, 16))
        ttk.Label(filters, text="Channel").pack(side="left")
        self.channel_filter = ttk.Combobox(filters, state="readonly", width=22)
        self.channel_filter.pack(side="left", padx=(6, 16))
        ttk.Label(filters, text="Status").pack(side="left")
        self.status_filter = ttk.Combobox(filters, state="readonly", width=14,
                                          values=("All",) + tuple(x.value for x in ReleaseStatus))
        self.status_filter.set("All")
        self.status_filter.pack(side="left", padx=(6, 16))
        ttk.Button(filters, text="APPLY", command=self.refresh_schedule).pack(side="left")
        ttk.Button(filters, text="EXPORT CSV", command=self.export_csv).pack(side="right")

        table = ttk.Frame(tab)
        table.grid(row=1, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = ("date", "time", "vn", "channel", "song", "readiness", "status", "market")
        self.release_tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        labels = ("Date", "Time", "VN Time", "Channel", "Song", "Readiness", "Status", "Market")
        widths = (95, 70, 145, 150, 230, 210, 110, 110)
        for field, label, width in zip(columns, labels, widths):
            self.release_tree.heading(field, text=label)
            self.release_tree.column(field, width=width, minwidth=65)
        self.release_tree.grid(row=0, column=0, sticky="nsew")
        y = ttk.Scrollbar(table, orient="vertical", command=self.release_tree.yview)
        x = ttk.Scrollbar(table, orient="horizontal", command=self.release_tree.xview)
        self.release_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        self.release_tree.bind("<Double-1>", lambda event: self.edit_release())

        actions = ttk.Frame(tab)
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="EDIT RELEASE", command=self.edit_release).pack(side="left")
        ttk.Button(actions, text="MARK PUBLISHED", command=self.mark_published).pack(side="left", padx=8)
        ttk.Button(actions, text="ARCHIVE", command=self.archive_release).pack(side="left")
        ttk.Button(actions, text="REFRESH", command=self.refresh_all).pack(side="right")

    def _build_channels(self):
        tab = self.channels_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        columns = ("name", "market", "timezone", "time", "days")
        self.channel_tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="browse")
        labels = ("Channel", "Market", "Timezone", "Default Time", "Release Days")
        widths = (220, 140, 180, 100, 260)
        for field, label, width in zip(columns, labels, widths):
            self.channel_tree.heading(field, text=label)
            self.channel_tree.column(field, width=width, minwidth=70)
        self.channel_tree.grid(row=0, column=0, sticky="nsew")
        self.channel_tree.bind("<Double-1>", lambda event: self.edit_channel())
        actions = ttk.Frame(tab)
        actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="EDIT CHANNEL", command=self.edit_channel).pack(side="left")
        ttk.Button(actions, text="ARCHIVE CHANNEL", command=self.archive_channel).pack(side="left", padx=8)

    def refresh_all(self):
        self.window.run_task(self.window.controller.release_planner_snapshot, self.populate_all)

    def populate_all(self, snapshot):
        self.channel_map = {item.channel_id: item for item in snapshot["channels"]}
        self.channel_filter.configure(values=("All",) + tuple(item.name for item in snapshot["channels"]))
        if not self.channel_filter.get():
            self.channel_filter.set("All")
        self._populate_channels(snapshot["channels"])
        self._populate_releases(snapshot["releases"])
        summary = snapshot["summary"]
        self.summary_text.set(
            f"TODAY: {summary.today}    NEXT 7 DAYS: {summary.next_7_days}    "
            f"MISSING ASSETS: {summary.missing_assets}    READY: {summary.ready}    SCHEDULED: {summary.scheduled}"
        )

    def refresh_schedule(self):
        channel_id = None
        chosen = self.channel_filter.get()
        for identity, item in self.channel_map.items():
            if item.name == chosen:
                channel_id = identity
                break
        status = None if self.status_filter.get() in ("", "All") else self.status_filter.get()
        range_name = self.range_var.get()
        self.window.run_task(
            lambda: self.window.controller.list_release_rows(range_name=range_name, channel_id=channel_id, status=status),
            self._populate_releases,
        )

    def _populate_releases(self, rows):
        for child in self.release_tree.get_children():
            self.release_tree.delete(child)
        for item in rows:
            self.release_tree.insert("", "end", iid=item.release_id, values=(
                item.publish_date, item.publish_time, item.vietnam_time, item.channel_name,
                item.song_title, item.readiness, item.status, item.target_market or "",
            ))

    def _populate_channels(self, channels):
        for child in self.channel_tree.get_children():
            self.channel_tree.delete(child)
        for item in channels:
            days = ", ".join(WEEKDAY_NAMES[day] for day in item.release_days)
            self.channel_tree.insert("", "end", iid=item.channel_id, values=(
                item.name, item.target_market or "", item.timezone, item.default_time, days,
            ))

    def selected_release(self):
        selection = self.release_tree.selection()
        if not selection:
            self.window.show_error("Please select a release.")
            return None
        return selection[0]

    def selected_channel(self):
        selection = self.channel_tree.selection()
        if not selection:
            self.window.show_error("Please select a planner channel.")
            return None
        return selection[0]

    def new_channel(self):
        ChannelDialog(self.window, self, None)

    def edit_channel(self):
        identity = self.selected_channel()
        if identity:
            self.window.run_task(lambda: self.window.controller.get_release_channel(identity),
                                 lambda channel: ChannelDialog(self.window, self, channel))

    def archive_channel(self):
        identity = self.selected_channel()
        if identity and messagebox.askyesno(
            "Archive planner channel",
            "Archive this channel schedule? Existing releases stay in the planner.",
            parent=self.window,
        ):
            self.window.run_task(lambda: self.window.controller.archive_release_channel(identity),
                                 lambda result: self.refresh_all())

    def new_release(self):
        if not self.channel_map:
            self.window.show_error("Create at least one planner channel first.")
            return
        ReleaseDialog(self.window, self, None, list(self.channel_map.values()))

    def edit_release(self):
        identity = self.selected_release()
        if identity:
            self.window.run_task(
                lambda: (self.window.controller.get_release(identity), self.window.controller.list_release_channels()),
                lambda result: ReleaseDialog(self.window, self, result[0], result[1]),
            )

    def mark_published(self):
        identity = self.selected_release()
        if identity and messagebox.askyesno("Mark published", "Mark this release as PUBLISHED?", parent=self.window):
            self.window.run_task(lambda: self.window.controller.mark_release_published(identity),
                                 lambda result: self.refresh_all())

    def archive_release(self):
        identity = self.selected_release()
        if identity and messagebox.askyesno("Archive release", "Archive this release from the active schedule?", parent=self.window):
            self.window.run_task(lambda: self.window.controller.archive_release(identity),
                                 lambda result: self.refresh_all())

    def export_csv(self):
        self.window.run_task(
            self.window.controller.export_release_plan_csv,
            lambda path: messagebox.showinfo("Release Planner", f"CSV exported:\n{path}", parent=self.window),
        )


class ChannelDialog(tk.Toplevel):
    def __init__(self, window, planner_view, channel):
        super().__init__(window)
        self.window, self.planner_view, self.channel = window, planner_view, channel
        self.title("Channel Schedule")
        self.transient(window)
        self.grab_set()
        self.resizable(True, False)
        body = ttk.Frame(self, padding=18)
        body.pack(fill="both", expand=True)
        self.entries = {}
        for row, field, label in (
            (0, "name", "Channel Name"), (1, "target_market", "Target Market"),
            (2, "timezone", "Timezone (IANA)"), (3, "default_time", "Default Upload Time"),
        ):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            entry = ttk.Entry(body, width=38)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            self.entries[field] = entry
        self.entries["timezone"].insert(0, channel.timezone if channel else "Asia/Ho_Chi_Minh")
        self.entries["default_time"].insert(0, channel.default_time if channel else "20:00")
        if channel:
            self.entries["name"].insert(0, channel.name)
            if channel.target_market:
                self.entries["target_market"].insert(0, channel.target_market)

        ttk.Label(body, text="Release Days").grid(row=4, column=0, sticky="nw", pady=6)
        days = ttk.Frame(body)
        days.grid(row=4, column=1, sticky="w")
        selected = set(channel.release_days if channel else range(7))
        self.day_vars = []
        for index, label in enumerate(WEEKDAY_NAMES):
            var = tk.BooleanVar(value=index in selected)
            self.day_vars.append(var)
            ttk.Checkbutton(days, text=label, variable=var).grid(row=index // 4, column=index % 4, sticky="w", padx=(0, 8))

        ttk.Label(body, text="Notes").grid(row=5, column=0, sticky="nw", pady=6)
        self.notes = tk.Text(body, height=4, width=38)
        self.notes.grid(row=5, column=1, sticky="ew", pady=6)
        if channel and channel.notes:
            self.notes.insert("1.0", channel.notes)

        actions = ttk.Frame(body)
        actions.grid(row=6, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(actions, text="CANCEL", command=self.destroy).pack(side="left", padx=8)
        ttk.Button(actions, text="SAVE", style="Accent.TButton", command=self.save).pack(side="left")
        body.columnconfigure(1, weight=1)

    def save(self):
        values = {name: entry.get().strip() for name, entry in self.entries.items()}
        values["target_market"] = values["target_market"] or None
        values["release_days"] = [i for i, var in enumerate(self.day_vars) if var.get()]
        values["notes"] = self.notes.get("1.0", "end-1c").strip() or None
        if self.channel is None:
            operation = lambda: self.window.controller.add_release_channel(**values)
        else:
            identity = self.channel.channel_id
            operation = lambda: self.window.controller.update_release_channel(identity, **values)
        def done(result):
            self.destroy()
            self.planner_view.refresh_all()
        self.window.run_task(operation, done)


class ReleaseDialog(tk.Toplevel):
    def __init__(self, window, planner_view, release, channels):
        super().__init__(window)
        self.window, self.planner_view, self.release = window, planner_view, release
        self.channels = channels
        self.channel_by_name = {item.name: item for item in channels}
        self.title("Release")
        self.transient(window)
        self.grab_set()
        body = ttk.Frame(self, padding=18)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="Channel").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        self.channel_var = tk.StringVar()
        self.channel_combo = ttk.Combobox(body, textvariable=self.channel_var, state="readonly",
                                          values=tuple(item.name for item in channels), width=36)
        self.channel_combo.grid(row=0, column=1, sticky="ew", pady=6)
        if release:
            selected = next((item.name for item in channels if item.channel_id == release.channel_id), "")
            self.channel_var.set(selected)
        elif channels:
            self.channel_var.set(channels[0].name)

        self.entries = {}
        for row, field, label in (
            (1, "song_title", "Song Title"), (2, "video_title", "Video Title (optional)"),
            (3, "publish_date", "Publish Date YYYY-MM-DD"), (4, "publish_time", "Publish Time HH:MM"),
            (5, "timezone", "Timezone (IANA)"), (6, "youtube_url", "YouTube URL (optional)"),
        ):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            entry = ttk.Entry(body)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            self.entries[field] = entry
        if release:
            for field in self.entries:
                value = getattr(release, field)
                if value:
                    self.entries[field].insert(0, value)
        else:
            self.entries["publish_date"].insert(0, date.today().isoformat())
            channel = channels[0]
            self.entries["publish_time"].insert(0, channel.default_time)
            self.entries["timezone"].insert(0, channel.timezone)

        ttk.Button(body, text="USE NEXT AVAILABLE SLOT", command=self.next_slot).grid(row=7, column=1, sticky="w", pady=(2, 8))

        ttk.Label(body, text="Status").grid(row=8, column=0, sticky="w", padx=(0, 12), pady=6)
        self.status_var = tk.StringVar(value=release.status.value if release else ReleaseStatus.PLANNED.value)
        ttk.Combobox(body, textvariable=self.status_var, state="readonly",
                     values=tuple(x.value for x in ReleaseStatus)).grid(row=8, column=1, sticky="ew", pady=6)

        readiness = ttk.LabelFrame(body, text="Assets Ready", padding=8)
        readiness.grid(row=9, column=0, columnspan=2, sticky="ew", pady=8)
        self.ready_vars = {}
        for column, field, label in (
            (0, "audio_ready", "Audio"), (1, "thumbnail_ready", "Thumbnail"),
            (2, "video_ready", "Video"), (3, "seo_ready", "SEO"),
        ):
            var = tk.BooleanVar(value=getattr(release, field) if release else False)
            self.ready_vars[field] = var
            ttk.Checkbutton(readiness, text=label, variable=var).grid(row=0, column=column, padx=(0, 12))

        ttk.Label(body, text="Notes").grid(row=10, column=0, sticky="nw", padx=(0, 12), pady=6)
        self.notes = tk.Text(body, height=4)
        self.notes.grid(row=10, column=1, sticky="ew", pady=6)
        if release and release.notes:
            self.notes.insert("1.0", release.notes)

        actions = ttk.Frame(body)
        actions.grid(row=11, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(actions, text="CANCEL", command=self.destroy).pack(side="left", padx=8)
        ttk.Button(actions, text="SAVE RELEASE", style="Accent.TButton", command=self.save).pack(side="left")

    def next_slot(self):
        channel = self.channel_by_name.get(self.channel_var.get())
        if not channel:
            self.window.show_error("Select a channel first.")
            return
        start = self.entries["publish_date"].get().strip() or None
        def fill(slot):
            publish_date, publish_time, timezone = slot
            for field, value in (("publish_date", publish_date), ("publish_time", publish_time), ("timezone", timezone)):
                self.entries[field].delete(0, "end")
                self.entries[field].insert(0, value)
        self.window.run_task(lambda: self.window.controller.suggest_next_release_slot(channel.channel_id, start_date=start), fill)

    def save(self):
        channel = self.channel_by_name.get(self.channel_var.get())
        if not channel:
            self.window.show_error("Select a channel.")
            return
        values = {name: entry.get().strip() for name, entry in self.entries.items()}
        for field in ("video_title", "youtube_url"):
            values[field] = values[field] or None
        values.update({name: var.get() for name, var in self.ready_vars.items()})
        values["status"] = self.status_var.get()
        values["notes"] = self.notes.get("1.0", "end-1c").strip() or None
        values["channel_id"] = channel.channel_id
        if self.release is None:
            operation = lambda: self.window.controller.add_release(**values)
        else:
            identity = self.release.release_id
            operation = lambda: self.window.controller.update_release(identity, **values)
        def done(result):
            self.destroy()
            self.planner_view.refresh_all()
        self.window.run_task(operation, done)
