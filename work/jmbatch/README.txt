JM Batch 0.2.4 — Windows 使用说明

1. 选择保存目录，输入编号或区间并加入队列，点击开始。
2. 默认同时下载 2 本。在“下载设置”中将“同时下载任务数”设为 1–4；“每个任务图片线程数”控制单本图片并发。
3. 调高任务数自动补位；调低时等待已运行任务结束。取消单个任务不会影响其他任务；暂停会停止全部下载并保留缓存。
4. 文件夹和 ZIP 只含图片：单章节平铺，多章节先分章节文件夹再平铺图片；下载后可在任务详情或漫画库单独导出 PDF / ZIP。导出和文件删除前请暂停下载并等待请求退出。
5. Windows 完整解压 ZIP 后运行 JMBatch.exe；Android 覆盖安装 APK，保留设置、队列和收藏。Android 卸载应用可能删除应用目录中的图片，请事先备份。

安装包下载（2026-10-15）
GitHub：https://github.com/norskhelo/jmbatch/releases/download/release-0.2.4-0.3.4/JMBatch-0.2.4-Windows-x64.zip
国内镜像 1：https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.2.4-0.3.4/JMBatch-0.2.4-Windows-x64.zip
国内镜像 2：https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.2.4-0.3.4/JMBatch-0.2.4-Windows-x64.zip
SHA-256：https://github.com/norskhelo/jmbatch/releases/download/release-0.2.4-0.3.4/SHA256-release-0.2.4-0.3.4.txt
发布列表：https://github.com/norskhelo/jmbatch/releases
镜像转发 GitHub 附件，无需单独上传；可用性随缓存和网络变化。应用内更新仓库为 norskhelo/jmbatch。

Windows 0.2.4 / Android 0.3.4 — 2026-10-15

图片目录与 ZIP 统一结构

• 新下载的图片文件夹和新导出的 ZIP 只包含图片，不再附带“下载信息.json”或“.jmbatch-album.json”等下载信息文件。
• 单章节直接平铺为 00001.jpg、00002.jpg……；多章节先按 0001、0002……分文件夹，每章内再平铺按页码排序的图片。
• 移除导出窗口中的 ZIP 平铺开关，自动按章节数选择上述结构；旧设置不会改变新规则。
• 排序、恢复与完整性校验信息保存在应用内部。保留名称与页码结构的新版图片目录复制或移动后可重新扫描、离线导出。
• 旧版图片目录仍可读取并导出为新结构；已有文件不会被批量改写，需获得新结构时可重新下载或重新导出 ZIP。

版本与交付

• Windows 升至 0.2.4；Android 升至 0.3.4（versionCode 304），沿用 app.jmbatch.android 包名、原 APK 签名与更新公钥。
• 同步双端使用说明、源码、更新日志、安装包、SHA-256 校验文件和签名更新清单。
• 验证采用隔离离线素材、Windows 自动检查及 Android 宿主测试和编译；不将这些检查视为 Android 真机、SAF 厂商兼容性或真实网站下载验证。
