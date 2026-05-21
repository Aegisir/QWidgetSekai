# coding:utf-8
from math import cos, pi, sin
from random import random
from typing import Optional

from PyQt5.QtCore import QPointF, QElapsedTimer, Qt, QTimer, pyqtProperty  # type: ignore[reportAttributeAccessIssue]
from PyQt5.QtGui import QColor, QImage, QMouseEvent, QPainter
from PyQt5.QtWidgets import QWidget


class _FlowParticle:
    """ Flow particle """

    __slots__ = ('x', 'y', 'vx', 'vy', 'age', 'life')

    def __init__(self, width: int, height: int):
        self.vx = self.vy = self.age = 0.0
        self.x = random() * width
        self.y = random() * height
        self.life = random() * 200 + 100

    def reset(self, width: int, height: int):
        self.__init__(width, height)


class FlowFieldBackground(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._color = QColor('#6366f1')
        self._backgroundColor = QColor(0, 0, 0)
        self._trailOpacity = 0.15
        self._particleCount = 600
        self._speed = 1.0
        self._targetFps = 60
        self._paused = False
        self._pointerEnabled = True
        self._isPointerIn = False
        self._pointerPosition = QPointF(-1000, -1000)
        self._canvas = QImage()
        self._particles = []
        self._alphaColors = []

        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._tick)

        self._updateAlphaColors()
        self._updateTimer()
        self.clock.start()
        self.timer.start()

        self.setMouseTracking(True)
        self.setMinimumSize(300, 180)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def _resetCanvas(self):
        size = self.size()
        if size.isEmpty():
            return

        self._canvas = QImage(size, QImage.Format_ARGB32_Premultiplied)
        self._canvas.fill(self.backgroundColor)
        self._resetParticles()
        self.update()

    def _resetParticles(self):
        w, h = max(1, self.width()), max(1, self.height())
        self._particles = [_FlowParticle(w, h) for _ in range(self.particleCount)]

    def _updateAlphaColors(self):
        self._alphaColors = []
        for alpha in range(256):
            color = QColor(self.color)
            color.setAlpha(alpha)
            self._alphaColors.append(color)

    def _updateTimer(self):
        self.timer.setInterval(0 if self.targetFps <= 0 else max(1, round(1000 / self.targetFps)))

    def _tick(self):
        if self.paused or self.width() <= 0 or self.height() <= 0:
            return
        if self._canvas.isNull() or self._canvas.size() != self.size():
            self._resetCanvas()

        elapsed = self.clock.nsecsElapsed()
        self.clock.restart()
        self._drawFrame(max(0.25, min(3.0, elapsed / 16666667)))
        self.update()

    def _drawFrame(self, frameScale: float):
        painter = QPainter(self._canvas)
        painter.setPen(Qt.PenStyle.NoPen)
        trailColor = QColor(self.backgroundColor)
        trailColor.setAlpha(round(255 * self.trailOpacity))
        painter.fillRect(self.rect(), trailColor)

        w, h = max(1, self.width()), max(1, self.height())
        mx, my = self._pointerPosition.x(), self._pointerPosition.y()
        usePointer = self.pointerEnabled and self._isPointerIn
        forceScale = frameScale * self.speed

        for particle in self._particles:
            angle = (cos(particle.x * 0.005) + sin(particle.y * 0.005)) * pi
            particle.vx += cos(angle) * 0.2 * forceScale
            particle.vy += sin(angle) * 0.2 * forceScale

            if usePointer:
                dx, dy = mx - particle.x, my - particle.y
                dist2 = dx * dx + dy * dy
                if dist2 < 22500:
                    force = (150 - dist2 ** 0.5) / 150
                    particle.vx -= dx * force * 0.05 * frameScale
                    particle.vy -= dy * force * 0.05 * frameScale

            particle.x += particle.vx * frameScale
            particle.y += particle.vy * frameScale
            friction = 0.95 ** frameScale
            particle.vx *= friction
            particle.vy *= friction
            particle.age += frameScale

            if particle.age > particle.life:
                particle.reset(w, h)
            elif particle.x < 0:
                particle.x = w
            elif particle.x > w:
                particle.x = 0
            elif particle.y < 0:
                particle.y = h
            elif particle.y > h:
                particle.y = 0

            alpha = round((1 - abs(particle.age / particle.life - 0.5) * 2) * 255)
            painter.fillRect(round(particle.x), round(particle.y), 2, 2, self._alphaColors[max(0, min(255, alpha))])

        painter.end()

    def paintEvent(self, a0):
        if self._canvas.isNull():
            self._resetCanvas()

        painter = QPainter(self)
        painter.drawImage(self.rect(), self._canvas)

    def resizeEvent(self, a0):
        self._resetCanvas()

    def showEvent(self, a0):
        super().showEvent(a0)
        self.clock.restart()
        if not self.paused:
            self.timer.start()

    def hideEvent(self, a0):
        self.timer.stop()
        super().hideEvent(a0)

    def mouseMoveEvent(self, a0: Optional[QMouseEvent] = None):
        if a0 is not None and self.pointerEnabled:
            self._isPointerIn = True
            self._pointerPosition = a0.pos()

    def leaveEvent(self, a0):
        self._isPointerIn = False
        self._pointerPosition = QPointF(-1000, -1000)

    def getColor(self):
        return self._color

    def setColor(self, color):
        color = QColor(color)
        if color == self.color:
            return
        self._color = color
        self._updateAlphaColors()
        self.update()

    def getBackgroundColor(self):
        return self._backgroundColor

    def setBackgroundColor(self, color):
        color = QColor(color)
        if color == self.backgroundColor:
            return
        self._backgroundColor = color
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, color.alpha() == 255)
        self._resetCanvas()

    def getTrailOpacity(self):
        return self._trailOpacity

    def setTrailOpacity(self, opacity: float):
        opacity = max(0.0, min(1.0, float(opacity)))
        if opacity == self.trailOpacity:
            return
        self._trailOpacity = opacity

    def getParticleCount(self):
        return self._particleCount

    def setParticleCount(self, count: int):
        count = max(0, min(5000, int(count)))
        if count == self.particleCount:
            return
        self._particleCount = count
        self._resetParticles()

    def getSpeed(self):
        return self._speed

    def setSpeed(self, speed: float):
        speed = max(0.0, float(speed))
        if speed == self.speed:
            return
        self._speed = speed

    def getTargetFps(self):
        return self._targetFps

    def setTargetFps(self, fps: int):
        fps = max(0, min(240, int(fps)))
        if fps == self.targetFps:
            return
        self._targetFps = fps
        self._updateTimer()

    def isPaused(self):
        return self._paused

    def setPaused(self, isPaused: bool):
        if isPaused == self.paused:
            return
        self._paused = isPaused
        self.timer.stop() if isPaused else self.timer.start()
        self.clock.restart()

    def isPointerEnabled(self):
        return self._pointerEnabled

    def setPointerEnabled(self, isEnabled: bool):
        if isEnabled == self.pointerEnabled:
            return
        self._pointerEnabled = isEnabled
        self.setMouseTracking(isEnabled)
        self._isPointerIn = self._isPointerIn and isEnabled

    color = pyqtProperty(QColor, getColor, setColor)
    backgroundColor = pyqtProperty(QColor, getBackgroundColor, setBackgroundColor)
    trailOpacity = pyqtProperty(float, getTrailOpacity, setTrailOpacity)
    particleCount = pyqtProperty(int, getParticleCount, setParticleCount)
    speed = pyqtProperty(float, getSpeed, setSpeed)
    targetFps = pyqtProperty(int, getTargetFps, setTargetFps)
    paused = pyqtProperty(bool, isPaused, setPaused)
    pointerEnabled = pyqtProperty(bool, isPointerEnabled, setPointerEnabled)
