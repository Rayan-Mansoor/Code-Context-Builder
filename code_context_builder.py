"""
Code Context Builder — A tkinter GUI tool for merging code files
into a single text block for pasting into LLM chats.
"""

import json
import sys
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ==============================================================
# Config
# ==============================================================

def get_config_file_path():
    """
    Store config in APPDATA for both .py runs and packaged exe builds
    (PyInstaller / Nuitka / others) so behavior stays consistent.
    """
    appdata = os.getenv("APPDATA") or os.path.expanduser("~")
    app_dir = os.path.join(appdata, "CodeContextBuilder")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, "config.json")


CONFIG_FILE = get_config_file_path()

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

# Common folders to skip in tree browser
SKIP_FOLDERS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".idea", ".vscode", ".vs", "dist", "build", ".next", ".nuxt",
    ".svelte-kit", "vendor", ".tox", ".mypy_cache", ".pytest_cache",
    ".eggs", "*.egg-info", ".gradle", ".dart_tool", ".pub-cache",
    "Pods", ".expo", ".cache",
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
# Folder Tree File Picker Dialog
# ==============================================================

class FolderTreePicker(tk.Toplevel):
    """
    A custom file picker that shows a folder tree with highlight-based selection.
    Click a file to select it (highlighted in a distinct color), click again to deselect.
    Click a folder to expand/collapse. Double-click a folder to select/deselect all files inside it.
    """

    DUMMY_TEXT = "…"

    def __init__(self, parent, initial_dir=None, colors=None):
        super().__init__(parent)
        self.title("Select Files — Folder Tree")
        self.geometry("720x620")
        self.minsize(520, 400)
        self.transient(parent)
        self.grab_set()

        self.colors = colors or {
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
            "success": "#33c48d",
            "warning": "#f5b84d",
        }

        # Distinct highlight color for "selected" files (green-tinted)
        self.SELECTED_BG = "#1a3a2a"
        self.SELECTED_FG = "#6ee7a0"

        self.configure(bg=self.colors["bg"])
        self.selected_files = []  # result returned after dialog closes
        self.root_dir = initial_dir or os.path.expanduser("~")
        self._selected_order = []       # ordered list of selected absolute paths (insertion order)
        self._selected_lookup = set()   # fast lookup mirror of _selected_order
        self._file_paths = {}           # node_id -> absolute path (for files)
        self._folder_nodes = {}         # node_id -> absolute path (for folders)
        self._dummy_nodes = set()       # node IDs used as lazy-load placeholders
        self._loaded_folders = set()    # folder node IDs whose direct children were loaded
        self._pending_click_id = None   # for delayed folder single-click

        self._build_ui()

        # Defer initial population so window paints first (prevents "looks hung" feeling)
        self.after(10, lambda: self._populate_tree(self.root_dir))

        # Center on parent
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        # Top bar: folder path + Browse button
        top = tk.Frame(self, bg=self.colors["surface"])
        top.pack(fill=tk.X, padx=10, pady=(10, 6))

        tk.Label(
            top, text="Root Folder:", bg=self.colors["surface"],
            fg=self.colors["text_dim"], font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=(8, 4))

        self.path_var = tk.StringVar(value=self.root_dir)
        self.path_label = tk.Label(
            top, textvariable=self.path_var, bg=self.colors["surface"],
            fg=self.colors["text"], font=("Segoe UI", 9), anchor="w"
        )
        self.path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        browse_btn = tk.Button(
            top, text="Browse…", command=self._browse_folder,
            bg=self.colors["surface2"], fg=self.colors["text"],
            activebackground=self.colors["surface3"], activeforeground=self.colors["text"],
            relief="flat", bd=0, padx=10, pady=4, font=("Segoe UI", 9),
            highlightthickness=0, cursor="hand2"
        )
        browse_btn.pack(side=tk.RIGHT, padx=(0, 8))

        # Filter bar
        filter_bar = tk.Frame(self, bg=self.colors["bg"])
        filter_bar.pack(fill=tk.X, padx=10, pady=(0, 6))

        tk.Label(
            filter_bar, text="Filter:", bg=self.colors["bg"],
            fg=self.colors["text_dim"], font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=(0, 4))

        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())

        filter_shell = tk.Frame(filter_bar, bg=self.colors["border"], bd=0)
        filter_shell.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.filter_entry = tk.Entry(
            filter_shell, textvariable=self.filter_var,
            bg=self.colors["surface2"], fg=self.colors["text"],
            insertbackground=self.colors["text"], relief="flat",
            borderwidth=0, highlightthickness=0, font=("Segoe UI", 9),
        )
        self.filter_entry.pack(fill=tk.X, padx=1, pady=1, ipady=4)

        # Quick-select buttons
        qs_frame = tk.Frame(filter_bar, bg=self.colors["bg"])
        qs_frame.pack(side=tk.RIGHT)

        for text, cmd in [
            ("Select All Visible", self._select_all_visible),
            ("Deselect All", self._deselect_all),
        ]:
            tk.Button(
                qs_frame, text=text, command=cmd,
                bg=self.colors["surface2"], fg=self.colors["text"],
                activebackground=self.colors["surface3"], activeforeground=self.colors["text"],
                relief="flat", bd=0, padx=8, pady=3, font=("Segoe UI", 9),
                highlightthickness=0, cursor="hand2"
            ).pack(side=tk.LEFT, padx=(4, 0))

        # Tree area
        tree_shell = tk.Frame(self, bg=self.colors["border_soft"])
        tree_shell.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        tree_inner = tk.Frame(tree_shell, bg=self.colors["surface"])
        tree_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        y_scroll = ttk.Scrollbar(tree_inner, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll = ttk.Scrollbar(tree_inner, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Style the Treeview — disable the default selection highlight
        # so our tag-based highlight is the only visual indicator
        style = ttk.Style(self)
        style.configure(
            "Picker.Treeview",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            fieldbackground=self.colors["surface"],
            borderwidth=0,
            font=("Cascadia Code", 9),
            rowheight=26,
        )
        style.configure(
            "Picker.Treeview.Heading",
            background=self.colors["surface2"],
            foreground=self.colors["text"],
            font=("Segoe UI Semibold", 9),
            borderwidth=0,
        )
        # Make the built-in selection invisible — same as normal bg
        style.map(
            "Picker.Treeview",
            background=[("selected", self.colors["surface"])],
            foreground=[("selected", self.colors["text"])],
        )

        self.tree = ttk.Treeview(
            tree_inner,
            columns=("size",),
            show="tree headings",
            selectmode="none",
            style="Picker.Treeview",
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )
        self.tree.heading("#0", text="Name", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.column("#0", width=500, minwidth=200)
        self.tree.column("size", width=80, minwidth=60, stretch=False, anchor="e")

        # Configure tags for selected highlight
        self.tree.tag_configure(
            "selected",
            background=self.SELECTED_BG,
            foreground=self.SELECTED_FG,
        )
        self.tree.tag_configure(
            "folder",
            foreground=self.colors["text"],
        )
        self.tree.tag_configure(
            "dummy",
            foreground=self.colors["text_dim"],
        )

        self.tree.pack(fill=tk.BOTH, expand=True)
        y_scroll.config(command=self.tree.yview)
        x_scroll.config(command=self.tree.xview)

        # Bind click — single click for files and folder expand/collapse
        # Double-click on folders for bulk select
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # Selection count + bottom buttons
        bottom = tk.Frame(self, bg=self.colors["bg"])
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.count_label = tk.Label(
            bottom, text="0 files selected", bg=self.colors["bg"],
            fg=self.colors["text_dim"], font=("Segoe UI", 9)
        )
        self.count_label.pack(side=tk.LEFT)

        cancel_btn = tk.Button(
            bottom, text="Cancel", command=self._on_cancel,
            bg=self.colors["surface2"], fg=self.colors["text"],
            activebackground=self.colors["surface3"], activeforeground=self.colors["text"],
            relief="flat", bd=0, padx=14, pady=6, font=("Segoe UI", 9),
            highlightthickness=0, cursor="hand2"
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(6, 0))

        add_btn = tk.Button(
            bottom, text="Add Selected Files", command=self._on_confirm,
            bg=self.colors["accent"], fg="white",
            activebackground=self.colors["accent_hover"], activeforeground="white",
            relief="flat", bd=0, padx=14, pady=6, font=("Segoe UI Semibold", 9),
            highlightthickness=0, cursor="hand2"
        )
        add_btn.pack(side=tk.RIGHT)

    def _browse_folder(self):
        # Release modal grab while native folder dialog is open (important in packaged EXEs)
        try:
            self.grab_release()
        except Exception:
            pass

        try:
            folder = filedialog.askdirectory(
                parent=self,
                title="Select Root Folder",
                initialdir=self.root_dir,
            )
        finally:
            try:
                self.grab_set()
                self.lift()
                self.focus_force()
            except Exception:
                pass

        if folder:
            self.root_dir = folder
            self.path_var.set(folder)
            self._populate_tree(folder)

    def _populate_tree(self, root_dir):
        """Populate top level lazily (folders load children on expand)."""
        self.tree.delete(*self.tree.get_children())
        self._file_paths.clear()
        self._folder_nodes.clear()
        self._dummy_nodes.clear()
        self._loaded_folders.clear()

        if not os.path.isdir(root_dir):
            return

        old_cursor = self.cget("cursor")
        try:
            self.configure(cursor="watch")
            self.update_idletasks()
            self._insert_dir_contents_one_level("", root_dir)
            self._reapply_highlights()
        finally:
            try:
                self.configure(cursor=old_cursor)
            except Exception:
                pass

    def _should_skip_folder(self, name):
        if name.startswith("."):
            return True
        return name in SKIP_FOLDERS

    def _format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _sorted_entries(self, dir_path):
        try:
            entries = os.listdir(dir_path)
        except (PermissionError, FileNotFoundError, OSError):
            return []

        def sort_key(name):
            full = os.path.join(dir_path, name)
            is_dir = False
            try:
                is_dir = os.path.isdir(full)
            except OSError:
                pass
            return (not is_dir, name.lower())

        return sorted(entries, key=sort_key)

    def _add_dummy_child(self, folder_id):
        dummy_id = self.tree.insert(
            folder_id,
            "end",
            text=f"  {self.DUMMY_TEXT}",
            values=("",),
            tags=("dummy",),
        )
        self._dummy_nodes.add(dummy_id)

    def _clear_dummy_children(self, folder_id):
        for child in list(self.tree.get_children(folder_id)):
            if child in self._dummy_nodes:
                self.tree.delete(child)
                self._dummy_nodes.discard(child)

    def _insert_dir_contents_one_level(self, parent_node, dir_path):
        """
        Insert only direct children (lazy loading for folders).
        This avoids freezing when opening huge roots in packaged EXE.
        """
        entries = self._sorted_entries(dir_path)

        for entry_name in entries:
            full_path = os.path.join(dir_path, entry_name)

            try:
                if os.path.islink(full_path):
                    # Avoid symlink/junction loops and very deep unexpected recursion
                    continue
            except OSError:
                continue

            is_dir = False
            try:
                is_dir = os.path.isdir(full_path)
            except OSError:
                continue

            if is_dir:
                if self._should_skip_folder(entry_name):
                    continue
                folder_id = self.tree.insert(
                    parent_node, "end",
                    text=f"📁 {entry_name}",
                    values=("",),
                    tags=("folder",),
                    open=False,
                )
                self._folder_nodes[folder_id] = full_path
                # Add placeholder so expand arrow is shown; real children load on expand.
                self._add_dummy_child(folder_id)
            else:
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                file_id = self.tree.insert(
                    parent_node, "end",
                    text=f"  {entry_name}",
                    values=(self._format_size(size),),
                )
                self._file_paths[file_id] = full_path

    def _ensure_folder_loaded(self, folder_id):
        """Load one folder's direct children if not loaded yet."""
        if folder_id not in self._folder_nodes:
            return
        if folder_id in self._loaded_folders:
            return

        folder_path = self._folder_nodes[folder_id]
        self._clear_dummy_children(folder_id)
        self._insert_dir_contents_one_level(folder_id, folder_path)
        self._loaded_folders.add(folder_id)

        # Re-apply selected highlight for any newly added files
        self._reapply_highlights()

    def _reapply_highlights(self):
        """After rebuilding tree, re-apply 'selected' tag to nodes whose path is in selection."""
        for fid, path in self._file_paths.items():
            if path in self._selected_lookup:
                self.tree.item(fid, tags=("selected",))
            else:
                # only clear file tags (do not touch folder tags / dummy tags)
                if fid not in self._folder_nodes and fid not in self._dummy_nodes:
                    self.tree.item(fid, tags=())
        self._update_count()

    # ----------------------------------------------------------
    # Click handling — toggle highlight on files
    # ----------------------------------------------------------

    def _on_tree_click(self, event):
        """Single click: toggle file selection, or delayed expand/collapse folder."""
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return "break"

        # Ignore clicks on dummy placeholder rows
        if row_id in self._dummy_nodes:
            return "break"

        # For folders, delay expand/collapse so double-click can cancel it
        if row_id in self._folder_nodes:
            # Cancel any previous pending folder click
            if self._pending_click_id is not None:
                self.after_cancel(self._pending_click_id)
            self._pending_click_id = self.after(300, lambda r=row_id: self._handle_single_click_folder(r))
            return "break"

        # For files, act immediately
        if row_id in self._file_paths:
            self._handle_single_click_file(row_id)
            return "break"

        return "break"

    def _on_tree_double_click(self, event):
        """Double click on folder: cancel pending expand and bulk select files."""
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return "break"

        if row_id in self._dummy_nodes:
            return "break"

        # Cancel the pending single-click folder expand/collapse
        if self._pending_click_id is not None:
            self.after_cancel(self._pending_click_id)
            self._pending_click_id = None

        if row_id in self._folder_nodes:
            self._handle_double_click(row_id)

        return "break"

    def _handle_single_click_folder(self, row_id):
        """Single click on folder: expand/collapse (lazy load on first expand)."""
        self._pending_click_id = None
        try:
            is_open = self.tree.item(row_id, "open")
            if not is_open:
                self._ensure_folder_loaded(row_id)
            self.tree.item(row_id, open=not is_open)
        except tk.TclError:
            pass  # node may have been removed by filter

    def _handle_single_click_file(self, row_id):
        """Single click on file: toggle selection highlight."""
        if row_id in self._file_paths:
            path = self._file_paths[row_id]
            if path in self._selected_lookup:
                self._deselect_path(path)
                self.tree.item(row_id, tags=())
            else:
                self._select_path(path)
                self.tree.item(row_id, tags=("selected",))
            self._update_count()

    def _path_is_under(self, path, root):
        try:
            return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
        except ValueError:
            return False

    def _iter_files_under_folder_fs(self, folder_path):
        """
        Recursively yield files from filesystem for bulk folder select/deselect.
        Uses os.walk without following links to avoid loops.
        """
        for current_root, dirs, files in os.walk(folder_path, topdown=True, followlinks=False):
            # Skip hidden/special folders and links
            filtered_dirs = []
            for d in dirs:
                full_d = os.path.join(current_root, d)
                try:
                    if os.path.islink(full_d):
                        continue
                except OSError:
                    continue
                if self._should_skip_folder(d):
                    continue
                filtered_dirs.append(d)
            dirs[:] = filtered_dirs

            for fn in files:
                fp = os.path.join(current_root, fn)
                try:
                    if os.path.islink(fp):
                        continue
                except OSError:
                    continue
                yield fp

    def _refresh_visible_highlights_under_folder(self, folder_path):
        """Refresh only currently visible/loaded file nodes under a folder path."""
        for fid, path in self._file_paths.items():
            if self._path_is_under(path, folder_path):
                if path in self._selected_lookup:
                    self.tree.item(fid, tags=("selected",))
                else:
                    self.tree.item(fid, tags=())

    def _handle_double_click(self, row_id):
        """
        Double click on folder: select/deselect all files in that folder recursively.
        Does NOT fully expand entire subtree (keeps UI fast).
        """
        if row_id not in self._folder_nodes:
            return

        folder_path = self._folder_nodes[row_id]

        # Gather all files in filesystem under this folder (can be large, but explicit action)
        all_paths = list(self._iter_files_under_folder_fs(folder_path))
        if not all_paths:
            # Still expand one level for visibility
            self._ensure_folder_loaded(row_id)
            try:
                self.tree.item(row_id, open=True)
            except tk.TclError:
                pass
            return

        # If all children are selected -> deselect all, otherwise select all
        all_selected = all(p in self._selected_lookup for p in all_paths)
        for path in all_paths:
            if all_selected:
                self._deselect_path(path)
            else:
                self._select_path(path)

        # Ensure one-level children are loaded and visible, but avoid full recursive expansion
        self._ensure_folder_loaded(row_id)
        try:
            self.tree.item(row_id, open=True)
        except tk.TclError:
            pass

        # Update highlights for currently visible nodes
        self._refresh_visible_highlights_under_folder(folder_path)
        self._update_count()

    def _expand_node_recursive(self, node_id):
        """Expand a folder node and all currently loaded subfolder children (kept for compatibility)."""
        if node_id in self._folder_nodes:
            self._ensure_folder_loaded(node_id)
        self.tree.item(node_id, open=True)
        for child in self.tree.get_children(node_id):
            if child in self._folder_nodes:
                self._expand_node_recursive(child)

    def _get_all_file_children(self, node_id):
        """Recursively get all loaded file node IDs under a folder node."""
        result = []
        for child in self.tree.get_children(node_id):
            if child in self._file_paths:
                result.append(child)
            elif child in self._folder_nodes:
                result.extend(self._get_all_file_children(child))
        return result

    def _update_count(self):
        count = len(self._selected_order)
        self.count_label.config(text=f"{count} file{'s' if count != 1 else ''} selected")

    # ----------------------------------------------------------
    # Filtering
    # ----------------------------------------------------------

    def _apply_filter(self):
        query = self.filter_var.get().strip().lower()
        if not query:
            # Go back to fast lazy-loaded tree (avoid recursive full rebuild on empty filter)
            self._populate_tree(self.root_dir)
            return
        self._rebuild_with_filter(query)

    def _rebuild_with_filter(self, query):
        """
        Rebuild tree applying filter, preserving selected paths.
        Note: filtered mode is recursive for accurate matching.
        """
        self.tree.delete(*self.tree.get_children())
        self._file_paths.clear()
        self._folder_nodes.clear()
        self._dummy_nodes.clear()
        self._loaded_folders.clear()

        if os.path.isdir(self.root_dir):
            self._insert_dir_contents_filtered("", self.root_dir, query)

        # Re-apply highlights from selection
        self._reapply_highlights()

        # Expand all when filtering
        if query:
            self._expand_all("")

    def _insert_dir_contents_filtered(self, parent_node, dir_path, query):
        """Insert with optional filter recursively. Empty query handled elsewhere."""
        try:
            entries = sorted(
                os.listdir(dir_path),
                key=lambda x: (not os.path.isdir(os.path.join(dir_path, x)), x.lower())
            )
        except (PermissionError, FileNotFoundError, OSError):
            return

        for entry_name in entries:
            full_path = os.path.join(dir_path, entry_name)

            try:
                if os.path.islink(full_path):
                    continue
            except OSError:
                continue

            if os.path.isdir(full_path):
                if self._should_skip_folder(entry_name):
                    continue
                folder_id = self.tree.insert(
                    parent_node, "end",
                    text=f"📁 {entry_name}",
                    values=("",),
                    tags=("folder",),
                    open=False,
                )
                self._folder_nodes[folder_id] = full_path
                self._insert_dir_contents_filtered(folder_id, full_path, query)
                if not self.tree.get_children(folder_id):
                    self.tree.delete(folder_id)
                    self._folder_nodes.pop(folder_id, None)
            else:
                if query and query not in entry_name.lower():
                    continue
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                file_id = self.tree.insert(
                    parent_node, "end",
                    text=f"  {entry_name}",
                    values=(self._format_size(size),),
                )
                self._file_paths[file_id] = full_path

    def _expand_all(self, parent):
        for child in self.tree.get_children(parent):
            if child in self._folder_nodes:
                self.tree.item(child, open=True)
                self._expand_all(child)

    def _select_all_visible(self):
        for fid, path in self._file_paths.items():
            self._select_path(path)
            self.tree.item(fid, tags=("selected",))
        self._update_count()

    def _deselect_all(self):
        for fid in self._file_paths:
            self.tree.item(fid, tags=())
        self._selected_order.clear()
        self._selected_lookup.clear()
        self._update_count()

    def _select_path(self, path):
        """Add path to selection, preserving insertion order. No-op if already selected."""
        if path not in self._selected_lookup:
            self._selected_order.append(path)
            self._selected_lookup.add(path)

    def _deselect_path(self, path):
        """Remove path from selection."""
        if path in self._selected_lookup:
            self._selected_lookup.discard(path)
            try:
                self._selected_order.remove(path)
            except ValueError:
                pass

    def _on_confirm(self):
        self.selected_files = list(self._selected_order)
        self.destroy()

    def _on_cancel(self):
        self.selected_files = []
        self.destroy()


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

    def _update_selected_files_buttons_state(self):
        """
        Disable file actions unless a valid active project folder exists.
        """
        folders = self.app_config.get("project_folders", {})
        valid_paths = set(folders.values())

        has_active_folder = bool(self.active_project_folder) and self.active_project_folder in valid_paths
        state = tk.NORMAL if has_active_folder else tk.DISABLED

        # Buttons are created in _build_file_list_section
        if hasattr(self, "add_files_btn"):
            self.add_files_btn.config(state=state)
        if hasattr(self, "remove_files_btn"):
            self.remove_files_btn.config(state=state)
        if hasattr(self, "clear_files_btn"):
            self.clear_files_btn.config(state=state)

    def _sync_active_folder_selection_ui(self):
        """
        Keep listbox highlight in sync with self.active_project_folder.
        If folders exist but no active folder is set, auto-select the first one.
        """
        folders = self.app_config.get("project_folders", {})
        keys = list(folders.keys())

        # No folders -> clear active + clear highlight + disable buttons
        if not keys:
            self.active_project_folder = None
            self.folder_listbox.selection_clear(0, tk.END)
            self._refresh_file_listbox()
            self._update_selected_files_buttons_state()
            return

        # If current active folder is missing/invalid, fallback to first folder
        valid_paths = set(folders.values())
        if not self.active_project_folder or self.active_project_folder not in valid_paths:
            self.active_project_folder = folders[keys[0]]

        # Highlight matching row
        selected_index = 0
        for i, name in enumerate(keys):
            if folders[name] == self.active_project_folder:
                selected_index = i
                break

        self.folder_listbox.selection_clear(0, tk.END)
        self.folder_listbox.selection_set(selected_index)
        self.folder_listbox.activate(selected_index)
        self.folder_listbox.see(selected_index)

        # Update relative names + buttons
        self._refresh_file_listbox()
        self._update_selected_files_buttons_state()

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

        self.add_files_btn = ttk.Button(
            btn_frame, text="+ Add Files", style="Secondary.TButton", command=self._add_files
        )
        self.add_files_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.remove_files_btn = ttk.Button(
            btn_frame, text="Remove", style="Secondary.TButton", command=self._remove_selected_files
        )
        self.remove_files_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.clear_files_btn = ttk.Button(
            btn_frame, text="Clear All", style="Danger.TButton", command=self._clear_files
        )
        self.clear_files_btn.pack(side=tk.LEFT)

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

        # Initial state until a project folder is selected/synced
        self._update_selected_files_buttons_state()

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

        # Keep active folder highlighted (or auto-pick first if available)
        self._sync_active_folder_selection_ui()

    def _add_project_folder(self):
        folder = filedialog.askdirectory(parent=self, title="Select Project Folder")
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
            self.active_project_folder = folder  # newly added folder becomes active/highlighted
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
        removed_path = self.app_config["project_folders"][name]

        del self.app_config["project_folders"][name]
        save_config(self.app_config)

        # If the active folder was removed, clear it; loader will auto-pick next one if available
        if self.active_project_folder == removed_path:
            self.active_project_folder = None

        self._load_project_folders()
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
        self._update_selected_files_buttons_state()
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
            parent=self,
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

        # Avoid defaulting to huge home folder (common cause of "Not Responding" on packaged EXE)
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = filedialog.askdirectory(
                parent=self,
                title="Select Root Folder First"
            )
            if not initial_dir:
                return

        # Open custom folder tree picker
        picker = FolderTreePicker(
            self,
            initial_dir=initial_dir,
            colors=self.colors,
        )
        self.wait_window(picker)

        files = picker.selected_files
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
            parent=self,
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