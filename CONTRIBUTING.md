# 更新约定

- 未明确指定平台时，默认同时更新 Windows 和 Android。
- 每次更新必须同步维护 CHANGELOG.md，并在 GitHub Release 中填写对应更新日志。
- 两端版本独立递增；安装包名使用 JMBatch-x.y.z-Windows-x64.zip 和 JMBatch-x.y.z-Android.apk。
- Android 保持包名、签名密钥，并递增 versionCode。
- 先构建、验证、上传完整附件，再发布正式 Release；草稿和预发布不会触发软件更新提示。
- 签名私钥、账号凭据、个人配置及下载内容不进入仓库或发布附件。

## 签名更新发布

- Windows 0.1.6 / Android 0.2.5 起，正式 Release 除双端安装包，还必须包含 `update-manifest.json` 和 `update-manifest.sig`。
- 清单 schema 为 1，绑定 repository、tag，以及 packages.windows / packages.android 的 version、name、size、sha256。
- 对清单原始 UTF-8 字节作 RSA-SHA256（PKCS#1 v1.5）签名；签名文件保存原始二进制，不是 Base64。签名后不得修改清单或安装包。
- 必须沿用现有发布私钥，客户端内置对应公钥。单独发布 SHA-256 文本不能替代数字签名。
- 更新清单签名与安卓 APK 签名是两套密钥，都需离线妥善备份；不得上传私钥。
- 上传草稿全部附件并核对远端摘要后再正式发布。
