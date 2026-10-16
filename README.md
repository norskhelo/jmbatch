# JM Batch Downloader

支持 Windows 和 Android 的批量漫画下载工具。下载可选择 PDF、ZIP 或图片文件夹，三种成品可离线互相导出。

当前源码及正式版本：**Windows 0.3.4 / Android 0.4.4（versionCode 404）**。本版支持下载过程中在任务列表显示首章第一页封面，暂停、续传和下载完成后均可查看。安装包、更新日志与镜像入口见下方。

## 下载安装包（含国内镜像）

GitHub 下载缓慢或无法打开时，可直接点击“国内镜像 1”或“国内镜像 2”，在浏览器中下载，无需登录 GitHub。一个入口不可用时可切换另一个。

当前正式版为 **Windows 0.3.4 / Android 0.4.4**（[发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.4-0.4.4)）。完整附件及后续更新见 [Releases 页面](https://github.com/norskhelo/jmbatch/releases)。

| 文件 | 国内镜像 1（GHFast） | 国内镜像 2（GH-Proxy） | GitHub 原始下载 |
| --- | --- | --- | --- |
| Windows 0.3.4 · 完整 ZIP（64 位） | [下载 ZIP](https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.4-0.4.4/JMBatch-0.3.4-Windows-x64.zip) | [下载 ZIP](https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.4-0.4.4/JMBatch-0.3.4-Windows-x64.zip) | [下载 ZIP](https://github.com/norskhelo/jmbatch/releases/download/release-0.3.4-0.4.4/JMBatch-0.3.4-Windows-x64.zip) |
| Android 0.4.4 · APK（Android 8.0+） | [下载 APK](https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.4-0.4.4/JMBatch-0.4.4-Android.apk) | [下载 APK](https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.4-0.4.4/JMBatch-0.4.4-Android.apk) | [下载 APK](https://github.com/norskhelo/jmbatch/releases/download/release-0.3.4-0.4.4/JMBatch-0.4.4-Android.apk) |
| 上述版本的 SHA-256 校验文件 | [下载校验文件](https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.4-0.4.4/SHA256-release-0.3.4-0.4.4.txt) | [下载校验文件](https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.4-0.4.4/SHA256-release-0.3.4-0.4.4.txt) | [下载校验文件](https://github.com/norskhelo/jmbatch/releases/download/release-0.3.4-0.4.4/SHA256-release-0.3.4-0.4.4.txt) |

镜像由第三方转发 GitHub Release 的附件，无需向镜像站单独上传安装包。可用性受缓存、线路及地区网络影响，请按官方校验文件核对下载内容。镜像用于手动下载，应用内更新仓库仍填写 `norskhelo/jmbatch`。已安装更高版本的用户无需下载旧版降级。

下载后可按校验文件核对 SHA-256。Windows 完整解压 ZIP 后运行；Android 下载 APK 后覆盖安装，保留原应用数据。

## 下载与导出

1. 选择保存目录和 PDF / ZIP / 文件夹格式，输入编号、多个编号或区间，加入队列并开始。
2. PDF 下载为一本文件；文件夹与 ZIP 仅包含图片。单章节根目录直接是 `00001.jpg`、`00002.jpg`；多章节结构如下，ZIP 使用相同规则：

       JM123456-标题-任务标识/
         0001/00001.jpg
         0001/00002.jpg
         0002/00001.jpg

3. 在任务详情或“已下载漫画”选择任一 PDF、ZIP 或图片文件夹，点击“导出”。
4. 选择 PDF / ZIP / 文件夹和导出目录；PDF / ZIP 可选纯编号命名；ZIP 结构自动按章节数确定。多章节 PDF 可统一导出一本，或分章节导出；分章文件名附带章节序号。
5. 导出不删除源文件，可离线重复导出。同名输出会停止并提示，不覆盖已有文件。

图片保存为下载处理后的原分辨率 JPG；文件夹和 ZIP 互转、图片嵌入 PDF 不额外缩放。PDF 转图片会按页面渲染，作为一个章节，可能损失画质；最高 144 DPI，长边最多 8192 像素，每页约 1600 万像素。上游图片的必要解码/还原沿用原实现，不保证与网站原始响应逐字节相同。请保留漫画文件夹名称和图片排序结构，便于重新扫描与导出。恢复与校验信息保存在应用内部，成品目录不附带信息文件；旧版带清单的图片目录仍可读取。

## 下载封面

下载列表会在首章第一页成功下载后自动显示封面，无需等待整本完成；暂停、继续和重启后可从缓存恢复。尚未就绪或无法读取时显示占位，完成后从 PDF、ZIP 或文件夹成品读取。

## 内置阅读器

从任务或漫画库打开后直接在软件内阅读。支持章节切换、本章/总页码、跳页、快捷收藏、书签列表及跳转；再次打开恢复上次页码和模式。滚动阅读与左右翻页可随时切换，Windows 使用滚轮、方向键或页面两侧，Android 使用上下滚动、左右滑动或页面两侧。PDF 按一个章节显示。阅读记录绑定原文件路径/地址；移动文件或清除应用数据后不自动迁移。Android 外部 ZIP 首次打开需准备临时缓存，返回可取消，关闭后清理。

## 更新公告

更新公告随后台检查结果刷新；升级后保留本次升级起点和全部中间版本日志，重启或再次检查仍可查看。未来新版另列为“可用更新”。日志未取全时保留本版说明并明确提示，联网检查后补齐。

## 其他功能

- 批量编号、JM 前缀、换行和连续区间；自动去重。
- 进度百分比、预计完成时间、图片大小及自适应下载速度单位。
- 同时下载 1–4 本（默认 2），每本 1–16 个图片线程（默认 8）；独立进度、取消和重连，总速度汇总。
- 并行任务数保存后用于后续调度，调低不打断已运行任务；暂停会停止全部下载。
- 可调线程、停滞重连、缓存复用和有上限的单页恢复。
- 连接失败自动尝试备用 API / 图片线路，显示明确原因。
- 漫画库支持排序图片目录及旧版 PDF / ZIP，提供搜索、收藏、扫描和批量管理。
- Windows 打开保存目录；Android 提供图片浏览、文件分享和系统文档入口。
- 从当前版本之后至最新版的全部更新日志，支持完整离线缓存。
- 签名更新清单、安装包摘要及 Android 签名身份验证。

已有 PDF / ZIP 记录和收藏保留。未完成任务继续下载和重试时保留原格式，并复用已验证缓存。删除图片目录会删除其中的原始图片，需要确认；只移除记录不会删除文件。导出和文件删除前请暂停下载队列。

## 源码与构建

- Windows：`work/jmbatch`，构建入口 `work/jmbatch/build.ps1`。
- Android：`work/jmbatch-android`，构建入口 `work/jmbatch-android/build.py`；需要 JDK 17、Android SDK 35 与 build-tools。
- 打包：`work/package_network_update.py`；正式签名需要独立保管的原密钥，不包含在仓库中。
- 用户更新日志：[CHANGELOG.md](CHANGELOG.md)。

测试采用离线素材和宿主环境。Android 真机、厂商文件管理器、SAF 授权和真实网络下载未因编译通过而视为验收通过。

## 安装与更新

通过上方“下载安装包（含国内镜像）”或 [Releases 页面](https://github.com/norskhelo/jmbatch/releases) 下载已发布版本的完整 Windows ZIP 或 Android APK。Windows 解压后运行；Android 支持 8.0 及以上。正常更新保留队列、设置与收藏，Android 请覆盖安装而非卸载重装。应用内部目录可能在卸载后被系统删除，重要图片请选择公共目录或另行备份。

应用内更新只接受项目原发布密钥签署的清单和对应安装包。新源码推送不等于发布了可供应用内下载的安装包。

## 说明

本工具为独立第三方项目，与内容平台无隶属关系。可用性受网络和上游服务影响。请仅下载有权获取和保存的内容，并遵守所在地法律和相关平台条款。反馈问题时请提供版本、系统和报错，避免公开账号、Cookie 等敏感信息。
