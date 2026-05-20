# coding:utf-8
from math import sqrt
from random import random, randrange

from PyQt5.QtCore import Qt, QPointF, QTimer, pyqtProperty
from PyQt5.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt5.QtWidgets import QWidget

from qfluentwidgets import isDarkTheme


class _ParticleModel:
    """ Particle model """

    __slots__ = ('container', 'offset', 'head')

    def __init__(self, container):
        self.container = [container[0], container[1], randrange(30, 61)]
        self.offset = self._randomOffset(self.container)
        self.head = [random() / 2, self._randomHead(), self._randomHead()]

    def nextStep(self):
        for i, value in enumerate((self.offset[0] + self.head[0], self.offset[1] + self.head[1], self.offset[2] + self.head[2])):
            low = 25 if i == 2 else 0
            high = self.container[i]
            if value < low:
                value = low
                self.head[i] = -self.head[i]
            elif value > high:
                value = high
                self.head[i] = -self.head[i]

            self.offset[i] = value

    def resetOffset(self, container):
        self.offset = self._randomOffset([container[0], container[1], randrange(30, 61)])

    @staticmethod
    def _randomHead():
        value = random() / 2
        return -value if randrange(2) == 0 else value

    @staticmethod
    def _randomOffset(container):
        return [random() * container[0], random() * container[1], random() * container[2]]


class Particle(QWidget):
    """ Particle """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._density = 5
        self._paused = False
        self._pointerEnabled = True
        self._isPointerIn = False
        self._pointerDrawCount = 0
        self._pointerPosition = QPointF()
        self._particles = []
        self._customLineColor = QColor()
        self._customParticleColor = QColor()

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(1)
        self.timer.timeout.connect(self.update)
        self.timer.start()

        self.setMouseTracking(True)
        self.setMinimumSize(300, 180)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def getDensity(self):
        return self._density

    def setDensity(self, density: int):
        if density == self.density:
            return

        self._density = density
        self._updateParticles()

    def isPaused(self):
        return self._paused

    def setPaused(self, isPaused: bool):
        if isPaused == self.paused:
            return

        self._paused = isPaused
        self.timer.stop() if isPaused else self.timer.start()
        self.update()

    def isPointerEnabled(self):
        return self._pointerEnabled

    def setPointerEnabled(self, isEnabled: bool):
        if isEnabled == self.pointerEnabled:
            return

        self._pointerEnabled = isEnabled
        self.setMouseTracking(isEnabled)
        self._isPointerIn = self._isPointerIn and isEnabled
        self.update()

    def getLineColor(self):
        return self._customLineColor

    def setLineColor(self, color):
        self._customLineColor = QColor(color)
        self.update()

    def getParticleColor(self):
        return self._customParticleColor

    def setParticleColor(self, color):
        self._customParticleColor = QColor(color)
        self.update()

    def _linePenColor(self):
        if self._customLineColor.isValid():
            return self._customLineColor

        return QColor(255, 255, 255, 102) if isDarkTheme() else QColor(0, 0, 0, 102)

    def _particleBrushColor(self):
        if self._customParticleColor.isValid():
            return self._customParticleColor

        return QColor(255, 255, 255, 51) if isDarkTheme() else QColor(0, 0, 0, 51)

    def _particleCount(self):
        density = min(self.density, 9)
        if density < 0:
            density = 5

        return int(min(self.width(), self.height()) / (10 - density))

    def _container(self):
        return [max(1, self.width()), max(1, self.height())]

    def _updateParticles(self):
        count = self._particleCount()
        container = self._container()
        diff = count - len(self._particles)

        if diff > 0:
            self._particles.extend(_ParticleModel(container) for _ in range(diff))
        elif diff < 0:
            del self._particles[: -diff]

        for p in self._particles:
            p.container = [container[0], container[1], p.container[2]]
            if p.offset[0] > container[0] or p.offset[1] > container[1]:
                p.resetOffset(container)

        self.update()

    def _drawLine(self, painter: QPainter, p1, p2, dist2: float, color: QColor):
        if dist2 >= 14400:
            return

        dist = sqrt(dist2)
        painter.setPen(QPen(color, (120 - dist) / 80))
        painter.drawLine(QPointF(p1[0], p1[1]), QPointF(p2[0], p2[1]))

    def _drawPointer(self, painter: QPainter, particle: _ParticleModel, lineColor: QColor):
        if not self.pointerEnabled or not self._isPointerIn:
            return

        px, py = self._pointerPosition.x(), self._pointerPosition.y()
        dx, dy = particle.offset[0] - px, particle.offset[1] - py
        dist2 = dx * dx + dy * dy
        if dist2 >= 14400:
            return

        self._drawLine(painter, particle.offset, (px, py), dist2, lineColor)
        if dist2 > 6400:
            dx, dy = px - particle.offset[0], py - particle.offset[1]
            m = abs(max(dx, dy)) or 1
            particle.offset[0] += dx / m
            particle.offset[1] += dy / m

    def paintEvent(self, e):
        if self.paused:
            return

        if not self._particles:
            self._updateParticles()

        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)
        lineColor = self._linePenColor()
        particleColor = self._particleBrushColor()
        grid = {}

        for i, p in enumerate(self._particles):
            cell = (int(p.offset[0] // 120), int(p.offset[1] // 120))
            for x in range(cell[0] - 1, cell[0] + 2):
                for y in range(cell[1] - 1, cell[1] + 2):
                    for j in grid.get((x, y), ()):
                        q = self._particles[j]
                        dx, dy = p.offset[0] - q.offset[0], p.offset[1] - q.offset[1]
                        self._drawLine(painter, p.offset, q.offset, dx * dx + dy * dy, QColor(lineColor))

            grid.setdefault(cell, []).append(i)
            self._drawPointer(painter, p, QColor(lineColor))
            painter.setPen(Qt.NoPen)
            painter.setBrush(particleColor)
            painter.drawEllipse(QPointF(p.offset[0], p.offset[1]), p.offset[2] / 30, p.offset[2] / 30)
            p.nextStep()

        if self._isPointerIn:
            self._pointerDrawCount += 1
            if self._pointerDrawCount > 36000:
                self._isPointerIn = False

    def resizeEvent(self, e):
        self._updateParticles()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self.pointerEnabled:
            self._isPointerIn = True
            self._pointerDrawCount = 0
            self._pointerPosition = e.pos()

    def leaveEvent(self, e):
        self._isPointerIn = False

    density = pyqtProperty(int, getDensity, setDensity)
    paused = pyqtProperty(bool, isPaused, setPaused)
    pointerEnabled = pyqtProperty(bool, isPointerEnabled, setPointerEnabled)
    lineColor = pyqtProperty(QColor, getLineColor, setLineColor)
    particleColor = pyqtProperty(QColor, getParticleColor, setParticleColor)
