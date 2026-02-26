"""
Code Context Builder — A tkinter GUI tool for merging code files
into a single text block for pasting into LLM chats.
"""

import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ==============================================================
# Config
# ==============================================================

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "project_folders": {},  # name -> path
    "divider_mode": "code_block",  # "line" or "code_block"
    "line_divider": "=" * 60,
    "show_filenames": True,
    "last_folder": "",
    "window_geometry": "1140x780",
}

EXTENSION_LANG_MAP = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx", ".jsx": "jsx",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".xml": "xml", ".svg": "svg",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".swift": "swift", ".m": "objectivec", ".mm": "objectivec",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp",
    ".cs": "csharp", ".fs": "fsharp",
    ".go": "go", ".rs": "rust",
    ".rb": "ruby", ".php": "php",
    ".sh": "bash", ".bash": "bash", ".zsh": "zsh", ".fish": "fish",
    ".sql": "sql",
    ".r": "r", ".R": "r",
    ".lua": "lua", ".pl": "perl", ".pm": "perl",
    ".dart": "dart", ".ex": "elixir", ".exs": "elixir",
    ".hs": "haskell", ".ml": "ocaml",
    ".vue": "vue", ".svelte": "svelte",
    ".md": "markdown", ".mdx": "mdx",
    ".graphql": "graphql", ".gql": "graphql",
    ".proto": "protobuf",
    ".tf": "hcl", ".dockerfile": "dockerfile",
    ".gradle": "gradle", ".groovy": "groovy",
    ".ini": "ini", ".cfg": "ini", ".conf": "ini",
    ".env": "bash",
    ".blade.php": "blade",
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            return {**DEFAULT_CONFIG, **saved}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save config: {e}")


def detect_language(filepath):
    name = os.path.basename(filepath).lower()
    # Check compound extensions first
    for ext, lang in EXTENSION_LANG_MAP.items():
        if name.endswith(ext):
            return lang
    # Check simple extension
    _, ext = os.path.splitext(filepath)
    return EXTENSION_LANG_MAP.get(ext.lower(), "")


def get_relative_name(filepath, base_folder=None):
    """Get display name — relative to base if possible."""
    if base_folder:
        try:
            return os.path.relpath(filepath, base_folder)
        except ValueError:
            pass
    return os.path.basename(filepath)


# ==============================================================
# Main Application
# ==============================================================

