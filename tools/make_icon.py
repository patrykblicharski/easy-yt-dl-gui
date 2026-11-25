"""Generates the Easy yt-dl-gui logo: a blue rounded play button with a download badge.

Output: ytddlg/assets/ytddlg.ico (window / .exe icon) and ytddlg/assets/logo.png (app header).
Run: .venv\\Scripts\\python tools\\make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "ytddlg" / "assets"
S = 1024  # draw at high resolution and downscale (smooth edges)

TOP, BOTTOM = (59, 130, 246), (29, 78, 216)  # #3b82f6 -> #1d4ed8


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # button: horizontal rounded rectangle with a vertical gradient
    box = (40, 190, S - 40, S - 190)
    grad = Image.new("RGB", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        gd.line([(0, y), (S, y)], fill=lerp(TOP, BOTTOM, y / S))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=200, fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    # white play triangle
    cx, cy = S // 2 - 20, S // 2
    d.polygon([(cx - 120, cy - 165), (cx - 120, cy + 165), (cx + 175, cy)], fill="white")

    # download badge: white circle in the bottom-right corner with a blue down arrow
    r = 150
    bx, by = S - 40 - r + 10, S - 190 - r + 40
    d.ellipse((bx - r, by - r, bx + r, by + r), fill="white")
    d.ellipse((bx - r + 22, by - r + 22, bx + r - 22, by + r - 22), fill=BOTTOM)
    w = 34
    d.rounded_rectangle((bx - w, by - 95, bx + w, by + 20), radius=14, fill="white")
    d.polygon([(bx - 85, by + 5), (bx + 85, by + 5), (bx, by + 95)], fill="white")
    return img


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    big = make()
    big.resize((256, 256), Image.LANCZOS).save(
        ASSETS / "ytddlg.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    big.resize((128, 128), Image.LANCZOS).save(ASSETS / "logo.png")
    print(ASSETS / "ytddlg.ico")
