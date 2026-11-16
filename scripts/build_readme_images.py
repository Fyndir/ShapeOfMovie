"""Regenerate the images shown in the README from the JSON files in examples/.

python scripts/build_readme_images.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from shapeofmovie import MovieShape, render

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
OUT = ROOT / "docs" / "images"


def font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def gallery(shapes: list[MovieShape], width=1200, bar=110, label=34, pad=16) -> Image.Image:
    """Stack labelled barcodes on a dark background."""
    row = label + bar + pad
    img = Image.new("RGB", (width + 2 * pad, pad + row * len(shapes)), "#111")
    draw = ImageDraw.Draw(img)
    for i, shape in enumerate(shapes):
        y = pad + i * row
        draw.text((pad, y), shape.title, fill="#eee", font=font(22))
        img.paste(render(shape, "barcode", width=width, height=bar, smooth=9), (pad, y + label))
    return img


def load_examples(method: str) -> dict[str, MovieShape]:
    shapes = [MovieShape.load(p) for p in sorted((EXAMPLES / method).glob("*.json"))]
    return {s.title: s for s in shapes}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    avg, km = load_examples("mean"), load_examples("dominant")

    gallery(list(avg.values())).save(OUT / "gallery.png")

    spider = avg["Spider-Man Into the Spider-Verse"]
    render(spider, "barcode", width=1200, height=300, smooth=9).save(OUT / "style-barcode.png")
    render(spider, "vertical", width=300, height=500, smooth=9).save(OUT / "style-vertical.png")
    render(spider, "ring", width=500, smooth=9).save(OUT / "style-ring.png")

    pulp_avg, pulp_km = avg["Pulp Fiction"], km["Pulp Fiction"]
    pulp_avg.title, pulp_km.title = "Pulp Fiction — mean", "Pulp Fiction — dominant (k-means)"
    gallery([pulp_avg, pulp_km]).save(OUT / "methods.png")

    raw = render(spider, "barcode", width=600, height=120)
    smooth = render(spider, "barcode", width=600, height=120, smooth=30)
    both = Image.new("RGB", (1216, 120), "#111")
    both.paste(raw, (0, 0))
    both.paste(smooth, (616, 0))
    both.save(OUT / "smooth.png")
    print(f"images written to {OUT}")


if __name__ == "__main__":
    main()
