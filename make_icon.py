from PIL import Image, ImageDraw

def create_notchgent_icon():
    # Create base high-res 256x256 image with RGBA
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded background / Squircle badge
    bg_pad = 12
    draw.rounded_rectangle(
        [bg_pad, bg_pad, size - bg_pad, size - bg_pad],
        radius=52,
        fill=(15, 17, 23, 255),
        outline=(45, 49, 66, 255),
        width=3
    )

    # Dynamic Island Pill
    pill_w = 180
    pill_h = 70
    pill_x0 = (size - pill_w) // 2
    pill_y0 = (size - pill_h) // 2 - 10
    pill_x1 = pill_x0 + pill_w
    pill_y1 = pill_y0 + pill_h

    # Outer pill glow
    draw.rounded_rectangle(
        [pill_x0 - 2, pill_y0 - 2, pill_x1 + 2, pill_y1 + 2],
        radius=35,
        fill=(30, 32, 42, 180)
    )

    # Pill body (Deep OLED Black)
    draw.rounded_rectangle(
        [pill_x0, pill_y0, pill_x1, pill_y1],
        radius=35,
        fill=(5, 5, 8, 255),
        outline=(70, 75, 95, 255),
        width=2
    )

    # Green glowing status dot
    dot_radius = 10
    dot_cx = pill_x0 + 34
    dot_cy = (pill_y0 + pill_y1) // 2

    # Glow around dot
    draw.ellipse(
        [dot_cx - dot_radius - 4, dot_cy - dot_radius - 4, dot_cx + dot_radius + 4, dot_cy + dot_radius + 4],
        fill=(16, 185, 129, 60)
    )
    # Core dot
    draw.ellipse(
        [dot_cx - dot_radius, dot_cy - dot_radius, dot_cx + dot_radius, dot_cy + dot_radius],
        fill=(16, 185, 129, 255)
    )

    # Action bar / Soundwave bars on the right
    bars = [
        (pill_x0 + 75, 16),
        (pill_x0 + 95, 28),
        (pill_x0 + 115, 38),
        (pill_x0 + 135, 24),
        (pill_x0 + 152, 14),
    ]
    bar_w = 6
    for bx, bh in bars:
        by0 = dot_cy - bh // 2
        by1 = dot_cy + bh // 2
        draw.rounded_rectangle(
            [bx, by0, bx + bar_w, by1],
            radius=3,
            fill=(147, 197, 253, 230)
        )

    # Lower indicator text / glow line
    line_y = size - 50
    draw.rounded_rectangle(
        [size // 2 - 30, line_y, size // 2 + 30, line_y + 4],
        radius=2,
        fill=(100, 116, 139, 180)
    )

    # Save multi-resolution .ico
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save("app_icon.ico", format="ICO", sizes=icon_sizes)
    print("app_icon.ico generated successfully!")

if __name__ == "__main__":
    create_notchgent_icon()
