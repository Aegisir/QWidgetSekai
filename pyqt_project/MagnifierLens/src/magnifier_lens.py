# coding:utf-8
from typing import Union

from PyQt5.QtCore import Qt, QPointF, QRectF, QSize, QTimer, QElapsedTimer, pyqtProperty, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QImage, QMouseEvent, QPainter, QPainterPath, QPixmap, QImageReader
from PyQt5.QtWidgets import QWidget


class MagnifierLens(QWidget):
    """ Magnifier lens """

    hoveringChanged = pyqtSignal(bool)

    def __init__(self, image: Union[QImage, QPixmap, str, QWidget] = None, parent=None):
        if isinstance(image, QWidget) and parent is None:
            parent, image = image, None
        super().__init__(parent=parent)
        self._image = QImage()
        self._cache = QImage()
        self._cacheKey = None
        self._overlay = QImage()
        self._overlayKey = None
        self._zoomFactor = 2.0
        self._lensSize = 150
        self._borderRadius = 8
        self._duration = 300
        self._position = QPointF(200, 150)
        self._aspectRatioMode = Qt.AspectRatioMode.KeepAspectRatioByExpanding
        self._isStatic = False
        self._hovering = False
        self._cursorHidden = True
        self._opacity = 0.0
        self._scale = 0.8
        self._fromOpacity = self._toOpacity = 0.0
        self._fromScale = self._toScale = 0.8

        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self._tick)

        self.setMouseTracking(True)
        self.setMinimumSize(300, 200)
        self.setAttribute(Qt.WA_TranslucentBackground)
        if image is not None:
            self.setImage(image)

    def setImage(self, image: Union[QImage, QPixmap, str]):
        """ set lens image """
        if isinstance(image, QPixmap):
            image = image.toImage()
        elif isinstance(image, str):
            image = QImageReader(image).read()

        self._image = image if isinstance(image, QImage) else QImage()
        if not self._image.isNull():
            self.setMinimumSize(self._image.size().scaled(QSize(600, 400), Qt.KeepAspectRatio))
        self._clearCache()
        self.update()

    def image(self):
        return self._image

    def enterEvent(self, e):
        if not self.isStatic():
            self.setHovering(True)
            if self.cursorHidden:
                self.setCursor(QCursor(Qt.BlankCursor))

    def leaveEvent(self, e):
        if not self.isStatic():
            self.setHovering(False)
            self.unsetCursor()

    def mouseMoveEvent(self, e: QMouseEvent):
        if not self.isStatic():
            self.setLensPosition(e.pos())

    def paintEvent(self, e):
        image = self._scaledImage()
        if image.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.borderRadius, self.borderRadius)
        painter.setClipPath(path)
        painter.drawImage(self.rect(), image)

        if self._opacity <= 0:
            return

        pos = self._boundedPosition()
        radius = self.lensSize * self._scale / 2
        lensPath = QPainterPath()
        lensPath.addEllipse(pos, radius, radius)

        painter.save()
        painter.setOpacity(self._opacity)
        painter.setClipPath(lensPath)
        painter.translate(pos)
        painter.scale(self.zoomFactor * self._scale, self.zoomFactor * self._scale)
        painter.translate(-pos)
        painter.drawImage(self.rect(), image)
        painter.restore()

        overlay = self._lensOverlay()
        if not overlay.isNull():
            painter.setOpacity(self._opacity)
            painter.drawImage(QRectF(pos.x() - radius, pos.y() - radius, radius * 2, radius * 2), overlay)

    def _scaledImage(self):
        dpr = self.devicePixelRatioF()
        size = self.size() * dpr
        key = (self._image.cacheKey(), size.width(), size.height(), dpr, self.aspectRatioMode)
        if self._cacheKey != key:
            target = QSize(max(1, size.width()), max(1, size.height()))
            cache = self._image.scaled(target, self.aspectRatioMode, Qt.SmoothTransformation)
            if self.aspectRatioMode == Qt.AspectRatioMode.KeepAspectRatioByExpanding:
                cache = cache.copy(max(0, (cache.width() - target.width()) // 2),
                                   max(0, (cache.height() - target.height()) // 2), target.width(), target.height())
            cache.setDevicePixelRatio(dpr)
            self._cache = cache
            self._cacheKey = key
        return self._cache

    def _lensOverlay(self):
        dpr = self.devicePixelRatioF()
        size = max(1, round(self.lensSize * dpr))
        key = (size, dpr)
        if self._overlayKey == key:
            return self._overlay

        image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        image.setDevicePixelRatio(dpr)
        painter = QPainter(image)
        painter.setRenderHints(QPainter.Antialiasing)
        s = size / dpr
        for pad, alpha in ((6, 32), (3, 48), (0, 80)):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawEllipse(QPointF(s / 2, s / 2 + pad), s / 2 - 1, s / 2 - 1)

        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.drawEllipse(QPointF(s / 2, s / 2), s / 2 - 3, s / 2 - 3)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        for radius, alpha, width in ((0.64, 26, 10), (0.76, 48, 10)):
            painter.setPen(QColor(255, 255, 255, alpha))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(s / 2, s / 2), s * radius / 2, s * radius / 2)
        painter.end()

        self._overlay = image
        self._overlayKey = key
        return image

    def _boundedPosition(self):
        return QPointF(max(0, min(self.width(), self._position.x())),
                       max(0, min(self.height(), self._position.y())))

    def _startAnimation(self, hovering: bool):
        self._fromOpacity, self._fromScale = self._opacity, self._scale
        self._toOpacity = 1.0 if hovering else 0.0
        self._toScale = 1.0 if hovering else 0.8
        if hovering and self._opacity <= 0:
            self._fromScale = 0.58
        self.clock.restart()
        self.timer.start()
        self._tick()

    def _tick(self):
        t = min(1, self.clock.nsecsElapsed() / (self.duration * 1000000))
        v = 1 - pow(1 - t, 3)
        self._opacity = self._fromOpacity + (self._toOpacity - self._fromOpacity) * v
        self._scale = self._fromScale + (self._toScale - self._fromScale) * v
        self.update()
        if t >= 1:
            self.timer.stop()

    def _clearCache(self):
        self._cache = QImage()
        self._cacheKey = None

    def getZoomFactor(self):
        return self._zoomFactor

    def setZoomFactor(self, factor: float):
        self._zoomFactor = max(1.0, float(factor))
        self.update()

    def getLensSize(self):
        return self._lensSize

    def setLensSize(self, size: int):
        self._lensSize = max(1, int(size))
        self._overlayKey = None
        self.update()

    def getBorderRadius(self):
        return self._borderRadius

    def setBorderRadius(self, radius: int):
        self._borderRadius = max(0, int(radius))
        self.update()

    def getDuration(self):
        return self._duration

    def setDuration(self, ms: int):
        self._duration = max(1, int(ms))

    def getLensPosition(self):
        return self._position

    def setLensPosition(self, position):
        pos = QPointF(position)
        pos = QPointF(max(0, min(self.width(), pos.x())), max(0, min(self.height(), pos.y())))
        if pos == self._position:
            return
        self._position = pos
        self.update()

    def getAspectRatioMode(self):
        return self._aspectRatioMode

    def setAspectRatioMode(self, mode: Qt.AspectRatioMode):
        if mode == self.aspectRatioMode:
            return
        self._aspectRatioMode = mode
        self._clearCache()
        self.update()

    def isStatic(self):
        return self._isStatic

    def setStatic(self, isStatic: bool):
        if isStatic == self.static:
            return
        self._isStatic = isStatic
        self.setHovering(isStatic)
        self.unsetCursor()

    def isHovering(self):
        return self._hovering

    def setHovering(self, hovering: bool):
        if hovering == self.hovering:
            return
        self._hovering = hovering
        self.hoveringChanged.emit(hovering)
        self._startAnimation(hovering)

    def isCursorHidden(self):
        return self._cursorHidden

    def setCursorHidden(self, isHidden: bool):
        self._cursorHidden = isHidden
        if not isHidden:
            self.unsetCursor()
 
    zoomFactor = pyqtProperty(float, getZoomFactor, setZoomFactor)
    lensSize = pyqtProperty(int, getLensSize, setLensSize)
    borderRadius = pyqtProperty(int, getBorderRadius, setBorderRadius)
    duration = pyqtProperty(int, getDuration, setDuration)
    lensPosition = pyqtProperty(QPointF, getLensPosition, setLensPosition)
    aspectRatioMode = pyqtProperty(Qt.AspectRatioMode, getAspectRatioMode, setAspectRatioMode)
    static = pyqtProperty(bool, isStatic, setStatic)
    hovering = pyqtProperty(bool, isHovering, setHovering)
    cursorHidden = pyqtProperty(bool, isCursorHidden, setCursorHidden)
