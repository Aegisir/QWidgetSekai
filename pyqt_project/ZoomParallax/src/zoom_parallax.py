# coding:utf-8
from dataclasses import dataclass, field
from typing import List, Union

from PyQt5.QtCore import QRectF, QSize, QTimer, Qt, pyqtProperty, pyqtSignal  # type: ignore[reportAttributeAccessIssue]
from PyQt5.QtGui import QColor, QImage, QImageReader, QPainter, QPixmap, QWheelEvent
from PyQt5.QtWidgets import QWidget
from qfluentwidgets import ScrollArea


@dataclass
class ZoomParallaxItem:
    """ Parallax image item """

    image: QImage
    path: str = ''
    cache: QImage = field(default_factory=QImage)
    cacheKey: object = None

    @classmethod
    def fromImage(cls, image: Union[QImage, QPixmap, str]):
        if isinstance(image, QPixmap):
            image = image.toImage()
        if isinstance(image, QImage):
            return cls(image)
        return cls(QImage(), image or '')

    def load(self):
        if self.image.isNull() and self.path:
            self.image = QImageReader(self.path).read()
        return self.image

    def clearCache(self):
        self.cache = QImage()
        self.cacheKey = None


class _ZoomParallaxCanvas(QWidget):

    _SCALES = (4, 5, 6, 5, 6, 8, 9)
    _FRAMES = (
        (0, 0, 25, 25), (5, -30, 35, 30), (-25, -10, 20, 45),
        (27.5, 0, 25, 25), (5, 27.5, 20, 25), (-22.5, 27.5, 30, 25),
        (25, 22.5, 15, 15),
    )
    def __init__(self, view: 'ZoomParallax'):
        super().__init__(view.viewport())
        self.view = view
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet('background: transparent')

    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        for index, item in enumerate(self.view._items[:7]):
            image = self._cache(item, index)
            if image.isNull():
                continue
            rect = self._scaledRect(item, index)
            self._drawShadow(painter, rect)
            painter.drawImage(rect, image)

    def _drawShadow(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        for offset, alpha in ((8, 30), (4, 42), (1, 54)):
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRect(rect.translated(0, offset))
        painter.restore()

    def _scaledRect(self, item: ZoomParallaxItem, index: int):
        rect = self._baseRect(item, index)
        scale = 1 + self.view.progress * (self._SCALES[index] - 1) * self.view.zoomIntensity
        cx, cy = self.width() / 2, self.height() / 2
        x = cx + (rect.center().x() - cx) * scale
        y = cy + (rect.center().y() - cy) * scale
        return QRectF(x - rect.width() * scale / 2,
                      y - rect.height() * scale / 2,
                      rect.width() * scale, rect.height() * scale)

    def _baseRect(self, item: ZoomParallaxItem, index: int):
        x, y, w, h = self._FRAMES[index]
        width, height = self.width(), self.height()
        rw, rh = width * w / 100, height * h / 100
        return QRectF((width - rw) / 2 + width * x / 100,
                      (height - rh) / 2 + height * y / 100, rw, rh)

    def _cache(self, item: ZoomParallaxItem, index: int):
        image = item.load()
        if image.isNull():
            return QImage()

        size = (self._baseRect(item, index).size() * self._SCALES[index]).toSize() * self.devicePixelRatioF()
        size = QSize(max(1, size.width()), max(1, size.height()))
        key = (image.cacheKey(), size.width(), size.height(), self.view.aspectRatioMode)
        if item.cacheKey != key:
            cache = image.scaled(size, self.view.aspectRatioMode, Qt.TransformationMode.SmoothTransformation)
            if self.view.aspectRatioMode == Qt.AspectRatioMode.KeepAspectRatioByExpanding:
                cache = cache.copy(max(0, (cache.width() - size.width()) // 2),
                                   max(0, (cache.height() - size.height()) // 2),
                                   size.width(), size.height())
            cache.setDevicePixelRatio(self.devicePixelRatioF())
            item.cache = cache
            item.cacheKey = key
        return item.cache


class ZoomParallax(ScrollArea):
    """ Zoom parallax scroll view """

    progressChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._progress = 0.0
        self._targetProgress = 0.0
        self._contentHeightRatio = 3.0
        self._targetFps = 240
        self._zoomIntensity = 1.0
        self._aspectRatioMode = Qt.AspectRatioMode.KeepAspectRatioByExpanding

        self.contentWidget = QWidget()
        self.canvas = _ZoomParallaxCanvas(self)
        self.smoothTimer = QTimer(self)
        self.smoothTimer.setTimerType(Qt.TimerType.PreciseTimer)
        self.smoothTimer.timeout.connect(self._tick)

        self.setWidget(self.contentWidget)
        self.setFrameShape(self.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.enableTransparentBackground()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.contentWidget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.contentWidget.setStyleSheet('background: transparent')
        viewport = self.viewport()
        assert viewport is not None
        viewport.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        viewport.setStyleSheet('background: transparent')
        bar = self.verticalScrollBar()
        assert bar is not None
        bar.valueChanged.connect(self._onScroll)
        self.setMinimumSize(360, 300)
        self._updateTimer()

    def addImage(self, image: Union[QImage, QPixmap, str]):
        """ add image """
        self.addImages([image])

    def addImages(self, images: List[Union[QImage, QPixmap, str]]):
        """ add images """
        self._items.extend(ZoomParallaxItem.fromImage(i) for i in images)
        self.canvas.update()

    def setImage(self, index: int, image: Union[QImage, QPixmap, str]):
        """ set image by index """
        if not 0 <= index < self.count():
            return
        self._items[index] = ZoomParallaxItem.fromImage(image)
        self.canvas.update()

    def image(self, index: int):
        if not 0 <= index < self.count():
            return QImage()
        return self._items[index].load()

    def clear(self):
        self._items.clear()
        self.canvas.update()

    def count(self):
        return len(self._items)

    def heightForWidth(self, a0: int):
        return max(300, round(a0 * 9 / 16))

    def hasHeightForWidth(self):
        return True

    def sizeHint(self):
        return QSize(960, 540)

    def wheelEvent(self, a0: Union[QWheelEvent, None] = None):
        if a0 is None:
            return
        super().wheelEvent(a0)
        bar = self.verticalScrollBar()
        assert bar is not None
        self._onScroll(bar.value())

    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        viewport = self.viewport()
        assert viewport is not None
        self.canvas.setGeometry(viewport.rect())
        self.canvas.raise_()
        self._updateContentSize()
        self._clearCache()

    def _updateContentSize(self):
        viewport = self.viewport()
        assert viewport is not None
        h = max(1, round(viewport.height() * self.contentHeightRatio))
        self.contentWidget.resize(max(1, viewport.width()), h)

    def _onScroll(self, value: int):
        bar = self.verticalScrollBar()
        assert bar is not None
        self._targetProgress = 0 if bar.maximum() <= 0 else value / bar.maximum()
        if not self.smoothTimer.isActive():
            self.smoothTimer.start()

    def _tick(self):
        delta = self._targetProgress - self._progress
        if abs(delta) < 0.001:
            self.smoothTimer.stop()
            self.setProgress(self._targetProgress)
        else:
            self.setProgress(self._progress + delta * 0.24)

    def _clearCache(self):
        for item in self._items:
            item.clearCache()
        self.canvas.update()

    def getProgress(self):
        return self._progress

    def setProgress(self, progress: float):
        progress = max(0.0, min(1.0, float(progress)))
        if progress == self.progress:
            return
        self._progress = progress
        self.progressChanged.emit(progress)
        self.canvas.update()

    def getContentHeightRatio(self):
        return self._contentHeightRatio

    def setContentHeightRatio(self, ratio: float):
        ratio = max(1.01, float(ratio))
        if ratio == self.contentHeightRatio:
            return
        self._contentHeightRatio = ratio
        self._updateContentSize()

    def getTargetFps(self):
        return self._targetFps

    def setTargetFps(self, fps: int):
        self._targetFps = max(0, min(240, int(fps)))
        self._updateTimer()

    def _updateTimer(self):
        self.smoothTimer.setInterval(0 if self.targetFps <= 0 else max(1, round(1000 / self.targetFps)))

    def getAspectRatioMode(self):
        return self._aspectRatioMode

    def setAspectRatioMode(self, mode: Qt.AspectRatioMode):
        if mode == self.aspectRatioMode:
            return
        self._aspectRatioMode = mode
        self._clearCache()

    def getZoomIntensity(self):
        return self._zoomIntensity

    def setZoomIntensity(self, value: float):
        value = max(0.0, min(2.0, float(value)))
        if value == self.zoomIntensity:
            return
        self._zoomIntensity = value
        self.canvas.update()

    progress = pyqtProperty(float, getProgress, setProgress, notify=progressChanged)
    contentHeightRatio = pyqtProperty(float, getContentHeightRatio, setContentHeightRatio)
    targetFps = pyqtProperty(int, getTargetFps, setTargetFps)
    aspectRatioMode = pyqtProperty(Qt.AspectRatioMode, getAspectRatioMode, setAspectRatioMode)
    zoomIntensity = pyqtProperty(float, getZoomIntensity, setZoomIntensity)
