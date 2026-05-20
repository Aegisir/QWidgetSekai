# coding:utf-8
from enum import Enum
from math import cos, pi, sin
from typing import List, Union

from PyQt5.QtCore import Qt, QTimer, QSize, QRectF, QPointF, pyqtProperty, pyqtSignal, QElapsedTimer, QObject
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPainterPath, QColor, QWheelEvent, QPolygonF, QTransform
from PyQt5.QtWidgets import QWidget


class BannerShiftingDirection(Enum):
    """ Banner shifting direction """
    FORWARD = 0
    BACKWARD = 1


class BannerImageItem:
    """ Banner image item """

    def __init__(self, image: Union[QImage, QPixmap, str]):
        self.path = ''
        self.image = QImage()
        self.cache = QImage()
        self.cacheKey = None
        self.setImage(image)

    def setImage(self, image: Union[QImage, QPixmap, str]):
        if isinstance(image, QPixmap):
            image = image.toImage()

        if isinstance(image, QImage):
            self.image = image
            self.path = ''
        else:
            self.image = QImage()
            self.path = image or ''

        self.cache = QImage()
        self.cacheKey = None

    def load(self):
        if self.image.isNull() and self.path:
            self.image.load(self.path)

        return self.image


class BannerImageDelegate:
    """ Banner image delegate """

    def __init__(self, view: 'BannerView'):
        self.view = view

    def paint(self, painter: QPainter, item: BannerImageItem, points: QPolygonF):
        image = item.load()
        if image.isNull():
            return

        view = self.view
        key = (image.cacheKey(), view.itemSize.width(), view.itemSize.height(), view.aspectRatioMode)

        if item.cacheKey != key:
            item.cache = image.scaled(view.itemSize, view.aspectRatioMode, Qt.SmoothTransformation)
            if view.aspectRatioMode == Qt.AspectRatioMode.KeepAspectRatioByExpanding:
                x = max(0, int((item.cache.width() - view.itemSize.width()) / 2))
                y = max(0, int((item.cache.height() - view.itemSize.height()) / 2))
                item.cache = item.cache.copy(x, y, view.itemSize.width(), view.itemSize.height())

            item.cacheKey = key

        rect = QRectF(0, 0, item.cache.width(), item.cache.height())
        src = QPolygonF([rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()])
        transform = QTransform()
        if not QTransform.quadToQuad(src, points, transform):
            return

        painter.save()
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        painter.setPen(Qt.NoPen)

        painter.setTransform(transform, True)
        path = QPainterPath()
        path.addRoundedRect(rect, view.borderRadius, view.borderRadius)
        painter.setClipPath(path)
        painter.drawImage(rect, item.cache)
        painter.restore()


class BannerSlideAnimator(QObject):
    """ High frequency slide animator """

    finished = pyqtSignal()

    def __init__(self, view: 'BannerView'):
        super().__init__(view)
        self.view = view
        self.duration = 500
        self.startValue = 0
        self.endValue = 0
        self.elapsedTimer = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self._onTimeout)

    def start(self, startValue: float, endValue: float):
        self.startValue = startValue
        self.endValue = endValue
        self.elapsedTimer.restart()
        self.timer.start()
        self._onTimeout()

    def stop(self):
        self.timer.stop()

    def isRunning(self):
        return self.timer.isActive()

    def _onTimeout(self):
        t = min(1, self.elapsedTimer.nsecsElapsed() / (self.duration * 1000000))
        self.view.setSlideIndex(self.startValue + (self.endValue - self.startValue) * (1 - pow(1 - t, 3)))
        if t >= 1:
            self.timer.stop()
            self.finished.emit()


