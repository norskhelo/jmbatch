"""Apply the reviewed UI copy and prepare Windows 0.3.14 / Android 0.5.9."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WIN = ROOT / 'work/jmbatch'
ANDROID = ROOT / 'work/jmbatch-android/app/src/main/java/app/jmbatch/android'
changes = []


def edit(path, replacements):
    text = path.read_text(encoding='utf-8')
    for old, new in replacements.items():
        if old not in text:
            if new in text:
                continue
            raise ValueError(f'Missing copy in {path.name}: {old}')
        changes.append(dict(file=path.relative_to(ROOT).as_posix(), before=old, after=new, occurrences=text.count(old)))
        text = text.replace(old, new)
    path.write_text(text, encoding='utf-8')


# Shared terms are changed only in presentation files, never persisted status keys.
files = [WIN / name for name in ('app.py', 'chapter_ui.py', 'cleanup_ui.py', 'export_ui.py', 'library_ui.py', 'reader_ui.py', 'updates.py')]
files += [ANDROID / name for name in ('MainActivity.java', 'LibraryScreen.java', 'ExportScreen.java', 'ReaderActivity.java', 'SavedDirectory.java', 'CleanupScreen.java', 'GithubUpdates.java')]
common = {
    '检查更新 / 公告': '软件更新',
    '格式互转 / 导出': '导出漫画',
    '已下载漫画 / 收藏': '漫画库',
    '已下载漫画': '漫画库',
    '软件内阅读': '开始阅读',
    '软件内查看': '应用内查看',
    '知道了': '确定',
    '只看收藏': '仅显示收藏',
    '清空选择': '取消选择',
    'ZIP 图片包': 'ZIP 压缩包',
    '全选当前结果': '全选',
    '全选结果': '全选',
    '查看本地使用说明': '使用说明',
    '完整更新公告': '完整更新日志',
    '更新公告': '更新日志',
    '下载新版': '下载更新',
    '安装新版': '安装更新',
    '当前已是适用版本，可查看下方更新日志': '当前已是最新版本',
    '仓库留空，不检查更新': '未设置更新来源',
    'GitHub 公开仓库（用户名/仓库名；修改后先保存，留空不检查）': '更新来源（GitHub 用户名/仓库名，留空可停用更新检查）',
    '未能取得完整更新日志，已保留离线公告，请稍后重试': '无法获取完整更新日志。已保留本地日志，请稍后重试。',
    '上次检查仍在结束中，请稍后点击检查更新重试': '上次检查尚未结束，请稍后重试。',
    '正在后台检查，最多等待 8 秒…': '正在检查更新…',
    '正在取消，当前网络请求结束后停止…': '正在取消下载，请稍候…',
    'PDF、ZIP、图片文件夹可互相导出，源文件保留。': '支持 PDF、ZIP 和图片文件夹之间的格式转换，保留源文件。',
    'PDF 转图片按页渲染（可能损失画质），按一个章节处理。': 'PDF 转图片可能损失画质，所有页面归为一个章节。',
    '文件名仅编号（分章节时附章节序号）': '仅使用编号命名（分章节导出时附加章节序号）',
    'ZIP / 文件夹：单章节图片平铺，多章节分目录；仅包含图片。': 'ZIP 和图片文件夹仅保存图片；多章节按章节分文件夹保存。',
    '成品': '已保存文件',
}
for path in files:
    current = path.read_text(encoding='utf-8')
    # Apply sequentially so longer names and derived terminology remain consistent.
    for old, new in common.items():
        if old in current:
            edit(path, {old: new})
            current = path.read_text(encoding='utf-8')

edit(WIN / 'app.py', {
    'JM Batch · 批量下载器': 'JM Batch',
    '  /  编号批量下载': '  批量漫画下载',
    'WINDOWS  ·': 'Windows  ·',
    'text="保存到"': 'text="保存位置"',
    '连号快捷添加': '连续编号',
    '连号输入': '连续编号',
    '添加区间': '添加连续编号',
    '例如 123456, 123460-123465   ·   支持空格、换行、逗号及 JM 前缀': '示例：123456, 123460-123465  ·  支持空格、换行、逗号及 JM 前缀',
    '加入队列时确定下载格式；下载后 PDF、ZIP、文件夹可互相导出。': '新任务使用当前保存位置和格式。下载完成后可在漫画库转换格式。',
    '▶  开始 / 继续': '开始下载',
    '重试选中': '重试任务',
    'text="打开目录"': 'text="打开保存目录"',
    '任务详情 / 失败原因': '任务详情',
    '请选中失败、暂停或取消的任务。': '请选择已失败、已暂停或已取消的任务，然后重试。',
    '请选中已完成、失败、取消或暂停的任务。': '请选择已结束或已暂停的任务。正在下载的任务无法移除。',
    '移除 {len(removable)} 条记录？\\n已保存文件和缓存均保留在原目录。移除后无法通过此记录续传。': '确定移除所选的 {len(removable)} 条任务记录？\\n已保存文件和缓存将保留。移除后无法通过这些记录继续下载。',
    '路径尚不存在': '保存位置不存在',
    '请先恢复漫画列表': '无法移除记录',
    '总落盘速度': '总保存速度',
    '落盘速度': '保存速度',
    '队列已暂停，点击开始继续': '队列已暂停，点击“开始下载”继续',
    '当前没有正在运行的任务': '暂无正在下载的任务',
    '请选择一本已下载的 PDF、ZIP 或文件夹，然后点击“导出”。': '请在漫画库选择一本漫画，然后点击“导出漫画”。',
    '每个任务图片线程数': '每任务图片线程数',
    '每个任务章节读取并行数': '每任务章节并行数',
    '1–4，默认 2；每个任务单独使用下方图片线程': '1–4，默认 2；各任务独立使用图片线程',
    '1–8，默认 4；可试 6 或 8，超时或限流时调低': '1–8，默认 4；超时或限流时可调低',
    '单次请求超时 / 秒': '请求超时（秒）',
    '单次请求重试': '请求重试次数',
    '慢速阈值 / KB/s': '慢速阈值（KB/s）',
    '慢速观察窗口 / 秒': '慢速检测时长（秒）',
    '无进度超时 / 秒': '无进度超时（秒）',
    '每本最大自动重置次数': '每任务自动重连上限',
    '0–10，达到上限后明确报错': '0–10，达到上限后停止任务并提示',
    '默认下载全章节（跳过章节选择，仅用于尚未选择章节的任务）': '默认下载全部章节（仅对未选择章节的任务生效）',
    '启用慢速 / 无进度自动重置': '下载缓慢或无进度时自动重连',
    '章节并行数独立于图片线程；越高不一定越快，多任务会叠加请求。\\n速度按已完成图片的文件大小估算，大图下载期间可能暂时显示 0。\\n重置会终止旧进程并重建连接；导出阶段不重置。\\n任务数保存后生效；调低时等待当前任务结束，不中断下载。\\n其他设置用于新任务及手动重试；运行中任务保留原设置。': '并行数越高，请求越多；遇到超时或限流时可适当调低。\\n保存速度按已完成图片统计，大图下载期间可能暂时显示为 0。\\n自动重连会重新建立下载连接，导出期间不执行。\\n任务数保存后生效；调低时等待当前任务完成。\\n其他设置用于新任务和手动重试，运行中任务保留原设置。',
    '数值设置必须填写整数。': '请输入有效的整数，并确认数值在允许范围内。',
})
edit(WIN / 'chapter_ui.py', {
    '选择要下载的章节；可全选或清空。关闭后暂停此任务。': '请选择要下载的章节。稍后选择或关闭此窗口会暂停任务。',
    'text="清空"': 'text="取消全选"',
})
edit(WIN / 'cleanup_ui.py', {
    '请先暂停全部下载，等待请求结束；清理过程中不能开始下载。': '请先暂停全部下载，待任务停止后再清理缓存。',
    '保留已保存文件、完成标记、未完成任务的完整图片和章节缓存。\\n仅清理已完成任务的可删除缓存及任务内临时文件。': '清理已完成任务的下载缓存及临时文件。\\n保留已保存文件和继续下载所需的数据。',
})
edit(WIN / 'export_ui.py', {
    'PDF 分章节导出（不勾选则统一导出为一本）': '按章节分别导出 PDF（未勾选时合并为一本）',
    '请选择完整的绝对路径': '请选择有效的导出文件夹。',
    '导出完成：{len(paths)} 个已保存文件，源文件保留。保存到 {folder}': '导出完成，已保存 {len(paths)} 项。源文件已保留。保存位置：{folder}',
})
edit(WIN / 'library_ui.py', {
    '图片目录 / PDF / ZIP · 默认以第一页为封面 · Ctrl / Shift 多选': '管理已下载的漫画；以第一页为封面。按住 Ctrl 或 Shift 可多选。',
    '编号 / 标题': '搜索编号或标题',
    '("导出", "export")': '("导出漫画", "export")',
    '正在停止；当前文件操作结束后即可关闭。': '正在停止操作，请稍候。当前文件处理完成后即可关闭。',
    '导入此目录中的 JM Batch 图片目录及 PDF / ZIP。图片目录按清单验证；重复项保留收藏和标题。': '将此目录中可识别的图片文件夹、PDF 和 ZIP 添加到漫画库。已存在的漫画保留原有标题和收藏。',
    '请选择一本 PDF、ZIP 或文件夹导出': '请选择一本漫画，再选择导出格式。',
    '确认处理 {len(selected)} 项': '确认删除文件' + '" if delete else "确认移除记录',
})
# The dynamic title above is handled separately to keep this pass literal-only.
p = WIN / 'library_ui.py'
s = p.read_text(encoding='utf-8').replace('f"确认删除文件" if delete else "确认移除记录"', '"确认删除文件" if delete else "确认移除记录"')
p.write_text(s, encoding='utf-8')
edit(WIN / 'reader_ui.py', {
    'text="跳页"': 'text="跳转页码"',
    'showinfo("跳页"': 'showinfo("跳转页码"',
    '书签 · 点击选择后跳转或删除': '书签列表',
    '还没有书签，阅读时点击“添加书签”。': '暂无书签。阅读时点击“添加书签”保存当前页。',
})

edit(ANDROID / 'MainActivity.java', {
    'button("设置"': 'button("下载设置"',
    '安卓独立下载  /  ': 'Android  ·  ',
    '新增任务保存到': '保存位置',
    'button("应用目录"': 'button("使用应用目录"',
    'text("批量编号"': 'text("添加下载编号"',
    '123456, 123460-123465\\n可连续输入，支持换行和 JM 前缀': '示例：123456, 123460-123465\\n支持空格、换行、逗号及 JM 前缀',
    '添加连续区间': '添加连续编号',
    '自动去重 · 每次最多 2000 个编号\\n保存目录和格式在加入队列时确定，下载后可互相导出': '每次最多添加 2000 个编号，自动跳过重复任务。\\n新任务使用当前保存位置和格式，下载后可在漫画库转换格式。',
    '开始 / 继续': '开始下载',
    '移除已完成 / 已取消记录': '清除已结束任务记录',
    '移除队列记录？': '清除已结束任务记录',
    '已保存文件和缓存不会删除；移除的记录不能继续用于续传。': '仅移除已完成和已取消的任务记录，保留已保存文件及缓存。移除后无法通过这些记录继续下载。',
    'setNegativeButton("返回"': 'setNegativeButton("取消"',
    '后台下载使用通知栏前台服务。系统强制关闭后，重新打开可继续。': '可在通知栏查看下载进度或暂停任务。应用被系统关闭后，重新打开即可继续下载。',
    '" · 重置 "': '" · 重连 "',
    '就绪 / 队列已停止': '暂无正在下载的任务',
    '"下载所选"': '"下载所选章节"',
    '"清空"': '"取消全选"',
    '已暂停；点击开始继续选择章节': '已暂停，点击“开始下载”继续选择章节',
    '旧请求正在结束，请稍后重试': '任务正在停止，请稍后重试。',
    'button("打开",v->open(task,false))': 'button("阅读",v->open(task,false))',
    '重试取消清理': '重试清理',
    '打开此任务保存目录': '打开保存目录',
    '清理临时缓存': '清理下载缓存',
    '每个任务图片线程数': '每任务图片线程数',
    '请求超时 / 秒（5–120）': '请求超时（秒，5–120）',
    '请求重试（0–5）': '请求重试次数（0–5）',
    '慢速阈值 / KB/s（0=仅检测停滞）': '慢速阈值（KB/s，0 表示仅检测无进度）',
    '慢速观察窗口 / 秒（15–600）': '慢速检测时长（秒，15–600）',
    '无进度超时 / 秒（30–1800）': '无进度超时（秒，30–1800）',
    '每本最大重置次数': '每任务自动重连上限',
    '每个任务章节读取并行数': '每任务章节并行数',
    '慢速 / 无进度时自动重连': '下载缓慢或无进度时自动重连',
    '默认下载全章节（跳过章节选择）': '默认下载全部章节（跳过章节选择）',
    'Cookie（可选，仅本次应用进程内保存）': 'Cookie（可选，仅本次会话有效）',
    '章节读取默认并行 4 章，可试 6 或 8；超时或限流时调低，越高不一定越快，多任务会叠加请求。\\n默认同时下载 2 本，每本 8 个图片线程；并行越多，流量和内存占用越高。速度统计为图片响应的接收字节，重试流量也计入。\\n任务数保存后用于后续调度；调低不会中断已运行任务。\\n其他设置影响新任务和手动重试；已有任务保留原目录和格式。': '并行数越高，请求和内存占用越多；超时或限流时可适当调低。\\n下载速度按实际接收的图片数据统计，包含重试流量。\\n任务数保存后生效；调低时等待当前任务完成。\\n其他设置用于新任务和手动重试，已有任务保留原保存位置和格式。',
    '运行离线自检（不访问网站）': '离线诊断',
    '1. 选择保存目录，添加编号或区间。\\n2. 点击开始，图片按章节和页码保存，通知栏可暂停。': '1. 选择保存位置和下载格式，添加编号或连续编号。\\n2. 点击“开始下载”，可在通知栏查看进度或暂停。',
    '选择“导出”': '选择“导出漫画”',
    '失败任务会保留已验证缓存，可修正后重试。': '下载失败时保留完整缓存，可查看失败原因后点击“重试”。',
    '参数必须是整数': '请输入有效的整数，并确认数值在允许范围内。',
    '正在生成本地测试图片和 PDF…': '正在运行离线诊断，无需联网…',
    '离线自检结果': '离线诊断结果',
    '自检失败：': '诊断未完成：',
    '请先暂停下载后再运行自检': '请先暂停下载，再运行离线诊断。',
})
edit(ANDROID / 'LibraryScreen.java', {
    '封面默认取第一页。选择 PDF、ZIP 或文件夹可互相导出，长按可打开或分享。': '以第一页为封面。选择漫画后可阅读、导出或收藏，长按可打开或分享文件。',
    '搜索编号 / 标题': '搜索编号或标题',
    'button("扫描目录"': 'button("扫描保存目录"',
    'button("导出"': 'button("导出漫画"',
    '请选择一本 PDF、ZIP 或文件夹导出': '请选择一本漫画，再选择导出格式。',
    '扫描保存目录？': '扫描保存目录',
    '导入本目录下的 JM Batch 图片目录和非空 PDF / ZIP；图片目录按清单验证，重复项保留收藏和标题。': '将此目录中可识别的图片文件夹、PDF 和 ZIP 添加到漫画库。已存在的漫画保留原有标题和收藏。',
    'setNegativeButton("返回"': 'setNegativeButton("取消"',
})
edit(ANDROID / 'ExportScreen.java', {
    'PDF 分章节导出（不勾选则统一导出）': '按章节分别导出 PDF（未勾选时合并为一本）',
    '"导出："': '"导出漫画 · "',
    '"导出完成："+files.size()+" 个已保存文件': '"导出完成，已保存 "+files.size()+" 项',
    '源文件保留，可在漫画库中打开或继续导出。': '源文件已保留，可在漫画库查看导出结果。',
})
edit(ANDROID / 'ReaderActivity.java', {
    '模式：滚动': '滚动阅读',
    '模式：左右': '左右翻页',
    '页码 / 跳页': '跳转页码',
    '外部 ZIP 首次打开需准备缓存，可返回取消。': '首次打开外部 ZIP 可能需要一些时间，点击返回可取消。',
    '章节切换': '选择章节',
    '跳到总页码（1–': '跳转页码（1–',
    '移除书签': '移除本页书签',
    ' · PDF 单章节': ' · PDF 按一个章节显示',
})
edit(ANDROID / 'SavedDirectory.java', {
    '备用打开方式': '其他打开方式',
    '文档管理（备用）': '系统文档管理',
    '选择其他应用打开': '选择其他应用',
    '用系统文件管理器打开此目录': '在文件管理器中打开',
    '此设备未提供可用的直接目录跳转，请在文件管理器中手动定位：': '此设备不支持直接定位到该目录，请手动打开以下位置：',
    '供以后下载使用': '用于后续下载',
    '目录授权已失效，请关闭后重新“选择目录”授权。': '目录访问权限已失效，请返回首页重新选择保存目录。',
})
edit(ANDROID / 'CleanupScreen.java', {
    '保留已保存文件、完成标记、未完成任务的完整图片和章节缓存。': '保留已保存文件和继续下载所需的数据。',
    '已保存文件、完成标记及续传所需完整图片和章节缓存已保留。': '已保留所有已保存文件和继续下载所需的数据。',
})
edit(WIN / 'updates.py', {
    '检查更新使用已保存的仓库，关闭自动检查后也可手动检查。\\n失败或超时可再次点击重试，不影响下载任务。\\n在应用内下载，验证签名和 SHA-256 后，确认安装并重启。\\n只信任本软件发布密钥签署的更新；不发送漫画编号或 Cookie。': '修改更新来源后请先保存。关闭自动检查后，仍可手动检查。\\n更新包通过签名和完整性校验后即可安装，安装时会暂停任务并重启应用。\\n检查更新不会发送漫画编号或 Cookie。',
    '签名和 SHA-256 校验通过，可以安装并重启': '更新包校验通过，可安装并重启。',
    '更新日志（离线也可查看）': '更新日志（支持离线查看）',
})
edit(ANDROID / 'GithubUpdates.java', {
    '"新版 "+latestVersion+" / 公告"': '"发现新版本 "+latestVersion',
    '查看完整更新日志（离线可用）': '完整更新日志（支持离线查看）',
    '检查更新使用已保存的仓库，关闭自动检查后也可手动检查。\\n失败或超时可再次点击重试，不影响下载任务。\\n下载后先核验清单签名和 SHA-256；APK 证书先在应用内预检查，系统未提供证书时交由系统安装器核验。已知证书不匹配会阻止安装。\\n下载更新时请保持应用在前台；安装前请暂停漫画下载任务。\\n只信任本软件发布密钥签署的更新；不发送漫画编号或 Cookie。': '修改更新来源后请先保存。关闭自动检查后，仍可手动检查。\\n更新包通过签名和完整性校验后即可安装，安装时由系统再次验证应用签名。\\n下载更新时请保持应用在前台，安装前请暂停漫画下载。\\n检查更新不会发送漫画编号或 Cookie。',
})

notes = '''# Windows 0.3.14 / Android 0.5.9 — 界面文案规范化

## 界面与提示

- 统一首页、任务列表、下载设置、漫画库、阅读器、导出、目录浏览、缓存清理及软件更新的名称和提示，减少重复说明与生硬的技术用语。
- 常用入口统一为“漫画库”“导出漫画”“开始阅读”“软件更新”；统一连续编号、选择章节、页码跳转、书签和收藏操作的措辞。
- 下载设置采用一致的参数名称与单位，自动恢复统一表述为“自动重连”；Windows 保留“保存速度”统计口径，Android 保留实际接收速度说明。
- 整理空状态、操作结果和错误提示，明确继续操作的方法；移除记录、删除文件、取消任务和清理缓存的影响说明继续保留。
- 更新应用内使用说明、离线更新日志和随包说明，使操作名称与界面一致。

## 版本与兼容性

- Windows 0.3.13 → 0.3.14；Android 0.5.8 → 0.5.9（versionCode 509）。保留原应用包名、APK 签名证书和更新公钥。
- 本次以文案整理为主，保留下载、阅读、导出、续传和更新校验流程，已有设置、队列、收藏及文件格式继续兼容。
- 执行双端既有回归、Windows 源码及成品自检、Android 构建与签名核验。未连接 Android 真机，宿主检查不代表真机视觉验收。
'''
folder = ROOT / 'work/release-0314-059'
folder.mkdir(exist_ok=True)
(folder / 'release-notes.md').write_text(notes, encoding='utf-8')
p = ROOT / 'CHANGELOG.md'
p.write_text(notes + '\n' + p.read_text(encoding='utf-8'), encoding='utf-8')
for name in ('work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java', 'work/jmbatch-android/app/src/main/AndroidManifest.xml', 'work/jmbatch-android/app/build.gradle'):
    p = ROOT / name
    s = p.read_text(encoding='utf-8').replace('0.3.13', '0.3.14').replace('0.5.8', '0.5.9').replace('versionCode 508', 'versionCode 509').replace('versionCode="508"', 'versionCode="509"')
    p.write_text(s, encoding='utf-8')
plain = notes.replace('## ', '').replace('# ', '').replace('- ', '• ')
for p in (WIN / 'updates.py', ANDROID / 'GithubUpdates.java'):
    s = re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$', lambda m: m[1] + json.dumps(plain, ensure_ascii=False) + (';' if p.suffix == '.java' else ''), p.read_text(encoding='utf-8'))
    p.write_text(s, encoding='utf-8')
for name in ('README.md', 'work/jmbatch/README.txt', 'work/jmbatch-android/README.txt'):
    p = ROOT / name
    s = p.read_text(encoding='utf-8')
    if name != 'README.md':
        s = re.split(r'\n(?:Windows 0\.3\.13 / Android 0\.5\.7|Android 0\.5\.8) — ', s)[0].rstrip() + '\n'
    s = s.replace('release-0.3.13-0.5.7', 'release-0.3.14-0.5.9').replace('release-android-0.5.8', 'release-0.3.14-0.5.9')
    s = s.replace('0.3.13', '0.3.14').replace('0.5.8', '0.5.9').replace('versionCode 508', 'versionCode 509')
    s = s.replace('SHA256-release-android-0.5.9', 'SHA256-release-0.3.14-0.5.9')
    s = s.replace('Android 本版修复更换系统字体、放大字号时的按钮尺寸与布局异常；Windows 保持 0.3.14。', '本版统一双端界面文案，优化按钮名称、操作提示和使用说明。')
    for old, new in common.items():
        if old != '成品': s = s.replace(old, new)
    s = s.replace('每个任务图片线程数', '每任务图片线程数').replace('选择“导出”', '选择“导出漫画”').replace('点击“导出”', '点击“导出漫画”')
    if name != 'README.md': s += '\n' + plain
    p.write_text(s, encoding='utf-8')

replacements = {
    '0.3.13': '0.3.14', '0.3.12': '0.3.13', '0.5.7': '0.5.9', '0.5.6': '0.5.8',
    '0313-057': '0314-059', '0313_057': '0314_059',
    'update-mirrors': 'copy', 'update_mirrors': 'copy',
    '应用内更新下载自动切换镜像': '界面文案规范化', '<= 507': '<= 509', "versionCode='507'": "versionCode='509'",
    '90d81bb1eb42ac218e3761db27d42371296518cd': 'f802d956236158266716692c7d672f0ba215236f',
    'range(1,14)': 'range(1,15)', '!=17': '!=19', '17-release': '19-release', 'full_history_versions=17': 'full_history_versions=19',
}
pattern = re.compile('|'.join(re.escape(k) for k in sorted(replacements, key=len, reverse=True)))
for old, new in (
    ('release/prepare_publication_0313_057.py', 'release/prepare_publication_0314_059.py'),
    ('release/publish_0313_057.py', 'release/publish_0314_059.py'),
    ('release/audit_update_mirrors_release.py', 'release/audit_copy_release.py'),
    ('release/verify_update_mirrors_commit.py', 'release/verify_copy_commit.py'),
    ('maintenance/verify_update_mirrors_online.py', 'maintenance/verify_copy_online.py'),
    ('maintenance/verify_android_update_mirrors_online.py', 'maintenance/verify_android_copy_online.py'),
):
    text = pattern.sub(lambda m: replacements[m[0]], (ROOT / 'work/scripts' / old).read_text(encoding='utf-8'))
    (ROOT / 'work/scripts' / new).write_text(text, encoding='utf-8')
report = ROOT / 'outputs/reports/copy-0314-059-complete'
report.mkdir(parents=True, exist_ok=True)
(report / 'copy-changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'Prepared {len(changes)} copy edits across {len(set(c["file"] for c in changes))} UI files.')
