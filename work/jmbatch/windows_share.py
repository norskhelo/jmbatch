"""Open the installed Windows sharing command; never choose a recipient."""
import base64
import subprocess
import uuid
import zipfile
from pathlib import Path


def prepare(files, home, cancelled=lambda: False):
    files = [Path(file) for file in files]
    if len(files) == 1:
        return files[0]
    folder = Path(home) / 'share'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ('JMBatch-' + uuid.uuid4().hex[:8] + '.zip')
    try:
        with zipfile.ZipFile(target, 'x', zipfile.ZIP_STORED) as archive:
            for index, file in enumerate(files, 1):
                with file.open('rb') as source, archive.open(f'{index:03d}-{file.name}', 'w', force_zip64=True) as output:
                    while block := source.read(1024 * 1024):
                        if cancelled(): raise InterruptedError('已取消分享准备')
                        output.write(block)
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise


def show(path):
    # Shell supplies the localized, installed Share verb. Do not guess handler IDs.
    quoted = str(Path(path).absolute()).replace("'", "''")
    script = f"""$ErrorActionPreference='Stop'
$path='{quoted}'
$shell=New-Object -ComObject Shell.Application
$folder=$shell.NameSpace([IO.Path]::GetDirectoryName($path))
$item=$folder.ParseName([IO.Path]::GetFileName($path))
$verb=$item.Verbs() | Where-Object {{ ($_.Name -replace '[(&)]','').Trim() -match '^(共享|分享|Share)(S)?$' }} | Select-Object -First 1
if ($null -eq $verb) {{ throw 'Windows 未提供可用的分享菜单，请从保存目录分享文件。' }}
$verb.DoIt()
"""
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-STA', '-EncodedCommand', encoded],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
    if result.returncode:
        raise OSError('无法打开 Windows 分享菜单，请从保存目录分享文件。')
