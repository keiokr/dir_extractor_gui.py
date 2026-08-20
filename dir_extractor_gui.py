from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


APP_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = APP_DIR / "dir_ok.txt"


def extract_directories_from_url(raw_url: str) -> list[str]:
    url = raw_url.strip()
    if not url or "://" not in url:
        return []

    try:
        parsed = urlsplit(url)
    except ValueError:
        return []

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if not scheme or not netloc:
        return []

    base_url = f"{scheme}://{netloc}/"
    path = parsed.path or "/"

    if path in ("", "/"):
        return [base_url]

    segments = [segment for segment in path.split("/") if segment]

    # URL 末尾没有 / 时，最后一段按页面或文件处理，不算目录。
    if not path.endswith("/") and segments:
        segments = segments[:-1]

    directory_segments: list[str] = []
    for segment in segments:
        if "." in segment:
            break
        directory_segments.append(segment)

    results: list[str] = []
    for index in range(len(directory_segments), 0, -1):
        results.append(base_url + "/".join(directory_segments[:index]) + "/")

    results.append(base_url)
    return results


def process_input_lines(text: str) -> tuple[list[str], int]:
    unique_results: list[str] = []
    seen: set[str] = set()
    valid_line_count = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        extracted = extract_directories_from_url(line)
        if not extracted:
            continue

        valid_line_count += 1
        for item in extracted:
            if item in seen:
                continue
            seen.add(item)
            unique_results.append(item)

    return unique_results, valid_line_count


class WindowsFileDrop:
    def __init__(self, root: tk.Tk, on_drop) -> None:
        self.root = root
        self.on_drop = on_drop
        self.enabled = False

    def enable(self) -> bool:
        if TkinterDnD is None or DND_FILES is None:
            return False

        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self.handle_drop_event)
            self.enabled = True
            return True
        except Exception:
            self.enabled = False
            return False

    def disable(self) -> None:
        if not self.enabled:
            return

        try:
            self.root.dnd_unbind("<<Drop>>")
        except Exception:
            pass
        finally:
            self.enabled = False

    def handle_drop_event(self, event) -> None:
        file_paths = self.root.tk.splitlist(event.data)
        if file_paths:
            self.on_drop(list(file_paths))


class DirectoryExtractorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("URL 目录提取工具")
        self.root.geometry("1000x700")
        self.root.minsize(860, 620)

        self.status_var = tk.StringVar(
            value="支持浏览 txt、拖入 txt、或直接粘贴文本。处理完成后自动写入 dir_ok.txt。"
        )
        self.output_path_var = tk.StringVar(value=f"输出文件：{OUTPUT_FILE}")

        self.build_ui()
        self.enable_drop_support()

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        top_bar = ttk.Frame(outer)
        top_bar.pack(fill="x")

        ttk.Button(top_bar, text="浏览 TXT", command=self.load_files).pack(side="left")
        ttk.Button(top_bar, text="处理并导出", command=self.process_current_text).pack(
            side="left",
            padx=(8, 0),
        )
        ttk.Button(top_bar, text="清空", command=self.clear_all).pack(side="left", padx=(8, 0))

        ttk.Label(
            outer,
            text=(
                "规则说明：按行读取 URL，只提取目录路径；忽略参数和 # 后内容；"
                "最后一段不是目录时不保留；遇到带 . 的路径段时，从该段开始不保留。"
            ),
            wraplength=940,
            justify="left",
        ).pack(fill="x", pady=(10, 8))

        drop_hint = ttk.Label(
            outer,
            text="支持直接粘贴文本，也支持把 txt 文件拖到窗口里。",
            foreground="#0b5cab",
        )
        drop_hint.pack(anchor="w", pady=(0, 10))

        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True)

        input_frame = ttk.Labelframe(panes, text="输入内容")
        output_frame = ttk.Labelframe(panes, text="输出结果")
        panes.add(input_frame, weight=1)
        panes.add(output_frame, weight=1)

        self.input_text = scrolledtext.ScrolledText(
            input_frame,
            wrap="word",
            font=("Consolas", 10),
        )
        self.input_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.input_text.bind("<Control-Return>", self.process_current_text)

        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap="word",
            font=("Consolas", 10),
        )
        self.output_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.output_text.configure(state="disabled")

        ttk.Label(outer, textvariable=self.output_path_var).pack(anchor="w", pady=(10, 2))
        ttk.Label(outer, textvariable=self.status_var, foreground="#444").pack(anchor="w")

    def enable_drop_support(self) -> None:
        self.file_drop = WindowsFileDrop(self.root, self.handle_dropped_files)
        if not self.file_drop.enable():
            self.status_var.set("拖拽启用失败，请使用“浏览 TXT”或直接粘贴文本。")
            return

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_files(self) -> None:
        file_paths = filedialog.askopenfilenames(
            title="选择文本文件",
            filetypes=[
                ("文本文件", "*.txt"),
                ("所有文件", "*.*"),
            ],
        )
        if not file_paths:
            return
        self.import_files([Path(item) for item in file_paths])

    def handle_dropped_files(self, file_paths: list[str]) -> None:
        paths = [Path(item) for item in file_paths]
        self.import_files(paths)

    def import_files(self, paths: list[Path]) -> None:
        text_blocks: list[str] = []
        loaded_files: list[str] = []

        for path in paths:
            if not path.is_file():
                continue

            try:
                text_blocks.append(self.read_text_file(path))
                loaded_files.append(str(path))
            except UnicodeDecodeError:
                messagebox.showerror("读取失败", f"文件编码无法识别：\n{path}")
                return
            except OSError as exc:
                messagebox.showerror("读取失败", f"无法读取文件：\n{path}\n\n{exc}")
                return

        if not text_blocks:
            self.status_var.set("没有读取到可用文件。")
            return

        merged_text = "\n".join(block.rstrip("\n") for block in text_blocks if block)
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", merged_text)
        self.status_var.set(f"已导入 {len(loaded_files)} 个文件，正在处理...")
        self.process_current_text()

    def read_text_file(self, path: Path) -> str:
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise UnicodeDecodeError("unknown", b"", 0, 1, "unsupported encoding")

    def process_current_text(self) -> None:
        input_content = self.input_text.get("1.0", "end").strip()
        if not input_content:
            messagebox.showinfo("提示", "请先导入或粘贴文本内容。")
            return

        results, valid_lines = process_input_lines(input_content)
        output_content = "\n".join(results)

        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", output_content)
        self.output_text.configure(state="disabled")

        OUTPUT_FILE.write_text(output_content, encoding="utf-8")

        total_lines = sum(1 for line in input_content.splitlines() if line.strip())
        self.status_var.set(
            f"处理完成：输入 {total_lines} 行，可识别 URL {valid_lines} 行，输出 {len(results)} 行。"
        )

    def clear_all(self) -> None:
        self.input_text.delete("1.0", "end")
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")
        self.status_var.set("内容已清空。")

    def on_close(self) -> None:
        file_drop = getattr(self, "file_drop", None)
        if file_drop is not None:
            file_drop.disable()
        self.root.destroy()


def main() -> None:
    root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
    try:
        root.iconbitmap(default="")
    except tk.TclError:
        pass

    DirectoryExtractorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
