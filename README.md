# JM Batch Downloader

面向 Windows 和 Android 的批量漫画下载与离线阅读工具。支持按编号建立下载队列，将漫画保存为 PDF、ZIP 或图片文件夹，并在本地管理、阅读和转换格式。

> **项目定位**：以个人自用为主，开发与维护基本依靠 AI 辅助完成，功能取舍优先围绕个人使用需求。

Windows 客户端使用 **Python / Tkinter**，Android 客户端使用 **Java / Android 原生 API**。两端独立实现，围绕下载队列、漫画库、阅读器和签名更新提供相近的使用体验。

[下载安装](#下载安装) · [开发入门](#开发入门) · [源码导览](#源码导览) · [参与贡献](#参与贡献) · [更新日志](CHANGELOG.md)

## 核心功能

| 能力 | 说明 |
| --- | --- |
| 批量下载 | 支持多个编号、JM 前缀和连续区间，自动去重；可选择部分章节或全部章节。 |
| 队列与恢复 | 多任务并行、暂停与继续、失败重试、缓存复用，以及备用 API / 图片线路。 |
| 格式与导出 | 下载为 PDF、ZIP 或图片文件夹；支持离线互转和批量导出，保留源文件。 |
| 漫画库 | 扫描本地内容、搜索、星标、收藏夹、列表 / 平铺显示及批量管理。 |
| 离线阅读 | 滚动阅读与左右翻页、章节切换、页码跳转、书签和阅读位置恢复。 |
| 更新 | 检查漫画新增章节；检查软件版本，并校验签名更新清单及安装包。 |

## 下载安装

| 平台 | 当前正式版 | 下载 | 发布说明与校验 |
| --- | --- | --- | --- |
| Windows x64 | **0.3.30** | [完整 ZIP](https://github.com/norskhelo/jmbatch/releases/download/release-0.3.30-0.6.12/JMBatch-0.3.30-Windows-x64.zip) | [发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.30-0.6.12) · [SHA-256](https://github.com/norskhelo/jmbatch/releases/download/release-0.3.30-0.6.12/SHA256-release-0.3.30-0.6.12.txt) |
| Android 8.0+ | **0.6.13** | [APK](https://github.com/norskhelo/jmbatch/releases/download/release-android-0.6.13/JMBatch-0.6.13-Android.apk) | [发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-android-0.6.13) · [SHA-256](https://github.com/norskhelo/jmbatch/releases/download/release-android-0.6.13/SHA256-release-android-0.6.13.txt) |

两端版本独立发布，最新一条 Release 可能只更新其中一个平台。完整历史与附件见 [Releases](https://github.com/norskhelo/jmbatch/releases)，功能变更见 [CHANGELOG.md](CHANGELOG.md)。

- **Windows**：完整解压 ZIP 后运行 `JMBatch.exe`，保留同目录的依赖文件。
- **Android**：安装 APK；更新正式版时覆盖安装，以保留应用数据。重要漫画请另行备份，卸载应用可能删除其内部目录。
- **软件更新**：在应用中点击“软件更新”，更新仓库使用 `norskhelo/jmbatch`；下载和安装需要手动确认。

<details>
<summary>GitHub 下载较慢时：备用镜像</summary>

| 文件 | GHFast | GH-Proxy |
| --- | --- | --- |
| Windows 0.3.30 ZIP | [下载](https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.30-0.6.12/JMBatch-0.3.30-Windows-x64.zip) | [下载](https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-0.3.30-0.6.12/JMBatch-0.3.30-Windows-x64.zip) |
| Android 0.6.13 APK | [下载](https://ghfast.top/https://github.com/norskhelo/jmbatch/releases/download/release-android-0.6.13/JMBatch-0.6.13-Android.apk) | [下载](https://gh-proxy.com/https://github.com/norskhelo/jmbatch/releases/download/release-android-0.6.13/JMBatch-0.6.13-Android.apk) |

镜像由第三方转发 GitHub Release 附件，可用性取决于线路与缓存。请使用上表的 GitHub 原始 SHA-256 文件核对下载内容；一个入口不可用时可切换另一个。

</details>

## 快速使用

1. 在下载设置中选择保存目录和 PDF / ZIP / 图片文件夹格式。
2. 输入一个或多个编号，加入队列并开始；按提示选择章节，也可在设置中启用“默认下载全章节”。
3. 下载完成后，在漫画库中打开阅读；需要转换格式或整理内容时，进入“批量处理”。

**暂停**保留续传数据；**取消未完成任务**会清理该任务的文件、缓存和队列记录。导出保留源文件，同名输出会跳过；只移除漫画库记录与删除实际文件是不同操作。

<details>
<summary>章节、收藏夹、格式与阅读说明</summary>

- **检查新增章节**：漫画库 → 批量处理（或长按）→ 选中一本 → 检查更新。先读取章节目录，有新增章节后再确认下载；新增内容独立保存，原漫画和阅读记录保留。缺少下载记录的导入漫画首次检查只建立目录基线。
- **收藏夹**：在漫画库中新建收藏夹，批量选择漫画后移入。分类不移动实际文件；删除收藏夹会将漫画归回默认库，保留文件、星标和阅读记录。
- **格式结构**：单章节 ZIP / 图片文件夹按 `00001.jpg`、`00002.jpg` 排列；多章节按 `0001/00001.jpg`、`0002/00001.jpg` 分目录。请保留目录名称与图片顺序，便于扫描和导出。
- **导出画质**：文件夹与 ZIP 互转、图片嵌入 PDF 不额外缩放；PDF 转图片需要渲染，可能损失画质，当前上限为 144 DPI、长边 8192 像素、每页约 1600 万像素。多章节 PDF 可合并导出或分章节导出。
- **删除章节**：支持图片目录和分章 ZIP，至少保留一章；PDF、平铺 ZIP 和单章漫画使用整本删除。操作前暂停下载，Windows 还需关闭对应阅读窗口，并预留临时空间。
- **阅读模式**：在下载设置中选择“多章节合一”或“分章节观看”，重新打开漫画后生效。两种模式共享书签和阅读位置；PDF、平铺 ZIP 和单章漫画按一个章节显示。
- **阅读位置**：绑定文件路径或地址；移动文件或清除应用数据后不会自动迁移。Android 外部 ZIP 首次打开需要准备临时缓存。
- **Android 相册**：漫画目录使用 `.nomedia` 减少系统相册收录，图片仍能在漫画库和文件管理器中访问；这不加密文件，旧缩略图可能需要等待系统缓存刷新。

</details>

## 开发入门

以下命令以 **Windows PowerShell** 为例，从仓库根目录执行。开发环境、依赖和生成物需要在本机准备。

```powershell
git clone https://github.com/norskhelo/jmbatch.git
cd jmbatch
```

### Windows 客户端

准备 **Python 3.14 x64（含 Tkinter）**。初始化脚本会创建 `work/venv`，安装 [固定版本依赖](work/jmbatch/requirements.txt) 和 PyInstaller；首次安装需要联网。已有虚拟环境时请直接复用，脚本不会覆盖它。

```powershell
# 首次初始化
.\tools\setup_windows.ps1

# 使用独立的开发配置目录，避免与日常使用的队列、设置混用
$env:JM_BATCH_HOME = Join-Path $PWD 'work\tests\dev-home'
.\work\venv\Scripts\python.exe .\work\jmbatch\app.py
```

运行 Python 单元测试：

```powershell
Push-Location .\work\jmbatch
try {
    ..\venv\Scripts\python.exe -m unittest discover -s tests -v
} finally {
    Pop-Location
}
```

执行隔离检查并构建可执行程序：

```powershell
.\work\jmbatch\build.ps1
```

构建入口会检查依赖、运行单元测试与源码自检，再打包并执行打包后的自检。可执行程序位于 `work/builds/windows-<version>/dist/JMBatch/JMBatch.exe`，检查日志位于 `outputs/reports/<run-id>/`。

### Android 客户端

项目采用 Java 和 Android 原生 API，配置见 [app/build.gradle](work/jmbatch-android/app/build.gradle)：`minSdk 26`、`targetSdk 34`、`compileSdk 35`，Android Gradle Plugin 为 **8.7.3**。

本地调试使用 **JDK 17、Gradle 8.9、Android SDK Platform 35 和 SDK Build Tools 34.0.0**，版本依据 [AGP 8.7 兼容性说明](https://developer.android.com/build/releases/agp-8-7-0-release-notes)。配置好 `JAVA_HOME`、`ANDROID_HOME`，并将 Gradle 加入 `PATH`。仓库尚未附带 Gradle Wrapper，因此下例使用已安装的 `gradle`。

```powershell
gradle -p .\work\jmbatch-android assembleDebug
```

调试 APK 输出到 `work/jmbatch-android/app/build/outputs/apk/debug/app-debug.apk`。调试签名与正式版不同，不能直接覆盖正式版；建议使用模拟器或独立测试设备。

[build.py](work/jmbatch-android/build.py) 是另一条用于 Windows 宿主检查和 APK 打包的构建路径，可通过 `--jdk`、`--sdk` 指定工具链，并要求已有 keystore。正式发布沿用维护者保管的原签名密钥，普通贡献者无需获取这些密钥。

### 测试范围

- **Windows**：单元测试位于 [work/jmbatch/tests](work/jmbatch/tests)，完整构建入口额外执行源码与打包自检。
- **Android**：[宿主测试](work/jmbatch-android/tests) 由 `build.py` 调用；[框架回归测试](work/jmbatch-android/tests/runtime/README.md) 使用 Robolectric，覆盖阅读、漫画库、权限与存储等场景。
- Android 框架测试的 [运行脚本](work/scripts/maintenance/run_android_runtime_tests.py) 当前使用 `work/android-tools/jdk-17.0.20.1+1` 和 `work/android-tools/android-35/android.jar` 固定路径；运行前需按脚本配置准备工具链。Maven 与测试依赖首次运行会联网下载。
- 宿主测试和编译成功不能代替真机验证。涉及文件选择器、SAF 授权、厂商界面或网络行为的改动，请在 PR 中注明设备、系统版本和实际验证范围。

## 源码导览

| 目录 / 文件 | 用途与阅读入口 |
| --- | --- |
| [work/jmbatch](work/jmbatch) | Windows 客户端。`app.py` 为界面入口，`engine.py` 调度队列，`worker.py` 执行下载；`library*`、`reader*`、`updates.py` 分别处理漫画库、阅读和软件更新。 |
| [work/jmbatch-android/app/src/main/java/app/jmbatch/android](work/jmbatch-android/app/src/main/java/app/jmbatch/android) | Android 客户端。`MainActivity.java` 为主界面，`DownloadService.java` / `Downloader.java` 处理下载，`JmApi.java` 负责上游请求，`ReaderActivity.java` 为阅读入口。 |
| [tools/setup_windows.ps1](tools/setup_windows.ps1) | 初始化 Windows Python 开发环境。 |
| [work/scripts/maintenance](work/scripts/maintenance) | 构建检查、回归测试与历史维护脚本；新贡献者可从 `check_development.py` 和 `run_android_runtime_tests.py` 开始。 |
| [work/package_network_update.py](work/package_network_update.py) · [work/sign_update_release.py](work/sign_update_release.py) | 维护者使用的发布打包与更新清单签名工具。 |
| [CHANGELOG.md](CHANGELOG.md) · [CONTRIBUTING.md](CONTRIBUTING.md) | 版本变更记录，以及版本号、发布附件和签名更新约定。 |

Windows 依赖 `jmcomic` 等 Python 库；Android 的协议与图片还原逻辑参考 `jmcomic`，通过原生 API 实现，不内嵌 Python 运行时。两端的业务改动需要分别检查实现与行为。

## 参与贡献

项目以自用为主，同时欢迎通过 [Issues](https://github.com/norskhelo/jmbatch/issues) 反馈问题、提出改进，或提交 [Pull Request](https://github.com/norskhelo/jmbatch/pulls)。文档纠错、复现用例、设备兼容性反馈和代码改进都可以参与。

> 虽说欢迎参与，但还是不建议在这个项目上浪费时间

1. 先搜索已有 Issue；较大的功能或结构调整，建议先描述使用场景和预期行为。
2. Fork 仓库并创建分支，围绕一个明确问题提交改动。
3. 为行为变更补充适当的回归验证，说明影响 Windows、Android 还是双端；涉及用户行为变化时同步更新 `CHANGELOG.md`。
4. 在 PR 中写明问题、改动后的行为、验证命令与结果，以及尚未验证的环境。

反馈 Bug 时，请提供：

- 应用版本、操作系统版本；Android 问题附设备型号。
- 最小复现步骤、预期行为和实际结果。
- 与问题有关的报错、日志或截图，提交前移除账号、Cookie、令牌及私人路径。
- 涉及文件问题时说明格式（PDF / ZIP / 图片文件夹）与保存位置类型，优先提供不含私人内容的合成样例。

签名私钥、账号凭据、个人配置和下载内容不进入仓库。正式发布的版本、附件与签名约定见 [CONTRIBUTING.md](CONTRIBUTING.md)；源码提交和正式安装包发布是独立步骤。

## 项目边界与第三方许可

本工具为独立第三方项目，与内容平台无隶属关系。请仅下载有权获取和保存的内容，遵守所在地法律及相关平台条款。下载可用性受网络和上游服务影响。

第三方依赖说明见 [Windows 许可目录](work/jmbatch/THIRD_PARTY_LICENSES) 和 [Android 第三方声明](work/jmbatch-android/THIRD_PARTY_NOTICES.txt)。当前仓库未提供项目级 `LICENSE` 文件；第三方依赖的许可记录不代表本项目整体采用相同许可证。
