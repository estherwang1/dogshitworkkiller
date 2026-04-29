"""编码兼容工具

设计原则:
  - 写入: 统一 UTF-8 (新世界标准)
  - 读取: 自动探测 (兼容旧文件)
  - 子进程: PYTHONUTF8=1 保证 stdout 一致

用法:
  from encoding_utils import safe_open

  with safe_open(path, "r") as f:   # 自动探测编码
      data = yaml.safe_load(f)

  with safe_open(path, "w") as f:   # 强制 UTF-8
      yaml.dump(data, f)
"""
import os
import sys
from pathlib import Path

# ────────── 全局: 强制子进程 UTF-8 模式 ──────────
# import encoding_utils 即可生效
os.environ.setdefault("PYTHONUTF8", "1")


def _detect_encoding(path: Path) -> str:
    """探测文件编码: UTF-8 → 系统 ANSI → latin-1 兜底。

    优先尝试 UTF-8 (最常见且可自校验);
    失败则回退到系统默认编码 (中文 Windows 为 GBK/cp936);
    再失败用 latin-1 (永远不会解码失败,只是中文变乱码)。
    """
    raw = path.read_bytes()
    # BOM 探测
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    # UTF-8 自校验: utf-8 编码有严格的字节模式,非法序列会抛异常
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    # 回退到系统 ANSI 编码 (中文 Windows = cp936/GBK)
    return _system_ansi()


def _system_ansi() -> str:
    """获取 Windows ANSI 编码,非 Windows 返回 utf-8。"""
    if sys.platform == "win32":
        import locale
        return locale.getpreferredencoding(False)  # 中文 Windows 返回 "cp936"
    return "utf-8"


def safe_open(path, mode="r", *, encoding=None, **kwargs):
    """安全的文件打开,读取时自动探测编码。

    - mode 含 "w"/"a"/"x": 强制 utf-8 写入 (统一出口)
    - mode 含 "r": encoding=None 时自动探测; 显式指定则尊重传入值
    """
    path = Path(path)

    if any(c in mode for c in ("w", "a", "x")):
        # 写入: 统一 UTF-8
        return path.open(mode, encoding=encoding or "utf-8", **kwargs)

    if "r" in mode and "b" not in mode:
        # 读取: 自动探测
        enc = encoding or _detect_encoding(path)
        try:
            return path.open(mode, encoding=enc, **kwargs)
        except UnicodeDecodeError:
            # 探测失败,二级 fallback
            fallback = "latin-1" if enc != "latin-1" else "utf-8"
            return path.open(mode, encoding=fallback, **kwargs)

    # 二进制模式或其它,直接透传
    return path.open(mode, encoding=encoding, **kwargs)