class BannerView(QWidget):
    """ Banner view """

    currentIndexChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._items = []
        self._currentIndex = -1
        self._slideIndex = 0.0
        self._itemSize = QSize(480, 270)
        self._borderRadius = 8
        self._itemSpacing = 60
        self._interval = 1000
        self._autoShuffle = False
        self._scaleEnabled = True
        self._perspectiveEnabled = False
        self._aspectRatioMode = Qt.AspectRatioMode.KeepAspectRatioByExpanding
        self._shiftingDirection = BannerShiftingDirection.FORWARD

        self.delegate = BannerImageDelegate(self)
        self.timer = QTimer(self)
        self.slideAni = BannerSlideAnimator(self)

        self.timer.setInterval(self.interval)
        self.timer.timeout.connect(self._onTimeout)
        self.slideAni.finished.connect(self._onSlideFinished)

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setMinimumSize(self.itemSize)

    def addImage(self, image: Union[QImage, QPixmap, str]):
        """ add image """
        self.addImages([image])

    def addImages(self, images: List[Union[QImage, QPixmap, str]], targetSize: QSize = None):
        """ add images """
        if not images:
            return

        self._items.extend(BannerImageItem(i) for i in images)
        if self.currentIndex() < 0:
            self._currentIndex = 0
            self._slideIndex = 0.0

        self.update()

    def setItemImage(self, index: int, image: Union[QImage, QPixmap, str], targetSize: QSize = None):
        """ set the image of specified item """
        if not 0 <= index < self.count():
            return

        self._items[index].setImage(image)
        self.update()

    def image(self, index: int):
        if not 0 <= index < self.count():
            return QImage()

        return self._items[index].load()

    def itemImage(self, index: int, load=True) -> QImage:
        """ get the image of specified item """
        if not 0 <= index < self.count():
            return QImage()

        return self._items[index].load() if load else self._items[index].image

    def count(self):
        return len(self._items)

    def currentIndex(self):
        return self._currentIndex

    def setCurrentIndex(self, index: int):
        """ set current index """
        if not 0 <= index < self.count() or index == self.currentIndex():
            return

        self.scrollToIndex(index)

    def scrollToIndex(self, index: int):
        """ scroll to index """
        if not 0 <= index < self.count():
            return

        n = self.count()
        delta = (index - self.slideIndex) % n
        if delta > n / 2:
            delta -= n

        self._currentIndex = index
        self.currentIndexChanged.emit(index)
        self.slideAni.start(self.slideIndex, self.slideIndex + delta)

    def scrollNext(self):
        """ scroll to next item """
        if self.count() > 1:
            self._scrollBy(1)

    def scrollPrevious(self):
        """ scroll to previous item """
        if self.count() > 1:
            self._scrollBy(-1)

    def _scrollBy(self, step: int):
        index = (self.currentIndex() + step) % self.count()
        self._currentIndex = index
        self.currentIndexChanged.emit(index)
        self.slideAni.start(self.slideIndex, self.slideIndex + step)

    def playShuffleForward(self):
        """ play shuffle forward """
        if not self.autoShuffle:
            return

        self.setShiftingDirection(BannerShiftingDirection.FORWARD)
        self.timer.start()

    def playShuffleBackward(self):
        """ play shuffle backward """
        if not self.autoShuffle:
            return

        self.setShiftingDirection(BannerShiftingDirection.BACKWARD)
        self.timer.start()

    def stopShuffle(self):
        """ stop shuffle """
        self.timer.stop()

    def _onTimeout(self):
        if self.shiftingDirection == BannerShiftingDirection.BACKWARD:
            self.scrollPrevious()
        else:
            self.scrollNext()

    def _onSlideFinished(self):
        if self.count() == 0:
            return

        index = int(round(self.slideIndex)) % self.count()
        self._slideIndex = float(index)
        self.update()

    def _visibleItems(self):
        n = self.count()
        if n < 2:
            return [(0, 0)] if n else []

        items = []
        for i in range(n):
            d = i - self.slideIndex
            for k in (-1, 0, 1):
                distance = d + k * n
                if abs(distance) <= 1.15:
                    items.append((distance, i))

        return sorted(items)

    def _itemTransform(self, distance: float):
        s = min(max(1, self.width() - 100) / self.itemSize.width(), max(1, self.height() - 20) / self.itemSize.height())
        w = self.itemSize.width() * s
        h = self.itemSize.height() * s
        d = max(-1.0, min(1.0, distance))
        scale = 1 - abs(d) * 0.1 if self.scaleEnabled else 1
        perspectiveSpacing = 0 if self.perspectiveEnabled else 20
        x = (self.width() - w) / 2 + distance * w - d * (self.itemSpacing + perspectiveSpacing)
        pivotRatio = (1 - d) / 2
        rect = QRectF(x + w * pivotRatio * (1 - scale), (self.height() - h * scale) / 2, w * scale, h * scale)
        return rect, self._perspectivePoints(rect, d)

    def _perspectivePoints(self, rect: QRectF, distance: float):
        if not self.perspectiveEnabled:
            return QPolygonF([rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()])

        angle = 0.2 * pi * distance
        c = cos(angle)
        z = sin(angle)
        depth = rect.width() * 0.5
        pivot = rect.left() + (1 - distance) * rect.width() / 2
        vanishing = self.width() / 2
        points = []

        for x, y in [(rect.left(), rect.top()), (rect.right(), rect.top()),
                     (rect.right(), rect.bottom()), (rect.left(), rect.bottom())]:
            dx = x - pivot
            rx = pivot + dx * c
            rz = dx * z
            factor = depth / (depth + rz) if depth + rz != 0 else 1
            points.append(QPointF(vanishing + (rx - vanishing) * factor, rect.center().y() + (y - rect.center().y()) * factor))

        return QPolygonF(points)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), Qt.transparent)

        for d, i in self._visibleItems():
            rect, points = self._itemTransform(d)
            self._drawShadow(painter, rect, points)
            self.delegate.paint(painter, self._items[i], points)

    def _drawShadow(self, painter: QPainter, rect: QRectF, points: QPolygonF):
        src = QPolygonF([rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()])
        path = QPainterPath()
        path.addRoundedRect(rect, self.borderRadius, self.borderRadius)
        painter.save()
        painter.setRenderHints(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        for y, a in ((6, 18), (3, 28), (1, 36)):
            transform = QTransform()
            if not QTransform.quadToQuad(src, QPolygonF([p + QPointF(0, y) for p in points]), transform):
                continue

            painter.setTransform(transform)
            painter.setBrush(QColor(0, 0, 0, a))
            painter.drawPath(path)
        painter.restore()

    def wheelEvent(self, e: QWheelEvent):
        e.setAccepted(True)
        if self.slideAni.isRunning():
            return

        if e.angleDelta().y() < 0:
            self.scrollNext()
        else:
            self.scrollPrevious()

    def getSlideIndex(self):
        return self._slideIndex

    def setSlideIndex(self, index: float):
        self._slideIndex = index
        self.update()

    def getItemSize(self):
        return self._itemSize

    def setItemSize(self, size: QSize):
        """ set the size of item """
        if size == self.itemSize:
            return

        self._itemSize = size
        self.setMinimumSize(size)
        self._clearCache()
        self.update()

    def getBorderRadius(self):
        return self._borderRadius

    def setBorderRadius(self, radius: int):
        """ set the border radius of item """
        if radius == self.borderRadius:
            return

        self._borderRadius = radius
        self.update()

    def getItemSpacing(self):
        return self._itemSpacing

    def setItemSpacing(self, spacing: int):
        """ set the spacing between items """
        if spacing == self.itemSpacing:
            return

        self._itemSpacing = spacing
        self.update()

    def getInterval(self):
        return self._interval

    def setInterval(self, ms: int):
        """ set shuffle interval """
        self._interval = max(0, ms)
        self.timer.setInterval(self.interval)

    def getShiftingDirection(self):
        return self._shiftingDirection

    def setShiftingDirection(self, direction: BannerShiftingDirection):
        """ set shifting direction """
        if direction == self.shiftingDirection:
            return

        self._shiftingDirection = direction

    def isAutoShuffle(self):
        return self._autoShuffle

    def setAutoShuffle(self, isEnabled: bool):
        """ set whether to shuffle automatically """
        if isEnabled == self.autoShuffle:
            return

        self._autoShuffle = isEnabled
        if isEnabled:
            self.timer.start()
        else:
            self.timer.stop()

    def isScaleEnabled(self):
        return self._scaleEnabled

    def setScaleEnabled(self, isEnabled: bool):
        """ set whether to enable scale animation """
        if isEnabled == self.scaleEnabled:
            return

        self._scaleEnabled = isEnabled
        self.update()

    def isPerspectiveEnabled(self):
        return self._perspectiveEnabled

    def setPerspectiveEnabled(self, isEnabled: bool):
        """ set whether to enable perspective animation """
        if isEnabled == self.perspectiveEnabled:
            return

        self._perspectiveEnabled = isEnabled
        self.update()

    def getAspectRatioMode(self):
        return self._aspectRatioMode

    def setAspectRatioMode(self, mode: Qt.AspectRatioMode):
        if mode == self.aspectRatioMode:
            return

        self._aspectRatioMode = mode
        self._clearCache()
        self.update()

    def _clearCache(self):
        for item in self._items:
            item.cache = QImage()
            item.cacheKey = None

    slideIndex = pyqtProperty(float, getSlideIndex, setSlideIndex)
    itemSize = pyqtProperty(QSize, getItemSize, setItemSize)
    borderRadius = pyqtProperty(int, getBorderRadius, setBorderRadius)
    itemSpacing = pyqtProperty(int, getItemSpacing, setItemSpacing)
    interval = pyqtProperty(int, getInterval, setInterval)
    shiftingDirection = pyqtProperty(BannerShiftingDirection, getShiftingDirection, setShiftingDirection)
    autoShuffle = pyqtProperty(bool, isAutoShuffle, setAutoShuffle)
    scaleEnabled = pyqtProperty(bool, isScaleEnabled, setScaleEnabled)
    perspectiveEnabled = pyqtProperty(bool, isPerspectiveEnabled, setPerspectiveEnabled)
    aspectRatioMode = pyqtProperty(Qt.AspectRatioMode, getAspectRatioMode, setAspectRatioMode)
