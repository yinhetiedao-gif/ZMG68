from pathlib import Path
from PIL import Image, ImageDraw
import math

ROOT = Path(__file__).parent


def canvas(name="test", size=(256, 256)):
    image = Image.new("L", size, "white"); return image, ImageDraw.Draw(image)


def main():
    image, draw = canvas(); cx = cy = 128
    for index in range(10):
        angle = 2 * math.pi * index / 10; x = cx + 82 * math.cos(angle); y = cy + 82 * math.sin(angle); r = 5 + (index % 3) * 2; draw.ellipse((x-r, y-r, x+r, y+r), fill="black")
    image.save(ROOT / "test_dot_star.png")

    image, draw = canvas()
    for row in range(12):
        for col in range(12):
            x, y = 20 + col * 19, 20 + row * 19; radius = 2 + int((col + row) / 22 * 6); draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill="black")
    image.save(ROOT / "test_dot_gradient.png")

    image, draw = canvas()
    for row in range(12):
        for col in range(12):
            x, y = 20 + col * 19, 20 + row * 19; draw.ellipse((x-4, y-4, x+4, y+4), fill="black")
    image.save(ROOT / "test_dot_grid.png")

    image, draw = canvas(); cx = cy = 128
    for ring, count in ((1, 8), (2, 14), (3, 20)):
        radius = ring * 30
        for index in range(count):
            angle = 2 * math.pi * index / count + ring * .15; x = cx + radius * math.cos(angle); y = cy + radius * math.sin(angle); draw.ellipse((x-5, y-5, x+5, y+5), fill="black")
    image.save(ROOT / "test_radial_dot.png")

    image, draw = canvas()
    for row in range(11):
        for col in range(15):
            x = 14 + col * 16; y = 35 + row * 18 + 9 * math.sin(col * .55); draw.ellipse((x-4, y-4, x+4, y+4), fill="black")
    image.save(ROOT / "test_wave_dot.png")

    image, draw = canvas(); draw.ellipse((90, 112, 132, 154), fill="black"); draw.ellipse((124, 112, 166, 154), fill="black")
    image.save(ROOT / "test_touching_dots.png")


if __name__ == "__main__": main()

