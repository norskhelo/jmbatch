JM Batch 0.3.0 — Windows 使用说明

1. 选择保存目录，输入编号或区间并加入队列，点击开始。
2. 默认同时下载 2 本。在“下载设置”中将“同时下载任务数”设为 1–4；“每个任务图片线程数”控制单本图片并发。
3. 调高任务数自动补位；调低时等待已运行任务结束。取消单个任务不会影响其他任务；暂停会停止全部下载并保留缓存。
4. 文件夹和 ZIP 只含图片：单章节平铺，多章节先分章节文件夹再平铺图片；下载后可在任务详情或漫画库单独导出 PDF / ZIP。导出和文件删除前请暂停下载并等待请求退出。
5. Windows 完整解压 ZIP 后运行 JMBatch.exe；Android 覆盖安装 APK，保留设置、队列和收藏。Android 卸载应用可能删除应用目录中的图片，请事先备份。

安装包下载（2026-10-15）
GitHub：https://github.com/norskhelo/jmbatch/releases/download/release-0.3.0-0.4.0/JMBatch-0.3.0-Windows-x64.zip
国内镜像 1：https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.0-0.4.0/JMBatch-0.3.0-Windows-x64.zip
国内镜像 2：https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.0-0.4.0/JMBatch-0.3.0-Windows-x64.zip
SHA-256：https://github.com/norskhelo/jmbatch/releases/download/release-0.3.0-0.4.0/SHA256-release-0.3.0-0.4.0.txt
发布列表：https://github.com/norskhelo/jmbatch/releases
镜像转发 GitHub 附件，无需单独上传；可用性随缓存和网络变化。应用内更新仓库为 norskhelo/jmbatch。

6. 漫画库 / 收藏列表默认显示第一页封面，多章节取第一章第一页。无法读取时显示占位图；恢复文件或授权后点击刷新。

Windows 0.3.0 / Android 0.4.0 — 2026-10-15

收藏列表显示封面

• 已下载漫画 / 收藏界面新增封面缩略图，默认取漫画第一页；多章节取第一章第一页，按章节和页码顺序读取。
• 同时支持图片文件夹、ZIP 和 PDF。封面按比例缩放，保留完整页面；ZIP 内的下载信息、隐藏文件不作为封面。
• 封面在后台按可见列表加载，滚动和搜索时复用有限内存缓存，保留搜索、收藏、多选和批量操作。
• 文件缺失、损坏、加密或目录权限失效时显示占位图，不妨碍管理记录；恢复文件或授权后点击“刷新”可重试。
• 缩略图不写入漫画文件夹或 ZIP，保留既有纯图片成品结构。Android 读取系统目录中的 ZIP 时仅在应用缓存临时读取，完成后清理；超过 512 MB 的外部 ZIP 显示占位图。

版本与交付

• 按 0.x.0 递增：Windows 0.2.4 → 0.3.0；Android 0.3.4 → 0.4.0（versionCode 400）。保留 app.jmbatch.android 包名、原 APK 签名和更新公钥。
• 同步源码、使用说明、更新日志、安装包、SHA-256 校验文件和签名更新清单。
• 验证使用隔离素材、Windows 实际界面与成品自检、Android 宿主测试和编译；尚未连接 Android 真机验证厂商目录权限和界面显示。
