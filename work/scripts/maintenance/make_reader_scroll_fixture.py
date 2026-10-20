"""Generate harmless numbered JPEGs for offline Android reader reproduction."""
from pathlib import Path
import hashlib
import io
import json
import zipfile
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs/reports/reader-scroll-fix-reproduction"
OUT.mkdir(parents=True, exist_ok=True)
TARGET = OUT / "JM999999999-Scroll-Repro-20261020.zip"
dimensions = [(1600, 2400), (2400, 1200), (1200, 3600)]
colors = ["#ddebf7", "#fbe4cf", "#e2efd9"]
font_path = Path("C:/Windows/Fonts/arial.ttf")
font = ImageFont.truetype(str(font_path), 110) if font_path.is_file() else ImageFont.load_default(size=110)
manifest = []
with zipfile.ZipFile(TARGET, "w", zipfile.ZIP_DEFLATED) as archive:
    for index in range(42):
        width, height = dimensions[index % 3]
        with Image.new("RGB", (width, height), colors[index % 3]) as image:
            draw = ImageDraw.Draw(image)
            for y in range(0, height, 200):
                draw.line((0, y, width, y), fill="#7a8897", width=3)
            draw.text((70, 70), f"PAGE {index+1:02d}", fill="#142a40", font=font)
            draw.text((70, 220), f"{width} x {height}", fill="#142a40", font=font)
            draw.text((70, height - 170), f"END {index+1:02d}", fill="#142a40", font=font)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=80)
        data = buffer.getvalue()
        name = f"{index+1:05d}.jpg"
        archive.writestr(name, data)
        manifest.append({"file": name, "width": width, "height": height, "sha256": hashlib.sha256(data).hexdigest()})
with zipfile.ZipFile(TARGET) as archive:
    assert archive.testzip() is None and len(archive.namelist()) == 42
    for entry in manifest:
        with Image.open(io.BytesIO(archive.read(entry["file"]))) as image:
            assert image.size == (entry["width"], entry["height"])
(OUT / "fixture.json").write_text(json.dumps({"zip": TARGET.name, "sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(), "pages": manifest}, indent=2), encoding="utf-8")
print(TARGET)
