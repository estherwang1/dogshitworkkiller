"""DogshitWorkKiller 启动器
双击或命令行运行即可: python launcher/main.py

主窗口布局:
┌──────────────────────────────────────────────────┐
│ 项目根目录: [____________________________] [浏览] │
├──────────────┬───────────────────────────────────┤
│ 任务列表     │ 任务详情 / 配置编辑               │
│              │                                   │
│ ○ 任务 1     │ 名称:...                          │
│ ● 任务 2     │ 说明:...                          │
│              │ 配置:                             │
│              │ (动态生成的编辑控件)               │
│              │                                   │
│              │ [保存配置] [运行] [动作...] [打开] │
│              ├───────────────────────────────────┤
│              │ 日志:                             │
│              │ ...                               │
└──────────────┴───────────────────────────────────┘
"""

import os
import platform
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Optional
import yaml

from encoding_utils import safe_open
from task_loader import discover_tasks
from config_editor import ConfigEditor
from runner_proxy import RunnerProxy

# ────────────────────── 启动器自身配置 ──────────────────────

LAUNCHER_DIR = Path(__file__).resolve().parent
LAUNCHER_CONFIG_PATH = LAUNCHER_DIR / "launcher_config.yaml"


def _load_launcher_config() -> dict:
    if LAUNCHER_CONFIG_PATH.is_file():
        try:
            with safe_open(LAUNCHER_CONFIG_PATH, "r") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def _save_launcher_config(config: dict):
    try:
        with safe_open(LAUNCHER_CONFIG_PATH, "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        print(f"保存启动器配置失败: {e}")


def _resolve_project_root(config: dict) -> Path:
    """从启动器配置解析项目根目录。空值时取 launcher/ 的父目录。"""
    raw = config.get("project_root", "").strip()
    if raw:
        p = Path(raw)
        if p.is_dir():
            return p.resolve()
    return LAUNCHER_DIR.parent.resolve()


# ────────────────────── 主应用 ──────────────────────


class App:
    # 排版常量
    PAD_X = 12
    PAD_Y = 6
    TASK_LIST_WIDTH = 22
    LOG_HEIGHT = 14
    MIN_WIDTH = 960
    MIN_HEIGHT = 640

    def __init__(self):
        self._launcher_config = _load_launcher_config()
        self._project_root = _resolve_project_root(self._launcher_config)
        self._tasks: list[dict] = []
        self._selected_index: int = -1
        self._config_editor: Optional[ConfigEditor] = None
        self._runner = RunnerProxy()
        self._build_window()
        self._refresh_tasks()

    # ──── 窗口构建 ────

    def _build_window(self):
        self._root = tk.Tk()
        self._root.title("DogshitWorkKiller")
        self._root.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self._root.geometry("1080x720")

        # macOS / Windows 窗口居中
        self._root.update_idletasks()
        w = self._root.winfo_width()
        h = self._root.winfo_height()
        x = (self._root.winfo_screenwidth() - w) // 2
        y = (self._root.winfo_screenheight() - h) // 2
        self._root.geometry(f"+{x}+{y}")

        self._build_top_bar()
        self._build_main_area()

    def _build_top_bar(self):
        """顶部:项目根目录选择。"""
        bar = tk.Frame(self._root, pady=6)
        bar.pack(fill="x", padx=self.PAD_X)

        tk.Label(bar, text="项目根目录:").pack(side="left")
        self._root_var = tk.StringVar(value=str(self._project_root))
        entry = tk.Entry(bar, textvariable=self._root_var, width=60)
        entry.pack(side="left", padx=(4, 0), fill="x", expand=True)
        btn = tk.Button(bar, text="浏览", width=6, command=self._browse_root)
        btn.pack(side="left", padx=(4, 0))
        btn_apply = tk.Button(bar, text="应用", width=6, command=self._apply_root)
        btn_apply.pack(side="left", padx=(4, 0))

        sep = ttk.Separator(self._root, orient="horizontal")
        sep.pack(fill="x", padx=self.PAD_X)

    def _build_main_area(self):
        """左右分栏:左侧任务列表,右侧详情+日志。"""
        main = tk.PanedWindow(self._root, orient="horizontal", sashwidth=4)
        main.pack(fill="both", expand=True, padx=self.PAD_X, pady=self.PAD_Y)

        # ── 左侧:任务列表 ──
        left = tk.Frame(main, width=200)
        main.add(left, minsize=160)
        tk.Label(left, text="任务列表", font=("", 10, "bold")).pack(
            anchor="w", padx=4, pady=(4, 2)
        )
        self._task_listbox = tk.Listbox(
            left,
            width=self.TASK_LIST_WIDTH,
            activestyle="dotbox",
            selectmode="browse",
            font=("", 9),
        )
        self._task_listbox.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self._task_listbox.bind("<<ListboxSelect>>", self._on_task_select)

        # ── 右侧:详情 + 日志 ──
        right = tk.Frame(main)
        main.add(right, minsize=500)

        # 右侧再上下分:上面是详情+配置+按钮,下面是日志
        right_paned = tk.PanedWindow(right, orient="vertical", sashwidth=4)
        right_paned.pack(fill="both", expand=True)

        # 上半:任务详情 + 配置
        self._detail_frame = tk.Frame(right_paned)
        right_paned.add(self._detail_frame, minsize=200)

        # 下半:日志
        log_frame = tk.Frame(right_paned)
        right_paned.add(log_frame, minsize=120)

        tk.Label(log_frame, text="运行日志", font=("", 10, "bold")).pack(
            anchor="w", padx=4, pady=(4, 2)
        )
        log_inner = tk.Frame(log_frame)
        log_inner.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        log_scroll = ttk.Scrollbar(log_inner, orient="vertical")
        log_scroll.pack(side="right", fill="y")

        self._log_text = tk.Text(
            log_inner,
            height=self.LOG_HEIGHT,
            state="disabled",
            wrap="word",
            font=("Consolas", 9),
            yscrollcommand=log_scroll.set,
        )
        self._log_text.pack(fill="both", expand=True)
        log_scroll.config(command=self._log_text.yview)

        # 初始占位
        self._show_placeholder()

    def _show_placeholder(self):
        """未选中任务时的占位提示。"""
        for child in self._detail_frame.winfo_children():
            child.destroy()
        tk.Label(
            self._detail_frame,
            text="← 请在左侧选择一个任务",
            fg="#888888",
            font=("", 11),
        ).pack(expand=True)

    # ──── 任务列表 ────

    def _refresh_tasks(self):
        self._tasks = discover_tasks(self._project_root)
        self._task_listbox.delete(0, "end")
        for t in self._tasks:
            self._task_listbox.insert("end", t["name"])
        self._selected_index = -1
        self._show_placeholder()

    def _on_task_select(self, event):
        sel = self._task_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == self._selected_index:
            return
        if self._runner.is_running:
            messagebox.showwarning("提示", "有任务正在运行,请等待完成后再切换")
            # 恢复选中
            self._task_listbox.selection_clear(0, "end")
            if self._selected_index >= 0:
                self._task_listbox.selection_set(self._selected_index)
            return
        self._selected_index = idx
        self._show_task_detail(self._tasks[idx])

    # ──── 任务详情 ────

    def _show_task_detail(self, task: dict):
        for child in self._detail_frame.winfo_children():
            child.destroy()

        task_dir = task["task_dir"]

        # ── 任务信息区 ──
        info_frame = tk.Frame(self._detail_frame)
        info_frame.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(
            info_frame,
            text=task["name"],
            font=("", 12, "bold"),
        ).pack(anchor="w")

        if task["description"]:
            tk.Label(
                info_frame,
                text=task["description"],
                fg="#555555",
                font=("", 9),
                wraplength=600,
                justify="left",
            ).pack(anchor="w", pady=(2, 0))

        if task.get("version"):
            tk.Label(
                info_frame,
                text=f"版本: {task['version']}",
                fg="#888888",
                font=("", 8),
            ).pack(anchor="w")

        ttk.Separator(self._detail_frame).pack(fill="x", padx=8, pady=4)

        # ── 配置编辑区 ──
        config_frame = tk.Frame(self._detail_frame)
        config_frame.pack(fill="both", expand=True)

        tk.Label(config_frame, text="配置", font=("", 10, "bold")).pack(
            anchor="w", padx=8, pady=(2, 0)
        )
        editor_container = tk.Frame(config_frame)
        editor_container.pack(fill="both", expand=True)

        self._config_editor = ConfigEditor(editor_container, Path(task_dir))

        # ── 按钮区 ──
        btn_frame = tk.Frame(self._detail_frame)
        btn_frame.pack(fill="x", padx=8, pady=(4, 8))

        self._btn_save = tk.Button(
            btn_frame,
            text="保存配置",
            width=10,
            command=self._on_save,
        )
        self._btn_save.pack(side="left", padx=(0, 6))

        self._btn_run = tk.Button(
            btn_frame,
            text="▶ 运行",
            width=10,
            command=lambda: self._on_run(task),
        )
        self._btn_run.pack(side="left", padx=(0, 6))

        # actions 按钮
        self._action_buttons = []
        for action in task.get("actions", []):
            btn = tk.Button(
                btn_frame,
                text=action.get("name", action.get("script", "?")),
                width=12,
                command=lambda a=action: self._on_action(task, a),
            )
            btn.pack(side="left", padx=(0, 6))
            self._action_buttons.append(btn)

        self._btn_open = tk.Button(
            btn_frame,
            text="打开输出目录",
            width=12,
            command=self._on_open_output,
        )
        self._btn_open.pack(side="right")

    # ──── 按钮事件 ────

    def _on_save(self):
        if self._config_editor and self._config_editor.save():
            messagebox.showinfo("保存配置", "已保存")
        else:
            messagebox.showerror("保存配置", "保存失败")

    def _on_run(self, task: dict):
        script = Path(task["task_dir"]) / task["entry"]
        self._run_script(script, Path(task["task_dir"]))

    def _on_action(self, task: dict, action: dict):
        script = Path(task["task_dir"]) / action["script"]
        if not script.is_file():
            messagebox.showerror("错误", f"脚本不存在: {script}")
            return
        self._run_script(script, Path(task["task_dir"]))

    def _run_script(self, script: Path, task_dir: Path):
        if self._runner.is_running:
            messagebox.showwarning("提示", "已有任务在运行,请等待完成")
            return

        if not script.is_file():
            messagebox.showerror("错误", f"脚本不存在: {script}")
            return

        # 清空日志
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.config(state="disabled")

        # 禁用按钮
        self._set_buttons_state("disabled")

        self._log_append(f">>> 启动: {script.name}\n")
        self._log_append(f">>> 任务目录: {task_dir}\n")
        self._log_append(f"{'─' * 50}\n")

        self._runner.start(
            script,
            task_dir,
            on_line=self._on_log_line,
            on_finish=self._on_run_finish,
        )

    def _on_log_line(self, line: str):
        """子线程回调,用 after 调度到主线程。"""
        self._root.after(0, self._log_append, line)

    def _on_run_finish(self, returncode: int):
        """子线程回调,用 after 调度到主线程。"""

        def _finish():
            self._log_append(f"{'─' * 50}\n")
            if returncode == 0:
                self._log_append(">>> 运行完成\n")
            else:
                self._log_append(f">>> 运行结束,退出码: {returncode}\n")
            self._set_buttons_state("normal")

        self._root.after(0, _finish)

    def _log_append(self, text: str):
        self._log_text.config(state="normal")
        self._log_text.insert("end", text)
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    def _set_buttons_state(self, state: str):
        """运行期间禁用/恢复所有操作按钮和任务列表。"""
        for w in (self._btn_save, self._btn_run, self._btn_open):
            if w.winfo_exists():
                w.config(state=state)
        for btn in self._action_buttons:
            if btn.winfo_exists():
                btn.config(state=state)
        self._task_listbox.config(state=state)

    def _on_open_output(self):
        """打开输出目录(读 config 里的 output_items_dir)。"""
        if not self._config_editor:
            return
        output_dir = self._config_editor.get_config_value("output_items_dir", "")
        if not output_dir:
            # 尝试其他可能的输出目录字段
            output_dir = self._config_editor.get_config_value("output_docx_dir", "")
        if not output_dir:
            messagebox.showinfo("提示", "配置中未设置输出目录")
            return
        p = Path(output_dir)
        if not p.is_dir():
            messagebox.showinfo("提示", f"输出目录不存在:\n{p}")
            return
        _open_folder(p)

    # ──── 项目根目录 ────

    def _browse_root(self):
        path = filedialog.askdirectory(initialdir=str(self._project_root))
        if path:
            self._root_var.set(path)

    def _apply_root(self):
        raw = self._root_var.get().strip()
        if not raw:
            messagebox.showwarning("提示", "请输入项目根目录路径")
            return
        p = Path(raw)
        if not p.is_dir():
            messagebox.showerror("错误", f"目录不存在: {p}")
            return
        tasks_dir = p / "tasks"
        if not tasks_dir.is_dir():
            messagebox.showwarning("提示", f"该目录下没有 tasks/ 子目录:\n{p}")
            return
        self._project_root = p.resolve()
        self._launcher_config["project_root"] = str(self._project_root)
        _save_launcher_config(self._launcher_config)
        self._refresh_tasks()

    # ──── 启动 ────

    def run(self):
        self._root.mainloop()


# ────────────────────── 工具函数 ──────────────────────


def _open_folder(path: Path):
    """跨平台打开文件夹。"""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))
        elif system == "Darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])
    except Exception as e:
        messagebox.showerror("打开目录失败", str(e))


# ────────────────────── 入口 ──────────────────────

if __name__ == "__main__":
    app = App()
    app.run()
