"""Layout manager: creates the container and draggable divider and
exposes a helper to register divider handlers.

This keeps divider and resizing logic out of `gui.py`.
"""
from typing import Any, Tuple
import customtkinter as ctk
import tkinter as tk


def create_container(app: Any) -> Tuple[Any, Any]:
    """Create the main container frame and a divider frame.

    Returns (container, divider).
    """
    bg_color = getattr(app, 'bg_color', '#242424')
    container = ctk.CTkFrame(app, fg_color=bg_color)
    container.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
    app.grid_rowconfigure(2, weight=1)
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)
    container.grid_columnconfigure(1, weight=0, minsize=8)
    container.grid_columnconfigure(2, weight=1)

    divider = tk.Frame(container, bg=bg_color, width=8, cursor="sb_h_double_arrow")
    divider.grid(row=0, column=1, sticky="ns", pady=6)

    return container, divider


def register_divider_handlers(container: Any, divider: Any, hand_frame: Any, app: Any, initial_left_ratio: float = 0.52):
    """Attach drag handlers and container resize behavior.

    This stores `_divider_drag` and `_left_ratio` on `app` for compatibility
    with existing code that may read those values.
    """
    app._divider_drag = {'dragging': False, 'start_x': 0, 'start_left': 0}
    app._left_ratio = float(initial_left_ratio)

    def _on_divider_press(event):
        app._divider_drag['dragging'] = True
        app._divider_drag['start_x'] = event.x_root
        try:
            app._divider_drag['start_left'] = hand_frame.winfo_width()
        except Exception:
            app._divider_drag['start_left'] = 0

    def _on_divider_release(event):
        app._divider_drag['dragging'] = False
        try:
            total_w = container.winfo_width() or (app.winfo_width() or 1200)
            from typing import Any, Tuple
            import customtkinter as ctk
            import tkinter as tk
        except Exception:
            pass


            """Layout manager: creates the container and draggable divider and
            exposes a helper to register divider handlers.

            This keeps divider and resizing logic out of `gui.py`.
            """


            def create_container(app: Any) -> Tuple[Any, Any]:
                """Create the main container frame and a divider frame.

                Returns (container, divider).
                """
                bg_color = getattr(app, 'bg_color', '#242424')
                container = ctk.CTkFrame(app, fg_color=bg_color)
                container.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
                app.grid_rowconfigure(2, weight=1)
                container.grid_rowconfigure(0, weight=1)
                container.grid_columnconfigure(0, weight=1)
                container.grid_columnconfigure(1, weight=0, minsize=8)
                container.grid_columnconfigure(2, weight=1)

                divider = tk.Frame(container, bg=bg_color, width=8, cursor="sb_h_double_arrow")
                divider.grid(row=0, column=1, sticky="ns", pady=6)

                return container, divider


            def register_divider_handlers(container: Any, divider: Any, hand_frame: Any, app: Any, initial_left_ratio: float = 0.52):
                """Attach drag handlers and container resize behavior.

                This stores `_divider_drag` and `_left_ratio` on `app` for compatibility
                with existing code that may read those values.
                """
                app._divider_drag = {'dragging': False, 'start_x': 0, 'start_left': 0}
                app._left_ratio = float(initial_left_ratio)

                def _on_divider_press(event):
                    app._divider_drag['dragging'] = True
                    app._divider_drag['start_x'] = event.x_root
                    try:
                        app._divider_drag['start_left'] = hand_frame.winfo_width()
                    except Exception:
                        app._divider_drag['start_left'] = 0

                def _on_divider_release(event):
                    app._divider_drag['dragging'] = False
                    try:
                        total_w = container.winfo_width() or (app.winfo_width() or 1200)
                        left_w = hand_frame.winfo_width()
                        app._left_ratio = max(0.1, min(0.9, left_w / total_w))
                    except Exception:
                        pass

                def _on_divider_motion(event):
                    if not app._divider_drag.get('dragging'):
                        return
                    try:
                        dx = event.x_root - app._divider_drag['start_x']
                        new_left = app._divider_drag['start_left'] + dx
                        total_w = container.winfo_width() or (app.winfo_width() or 1200)
                        min_left = 320
                        max_left = max(min_left, total_w - 320 - divider.winfo_width())
                        new_left = max(min_left, min(new_left, max_left))
                        container.grid_columnconfigure(0, minsize=int(new_left))
                    except Exception:
                        pass

                divider.bind("<ButtonPress-1>", _on_divider_press)
                divider.bind("<ButtonRelease-1>", _on_divider_release)
                divider.bind("<B1-Motion>", _on_divider_motion)

                # Initial left panel width and adapt on container resize
                try:
                    app.update_idletasks()
                    total_w = container.winfo_width() or app.winfo_width() or 1400
                    container.grid_columnconfigure(0, minsize=int(total_w * app._left_ratio))
                except Exception:
                    pass

                def _on_container_configure(event):
                    try:
                        total_w = container.winfo_width() or (app.winfo_width() or 1200)
                        new_left = int(total_w * app._left_ratio)
                        new_left = max(320, min(new_left, max(320, total_w - 320 - divider.winfo_width())))
                        container.grid_columnconfigure(0, minsize=new_left)
                    except Exception:
                        pass

                container.bind('<Configure>', _on_container_configure)
