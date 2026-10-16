JM Batch 0.4.2 — Android 使用说明

1. 选择保存目录和 PDF、ZIP 或文件夹格式，输入编号或区间并加入队列，点击开始。格式选择会保存，已有任务继续或重试时保持原格式。
2. 默认同时下载 2 本。在“下载设置”中将“同时下载任务数”设为 1–4；“每个任务图片线程数”控制单本图片并发。
3. 调高任务数自动补位；调低时等待已运行任务结束。取消单个任务不会影响其他任务；暂停会停止全部下载并保留缓存。
4. 文件夹和 ZIP 只含图片：单章节平铺，多章节先分章节文件夹再平铺图片；下载后可在任务详情或漫画库将 PDF、ZIP、文件夹互相导出，源文件保留。PDF 转图片按页渲染，可能损失画质，作为一个章节。导出和文件删除前请暂停下载并等待请求退出。
5. Windows 完整解压 ZIP 后运行 JMBatch.exe；Android 覆盖安装 APK，保留设置、队列和收藏。Android 卸载应用可能删除应用目录中的图片，请事先备份。

安装包下载（2026-10-16）
GitHub：https://github.com/norskhelo/jmbatch/releases/download/release-0.3.2-0.4.2/JMBatch-0.4.2-Android.apk
国内镜像 1：https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.2-0.4.2/JMBatch-0.4.2-Android.apk
国内镜像 2：https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.2-0.4.2/JMBatch-0.4.2-Android.apk
SHA-256：https://github.com/norskhelo/jmbatch/releases/download/release-0.3.2-0.4.2/SHA256-release-0.3.2-0.4.2.txt
发布列表：https://github.com/norskhelo/jmbatch/releases
镜像转发 GitHub 附件，无需单独上传；可用性随缓存和网络变化。应用内更新仓库为 norskhelo/jmbatch。

6. 漫画库 / 收藏列表默认显示第一页封面，多章节取第一章第一页。无法读取时显示占位图；恢复文件或授权后点击刷新。

7. 从任务或漫画库打开后直接在软件内阅读。支持章节切换、本章/总页码、跳页、快捷收藏、书签列表及跳转；再次打开恢复上次页码和模式。滚动阅读与左右翻页可随时切换，Windows 使用滚轮、方向键或页面两侧，Android 使用上下滚动、左右滑动或页面两侧。PDF 按一个章节显示。阅读记录绑定原文件路径/地址；移动文件或清除应用数据后不自动迁移。Android 外部 ZIP 首次打开需准备临时缓存，返回可取消，关闭后清理。

Windows 0.3.2 / Android 0.4.2 — 2026-10-16

#软件内阅读

• 从下载任务或漫画库打开 PDF、ZIP、图片文件夹，直接进入内置阅读器。
• 支持章节列表、上一章/下一章、本章页码与总页码、输入总页码跳转。文件夹和 ZIP 按图片目录识别章节；PDF 作为一个章节，不恢复原章节。
• 阅读时可快捷收藏/取消收藏，与已有漫画库共用收藏记录。
• 支持添加、移除、查看和跳转书签。每本漫画分别保存书签、上次页码和阅读模式，重新打开恢复。
• 可在连续滚动与左右翻页之间切换。Windows 支持滚轮、方向键、PageUp/PageDown 和点击两侧；Android 支持上下滚动、左右滑动、点击两侧及按钮翻页。
• 页面按需后台加载，限制解码尺寸和缓存；关闭阅读器释放文件。阅读记录保存在应用内部，不向漫画文件夹或 ZIP 写入信息。
• Android 外部 ZIP 先复制到应用临时缓存再按页读取，关闭后清理；最多支持 8 GB 文件、20000 页。首次打开大文件需要等待，返回可取消。无效、加密或无权限文件显示错误，单页损坏可继续翻页。

#版本与验证

• Windows 0.3.1 → 0.3.2；Android 0.4.1 → 0.4.2（versionCode 402）。保留原包名、APK 签名和更新公钥。
• 同步源码、使用说明、更新日志、安装包、SHA-256 和签名更新清单。
• 验证使用隔离素材、Windows 自动化界面与冻结成品自检、Android 宿主测试和编译；Android 真机手势及厂商 SAF 行为未因编译通过而视为验证通过。
