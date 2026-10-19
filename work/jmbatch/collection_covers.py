"""Small local-only folder previews, loaded through the existing cover worker."""
from PIL import Image, ImageDraw, ImageOps


def load_collection_cover(children, load):
    preview = Image.new("RGB", (144, 192), "#e8edf1")
    draw = ImageDraw.Draw(preview)
    draw.rounded_rectangle((4, 4, 139, 187), radius=10, fill="#d9e6ef", outline="#8da4b5", width=2)
    draw.rectangle((12, 12, 67, 23), fill="#8da4b5")
    for index, (path, fmt) in enumerate(children[:4]):
        x, y = 12 + (index % 2) * 64, 30 + (index // 2) * 76
        draw.rectangle((x, y, x + 55, y + 69), fill="#f5f7fa", outline="#b5c4ce")
        image = load(path, fmt)
        if image is not None:
            image = ImageOps.contain(image.convert("RGB"), (56, 70))
            preview.paste(image, (x + (56-image.width)//2, y + (70-image.height)//2))
    return preview.resize((72, 96), Image.Resampling.LANCZOS)
