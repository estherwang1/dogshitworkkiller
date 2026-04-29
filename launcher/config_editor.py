"""配置编辑器
读 config.schema.yaml 和 config.yaml,在指定的 Tkinter 父容器里动态生成
编辑控件。用户改完后可调 save() 写回 config.yaml。

每个 schema 字段映射到一种控件:
- dir / file / file_or_dir → Entry + 浏览按钮
- text / string → Entry
- number → Entry(不做强制校验,保存时原样写回)
- checkbox → Checkbutton
- dropdown → Combobox

设计要点:
- 不做类型校验(当前阶段保存时原样写回,不拦截)
- 字段按 schema 文件中的顺序排列
- description 显示为控件下方的灰色提示文字
"""

import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from typing import Optional
import yaml
from encoding_utils import safe_open


class ConfigEditor:
    """在指定 frame 里生成配置编辑控件。

    Args:
        parent: 放置控件的 Tkinter 容器。
        task_dir: 任务目录(含 config.yaml 和 config.schema.yaml)。
    """

    def __init__(self, parent: tk.Widget, task_dir: Path):
        self._parent = parent
        self._task_dir = task_dir
        self._schema: dict = {}
        self._config: dict = {}
        self._widgets: dict[str, tk.Variable] = {}  # 字段名 → Variable
        self._field_order: list[str] = []
        self._load_schema()
        self._load_config()
        self._build_ui()

    def _load_schema(self):
        schema_path = self._task_dir / "config.schema.yaml"
        if not schema_path.is_file():
            self._schema = {}
            return
        try:
            with safe_open(schema_path, "r") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                self._schema = data
                self._field_order = list(data.keys())
            else:
                self._schema = {}
        except Exception:
            self._schema = {}

    def _load_config(self):
        config_path = self._task_dir / "config.yaml"
        if not config_path.is_file():
            self._config = {}
            return
        try:
            with safe_open(config_path, "r") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                self._config = data
            else:
                self._config = {}
        except Exception:
            self._config = {}

    def _build_ui(self):
        """按 schema 顺序逐字段生成控件。"""
        for child in self._parent.winfo_children():
            child.destroy()

        if not self._schema:
            label = tk.Label(
                self._parent,
                text="(该任务无 config.schema.yaml,无法生成配置界面)",
                fg="#888888",
            )
            label.pack(anchor="w", padx=8, pady=16)
            return

        # 用 Canvas + Scrollbar 实现可滚动区域
        canvas = tk.Canvas(self._parent, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(self._parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 鼠标滚轮绑定
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 逐字段生成
        for field_name in self._field_order:
            field_schema = self._schema[field_name]
            if not isinstance(field_schema, dict):
                continue
            self._build_field(scroll_frame, field_name, field_schema)

    def _build_field(self, parent: tk.Widget, name: str, schema: dict):
        """生成单个字段的控件组:标签 + 输入控件 + 描述。"""
        widget_type = schema.get("widget", "text")
        description = schema.get("description", "")
        default = schema.get("default", "")
        current_value = self._config.get(name, default)
        options = schema.get("options", [])

        # 外层容器,每个字段之间留间距
        field_frame = tk.Frame(parent)
        field_frame.pack(fill="x", padx=12, pady=(8, 0))

        # 字段名标签
        required = schema.get("required", False)
        label_text = name
        if required:
            label_text += " *"
        label = tk.Label(field_frame, text=label_text, font=("", 9, "bold"))
        label.pack(anchor="w")

        # 输入控件
        if widget_type == "checkbox":
            var = tk.BooleanVar(value=bool(current_value))
            cb = tk.Checkbutton(field_frame, variable=var)
            cb.pack(anchor="w")
            self._widgets[name] = var

        elif widget_type == "dropdown":
            var = tk.StringVar(value=str(current_value) if current_value else "")
            combo = ttk.Combobox(
                field_frame,
                textvariable=var,
                values=[str(o) for o in options],
                state="readonly",
                width=40,
            )
            combo.pack(anchor="w", fill="x")
            self._widgets[name] = var

        elif widget_type in ("dir", "file", "file_or_dir"):
            var = tk.StringVar(value=str(current_value) if current_value else "")
            entry_frame = tk.Frame(field_frame)
            entry_frame.pack(fill="x")
            entry = tk.Entry(entry_frame, textvariable=var)
            entry.pack(side="left", fill="x", expand=True)
            if widget_type in ("dir", "file_or_dir"):
                btn_dir = tk.Button(
                    entry_frame,
                    text="选目录",
                    width=7,
                    command=lambda v=var: self._browse_dir(v),
                )
                btn_dir.pack(side="left", padx=(4, 0))
            if widget_type in ("file", "file_or_dir"):
                btn_file = tk.Button(
                    entry_frame,
                    text="选文件",
                    width=7,
                    command=lambda v=var: self._browse_file(v),
                )
                btn_file.pack(side="left", padx=(4, 0))
            self._widgets[name] = var

        else:  # text / number / 其他一律用 Entry
            var = tk.StringVar(value=str(current_value) if current_value is not None else "")
            entry = tk.Entry(field_frame, textvariable=var)
            entry.pack(fill="x")
            self._widgets[name] = var

        # 描述提示
        if description:
            desc_label = tk.Label(
                field_frame,
                text=description,
                fg="#888888",
                font=("", 8),
                wraplength=500,
                justify="left",
            )
            desc_label.pack(anchor="w", pady=(0, 2))

    def _browse_dir(self, var: tk.StringVar):
        initial = var.get() or ""
        path = filedialog.askdirectory(initialdir=initial)
        if path:
            var.set(path)

    def _browse_file(self, var: tk.StringVar):
        initial = var.get() or ""
        initial_dir = str(Path(initial).parent) if initial else ""
        path = filedialog.askopenfilename(initialdir=initial_dir)
        if path:
            var.set(path)

    def save(self) -> bool:
        """把当前控件值写回 config.yaml。

        保留 config.yaml 中不在 schema 里的字段(如 llm_extra_body)。

        Returns:
            True 保存成功,False 失败。
        """
        # 从控件收集值
        updated = dict(self._config)  # 保留 schema 未覆盖的字段

        for name in self._field_order:
            schema = self._schema.get(name, {})
            if not isinstance(schema, dict):
                continue
            if name not in self._widgets:
                continue

            var = self._widgets[name]
            widget_type = schema.get("widget", "text")
            field_type = schema.get("type", "string")

            if widget_type == "checkbox":
                updated[name] = var.get()
            else:
                raw = var.get().strip()
                # 尝试按 schema type 转换
                if field_type == "integer" and raw:
                    try:
                        updated[name] = int(raw)
                    except ValueError:
                        updated[name] = raw
                elif field_type == "float" and raw:
                    try:
                        updated[name] = float(raw)
                    except ValueError:
                        updated[name] = raw
                elif field_type == "boolean":
                    updated[name] = raw.lower() in ("true", "1", "yes") if raw else False
                else:
                    updated[name] = raw

        config_path = self._task_dir / "config.yaml"
        try:
            with safe_open(config_path, "w") as f:
                yaml.dump(
                    updated,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def get_config_value(self, key: str, default=None):
        """读取当前配置值(从控件状态,不是文件)。"""
        if key in self._widgets:
            return self._widgets[key].get()
        return self._config.get(key, default)
