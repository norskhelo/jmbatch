# JM Batch Downloader

支持 Windows 和 Android 的批量漫画下载工具。下载默认保存排序图片；需要 PDF 或 ZIP 时，在下载完成后单独导出。

当前源码版本：**Windows 0.2.0 / Android 0.3.0（versionCode 300）**。对应正式安装包、更新日志及国内镜像入口见下方。

## 下载安装包（含国内镜像）

GitHub 下载缓慢或无法打开时，可直接点击“国内镜像 1”或“国内镜像 2”，在浏览器中下载，无需登录 GitHub。一个入口不可用时可切换另一个。

当前正式版为 **Windows 0.2.0 / Android 0.3.0**（[发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.2.0-0.3.0)）。完整附件及后续更新见 [Releases 页面](https://github.com/norskhelo/jmbatch/releases)。

| 文件 | 国内镜像 1（GHFast） | 国内镜像 2（GH-Proxy） | GitHub 原始下载 |
| --- | --- | --- | --- |
| Windows 0.2.0 · 完整 ZIP（64 位） | [下载 ZIP](https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.2.0-0.3.0/JMBatch-0.2.0-Windows-x64.zip) | [下载 ZIP](https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.2.0-0.3.0/JMBatch-0.2.0-Windows-x64.zip) | [下载 ZIP](https://github.com/norskhelo/jmbatch/releases/download/release-0.2.0-0.3.0/JMBatch-0.2.0-Windows-x64.zip) |
| Android 0.3.0 · APK（Android 8.0+） | [下载 APK](https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.2.0-0.3.0/JMBatch-0.3.0-Android.apk) | [下载 APK](https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.2.0-0.3.0/JMBatch-0.3.0-Android.apk) | [下载 APK](https://github.com/norskhelo/jmbatch/releases/download/release-0.2.0-0.3.0/JMBatch-0.3.0-Android.apk) |
| 上述版本的 SHA-256 校验文件 | [下载校验文件](https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.2.0-0.3.0/SHA256-release-0.2.0-0.3.0.txt) | [下载校验文件](https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.2.0-0.3.0/SHA256-release-0.2.0-0.3.0.txt) | [下载校验文件](https://github.com/norskhelo/jmbatch/releases/download/release-0.2.0-0.3.0/SHA256-release-0.2.0-0.3.0.txt) |

镜像由第三方提供下载加速。新发布附件可能需要等待镜像同步；不同地区和运营商的可用性可能变化，请按官方校验文件核对下载内容。镜像用于手动下载，应用内更新仓库仍填写 `norskhelo/jmbatch`。

下载后可按校验文件核对 SHA-256。Windows 完整解压 ZIP 后运行；Android 下载 APK 后覆盖安装，保留原应用数据。

## 下载与导出

1. 选择保存目录，输入编号、多个编号或区间，加入队列并开始。
2. 下载结果为图片文件夹。章节目录和图片名称补零排序，例如：

       JM123456-标题-任务标识/
         0001/00001.jpg
         0001/00002.jpg
         0002/00001.jpg
         .jmbatch-album.json

3. 在任务详情或“已下载漫画”选择图片漫画，点击“导出”。
4. 选择 PDF / ZIP、导出目录、纯编号命名及 ZIP 布局。多章节 PDF 可统一导出一本，或分章节导出；分章文件名附带章节序号。
5. 导出不删除图片，可离线重复导出。同名输出会停止并提示，不覆盖已有文件。

图片保存为下载处理后的原分辨率 JPG；保存、ZIP 打包及 PDF 嵌入不额外缩放。上游图片的必要解码/还原沿用原实现，不保证与网站原始响应逐字节相同。请保留图片目录中的清单和排序结构，供校验、恢复、扫描和导出使用。

## 其他功能

- 批量编号、JM 前缀、换行和连续区间；自动去重。
- 进度百分比、预计完成时间、图片大小及自适应下载速度单位。
- 可调线程、停滞重连、缓存复用和有上限的单页恢复。
- 连接失败自动尝试备用 API / 图片线路，显示明确原因。
- 漫画库支持排序图片目录及旧版 PDF / ZIP，提供搜索、收藏、扫描和批量管理。
- Windows 打开保存目录；Android 提供图片浏览、文件分享和系统文档入口。
- 签名更新清单、安装包摘要及 Android 签名身份验证。

已有 PDF / ZIP 记录和收藏保留。旧版未完成任务继续下载时改为图片目录并复用已验证缓存。删除图片目录会删除其中的原始图片，需要确认；只移除记录不会删除文件。导出和文件删除前请暂停下载队列。

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
