from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def make_icon(path: Path):
    sizes = [256,128,64,32,16]
    imgs = []
    for s in sizes:
        img = Image.new("RGBA", (s, s), (42, 131, 247, 255))
        d = ImageDraw.Draw(img)
        # rounded rectangle
        radius = int(s*0.2)
        d.rounded_rectangle([2,2,s-2,s-2], radius=radius, outline=(255,255,255,230), width=max(2,int(s*0.03)))
        # text
        text = "M2S"
        try:
            font = ImageFont.truetype("arial.ttf", int(s*0.38))
        except Exception:
            font = ImageFont.load_default()
        try:
            x0, y0, x1, y1 = d.textbbox((0,0), text, font=font)
            tw, th = x1 - x0, y1 - y0
        except Exception:
            tw, th = s//2, s//3
        d.text(((s-tw)//2,(s-th)//2-2), text, font=font, fill=(255,255,255,255))
        imgs.append(img)
    path.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].save(path, sizes=[(i.size[0], i.size[1]) for i in imgs])

if __name__ == "__main__":
    make_icon(Path(__file__).parent / "icon.ico")
