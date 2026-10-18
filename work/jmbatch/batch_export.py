"""Sequential, cancellable exports; completed comics survive later failures."""
from dataclasses import dataclass, field
from pathlib import Path

from albums import export_album


@dataclass
class ExportResult:
    succeeded: int = 0
    failed: int = 0
    unprocessed: int = 0
    stopped: bool = False
    paths: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def summary(self):
        return (f"{'已停止导出' if self.stopped else '导出结束'}：成功 {self.succeeded} 本，"
                f"失败 {self.failed} 本，未处理 {self.unprocessed} 本；已保存 {len(self.paths)} 项。")


def export_many(library, keys, destination, fmt, numeric=False, split_pdf=False,
                progress=lambda message: None, cancelled=lambda: False):
    keys = list(dict.fromkeys(keys))
    destination = Path(destination).resolve()
    result = ExportResult()
    for index, key in enumerate(keys, 1):
        if cancelled():
            result.stopped = True
            break
        item = library.entries.get(key, {})
        title = (f"JM{item['id']} · " if item.get('id') else '') + item.get('title', Path(key).name)
        prefix = f"第 {index}/{len(keys)} 本 · {title}"
        try:
            progress(prefix + " · 正在读取…")
            source = library.checked_path(key)
            paths = export_album(source, destination, fmt, numeric and fmt != 'images', False,
                                 split_pdf and fmt == 'pdf' and item['format'] != 'pdf',
                                 lambda event: progress(prefix + " · " + event.get('message', '正在导出')),
                                 cancelled)
            result.paths.extend(paths)
            result.succeeded += 1
        except Exception as error:
            if isinstance(error, InterruptedError) and cancelled():
                result.stopped = True
                break
            result.failed += 1
            result.errors.append(f"{title}：{error}")
        progress(f"已处理 {result.succeeded + result.failed}/{len(keys)} 本 · 成功 {result.succeeded} 本，失败 {result.failed} 本")
    result.unprocessed = len(keys) - result.succeeded - result.failed
    # Index only complete outputs, including those finished before cancellation.
    # Discovery and catalogue writes stay on the same background worker as export.
    if result.paths:
        try:
            progress("正在将已导出的漫画加入漫画库…")
            found, _ = library.discover(destination)
            identities = {library.key(path) for path in result.paths}
            library.import_found([entry for entry in found if library.key(entry['path']) in identities])
        except Exception as error:
            result.warnings.append(f"文件已保存，但漫画库更新失败：{error}。可稍后扫描导出目录重新导入。")
    return result