class CodeContextBuilder(tk.Tk):
    def __init__(self):
        super().__init__()

        self.app_config = load_config()
        self.title("Code Context Builder")
        self.geometry(self.app_config.get("window_geometry", "1140x780"))
        self.minsize(860, 560)

        # State
        self.file_paths = []  # list of absolute file paths
        self.active_project_folder = None  # currently active project folder path
        self._status_after_id = None

        # Modern palette
        self.colors = {
            "bg": "#0f1115",
            "surface": "#161a22",
            "surface2": "#1d2330",
            "surface3": "#242c3b",
            "accent": "#4f8cff",
            "accent_hover": "#6aa0ff",
            "accent_soft": "#233a66",
            "text": "#e6eaf2",
            "text_dim": "#9aa4b2",
            "border": "#2a3140",
            "border_soft": "#202633",
            "danger": "#ef5d6c",
            "danger_hover": "#ff7382",
            "success": "#33c48d",
            "warning": "#f5b84d",
        }

        self._setup_styles()
        self._build_ui()
        self._bind_shortcuts()
        self._attach_live_preview_triggers()
        self._load_project_folders()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------------------------------------------
    # Styling
    # ----------------------------------------------------------

    def _setup_styles(self):
        self.configure(bg=self.colors["bg"])

        style = ttk.Style(self)
        style.theme_use("clam")

        # Base
        style.configure(".", background=self.colors["bg"], foreground=self.colors["text"])
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("TPanedwindow", background=self.colors["bg"], sashrelief="flat")
        style.configure("TSeparator", background=self.colors["border_soft"])

        # Cards / surfaces
        style.configure("Card.TFrame", background=self.colors["surface"])
        style.configure("CardInner.TFrame", background=self.colors["surface2"])
        style.configure("HeaderCard.TFrame", background=self.colors["surface"])

        # Labels
        style.configure(
            "TLabel",
            background=self.colors["bg"],
            foreground=self.colors["text"],
            font=("Segoe UI", 10)
        )
        style.configure(
            "AppTitle.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            font=("Segoe UI Semibold", 12)
        )
        style.configure(
            "AppSubtitle.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["text_dim"],
            font=("Segoe UI", 9)
        )
        style.configure(
            "CardTitle.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            font=("Segoe UI Semibold", 10)
        )
        style.configure(
            "Title.TLabel",
            background=self.colors["bg"],
            foreground=self.colors["text"],
            font=("Segoe UI Semibold", 11)
        )
        style.configure(
            "Dim.TLabel",
            background=self.colors["bg"],
            foreground=self.colors["text_dim"],
            font=("Segoe UI", 9)
        )
        style.configure(
            "CardDim.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["text_dim"],
            font=("Segoe UI", 9)
        )

        # Buttons
        style.configure(
            "Primary.TButton",
            background=self.colors["accent"],
            foreground="white",
            borderwidth=0,
            focusthickness=0,
            focuscolor=self.colors["accent"],
            padding=(12, 8),
            font=("Segoe UI Semibold", 9)
        )
        style.map(
            "Primary.TButton",
            background=[("active", self.colors["accent_hover"]), ("pressed", self.colors["accent_hover"])],
            foreground=[("disabled", "#c7cfdb")]
        )

        style.configure(
            "Secondary.TButton",
            background=self.colors["surface2"],
            foreground=self.colors["text"],
            borderwidth=0,
            focusthickness=0,
            focuscolor=self.colors["surface2"],
            padding=(10, 7),
            font=("Segoe UI", 9)
        )
        style.map(
            "Secondary.TButton",
            background=[("active", self.colors["surface3"]), ("pressed", self.colors["surface3"])]
        )

        style.configure(
            "Danger.TButton",
            background=self.colors["danger"],
            foreground="white",
            borderwidth=0,
            focusthickness=0,
            focuscolor=self.colors["danger"],
            padding=(10, 7),
            font=("Segoe UI Semibold", 9)
        )
        style.map(
            "Danger.TButton",
            background=[("active", self.colors["danger_hover"]), ("pressed", self.colors["danger_hover"])]
        )

        # Check / radio
        style.configure(
            "TCheckbutton",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            font=("Segoe UI", 9)
        )
        style.map(
            "TCheckbutton",
            background=[("active", self.colors["surface"])],
            foreground=[("disabled", self.colors["text_dim"])]
        )

        style.configure(
            "TRadiobutton",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            font=("Segoe UI", 9)
        )
        style.map(
            "TRadiobutton",
            background=[("active", self.colors["surface"])],
            foreground=[("disabled", self.colors["text_dim"])]
        )

        # Scrollbars (subtle)
        style.configure(
            "Vertical.TScrollbar",
            background=self.colors["surface2"],
            troughcolor=self.colors["surface"],
            bordercolor=self.colors["surface"],
            arrowcolor=self.colors["text_dim"],
            darkcolor=self.colors["surface2"],
            lightcolor=self.colors["surface2"],
            gripcount=0
        )
        style.configure(
            "Horizontal.TScrollbar",
            background=self.colors["surface2"],
            troughcolor=self.colors["surface"],
            bordercolor=self.colors["surface"],
            arrowcolor=self.colors["text_dim"],
            darkcolor=self.colors["surface2"],
            lightcolor=self.colors["surface2"],
            gripcount=0
        )

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def _make_card(self, parent, fill=tk.X, expand=False, padx=0, pady=(0, 10), inner_pad=10):
        outer = ttk.Frame(parent, style="Card.TFrame")
        outer.pack(fill=fill, expand=expand, padx=padx, pady=pady)
        inner = ttk.Frame(outer, style="Card.TFrame")
        inner.pack(fill=tk.BOTH, expand=True, padx=inner_pad, pady=inner_pad)
        return outer, inner

    def _bind_shortcuts(self):
        self.bind_all("<Control-r>", lambda e: self._regenerate_preview())
        self.bind_all("<Control-R>", lambda e: self._regenerate_preview())
        self.bind_all("<Control-s>", lambda e: self._download_txt())
        self.bind_all("<Control-S>", lambda e: self._download_txt())
        self.bind_all("<Control-Shift-C>", lambda e: self._copy_to_clipboard())
        self.bind_all("<Control-Shift-c>", lambda e: self._copy_to_clipboard())

    def _attach_live_preview_triggers(self):
        self.show_filenames_var.trace_add("write", lambda *_: self._regenerate_preview())
        self.divider_mode_var.trace_add("write", lambda *_: self._regenerate_preview())
        self.divider_entry.bind("<FocusOut>", lambda e: self._regenerate_preview())
        self.divider_entry.bind("<Return>", lambda e: self._regenerate_preview())

    def _status_color_for_kind(self, kind):
        if kind == "success":
            return self.colors["success"]
        if kind == "error":
            return self.colors["danger"]
        if kind == "warning":
            return self.colors["warning"]
        return self.colors["text_dim"]

    # ----------------------------------------------------------
    # UI Build
    # ----------------------------------------------------------

    def _build_ui(self):
        # Top app header
        header_outer = ttk.Frame(self, style="HeaderCard.TFrame")
        header_outer.pack(fill=tk.X, padx=12, pady=(12, 8))
        header = ttk.Frame(header_outer, style="HeaderCard.TFrame")
        header.pack(fill=tk.X, padx=12, pady=10)

        left_head = ttk.Frame(header, style="HeaderCard.TFrame")
        left_head.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(left_head, text="Code Context Builder", style="AppTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(
            left_head,
            text="Merge selected code files into one clean LLM-ready context block",
            style="AppSubtitle.TLabel"
        ).pack(anchor=tk.W, pady=(2, 0))

        shortcut_text = "Shortcuts: Ctrl+R regenerate • Ctrl+S save • Ctrl+Shift+C copy"
        ttk.Label(header, text=shortcut_text, style="AppSubtitle.TLabel").pack(side=tk.RIGHT)

        # Main horizontal pane
        self.main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL, style="TPanedwindow")
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        # LEFT PANEL
        left = ttk.Frame(self.main_pane, style="TFrame", width=340)
        self.main_pane.add(left, weight=1)

        self._build_project_folders_section(left)
        self._build_file_list_section(left)
        self._build_settings_section(left)

        # RIGHT PANEL
        right = ttk.Frame(self.main_pane, style="TFrame")
        self.main_pane.add(right, weight=3)

        self._build_preview_section(right)

    # --- Project Folders ---
    def _build_project_folders_section(self, parent):
        _, section = self._make_card(parent, fill=tk.X, expand=False, padx=4, pady=(0, 10), inner_pad=10)

        header = ttk.Frame(section, style="Card.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(header, text="📁 Project Folders", style="CardTitle.TLabel").pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header, style="Card.TFrame")
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="+ Add", style="Secondary.TButton", command=self._add_project_folder).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Remove", style="Secondary.TButton", command=self._remove_project_folder).pack(side=tk.LEFT)

        ttk.Separator(section, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(8, 8))

        # Listbox wrapper
        list_shell = tk.Frame(section, bg=self.colors["border_soft"], bd=0, highlightthickness=0)
        list_shell.pack(fill=tk.X)

        self.folder_listbox = tk.Listbox(
            list_shell,
            height=5,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            selectbackground=self.colors["accent_soft"],
            selectforeground=self.colors["text"],
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
            font=("Segoe UI", 10),
            activestyle="none",
            exportselection=False,
        )
        self.folder_listbox.pack(fill=tk.X, padx=1, pady=1)
        self.folder_listbox.bind("<<ListboxSelect>>", self._on_folder_click)
        self.folder_listbox.bind("<Double-1>", self._on_folder_double_click)

    # --- File List ---
    def _build_file_list_section(self, parent):
        _, section = self._make_card(parent, fill=tk.BOTH, expand=True, padx=4, pady=(0, 10), inner_pad=10)

        header = ttk.Frame(section, style="Card.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(header, text="📄 Selected Files", style="CardTitle.TLabel").pack(side=tk.LEFT)
        self.file_count_label = ttk.Label(header, text="0 files", style="CardDim.TLabel")
        self.file_count_label.pack(side=tk.LEFT, padx=(8, 0))

        btn_frame = ttk.Frame(header, style="Card.TFrame")
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="+ Add Files", style="Secondary.TButton", command=self._add_files).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Remove", style="Secondary.TButton", command=self._remove_selected_files).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Clear All", style="Danger.TButton", command=self._clear_files).pack(side=tk.LEFT)

        ttk.Separator(section, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(8, 8))

        # File list area
        list_shell = tk.Frame(section, bg=self.colors["border_soft"], bd=0, highlightthickness=0)
        list_shell.pack(fill=tk.BOTH, expand=True)

        list_inner = tk.Frame(list_shell, bg=self.colors["surface"])
        list_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        scrollbar = ttk.Scrollbar(list_inner, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(
            list_inner,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            selectbackground=self.colors["accent_soft"],
            selectforeground=self.colors["text"],
            selectmode=tk.EXTENDED,
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
            font=("Cascadia Code", 9),
            activestyle="none",
            yscrollcommand=scrollbar.set,
            exportselection=False,
        )
        self.file_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        scrollbar.config(command=self.file_listbox.yview)

        # Move controls
        move_frame = ttk.Frame(section, style="Card.TFrame")
        move_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(move_frame, text="▲ Move Up", style="Secondary.TButton", command=self._move_file_up).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(move_frame, text="▼ Move Down", style="Secondary.TButton", command=self._move_file_down).pack(side=tk.LEFT)

    # --- Settings ---
    def _build_settings_section(self, parent):
        _, section = self._make_card(parent, fill=tk.X, expand=False, padx=4, pady=(0, 4), inner_pad=10)

        ttk.Label(section, text="⚙ Settings", style="CardTitle.TLabel").pack(anchor=tk.W)

        ttk.Separator(section, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(8, 8))

        settings_inner = ttk.Frame(section, style="Card.TFrame")
        settings_inner.pack(fill=tk.X)

        # Filename toggle
        self.show_filenames_var = tk.BooleanVar(value=self.app_config.get("show_filenames", True))
        ttk.Checkbutton(
            settings_inner,
            text="Show filename headers",
            variable=self.show_filenames_var
        ).pack(anchor=tk.W)

        # Divider mode
        ttk.Label(settings_inner, text="Divider mode", style="CardDim.TLabel").pack(anchor=tk.W, pady=(10, 4))

        self.divider_mode_var = tk.StringVar(value=self.app_config.get("divider_mode", "code_block"))

        mode_frame = ttk.Frame(settings_inner, style="Card.TFrame")
        mode_frame.pack(anchor=tk.W)
        ttk.Radiobutton(
            mode_frame, text="Code blocks", variable=self.divider_mode_var, value="code_block"
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(
            mode_frame, text="Line divider", variable=self.divider_mode_var, value="line"
        ).pack(side=tk.LEFT)

        # Line divider entry
        ttk.Label(settings_inner, text="Line divider string", style="CardDim.TLabel").pack(anchor=tk.W, pady=(10, 4))

        entry_shell = tk.Frame(settings_inner, bg=self.colors["border"], bd=0, highlightthickness=0)
        entry_shell.pack(fill=tk.X)

        self.divider_entry = tk.Entry(
            entry_shell,
            bg=self.colors["surface2"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Cascadia Code", 10),
        )
        self.divider_entry.pack(fill=tk.X, padx=1, pady=1, ipady=6)
        self.divider_entry.insert(0, self.app_config.get("line_divider", "=" * 60))

    # --- Preview ---
    def _build_preview_section(self, parent):
        _, section = self._make_card(parent, fill=tk.BOTH, expand=True, padx=4, pady=(0, 0), inner_pad=10)

        header = ttk.Frame(section, style="Card.TFrame")
        header.pack(fill=tk.X)

        title_wrap = ttk.Frame(header, style="Card.TFrame")
        title_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(title_wrap, text="📋 Preview", style="CardTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(title_wrap, text="Editable output (you can tweak before copying)", style="CardDim.TLabel").pack(anchor=tk.W, pady=(1, 0))

        btn_frame = ttk.Frame(header, style="Card.TFrame")
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(btn_frame, text="Regenerate", style="Secondary.TButton", command=self._regenerate_preview).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Copy", style="Primary.TButton", command=self._copy_to_clipboard).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Download .txt", style="Secondary.TButton", command=self._download_txt).pack(side=tk.LEFT)

        ttk.Separator(section, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(8, 8))

        # Status label
        self.status_label = tk.Label(
            section,
            text="",
            bg=self.colors["surface"],
            fg=self.colors["text_dim"],
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.status_label.pack(fill=tk.X, pady=(0, 8))

        # Text area shell
        text_shell = tk.Frame(section, bg=self.colors["border_soft"], bd=0, highlightthickness=0)
        text_shell.pack(fill=tk.BOTH, expand=True)

        text_frame = tk.Frame(text_shell, bg=self.colors["surface"])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        y_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        x_scroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.preview_text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            selectbackground=self.colors["accent_soft"],
            selectforeground=self.colors["text"],
            font=("Cascadia Code", 10),
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
            undo=True,
            padx=12,
            pady=12,
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        y_scroll.config(command=self.preview_text.yview)
        x_scroll.config(command=self.preview_text.xview)

    # ----------------------------------------------------------
    # Project Folder Management
    # ----------------------------------------------------------

    def _load_project_folders(self):
        self.folder_listbox.delete(0, tk.END)
        for name, path in self.app_config.get("project_folders", {}).items():
            self.folder_listbox.insert(tk.END, f"{name}  →  {path}")

    def _add_project_folder(self):
        folder = filedialog.askdirectory(title="Select Project Folder")
        if not folder:
            return

        # Ask for a name
        name_win = tk.Toplevel(self)
        name_win.title("Name this folder")
        name_win.geometry("390x160")
        name_win.resizable(False, False)
        name_win.configure(bg=self.colors["bg"])
        name_win.transient(self)
        name_win.grab_set()

        shell = tk.Frame(name_win, bg=self.colors["surface"], bd=0)
        shell.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            shell,
            text="Give this project folder a name",
            bg=self.colors["surface"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 10),
            anchor="w"
        ).pack(fill=tk.X, pady=(10, 6), padx=10)

        entry_shell = tk.Frame(shell, bg=self.colors["border"], bd=0)
        entry_shell.pack(fill=tk.X, padx=10)

        name_entry = tk.Entry(
            entry_shell,
            bg=self.colors["surface2"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 11),
        )
        name_entry.pack(fill=tk.X, padx=1, pady=1, ipady=7)
        name_entry.insert(0, os.path.basename(folder))
        name_entry.select_range(0, tk.END)
        name_entry.focus_set()

        footer = tk.Frame(shell, bg=self.colors["surface"])
        footer.pack(fill=tk.X, pady=(10, 10), padx=10)

        def save_name(event=None):
            name = name_entry.get().strip()
            if not name:
                return
            self.app_config.setdefault("project_folders", {})[name] = folder
            save_config(self.app_config)
            self._load_project_folders()
            self._show_status(f"Added project folder: {name}", kind="success")
            name_win.destroy()

        cancel_btn = tk.Button(
            footer, text="Cancel", command=name_win.destroy,
            bg=self.colors["surface2"], fg=self.colors["text"], relief="flat",
            activebackground=self.colors["surface3"], activeforeground=self.colors["text"],
            bd=0, padx=12, pady=6, highlightthickness=0
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(6, 0))

        save_btn = tk.Button(
            footer, text="Save", command=save_name,
            bg=self.colors["accent"], fg="white", relief="flat",
            activebackground=self.colors["accent_hover"], activeforeground="white",
            bd=0, padx=12, pady=6, highlightthickness=0
        )
        save_btn.pack(side=tk.RIGHT)

        name_entry.bind("<Return>", save_name)

    def _remove_project_folder(self):
        sel = self.folder_listbox.curselection()
        if not sel:
            self._show_status("Select a project folder first", kind="warning")
            return
        keys = list(self.app_config.get("project_folders", {}).keys())
        name = keys[sel[0]]
        del self.app_config["project_folders"][name]
        save_config(self.app_config)
        self._load_project_folders()
        self.active_project_folder = None
        self._show_status(f"Removed project folder: {name}", kind="success")

    def _on_folder_click(self, event):
        """Single click — just set as active project folder."""
        sel = self.folder_listbox.curselection()
        if not sel:
            return
        keys = list(self.app_config.get("project_folders", {}).keys())
        name = keys[sel[0]]
        self.active_project_folder = self.app_config["project_folders"][name]
        self._refresh_file_listbox()  # update relative display names if needed
        self._show_status(f"Active folder: {name}")

    def _on_folder_double_click(self, event):
        """Double click — edit the root folder path of this project."""
        sel = self.folder_listbox.curselection()
        if not sel:
            return
        keys = list(self.app_config.get("project_folders", {}).keys())
        name = keys[sel[0]]
        current_path = self.app_config["project_folders"][name]

        new_folder = filedialog.askdirectory(
            title=f"Change folder for '{name}'",
            initialdir=current_path,
        )
        if not new_folder:
            return

        self.app_config["project_folders"][name] = new_folder
        self.active_project_folder = new_folder
        save_config(self.app_config)
        self._load_project_folders()
        self._refresh_file_listbox()
        self._show_status(f"Updated '{name}' → {new_folder}", kind="success")

    # ----------------------------------------------------------
    # File Management
    # ----------------------------------------------------------

    def _add_files(self, initial_dir=None):
        if not initial_dir:
            initial_dir = self.active_project_folder or self.app_config.get("last_folder", "") or None

        filetypes = [
            ("All Files", "*.*"),
            ("Python", "*.py"),
            ("JavaScript/TypeScript", "*.js *.ts *.jsx *.tsx"),
            ("PHP", "*.php"),
            ("Java/Kotlin", "*.java *.kt"),
            ("C/C++", "*.c *.cpp *.h *.hpp"),
            ("Go", "*.go"),
            ("Rust", "*.rs"),
            ("HTML/CSS", "*.html *.css *.scss"),
            ("JSON/YAML", "*.json *.yaml *.yml"),
            ("Ruby", "*.rb"),
            ("Shell", "*.sh *.bash *.zsh"),
        ]

        files = filedialog.askopenfilenames(
            title="Select Code Files",
            initialdir=initial_dir,
            filetypes=filetypes,
        )

        if not files:
            return

        # Remember last folder
        self.app_config["last_folder"] = os.path.dirname(files[0])
        save_config(self.app_config)

        added_count = 0
        for f in files:
            if f not in self.file_paths:
                self.file_paths.append(f)
                added_count += 1

        self._refresh_file_listbox()
        self._regenerate_preview()

        if added_count == 0:
            self._show_status("All selected files were already added", kind="warning")
        else:
            self._show_status(f"Added {added_count} file(s)", kind="success")

    def _refresh_file_listbox(self):
        self.file_listbox.delete(0, tk.END)
        for fp in self.file_paths:
            display = get_relative_name(fp, self.active_project_folder)
            self.file_listbox.insert(tk.END, display)
        count = len(self.file_paths)
        self.file_count_label.config(text=f"{count} file" if count == 1 else f"{count} files")

    def _remove_selected_files(self):
        sel = list(self.file_listbox.curselection())
        if not sel:
            self._show_status("Select file(s) to remove", kind="warning")
            return
        removed = len(sel)
        for idx in reversed(sel):
            del self.file_paths[idx]
        self._refresh_file_listbox()
        self._regenerate_preview()
        self._show_status(f"Removed {removed} file(s)", kind="success")

    def _clear_files(self):
        if not self.file_paths:
            self._show_status("Nothing to clear", kind="warning")
            return
        count = len(self.file_paths)
        self.file_paths.clear()
        self._refresh_file_listbox()
        self._regenerate_preview()
        self._show_status(f"Cleared {count} file(s)", kind="success")

    def _move_file_up(self):
        sel = self.file_listbox.curselection()
        if not sel:
            self._show_status("Select a file to move", kind="warning")
            return
        idx = sel[0]
        if idx == 0:
            return
        self.file_paths[idx], self.file_paths[idx - 1] = self.file_paths[idx - 1], self.file_paths[idx]
        self._refresh_file_listbox()
        self.file_listbox.selection_set(idx - 1)
        self.file_listbox.see(idx - 1)
        self._regenerate_preview()

    def _move_file_down(self):
        sel = self.file_listbox.curselection()
        if not sel:
            self._show_status("Select a file to move", kind="warning")
            return
        idx = sel[0]
        if idx >= len(self.file_paths) - 1:
            return
        self.file_paths[idx], self.file_paths[idx + 1] = self.file_paths[idx + 1], self.file_paths[idx]
        self._refresh_file_listbox()
        self.file_listbox.selection_set(idx + 1)
        self.file_listbox.see(idx + 1)
        self._regenerate_preview()

    # ----------------------------------------------------------
    # Preview Generation
    # ----------------------------------------------------------

    def _generate_merged_text(self):
        if not self.file_paths:
            return ""

        mode = self.divider_mode_var.get()
        show_names = self.show_filenames_var.get()
        line_divider = self.divider_entry.get() or "=" * 60

        blocks = []
        for fp in self.file_paths:
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                content = f"[Error reading file: {e}]"

            display_name = get_relative_name(fp, self.active_project_folder)
            lang = detect_language(fp)

            if mode == "code_block":
                parts = []
                if show_names:
                    parts.append(f"📄 {display_name}")
                lang_tag = lang if lang else ""
                parts.append(f"```{lang_tag}")
                parts.append(content.rstrip())
                parts.append("```")
                blocks.append("\n".join(parts))
            else:  # line mode
                parts = []
                if show_names:
                    parts.append(f"📄 {display_name}")
                parts.append(content.rstrip())
                blocks.append("\n".join(parts))

        if mode == "code_block":
            return "\n\n".join(blocks)
        else:
            divider = f"\n\n{line_divider}\n\n"
            return divider.join(blocks)

    def _regenerate_preview(self):
        text = self._generate_merged_text()
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", text)
        self._show_status("Preview regenerated")

    # ----------------------------------------------------------
    # Actions
    # ----------------------------------------------------------

    def _copy_to_clipboard(self):
        text = self.preview_text.get("1.0", tk.END).rstrip()
        if not text:
            self._show_status("Nothing to copy", kind="warning")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._show_status("Copied to clipboard", kind="success")

    def _download_txt(self):
        text = self.preview_text.get("1.0", tk.END).rstrip()
        if not text:
            self._show_status("Nothing to download", kind="warning")
            return

        filepath = filedialog.asksaveasfilename(
            title="Save as .txt",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="code_context.txt",
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
            self._show_status(f"Saved to {os.path.basename(filepath)}", kind="success")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")
            self._show_status("Save failed", kind="error")

    def _show_status(self, msg, duration=2800, kind="info"):
        self.status_label.config(text=msg, fg=self._status_color_for_kind(kind))
        if self._status_after_id:
            try:
                self.after_cancel(self._status_after_id)
            except Exception:
                pass
        self._status_after_id = self.after(duration, lambda: self.status_label.config(text=""))

    # ----------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------

    def _on_close(self):
        self.app_config["divider_mode"] = self.divider_mode_var.get()
        self.app_config["show_filenames"] = self.show_filenames_var.get()
        self.app_config["line_divider"] = self.divider_entry.get()
        self.app_config["window_geometry"] = self.geometry()
        save_config(self.app_config)
        self.destroy()


# ==============================================================
# Entry Point
# ==============================================================

if __name__ == "__main__":
    # Fix blurry rendering on Windows (DPI awareness)
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass  # Not on Windows or older version

    app = CodeContextBuilder()
    app.mainloop()