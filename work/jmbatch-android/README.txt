JM Batch 0.4.1 — Android 使用说明

1. 选择保存目录和 PDF、ZIP 或文件夹格式，输入编号或区间并加入队列，点击开始。格式选择会保存，已有任务继续或重试时保持原格式。
2. 默认同时下载 2 本。在“下载设置”中将“同时下载任务数”设为 1–4；“每个任务图片线程数”控制单本图片并发。
3. 调高任务数自动补位；调低时等待已运行任务结束。取消单个任务不会影响其他任务；暂停会停止全部下载并保留缓存。
4. 文件夹和 ZIP 只含图片：单章节平铺，多章节先分章节文件夹再平铺图片；下载后可在任务详情或漫画库将 PDF、ZIP、文件夹互相导出，源文件保留。PDF 转图片按页渲染，可能损失画质，作为一个章节。导出和文件删除前请暂停下载并等待请求退出。
5. Windows 完整解压 ZIP 后运行 JMBatch.exe；Android 覆盖安装 APK，保留设置、队列和收藏。Android 卸载应用可能删除应用目录中的图片，请事先备份。

安装包下载（2026-10-16）
GitHub：https://github.com/norskhelo/jmbatch/releases/download/release-0.3.1-0.4.1/JMBatch-0.4.1-Android.apk
国内镜像 1：https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.1-0.4.1/JMBatch-0.4.1-Android.apk
国内镜像 2：https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.1-0.4.1/JMBatch-0.4.1-Android.apk
SHA-256：https://github.com/norskhelo/jmbatch/releases/download/release-0.3.1-0.4.1/SHA256-release-0.3.1-0.4.1.txt
发布列表：https://github.com/norskhelo/jmbatch/releases
镜像转发 GitHub 附件，无需单独上传；可用性随缓存和网络变化。应用内更新仓库为 norskhelo/jmbatch。

6. 漫画库 / 收藏列表默认显示第一页封面，多章节取第一章第一页。无法读取时显示占位图；恢复文件或授权后点击刷新。

Windows 0.3.1 / Android 0.4.1 — 2026-10-16

三种下载格式与互相导出

• 新增任务可直接选择 PDF、ZIP 或图片文件夹，默认仍为文件夹；格式选择保存，下次打开继续使用。
• 下载格式在加入队列时确定；暂停、重启续传及手动重试保留原任务格式，不会被当前选择改写。
• 已下载漫画中的 PDF、ZIP、文件夹均可离线导出另外两种格式。任务详情和漫画库提供统一导出入口，保留源文件并拒绝覆盖同名成品。
• 文件夹与 ZIP 仅含图片：单章节图片平铺，多章节按章节分目录；ZIP 转文件夹保留 JPEG 图片字节，并按自然页码顺序读取旧图片包，忽略下载信息。
• PDF 转 ZIP / 文件夹按页渲染为 JPEG，可能损失画质；每页最高按 144 DPI、长边 8192 像素和约 1600 万像素限制处理，作为一个章节，不恢复原章节。文件夹 / ZIP 导出 PDF 仍支持合并或分章节。
• 转换支持取消和失败清理，临时文件与索引不写入最终图片目录或 ZIP；加密、损坏、空文件及异常 ZIP 路径会停止并提示。

合并已推送的续传修复

• 停止后再次开始保留已完成张数和图片大小；缓存校验独立显示，不触发网络低速重连，仅下载缺失或损坏页面。
• 本次安装包包含此前已推送但尚未发布安装包的大漫画续传修复。

版本与交付

• Windows 0.3.0 → 0.3.1；Android 0.4.0 → 0.4.1（versionCode 401）。保留原包名、APK 签名和更新公钥。
• 同步源码、使用说明、更新日志、安装包、SHA-256 和签名更新清单。
• 验证采用隔离素材、Windows 自动化界面及成品自检、Android 宿主测试和编译；未连接 Android 真机，未验证厂商 SAF 行为或真实网站下载。
