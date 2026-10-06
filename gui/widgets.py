"""Reusable Tk widgets and copy/paste behavior, without domain logic."""
import tkinter as tk
from tkinter import ttk


class TextArea(ttk.Frame):
    def __init__(self, master, *, text="", readonly=False, height=10):
        super().__init__(master)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.text = tk.Text(self, wrap="word", height=height, undo=not readonly, font=("Segoe UI", 10),
                            relief="flat", padx=12, pady=10, highlightthickness=1,
                            highlightbackground="#d5dbea", highlightcolor="#4f46e5")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.set(text, readonly=readonly)
        self.text.bind("<Control-a>", self.select_all)
        self.text.bind("<Control-A>", self.select_all)
        # Tk's native Text bindings handle Ctrl+V, Unicode, and multiline paste.

    def select_all(self, event=None):
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "1.0")
        return "break"

    def get(self):
        return self.text.get("1.0", "end-1c")

    def set(self, value, *, readonly=False):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", value)
        self.text.configure(state="disabled" if readonly else "normal")


class CopyButton(ttk.Button):
    def __init__(self, master, window, get_text, *, label="COPY"):
        super().__init__(master, text=label, command=self.copy)
        self.label = label
        self.window, self.get_text = window, get_text
        self.timer = None

    def copy(self):
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.get_text())
            self.configure(text="Copied")
            if self.timer is not None:
                self.after_cancel(self.timer)
            self.timer = self.after(1600, self.reset)
        except tk.TclError:
            self.window.show_error("Clipboard is unavailable. Select the text and copy it manually.")

    def reset(self):
        if self.winfo_exists():
            self.configure(text=self.label)
        self.timer = None

    def destroy(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
        super().destroy()
