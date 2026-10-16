"""Prepare the authorized Android save optimization and shared concurrency setting release."""
from pathlib import Path
import json
import re

root = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.8 / Android 0.4.8 — 2026-10-16

## Android 图片文件夹校验与保存优化

- 图片直接复制到目标目录的临时文件夹，减少一遍完整中间复制；复制时计算源 CRC，写入完成后完整读回目标文件核验大小和 CRC。
- 保留默认目录逐文件刷盘、同名拒绝覆盖、失败清理和最终重命名；完成标记保存后才清理下载缓存。暂停或写入失败保留原图片缓存，重试可继续复用。
- 校验显示已检查张数；保存和读回校验显示张数与字节进度；核对目录、清理临时图片也显示进度。任务完成前总百分比仍以已下载图片为基础，上限为 99.9%，实际收尾进度看阶段文字。
- 核对成品时复用一次章节根目录枚举，避免逐章重复扫描。默认目录和自选系统目录都减少中间复制；系统目录实际速度仍取决于存储提供方。
- 对同样的图片有效载荷，复制与 CRC 的整图逻辑读写由 4 次读 + 2 次写减少为 2 次读 + 1 次写；不把此比例等同于耗时或闪存物理流量的减少比例。

## 双端章节读取并行数可配置

- Windows 与 Android 设置中加入“每个任务章节读取并行数”，范围 1–8，默认 4，独立于图片线程数。原配置和已有任务缺少此字段时使用 4。
- 网络稳定时可试 6 或 8；更高并行数不保证更快，出现超时或限流可调低。同时下载多本时，章节请求数会叠加。
- 设置用于新任务及手动重试；运行中任务和直接暂停后继续保留原设置。想让已有任务使用新值，先暂停、保存设置，再手动重试。
- 读取提示显示实际配置上限；保留选中章节、原编号顺序、24 小时章节缓存和图片断点续传。

## 版本与验证

- Windows 0.3.8；Android 0.4.8（versionCode 408），沿用原包名、APK 签名证书及更新公钥。
- 覆盖单章/多章保存、输出字节一致、CRC 不一致、截断/多余字节、写入/刷盘失败、中途暂停、重试、同名保护、清理边界和进度；双端验证 1、4、8 章并行及缓存复用。
- Windows 执行回归测试、源码及冻结成品自检；Android 执行宿主测试、编译和签名核验，未连接 Android 真机。宿主文件测试不代表手机保存耗时。
- 同步源码、使用说明、同版日志、安装包、SHA-256 校验文件及签名更新清单。
'''
folder = root / 'work/release-038-048'
folder.mkdir(exist_ok=True)
(folder / 'release-notes.md').write_text(notes, encoding='utf-8')
changelog = root / 'CHANGELOG.md'
if not changelog.read_text(encoding='utf-8').startswith(notes):
    changelog.write_text(notes + '\n' + changelog.read_text(encoding='utf-8'), encoding='utf-8')
for name in ['work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml', 'work/jmbatch-android/app/build.gradle',
             'README.md', 'work/jmbatch/README.txt', 'work/jmbatch-android/README.txt']:
    p = root / name
    value = p.read_text(encoding='utf-8').replace('0.3.7','0.3.8').replace('0.4.7','0.4.8')
    value = value.replace('versionCode 407','versionCode 408').replace('versionCode="407"','versionCode="408"')
    value = value.replace('本版优化多章节读取：最多 4 章并行，并缓存章节信息以加快暂停后的继续下载。',
                          '本版优化 Android 图片文件夹的校验与保存，并为双端加入 1–8 章读取并行数配置（默认 4）。')
    value = value.replace('每任务最多 4 章并行读取，图片线程数不影响此上限。',
                          '每任务可配置 1–8 章并行读取，默认 4，独立于图片线程。新值用于新任务和手动重试，直接继续保留原设置。可试 6 或 8，超时或限流时调低。')
    p.write_text(value, encoding='utf-8')
for name in ['README.md','work/jmbatch-android/README.txt']:
    p=root/name;value=p.read_text(encoding='utf-8')
    addition='\nAndroid 图片保存：一次复制到目标临时目录，复制时计算源 CRC，写后完整读回目标核验；默认目录保留刷盘。校验、保存/读回、核对目录、清理显示进度，减少重复复制和章节目录扫描。总百分比完成前上限 99.9%，请查看阶段张数和字节进度。\n'
    if addition.strip() not in value:p.write_text(value+addition,encoding='utf-8')
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ['work/jmbatch/README.txt','work/jmbatch-android/README.txt']:
    p=root/name;value=p.read_text(encoding='utf-8')
    body=value.split('\nWindows 0.3.8 / Android 0.4.8 — 2026-10-16\n',1)[0].rstrip()
    if '\n章节选择说明\n' not in body:
        body+='\n\n章节选择说明\n\n多章节在获取列表后选择下载范围，支持多选、全选和稍后选择。设置中可默认下载全章节；单章直接下载。选中范围随任务保存，保留原章节编号，暂停和重试不增加未选择的章节。\n'
    p.write_text(body+'\n\n'+plain,encoding='utf-8')
for name in ['work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java']:
    p=root/name;value=p.read_text(encoding='utf-8')
    value=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if name.endswith('.java') else ''),value)
    p.write_text(value,encoding='utf-8')
for prefix in ['prepare_publication','publish']:
    source=root/f'work/scripts/release/{prefix}_037_047.py'
    value=source.read_text(encoding='utf-8').replace('0.3.7','0.3.8').replace('0.4.7','0.4.8').replace('037-047','038-048').replace('多章节读取提速与缓存','图片保存优化与章节并行配置')
    (source.parent/f'{prefix}_038_048.py').write_text(value,encoding='utf-8')
source=root/'work/scripts/maintenance/verify_chapter_metadata_online.py'
value=source.read_text(encoding='utf-8').replace("'0.3.6'","'previous-version'").replace('0.3.7','0.3.8').replace("'previous-version'","'0.3.7'").replace('0.4.7','0.4.8').replace('037-047','038-048').replace('chapter-metadata','folder-save').replace('多章节读取提速与缓存','图片文件夹校验与保存优化')
value=value.replace("'0.3.5', '0.3.7', '0.3.8'","'0.3.5', '0.3.6', '0.3.7', '0.3.8'")
(source.parent/'verify_folder_save_online.py').write_text(value,encoding='utf-8')
print('Prepared Windows 0.3.8 / Android 0.4.8 release documents and recipes')
