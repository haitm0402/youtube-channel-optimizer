"""Desktop composition root; Tk is imported only for an explicit GUI launch."""
from config import Settings
from .controller import GUIController


def launch_gui(settings: Settings) -> None:
    try:
        from .main_window import MainWindow
        import tkinter as tk
    except ImportError as exc:
        raise RuntimeError("Tkinter is not installed. On Windows, install Python with Tcl/Tk support.") from exc
    try:
        window = MainWindow(GUIController(settings))
    except tk.TclError as exc:
        raise RuntimeError("Cannot open the desktop display. Launch --gui in a Windows desktop session (or a Linux desktop with Tk).") from exc
    window.mainloop()
