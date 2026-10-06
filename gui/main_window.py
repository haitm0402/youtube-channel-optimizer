"""ttk desktop shell with serialized local I/O off the Tk event thread."""
from concurrent.futures import ThreadPoolExecutor
import logging
import tkinter as tk
from tkinter import ttk
from .dialogs import error_message
from .project_editor import ProjectEditor
from .project_form import ProjectForm
from .project_list import ProjectList

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class MainWindow(tk.Tk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.title("YouTube Channel Optimizer")
        self.geometry("1200x820")
        self.minsize(900, 660)
        self.configure(background="#f4f6fb")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.busy = False
        self.closed = False
        self.library_filter = "Active"
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="channel-local-io")
        self.poll_id = None
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.configure_style()
        header = tk.Frame(self, background="#111827", padx=22, pady=16)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(header, text="YouTube Channel Optimizer", background="#111827", foreground="white",
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Button(header, text="MY CHANNELS", command=self.show_library).pack(side="right")
        self.body = ttk.Frame(self)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        self.error = tk.StringVar()
        ttk.Label(self, textvariable=self.error, foreground="#b42318", wraplength=1100, padding=(20, 10)).grid(row=2, column=0, sticky="ew")
        self.overlay = ttk.Frame(self.body, padding=35, takefocus=True)
        ttk.Label(self.overlay, text="Working…", style="Section.TLabel").pack(pady=(0, 14))
        self.spinner = ttk.Progressbar(self.overlay, mode="indeterminate", length=260)
        self.spinner.pack()
        self.overlay.bind("<Key>", lambda event: "break")
        self.view = None
        self.show_library()

    def configure_style(self):
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background="#f4f6fb", foreground="#182230")
        style.configure("TButton", padding=(12, 8))
        style.configure("Accent.TButton", background="#4f46e5", foreground="white")
        style.map("Accent.TButton", background=[("active", "#4338ca"), ("disabled", "#a5a7cf")])
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Current.TLabel", font=("Segoe UI", 11, "bold"), foreground="#4f46e5")
        style.configure("Muted.TLabel", foreground="#667085")
        style.configure("Treeview", rowheight=31, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Treeview", background=[("selected", "#4f46e5")], foreground=[("selected", "white")])

    def show_error(self, message):
        self.error.set(message)

    def replace_view(self, view_class, *args):
        if self.view is not None:
            self.view.destroy()
        self.error.set("")
        self.view = view_class(self.body, self, *args)
        self.view.grid(row=0, column=0, sticky="nsew")

    def show_library(self):
        if not self.busy:
            self.replace_view(ProjectList)

    def show_new(self):
        if not self.busy:
            self.replace_view(ProjectForm)

    def show_editor(self, session):
        self.replace_view(ProjectEditor, session)

    def open_project(self, identity):
        self.run_task(lambda: self.controller.open_project(identity), self.show_editor)

    def run_task(self, operation, on_success):
        if self.busy or self.closed:
            return
        self.busy = True
        self.error.set("")
        self.overlay.place(relx=0.5, rely=0.5, anchor="center", relwidth=1, relheight=1)
        self.overlay.lift()
        self.overlay.focus_set()
        self.spinner.start(12)
        future = self.executor.submit(operation)
        def poll():
            self.poll_id = None
            if self.closed:
                return
            if not future.done():
                self.poll_id = self.after(40, poll)
                return
            self.spinner.stop()
            self.overlay.place_forget()
            self.busy = False
            try:
                result = future.result()
                on_success(result)
            except Exception as exc:
                logger.debug("Desktop action failed", exc_info=True)
                self.show_error(error_message(exc))
        self.poll_id = self.after(40, poll)

    def close(self):
        self.closed = True
        if self.poll_id is not None:
            self.after_cancel(self.poll_id)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()
