"""Star desktop companion: original vector chibi, no external artwork.

Public rendering and animation interfaces intentionally match the original sprites.py.
Run: python pet/sprites.py sheet out.png [scale]
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, replace

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBitmap, QBrush, QColor, QImage, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QRegion,
)

W, H = 120, 150
FOOT_Y = 141
HALO = 1.5

OUTLINE = QColor("#302739")
SKIN = QColor("#FFE4D3")
SKIN_SH = QColor("#EFC0AF")
HAIR = QColor("#242033")
HAIR_HI = QColor("#696181")
GOLD = QColor("#F2BD58")
GOLD_L = QColor("#FFF0B4")
GOLD_D = QColor("#A5722B")
DRESS = QColor("#292535")
DRESS_HI = QColor("#464055")
CREAM = QColor("#FFF7E8")
BLUSH = QColor(239, 120, 135, 105)
BOOT = QColor("#262331")


@dataclass(frozen=True)
class Pose:
    look: float = 0.0
    bob: float = 0.0
    sit: bool = False
    tilt: float = 0.0
    sway: float = 0.0
    l_step: float = 0.0
    r_step: float = 0.0
    l_lift: float = 0.0
    r_lift: float = 0.0
    l_arm: float = 16.0
    r_arm: float = 16.0
    l_fore: float = 8.0
    r_fore: float = 8.0
    eyes: str = "open"
    mouth: str = "smile"
    extra: str = ""
    t: int = 0
    twinkle: bool = False


def _star4(cx: float, cy: float, r: float, rot: float = 0.0, fat: float = 0.2) -> QPainterPath:
    pts = [QPointF(cx + r * math.cos(rot + i * math.pi / 2),
                   cy + r * math.sin(rot + i * math.pi / 2)) for i in range(4)]
    path = QPainterPath(pts[0])
    for i in range(4):
        a = rot + i * math.pi / 2 + math.pi / 4
        path.quadTo(QPointF(cx + fat * r * math.cos(a), cy + fat * r * math.sin(a)),
                    pts[(i + 1) % 4])
    path.closeSubpath()
    return path


def _shape(p: QPainter, path: QPainterPath, fill, w: float = 1.5, outline=OUTLINE) -> None:
    p.setPen(QPen(outline, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(fill if isinstance(fill, QBrush) else QBrush(fill))
    p.drawPath(path)


def _stroke(p: QPainter, path: QPainterPath, color, w: float, outline_w: float = 0.0) -> None:
    p.setBrush(Qt.NoBrush)
    if outline_w:
        p.setPen(QPen(OUTLINE, w + outline_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
    p.setPen(QPen(color, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)


def _ellipse(cx: float, cy: float, rx: float, ry: float) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QPointF(cx, cy), rx, ry)
    return path


def _hair_back(p: QPainter, pose: Pose, by: float) -> None:
    back = QPainterPath()
    back.moveTo(24, 50 + by)
    back.cubicTo(23, 24 + by, 40, 15 + by, 60, 15 + by)
    back.cubicTo(84, 15 + by, 99, 30 + by, 96, 55 + by)
    back.lineTo(96, 81 + by)
    back.quadTo(QPointF(89, 88 + by), QPointF(82, 81 + by))
    back.quadTo(QPointF(60, 88 + by), QPointF(38, 81 + by))
    back.quadTo(QPointF(24, 88 + by), QPointF(24, 76 + by))
    back.closeSubpath()
    _shape(p, back, HAIR)
    for side in (-1, 1):
        x = 60 + side * 34
        dx = pose.sway * 6
        tail = QPainterPath(QPointF(x - 6, 57 + by))
        tail.cubicTo(QPointF(x - 9, 69 + by), QPointF(x + dx - 5, 92 + by),
                     QPointF(x + dx + side * 4, 96 + by))
        tail.cubicTo(QPointF(x + dx + 7, 86 + by), QPointF(x + 8, 68 + by),
                     QPointF(x + 6, 57 + by))
        tail.closeSubpath()
        g = QLinearGradient(x, 62 + by, x + dx, 96 + by)
        g.setColorAt(0, HAIR)
        g.setColorAt(0.65, HAIR)
        g.setColorAt(1, GOLD_D)
        _shape(p, tail, QBrush(g))
        _shape(p, _ellipse(x, 60 + by, 5.0, 3.2), GOLD, 1.2)


def _eye(p: QPainter, cx: float, cy: float, kind: str, side: int) -> None:
    # Both eye corners use the same baseline, even during a blink.
    rx, ry = (9.1, 11.0) if kind == "wide" else (8.8, 10.3)
    if kind in ("closed", "happy"):
        line = QPainterPath(QPointF(cx - rx + 1, cy + 1))
        if kind == "happy":
            line.quadTo(QPointF(cx, cy - 10), QPointF(cx + rx - 1, cy + 1))
        else:
            line.quadTo(QPointF(cx, cy + 5.5), QPointF(cx + rx - 1, cy + 1))
        _stroke(p, line, OUTLINE, 2.0)
        lash = QPainterPath(QPointF(cx + side * (rx - 1), cy + 1))
        lash.lineTo(QPointF(cx + side * (rx + 1.0), cy - 0.5))
        _stroke(p, lash, OUTLINE, 1.5)
        return

    # Blink is a squashed, mostly closed aperture, not an unrelated smile.
    if kind == "blink":
        top, bottom = 1.3, 3.2
    elif kind == "down":
        top, bottom = -6.0, 6.0
    else:
        top, bottom = -ry, ry
    aperture = QPainterPath(QPointF(cx - rx, cy + 0.7))
    aperture.cubicTo(QPointF(cx - rx, cy + top * 0.7),
                     QPointF(cx - rx * 0.55, cy + top),
                     QPointF(cx, cy + top))
    aperture.cubicTo(QPointF(cx + rx * 0.55, cy + top),
                     QPointF(cx + rx, cy + top * 0.7),
                     QPointF(cx + rx, cy + 0.7))
    aperture.cubicTo(QPointF(cx + rx, cy + bottom * 0.8),
                     QPointF(cx + rx * 0.35, cy + bottom),
                     QPointF(cx, cy + bottom))
    aperture.cubicTo(QPointF(cx - rx * 0.45, cy + bottom),
                     QPointF(cx - rx, cy + bottom * 0.8),
                     QPointF(cx - rx, cy + 0.7))
    aperture.closeSubpath()
    white = QLinearGradient(cx, cy - 11, cx, cy + 11)
    white.setColorAt(0, QColor("#FFFDFC"))
    white.setColorAt(1, QColor("#F6E9DC"))
    _shape(p, aperture, QBrush(white), 1.0, QColor("#735965"))

    p.save()
    p.setClipPath(aperture, Qt.IntersectClip)
    iris_y = cy + (2.5 if kind == "down" else 1.5)
    iris = QLinearGradient(cx, iris_y - 10, cx, iris_y + 10)
    iris.setColorAt(0, QColor("#442A35"))
    iris.setColorAt(0.32, QColor("#79503B"))
    iris.setColorAt(0.68, QColor("#C78B47"))
    iris.setColorAt(1, QColor("#F6C976"))
    _shape(p, _ellipse(cx, iris_y, 6.1, 9.5), QBrush(iris), 0.8, GOLD_D)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#2A2030"))
    p.drawEllipse(QPointF(cx, iris_y - 1.5), 2.65, 5.0)
    p.setBrush(CREAM)
    p.drawEllipse(QPointF(cx - 2.35, iris_y - 4.1), 2.2, 2.45)
    p.drawEllipse(QPointF(cx + 2.8, iris_y + 3.5), 1.0, 1.2)
    p.restore()

    lid = QPainterPath(QPointF(cx - rx, cy + 0.7))
    lid.cubicTo(QPointF(cx - rx, cy + top * 0.7),
                QPointF(cx - rx * 0.55, cy + top),
                QPointF(cx, cy + top))
    lid.cubicTo(QPointF(cx + rx * 0.55, cy + top),
                QPointF(cx + rx, cy + top * 0.7),
                QPointF(cx + rx, cy + 0.7))
    _stroke(p, lid, OUTLINE, 2.1)
    lash = QPainterPath(QPointF(cx + side * (rx - 0.2), cy + 0.5))
    lash.lineTo(QPointF(cx + side * (rx + 2), cy - 1.7))
    _stroke(p, lash, OUTLINE, 1.5)
    lower = QPainterPath(QPointF(cx - 4, cy + bottom + 1))
    lower.quadTo(QPointF(cx, cy + bottom + 2), QPointF(cx + 4, cy + bottom + 1))
    _stroke(p, lower, QColor("#C58F90"), 0.9)


def _mouth(p: QPainter, cx: float, cy: float, kind: str) -> None:
    if kind == "open":
        mouth = QPainterPath(QPointF(cx - 4.2, cy - 1))
        mouth.quadTo(QPointF(cx, cy + 0.5), QPointF(cx + 4.2, cy - 1))
        mouth.cubicTo(QPointF(cx + 4, cy + 5), QPointF(cx - 4, cy + 5),
                      QPointF(cx - 4.2, cy - 1))
        _shape(p, mouth, QColor("#913F58"), 1.2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FF9DA2"))
        p.drawEllipse(QPointF(cx, cy + 3.5), 2.1, 1)
    elif kind == "o":
        _shape(p, _ellipse(cx, cy + 1, 2.8, 3.4), QColor("#874358"), 1.3)
    elif kind == "flat":
        line = QPainterPath(QPointF(cx - 3, cy + 1))
        line.lineTo(QPointF(cx + 3, cy + 1))
        _stroke(p, line, OUTLINE, 1.5)
    else:
        line = QPainterPath(QPointF(cx - (4 if kind == "smile" else 2.5), cy))
        line.quadTo(QPointF(cx, cy + (3.8 if kind == "smile" else 2.5)),
                    QPointF(cx + (4 if kind == "smile" else 2.5), cy))
        _stroke(p, line, OUTLINE, 1.55)


def _head_front(p: QPainter, pose: Pose, by: float) -> None:
    cx, cy = 60.0, 51.0 + by
    face = QPainterPath()
    face.moveTo(30, cy - 22)
    face.cubicTo(QPointF(37, cy - 33), QPointF(83, cy - 33), QPointF(90, cy - 22))
    face.cubicTo(QPointF(95, cy - 5), QPointF(91, cy + 21), QPointF(77, cy + 27))
    face.quadTo(QPointF(60, cy + 34), QPointF(43, cy + 27))
    face.cubicTo(QPointF(29, cy + 21), QPointF(25, cy - 5), QPointF(30, cy - 22))
    face.closeSubpath()
    _shape(p, face, SKIN)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(234, 163, 151, 38))
    p.drawEllipse(QPointF(cx, cy + 26), 15, 3)
    dx = pose.look * 3.2
    for side in (-1, 1):
        blush = QRadialGradient(QPointF(cx + side * 23 + dx, cy + 15), 9)
        blush.setColorAt(0, BLUSH)
        blush.setColorAt(1, QColor(239, 120, 135, 0))
        p.setBrush(QBrush(blush))
        p.drawEllipse(QPointF(cx + side * 23 + dx, cy + 15), 9, 5.4)
    _eye(p, cx - 15 + dx, cy + 3.5, pose.eyes, -1)
    _eye(p, cx + 15 + dx, cy + 3.5, pose.eyes, 1)
    _mouth(p, cx + dx, cy + 19, pose.mouth)

    bangs = QPainterPath(QPointF(27, cy - 9))
    bangs.cubicTo(QPointF(24, cy - 39), QPointF(39, cy - 37), QPointF(60, cy - 37))
    bangs.cubicTo(QPointF(86, cy - 37), QPointF(98, cy - 30), QPointF(93, cy - 7))
    bangs.quadTo(QPointF(86, cy - 5), QPointF(83, cy - 15))
    bangs.quadTo(QPointF(76, cy - 12), QPointF(71, cy - 18))
    bangs.quadTo(QPointF(61, cy - 13), QPointF(54, cy - 19))
    bangs.quadTo(QPointF(42, cy - 10), QPointF(36, cy - 15))
    bangs.quadTo(QPointF(30, cy - 3), QPointF(27, cy - 9))
    bangs.closeSubpath()
    _shape(p, bangs, HAIR)
    for x, y, length in ((39, -25, 11), (48, -30, 9), (69, -29, 10), (79, -24, 8)):
        strand = QPainterPath(QPointF(x, cy + y))
        strand.quadTo(QPointF(x - 3, cy + y + length / 2),
                      QPointF(x - 4, cy + y + length))
        _stroke(p, strand, HAIR_HI, 1.25)
    ahoge = QPainterPath(QPointF(59, cy - 36))
    ahoge.cubicTo(QPointF(50, cy - 51), QPointF(68, cy - 51),
                   QPointF(64, cy - 43))
    _stroke(p, ahoge, HAIR, 3.0, 1.0)
    _shape(p, _star4(82, cy - 22, 9.3, -0.12), GOLD, 1.35, GOLD_D)
    p.setPen(Qt.NoPen)
    p.setBrush(GOLD_L)
    p.drawEllipse(QPointF(80.5, cy - 23), 1.5, 1.5)
    if pose.twinkle:
        _shape(p, _star4(90, cy - 32, 4), CREAM, 0.7, GOLD_D)


def _arm(p: QPainter, shoulder: QPointF, side: int, ang: float, fore: float, ln: float = 1.0) -> None:
    a = math.radians(ang)
    b = math.radians(ang + fore)
    elbow = QPointF(shoulder.x() + side * 10.5 * ln * math.sin(a),
                    shoulder.y() + 10.5 * ln * math.cos(a))
    hand = QPointF(elbow.x() + side * 9.5 * ln * math.sin(b),
                   elbow.y() + 9.5 * ln * math.cos(b))
    fore_path = QPainterPath(elbow)
    fore_path.lineTo(hand)
    _stroke(p, fore_path, SKIN, 5, 2)
    sleeve = QPainterPath(shoulder)
    sleeve.lineTo(elbow)
    _stroke(p, sleeve, DRESS, 7, 2)
    _stroke(p, QPainterPath(elbow), GOLD, 3.2)
    _shape(p, _ellipse(hand.x(), hand.y(), 3.7, 3.7), SKIN, 1.4)


def _foot(p: QPainter, hip: QPointF, step: float, lift: float, look: float, sit_x: float | None) -> None:
    ax = hip.x() + step * 5 + look * 1.5
    ay = min(135, 131 - lift)
    leg = QPainterPath(hip)
    leg.lineTo(QPointF(ax, ay))
    _stroke(p, leg, SKIN, 5.4, 2.1)
    boot = QPainterPath()
    boot.addRoundedRect(QRectF(ax - 6 + look * 1.5, ay - 1, 12, 10.5), 4, 4)
    _shape(p, boot, BOOT)
    band = QPainterPath(QPointF(ax - 5, ay + 1.4))
    band.lineTo(QPointF(ax + 5, ay + 1.4))
    _stroke(p, band, GOLD, 1.8)


def _sit_feet(p: QPainter, by: float) -> None:
    for side in (-1, 1):
        x = 60 + side * 25
        _shape(p, _ellipse(x, 137.5, 8, 4.8), BOOT)
        band = QPainterPath(QPointF(x - side * 2.5, 134.2))
        band.lineTo(QPointF(x - side * 2.5, 141))
        _stroke(p, band, GOLD, 1.8)


def _body(p: QPainter, pose: Pose, by: float) -> None:
    cx = 60.0
    skirt = QPainterPath(QPointF(44, 100 + by))
    skirt.lineTo(QPointF(33, 119 + by))
    skirt.quadTo(QPointF(60, 128 + by), QPointF(87, 119 + by))
    skirt.lineTo(QPointF(76, 100 + by))
    skirt.closeSubpath()
    _shape(p, skirt, DRESS)
    for side in (-1, 1):
        pleat = QPainterPath(QPointF(cx + side * 8, 106 + by))
        pleat.lineTo(QPointF(cx + side * 18, 121 + by))
        _stroke(p, pleat, DRESS_HI, 1.1)
    hem = QPainterPath(QPointF(35, 119 + by))
    hem.quadTo(QPointF(60, 126 + by), QPointF(85, 119 + by))
    _stroke(p, hem, GOLD, 1.6)
    torso = QPainterPath(QPointF(46, 81 + by))
    torso.quadTo(QPointF(41, 91 + by), QPointF(42, 107 + by))
    torso.lineTo(QPointF(78, 107 + by))
    torso.quadTo(QPointF(79, 91 + by), QPointF(74, 81 + by))
    torso.closeSubpath()
    _shape(p, torso, DRESS)
    collar = QPainterPath(QPointF(47, 82 + by))
    collar.lineTo(QPointF(60, 92 + by))
    collar.lineTo(QPointF(73, 82 + by))
    collar.quadTo(QPointF(60, 87 + by), QPointF(47, 82 + by))
    _shape(p, collar, CREAM, 1.2)
    for side in (-1, 1):
        bow = QPainterPath(QPointF(60, 89 + by))
        bow.lineTo(QPointF(60 + side * 8, 86 + by))
        bow.lineTo(QPointF(60 + side * 8, 94 + by))
        bow.closeSubpath()
        _shape(p, bow, GOLD, 1.0, GOLD_D)
    _shape(p, _ellipse(60, 89 + by, 2.2, 2.2), GOLD_L, 0.9, GOLD_D)
    _shape(p, _star4(60, 100 + by, 4.6), GOLD, 0.9, GOLD_D)
    waist = QPainterPath(QPointF(43, 106 + by))
    waist.lineTo(QPointF(77, 106 + by))
    _stroke(p, waist, GOLD, 2.0)


def _laptop(p: QPainter, pose: Pose, by: float) -> None:
    lid = QPainterPath()
    lid.addRoundedRect(QRectF(35, 113, 50, 23), 4, 4)
    _shape(p, lid, DRESS_HI)
    inner = QPainterPath()
    inner.addRoundedRect(QRectF(38, 116, 44, 17), 2, 2)
    _shape(p, inner, DRESS, 1.0)
    _shape(p, _star4(60, 124.5, 7), GOLD, 1.0, GOLD_D)
    base = QPainterPath()
    base.addRoundedRect(QRectF(31, 136, 58, 4.5), 2, 2)
    _shape(p, base, DRESS_HI)
    for side, up in ((-1, pose.t % 2), (1, 1 - pose.t % 2)):
        _shape(p, _ellipse(60 + side * 28, 126 - up * 3.2, 4.2, 4.2), SKIN)


def _gear(p: QPainter, cx: float, cy: float, r: float, rot: float) -> None:
    path = QPainterPath()
    for k in range(16):
        a = rot + k * math.pi / 8
        rad = r if k % 2 == 0 else r * 0.72
        pt = QPointF(cx + rad * math.cos(a), cy + rad * math.sin(a))
        if k == 0:
            path.moveTo(pt)
        else:
            path.lineTo(pt)
    path.closeSubpath()
    _shape(p, path, GOLD, 1.2, GOLD_D)
    _shape(p, _ellipse(cx, cy, r * .32, r * .32), CREAM, 1, GOLD_D)


def _zzz(p: QPainter, t: int) -> None:
    for k, (x, y, size) in enumerate(((80, 42, 9), (88, 28, 12), (94, 12, 15))):
        dy = -3 * ((t + k) % 2)
        z = QPainterPath(QPointF(x, y + dy))
        z.lineTo(QPointF(x + size, y + dy))
        z.lineTo(QPointF(x, y + size + dy))
        z.lineTo(QPointF(x + size, y + size + dy))
        _stroke(p, z, CREAM, 3.0, 2.4)


def draw_shadow(p: QPainter) -> None:
    p.setPen(Qt.NoPen)
    gradient = QRadialGradient(QPointF(60, FOOT_Y + 1), 32)
    gradient.setColorAt(0, QColor(0, 0, 0, 90))
    gradient.setColorAt(1, QColor(0, 0, 0, 0))
    p.setBrush(QBrush(gradient))
    p.drawEllipse(QPointF(60, FOOT_Y + 1), 32, 5)


def draw_pose(p: QPainter, pose: Pose) -> None:
    by = pose.bob + (18 if pose.sit else 0)
    p.save()
    p.translate(60, 76 + by)
    p.rotate(pose.tilt)
    p.translate(-60, -(76 + by))
    _hair_back(p, pose, by)
    p.restore()
    if not pose.sit:
        _foot(p, QPointF(52, 114 + by), pose.l_step, pose.l_lift, pose.look, None)
        _foot(p, QPointF(68, 114 + by), pose.r_step, pose.r_lift, pose.look, None)
    _body(p, pose, by)
    if pose.sit:
        _sit_feet(p, by)
    raised = []
    if pose.extra == "laptop":
        _laptop(p, pose, by)
    else:
        for side, ang, fore in ((-1, pose.l_arm, pose.l_fore), (1, pose.r_arm, pose.r_fore)):
            if ang > 100:
                raised.append((side, ang, fore))
            else:
                _arm(p, QPointF(60 + side * 14, 84 + by), side, ang, fore)
    p.save()
    p.translate(60, 76 + by)
    p.rotate(pose.tilt)
    p.translate(-60, -(76 + by))
    _head_front(p, pose, by)
    p.restore()
    for side, ang, fore in raised:
        _arm(p, QPointF(60 + side * 14, 84 + by), side, ang, fore, 1.2)
    if pose.extra == "zzz":
        _zzz(p, pose.t)
    elif pose.extra == "laptop":
        _gear(p, 98, 30 + by * .3, 8.5, pose.t * .35)


def _walk(facing: int) -> list[Pose]:
    out = []
    for i in range(6):
        ph = 2 * math.pi * i / 6
        s = math.sin(ph)
        out.append(Pose(
            look=facing, bob=-abs(math.cos(ph)) * 2.4 + 1,
            sway=-facing * (.55 + .35 * math.cos(2 * ph)),
            l_step=facing * s, r_step=-facing * s,
            l_lift=max(0., math.cos(ph)) * 4,
            r_lift=max(0., -math.cos(ph)) * 4,
            l_arm=18 + 10 * s, r_arm=18 - 10 * s,
            l_fore=10, r_fore=10, eyes="open", mouth="smile", twinkle=i == 0))
    return out


def _idle(facing: int) -> list[Pose]:
    base = Pose(look=facing * .4, eyes="open", mouth="smile")
    return [base, replace(base, bob=.9, sway=.2), replace(base, eyes="blink"),
            replace(base, mouth="small", twinkle=True, l_arm=12, r_arm=12)]


def _sit(facing: int) -> list[Pose]:
    base = Pose(look=facing * .4, sit=True, l_arm=10, r_arm=10, l_fore=24, r_fore=24)
    return [base, replace(base, bob=.9), replace(base, eyes="blink")]


def _sleep(facing: int) -> list[Pose]:
    base = Pose(look=0., sit=True, tilt=9 * (1 if facing >= 0 else -1),
                eyes="closed", mouth="small", l_arm=4, r_arm=4,
                l_fore=34, r_fore=34, extra="zzz")
    return [replace(base, t=0), replace(base, bob=.9, t=1)]


def _wave(facing: int) -> list[Pose]:
    out = []
    for k, f in enumerate((150, 175, 150, 118)):
        out.append(Pose(look=facing * .3, eyes="happy", mouth="open",
                        r_arm=128, r_fore=f - 128 + 8,
                        l_arm=14, l_fore=8, bob=-1. if k % 2 else 0.,
                        twinkle=k == 1))
    return out


def _work(facing: int) -> list[Pose]:
    out = []
    for k in range(4):
        out.append(Pose(look=0., sit=True, eyes="down" if k != 3 else "blink",
                        mouth="small" if k < 3 else "flat", extra="laptop",
                        t=k, bob=0., tilt=-3 if k % 2 else 3))
    return out


def _held(facing: int) -> list[Pose]:
    out = []
    for k in range(2):
        out.append(Pose(look=0., eyes="wide", mouth="o",
                        l_arm=122, r_arm=122, l_fore=22, r_fore=22,
                        l_step=-.6 + .8 * k, r_step=.6 - .8 * k,
                        l_lift=-6 + 3 * k, r_lift=-6 + 3 * (1 - k),
                        sway=.8 if k else -.8))
    return out


@dataclass
class Anim:
    make: object
    seq: list
    loop: bool = True


ANIMS: dict[str, Anim] = {
    "walk": Anim(_walk, [(i, 115) for i in range(6)]),
    "idle": Anim(_idle, [(0, 900), (1, 700), (0, 800), (2, 150), (0, 900), (3, 900), (1, 700), (2, 150)]),
    "sit": Anim(_sit, [(0, 1200), (1, 900), (0, 1000), (2, 150), (0, 1400)]),
    "sleep": Anim(_sleep, [(0, 900), (1, 900)]),
    "wave": Anim(_wave, [(0, 170), (1, 170), (2, 170), (3, 170), (0, 170), (1, 170),
                        (2, 170), (3, 170), (0, 170), (1, 170)], loop=False),
    "work": Anim(_work, [(0, 200), (1, 200), (2, 200), (0, 200), (1, 200), (3, 260), (2, 200), (1, 200)]),
    "held": Anim(_held, [(0, 160), (1, 160)]),
}
_POSES: dict[tuple, list[Pose]] = {}


def poses(state: str, facing: int) -> list[Pose]:
    key = (state, facing)
    if key not in _POSES:
        _POSES[key] = ANIMS[state].make(facing)
    return _POSES[key]


def render_image(state: str, index: int, facing: int, scale: float = 1.0, dpr: float = 1.0) -> QImage:
    pose = poses(state, facing)[index]
    w, h = round(W * scale * dpr), round(H * scale * dpr)
    hints = QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing
    body = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    body.fill(Qt.transparent)
    painter = QPainter(body)
    painter.setRenderHints(hints)
    painter.scale(scale * dpr, scale * dpr)
    draw_pose(painter, pose)
    painter.end()
    halo = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    halo.fill(Qt.transparent)
    hp = QPainter(halo)
    hp.setRenderHints(hints)
    r = HALO * scale * dpr
    for k in range(16):
        a = 2 * math.pi * k / 16
        hp.drawImage(QPointF(r * math.cos(a), r * math.sin(a)), body)
    hp.setCompositionMode(QPainter.CompositionMode_SourceIn)
    hp.fillRect(halo.rect(), QColor(255, 241, 210, 225))
    hp.end()
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    op = QPainter(img)
    op.setRenderHints(hints)
    op.save()
    op.scale(scale * dpr, scale * dpr)
    draw_shadow(op)
    op.restore()
    op.drawImage(0, 0, halo)
    op.drawImage(0, 0, body)
    op.end()
    img.setDevicePixelRatio(dpr)
    return img


def render(state: str, index: int, facing: int, scale: float, dpr: float) -> QPixmap:
    return QPixmap.fromImage(render_image(state, index, facing, scale, dpr))


def click_region(state: str, index: int, facing: int, scale: float) -> QRegion:
    """Where she can be clicked, in logical pixels: every pixel that is not transparent."""
    img = render_image(state, index, facing, scale, 1.0)
    bm = QBitmap.fromImage(img.createAlphaMask(Qt.MonoOnly | Qt.ThresholdDither))
    return QRegion(bm)


def click_region_union(state: str, facing: int, scale: float) -> QRegion:
    """Click area for a whole animation: the union of all its frames."""
    region = QRegion()
    for i in range(len(poses(state, facing))):
        region = region.united(click_region(state, i, facing, scale))
    return region


def face_icon(size: int = 64) -> QPixmap:
    img = render_image("idle", 0, 0, 1.0, 1.0)
    return QPixmap.fromImage(img.copy(10, 6, 100, 96)).scaled(
        size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def contact_sheet(path: str, scale: float = 2.0) -> None:
    from PySide6.QtGui import QGuiApplication
    rows = [("walk", 1), ("walk", -1), ("idle", 1), ("sit", 1),
            ("sleep", 1), ("wave", 1), ("work", 1), ("held", 1)]
    cols = max(len(poses(s, f)) for s, f in rows)
    cw, ch = int(W * scale), int(H * scale)
    sheet = QImage(cw * cols, ch * len(rows), QImage.Format_ARGB32_Premultiplied)
    sheet.fill(QColor("#7C8AA5"))
    p = QPainter(sheet)
    p.fillRect(0, 0, cw * cols, ch * 3, QColor("#0B0E15"))
    p.fillRect(0, ch * 6, cw * cols, ch * 2, QColor("#F2F2F2"))
    for row, (state, facing) in enumerate(rows):
        for col in range(len(poses(state, facing))):
            p.drawImage(col * cw, row * ch, render_image(state, col, facing, scale, 1.0))
    p.end()
    sheet.save(path)


if __name__ == "__main__":
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication(sys.argv[:1])
    if len(sys.argv) >= 3 and sys.argv[1] == "sheet":
        contact_sheet(sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 2.0)
        print("saved", sys.argv[2])
