#!/usr/bin/env python3
"""
Multi-monitor wallpaper combiner for Linux Mint Cinnamon
Combines 2-3 images into a single wallpaper for a three-monitor setup.

Monitor configuration:
- Left: 1920x1080
- Center: 3440x1440
- Right: 1920x1080
"""

import argparse
import sys
from pathlib import Path
from PIL import Image


# Monitor resolutions
LEFT_WIDTH, LEFT_HEIGHT = 1920, 1080
CENTER_WIDTH, CENTER_HEIGHT = 3440, 1440
RIGHT_WIDTH, RIGHT_HEIGHT = 1920, 1080

# Total canvas size
CANVAS_WIDTH = LEFT_WIDTH + CENTER_WIDTH + RIGHT_WIDTH  # 7280
CANVAS_HEIGHT = CENTER_HEIGHT  # 1440 (tallest monitor)


def scale_image_to_fit(image, target_width, target_height):
    """
    Scale/stretch an image to exactly fit the target dimensions.
    """
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)


def create_two_image_wallpaper(main_image_path, side_image_path, main_position):
    """
    Create wallpaper with 2 images: one for main monitor, one for both side monitors.

    Args:
        main_image_path: Path to image for main monitor
        side_image_path: Path to image for side monitors
        main_position: 'center' or 'side' - where the main image should go
    """
    main_img = Image.open(main_image_path)
    side_img = Image.open(side_image_path)

    # Create blank canvas
    canvas = Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), color='black')

    if main_position == 'center':
        # Main image on center monitor
        center_img = scale_image_to_fit(main_img, CENTER_WIDTH, CENTER_HEIGHT)
        # Side image on both left and right monitors
        left_img = scale_image_to_fit(side_img, LEFT_WIDTH, LEFT_HEIGHT)
        right_img = scale_image_to_fit(side_img, RIGHT_WIDTH, RIGHT_HEIGHT)

        # Paste images (aligned at top)
        canvas.paste(left_img, (0, 0))
        canvas.paste(center_img, (LEFT_WIDTH, 0))
        canvas.paste(right_img, (LEFT_WIDTH + CENTER_WIDTH, 0))
    else:  # main_position == 'side'
        # Main image on both side monitors
        left_img = scale_image_to_fit(main_img, LEFT_WIDTH, LEFT_HEIGHT)
        right_img = scale_image_to_fit(main_img, RIGHT_WIDTH, RIGHT_HEIGHT)
        # Side image on center monitor
        center_img = scale_image_to_fit(side_img, CENTER_WIDTH, CENTER_HEIGHT)

        # Paste images (aligned at top)
        canvas.paste(left_img, (0, 0))
        canvas.paste(center_img, (LEFT_WIDTH, 0))
        canvas.paste(right_img, (LEFT_WIDTH + CENTER_WIDTH, 0))

    return canvas


def create_three_image_wallpaper(left_image_path, center_image_path, right_image_path):
    """
    Create wallpaper with 3 images: one for each monitor.
    """
    left_img = Image.open(left_image_path)
    center_img = Image.open(center_image_path)
    right_img = Image.open(right_image_path)

    # Create blank canvas
    canvas = Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), color='black')

    # Scale each image to fit its monitor
    left_scaled = scale_image_to_fit(left_img, LEFT_WIDTH, LEFT_HEIGHT)
    center_scaled = scale_image_to_fit(center_img, CENTER_WIDTH, CENTER_HEIGHT)
    right_scaled = scale_image_to_fit(right_img, RIGHT_WIDTH, RIGHT_HEIGHT)

    # Paste images (aligned at top)
    canvas.paste(left_scaled, (0, 0))
    canvas.paste(center_scaled, (LEFT_WIDTH, 0))
    canvas.paste(right_scaled, (LEFT_WIDTH + CENTER_WIDTH, 0))

    return canvas


def main():
    parser = argparse.ArgumentParser(
        description='Combine images into a single multi-monitor wallpaper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Two images - main on center, side image on left/right
  %(prog)s -o output.png --center main.jpg --sides side.jpg

  # Two images - main on sides, center image in middle
  %(prog)s -o output.png --sides main.jpg --center side.jpg

  # Three images - specify each monitor
  %(prog)s -o output.png --left left.jpg --center center.jpg --right right.jpg
        """
    )

    parser.add_argument('-o', '--output', required=True,
                        help='Output wallpaper file path')
    parser.add_argument('--left', help='Image for left monitor')
    parser.add_argument('--center', help='Image for center monitor')
    parser.add_argument('--right', help='Image for right monitor')
    parser.add_argument('--sides', help='Image for both side monitors (use with --center)')

    args = parser.parse_args()

    # Validate arguments
    if args.left and args.center and args.right:
        # Three image mode
        if args.sides:
            print("Error: --sides cannot be used with --left/--center/--right", file=sys.stderr)
            sys.exit(1)

        print(f"Creating wallpaper with 3 images:")
        print(f"  Left: {args.left}")
        print(f"  Center: {args.center}")
        print(f"  Right: {args.right}")

        canvas = create_three_image_wallpaper(args.left, args.center, args.right)

    elif args.center and args.sides:
        # Two image mode
        if args.left or args.right:
            print("Error: --left/--right cannot be used with --center/--sides", file=sys.stderr)
            sys.exit(1)

        print(f"Creating wallpaper with 2 images:")
        print(f"  Center: {args.center}")
        print(f"  Sides: {args.sides}")

        canvas = create_two_image_wallpaper(args.center, args.sides, 'center')

    elif args.sides and (args.left or args.right):
        print("Error: --sides must be used with --center only", file=sys.stderr)
        sys.exit(1)

    else:
        print("Error: Invalid argument combination", file=sys.stderr)
        print("\nValid combinations:", file=sys.stderr)
        print("  1. --left --center --right (3 images)", file=sys.stderr)
        print("  2. --center --sides (2 images)", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    # Save the result
    output_path = Path(args.output)
    canvas.save(output_path, quality=95)
    print(f"\nWallpaper saved to: {output_path.absolute()}")
    print(f"Resolution: {CANVAS_WIDTH}x{CANVAS_HEIGHT}")
    print(f"\nTo set as wallpaper, use:")
    print(f"  gsettings set org.cinnamon.desktop.background picture-uri 'file://{output_path.absolute()}'")


if __name__ == '__main__':
    main()
