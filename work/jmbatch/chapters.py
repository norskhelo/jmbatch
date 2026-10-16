"""Persisted chapter choices, independent of the UI and downloader."""

class ChapterChoiceRequired(Exception):
    def __init__(self, chapters):
        self.chapters = chapters

def resolve_chapters(catalog, saved, download_all=False):
    if not catalog:
        raise ValueError("没有可下载的章节。")
    by_id = {item["id"]: item for item in catalog}
    if len(by_id) != len(catalog):
        raise ValueError("章节编号重复，请重新获取章节。")
    if saved:
        if any(item["id"] not in by_id for item in saved):
            raise ValueError("已选章节已从服务端移除，未改为下载其他章节。")
        return saved
    if len(catalog) > 1 and not download_all:
        raise ChapterChoiceRequired(catalog)
    return catalog

def select_chapters(catalog, ids):
    wanted = set(ids)
    chosen = [dict(item) for item in catalog if item["id"] in wanted]
    if not chosen or len(chosen) != len(wanted):
        raise ValueError("请至少选择一个有效章节。")
    return chosen
