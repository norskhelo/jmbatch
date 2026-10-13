# 更新约定

- 未明确指定平台时，默认同时更新 Windows 和 Android。
- 每次更新必须同步维护 CHANGELOG.md，并在 GitHub Release 中填写对应更新日志。
- 两端版本独立递增；安装包名使用 JMBatch-x.y.z-Windows-x64.zip 和 JMBatch-x.y.z-Android.apk。
- Android 保持包名、签名密钥，并递增 versionCode。
- 先构建、验证、上传完整附件，再发布正式 Release；草稿和预发布不会触发软件更新提示。
- 签名私钥、账号凭据、个人配置及下载内容不进入仓库或发布附件。
