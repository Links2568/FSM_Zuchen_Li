"""Reusable drawing primitives for the GUI panels."""

import cv2
import numpy as np


def rounded_rect(
    img: np.ndarray,
    pt1: tuple,
    pt2: tuple,
    color: tuple,
    radius: int = 10,
    thickness: int = 1,
) -> None:
    """Draw a rounded rectangle on *img* (in-place).

    Parameters
    ----------
    img : numpy array (BGR image)
    pt1 : (x1, y1) top-left corner
    pt2 : (x2, y2) bottom-right corner
    color : BGR tuple
    radius : corner radius in pixels
    thickness : line thickness, or -1 for filled
    """
    x1, y1 = pt1
    x2, y2 = pt2

    # Clamp radius so it doesn't exceed half the box dimension
    r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    if r < 1:
        cv2.rectangle(img, pt1, pt2, color, thickness)
        return

    fill = thickness == -1

    if fill:
        # Filled rounded rect: three overlapping filled rectangles + four filled ellipses
        cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, -1)
        cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, -1)
        # Four corner arcs (filled)
        cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, -1)
        cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, -1)
        cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, -1)
        cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, -1)
    else:
        # Outline: four lines + four corner arcs
        cv2.line(img, (x1 + r, y1), (x2 - r, y1), color, thickness)  # top
        cv2.line(img, (x1 + r, y2), (x2 - r, y2), color, thickness)  # bottom
        cv2.line(img, (x1, y1 + r), (x1, y2 - r), color, thickness)  # left
        cv2.line(img, (x2, y1 + r), (x2, y2 - r), color, thickness)  # right
        cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness)
        cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness)
        cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness)
        cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness)
