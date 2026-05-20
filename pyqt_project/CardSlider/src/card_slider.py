# coding:utf-8
from typing import List, Union

from PyQt5.QtCore import Qt, QSize, QRectF, QPointF, QTimer, QElapsedTimer, pyqtProperty, pyqtSignal
from PyQt5.QtGui import (QColor, QFont, QImage, QPainter, QPainterPath, QPixmap, QTransform,
                         QWheelEvent, QMouseEvent, QPolygonF)
from PyQt5.QtWidgets import QWidget

from qfluentwidgets.common.font import setFont


class CardSliderItem:

    def __init__(self, image: Union[QImage, QPixmap, str], title='', subtitle='', description=''):
        self.title = title
        self.subtitle = subtitle
        self.description = description
        self.path = ''
        self.image = QImage()
        self.cardCache = QImage()
        self.bgCache = QImage()
        self.cardCacheKey = None
        self.bgCacheKey = None
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

        self.clearCache()

    def load(self):
        if self.image.isNull() and self.path:
            self.image.load(self.path)

        return self.image

    def clearCache(self):
        self.cardCache = QImage()
        self.bgCache = QImage()
        self.cardCacheKey = None
        self.bgCacheKey = None


class _FrameClock:

    def __init__(self, view: 'CardSlider'):
        self.view = view
        self.timer = QTimer(view)
        self.elapsedTimer = QElapsedTimer()
        self.duration = 800
        self.fromIndex = 0
        self.toIndex = 0
        self.direction = 1
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self._tick)

    def start(self, fromIndex: int, toIndex: int, direction: int, duration: int):
        self.duration = max(1, duration)
        self.fromIndex = fromIndex
        self.toIndex = toIndex
        self.direction = direction
        self.elapsedTimer.restart()
        self.timer.start()
        self._tick()

    def stop(self):
        self.timer.stop()

    def isRunning(self):
        return self.timer.isActive()

    def _tick(self):
        t = min(1, self.elapsedTimer.nsecsElapsed() / (self.duration * 1000000))
        self.view._setProgress(1 - pow(1 - t, 3))
        if t >= 1:
            self.timer.stop()
            self.view._finishAnimation()


class CardSlider(QWidget):

    currentIndexChanged = pyqtSignal(int)
    animationStarted = pyqtSignal(int, int)
    animationFinished = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._items = []
        self._currentIndex = -1
        self._fromIndex = -1
        self._toIndex = -1
        self._direction = 1
        self._lastDirection = 1
        self._progress = 1.0
        self._hoverAngle = 0.0
        self._targetHoverAngle = 0.0
        self._itemSize = QSize(250, 400)
        self._borderRadius = 8
        self._duration = 800
        self._interval = 2000
        self._cardSpacing = 0
        self._backgroundEnabled = True
        self._tiltEnabled = True
        self._autoPlay = False
        self._aspectRatioMode = Qt.AspectRatioMode.KeepAspectRatioByExpanding

        self.frameClock = _FrameClock(self)
        self.tiltTimer = QTimer(self)
        self.playTimer = QTimer(self)

        self.tiltTimer.setTimerType(Qt.PreciseTimer)
        self.tiltTimer.setInterval(16)
        self.tiltTimer.timeout.connect(self._updateTilt)
        self.playTimer.setInterval(self.interval)
        self.playTimer.timeout.connect(self.scrollNext)

        setFont(self, 14)
        self.setMouseTracking(True)
        self.setMinimumSize(520, 500)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def addItem(self, image: Union[QImage, QPixmap, str], title='', subtitle='', description=''):

        self.addItems([CardSliderItem(image, title, subtitle, description)])

    def addItems(self, items: List[Union[CardSliderItem, tuple, dict]]):

        for item in items:
            if isinstance(item, CardSliderItem):
                self._items.append(item)
            elif isinstance(item, dict):
                self._items.append(CardSliderItem(item.get('image'), item.get('title', ''),
                                                 item.get('subtitle', ''), item.get('description', '')))
            else:
                values = list(item) + [''] * 4
                self._items.append(CardSliderItem(values[0], values[1], values[2], values[3]))

        if self._items and self.currentIndex() < 0:
            self._currentIndex = 0
            self._fromIndex = 0
            self._toIndex = 0

        self.update()

    def setItem(self, index: int, image=None, title=None, subtitle=None, description=None):

        if not 0 <= index < self.count():
            return

        item = self._items[index]
        if image is not None:
            item.setImage(image)
        if title is not None:
            item.title = title
        if subtitle is not None:
            item.subtitle = subtitle
        if description is not None:
            item.description = description
        self.update()

    def removeItem(self, index: int):
        if not 0 <= index < self.count():
            return

        del self._items[index]
        self._currentIndex = min(self._currentIndex, self.count() - 1)
        self._fromIndex = self._toIndex = self._currentIndex
        self.update()

    def clear(self):
        self._items.clear()
        self._currentIndex = self._fromIndex = self._toIndex = -1
        self.update()

    def count(self):
        return len(self._items)

    def currentIndex(self):
        return self._currentIndex

    def setCurrentIndex(self, index: int):

        self.scrollToIndex(index)

    def scrollToIndex(self, index: int):

        if not 0 <= index < self.count() or index == self.currentIndex() or self.frameClock.isRunning():
            return

        n = self.count()
        step = (index - self.currentIndex()) % n
        if step > n / 2:
            step -= n
        self._startSlide(index, 1 if step > 0 else -1)

    def scrollNext(self):

        if self.count() > 1:
            self._startSlide((self.currentIndex() + 1) % self.count(), 1)

    def scrollPrevious(self):

        if self.count() > 1:
            self._startSlide((self.currentIndex() - 1) % self.count(), -1)

    def play(self):
        """ play automatically """
        self.setAutoPlay(True)

    def pause(self):
        """ pause autoplay """
        self.setAutoPlay(False)

    def image(self, index: int):
        if not 0 <= index < self.count():
            return QImage()

        return self._items[index].load()

    def item(self, index: int):
        if not 0 <= index < self.count():
            return None

        return self._items[index]

    def _startSlide(self, index: int, direction: int):
        if not 0 <= index < self.count() or index == self.currentIndex() or self.frameClock.isRunning():
            return

        self._fromIndex = self.currentIndex()
        self._toIndex = index
        self._direction = direction
        self._lastDirection = direction
        self._progress = 0
        self._currentIndex = index
        self.currentIndexChanged.emit(index)
        self.animationStarted.emit(self._fromIndex, index)
        self.frameClock.start(self._fromIndex, self._toIndex, direction, self.duration)

    def _setProgress(self, progress: float):
        self._progress = progress
        self.update()

    def _finishAnimation(self):
        self._progress = 1.0
        self._fromIndex = self._toIndex = self.currentIndex()
        self.animationFinished.emit(self.currentIndex())
        self.update()

    def _visibleCards(self):
        if not self.count():
            return []
        if self.count() < 2:
            return [(0, self.currentIndex(), 1)]
        if self.count() == 2 and not self.frameClock.isRunning():
            side = -self._lastDirection
            return [(0, self.currentIndex(), 1), (side, self._sideIndex(side), 1)]

        if self.frameClock.isRunning():
            p = self._progress
            d = self._direction
            if self.count() == 2:
                return [(-d * p, self._fromIndex, 1), (d * (1 - p), self._toIndex, 1)]

            oldSide = (self._fromIndex - d) % self.count()
            newSide = (self._toIndex + d) % self.count()
            cards = [(-d * p, self._fromIndex, 1), (d * (1 - p), self._toIndex, 1)]
            if oldSide == newSide:
                cards.append((-d + 2 * d * p, oldSide, 1))
            else:
                cards.append((-d, oldSide, 1 - p))
                cards.append((d, newSide, p))
            return cards

        return [(0, self.currentIndex(), 1), (-1, self._sideIndex(-1), 1), (1, self._sideIndex(1), 1)]

    def _sideIndex(self, side: int):
        if self.count() < 2:
            return self.currentIndex()

        return (self.currentIndex() + side) % self.count()

    def _cardRect(self, slot: float):
        s = min(max(1, self.width()) / (self.itemSize.width() * 3),
                max(1, self.height() - 56) / (self.itemSize.height() * 1.25), 1.0)
        width = round(self.itemSize.width() * s)
        height = round(self.itemSize.height() * s)
        cx = round(self.width() / 2)
        cy = round(self.height() / 2 - 10)
        x = round(cx - width / 2 + slot * (width * 1.1 + self.cardSpacing))
        y = round(cy - height / 2)
        return QRectF(x, y, width, height)

    def _cardState(self, slot: float):
        a = min(1, abs(slot))
        scale = 1.2 + (0.9 - 1.2) * a
        opacity = 0.8 + (0.4 - 0.8) * a
        rotation = -25 * slot + self._hoverAngle * (1 - a)
        z = 100 - int(a * 20)
        return scale, opacity, rotation, z

    def _paintBackground(self, painter: QPainter):
        if not self.backgroundEnabled or self.currentIndex() < 0:
            return

        pairs = [(self._fromIndex, 1 - self._progress, -0.25 * self._direction * self._progress),
                 (self._toIndex, self._progress, 0.25 * self._direction * (1 - self._progress))]
        if not self.frameClock.isRunning():
            pairs = [(self.currentIndex(), 1, 0)]

        for index, opacity, offset in pairs:
            if index < 0 or opacity <= 0:
                continue
            image = self._backgroundCache(self._items[index])
            if image.isNull():
                continue
            painter.save()
            painter.setOpacity(opacity)
            x = (self.width() - image.width()) / 2 + offset * self.width()
            y = (self.height() - image.height()) / 2
            painter.drawImage(QPointF(x, y), image)
            painter.restore()

        painter.fillRect(self.rect(), QColor(0, 0, 0, 190))

    def _backgroundCache(self, item: CardSliderItem):
        image = item.load()
        if image.isNull():
            return QImage()

        size = QSize(max(1, int(self.width() * 1.8)), max(1, int(self.height() * 1.8)))
        key = ('bg', image.cacheKey(), int(size.width()), int(size.height()))
        if item.bgCacheKey != key:
            item.bgCache = image.scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            item.bgCacheKey = key

        return item.bgCache

    def _cardCache(self, item: CardSliderItem, size: QSize):
        image = item.load()
        if image.isNull():
            return QImage()

        key = ('card', image.cacheKey(), size.width(), size.height(), self.aspectRatioMode)
        if item.cardCache.isNull() or item.cardCacheKey != key:
            cache = image.scaled(size, self.aspectRatioMode, Qt.SmoothTransformation)
            if self.aspectRatioMode == Qt.AspectRatioMode.KeepAspectRatioByExpanding:
                cache = cache.copy(max(0, (cache.width() - size.width()) // 2),
                                   max(0, (cache.height() - size.height()) // 2),
                                   size.width(), size.height())
            item.cardCache = cache
            item.cardCacheKey = key

        return item.cardCache

    def _paintCard(self, painter: QPainter, index: int, slot: float, opacityFactor=1):
        if not 0 <= index < self.count():
            return

        rect = self._cardRect(slot)
        scale, opacity, rotation, _ = self._cardState(slot)
        image = self._cardCache(self._items[index], rect.size().toSize())
        if image.isNull():
            return

        cardRect = QRectF(rect.center().x() - rect.width() * scale / 2,
                          rect.center().y() - rect.height() * scale / 2,
                          rect.width() * scale, rect.height() * scale)
        transform = QTransform()
        transform.translate(cardRect.center().x(), cardRect.center().y())
        transform.rotate(rotation, Qt.YAxis)
        transform.translate(-cardRect.center().x(), -cardRect.center().y())
        points = transform.map(QPolygonF([cardRect.topLeft(), cardRect.topRight(),
                                          cardRect.bottomRight(), cardRect.bottomLeft()]))
        src = QPolygonF([QPointF(0, 0), QPointF(image.width(), 0),
                         QPointF(image.width(), image.height()), QPointF(0, image.height())])
        dst = QTransform()
        if not QTransform.quadToQuad(src, points, dst):
            return

        painter.save()
        painter.setOpacity((opacity + 0.2 * (1 - min(1, abs(slot)))) * opacityFactor)
        self._drawShadow(painter, cardRect, points)
        painter.setTransform(dst, True)
        painter.setPen(Qt.NoPen)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, image.width(), image.height()), self.borderRadius, self.borderRadius)
        painter.setClipPath(path)
        painter.drawImage(QRectF(0, 0, image.width(), image.height()), image)
        painter.fillRect(QRectF(0, 0, image.width(), image.height()), QColor(0, 0, 0, int(150 * (1 - opacity))))
        painter.restore()

    def _drawShadow(self, painter: QPainter, rect: QRectF, points: QPolygonF):
        painter.save()
        painter.setPen(Qt.NoPen)
        src = QPolygonF([rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()])
        path = QPainterPath()
        path.addRoundedRect(rect, self.borderRadius, self.borderRadius)
        shadowPoints = QPolygonF([p + QPointF(0, 8) for p in points])
        transform = QTransform()
        if QTransform.quadToQuad(src, shadowPoints, transform):
            painter.setBrush(QColor(0, 0, 0, 28))
            painter.setTransform(transform, True)
            painter.drawPath(path)
        painter.restore()

    def _paintInfo(self, painter: QPainter):
        if self.currentIndex() < 0:
            return

        p = self._progress if self.frameClock.isRunning() else 1
        oldOpacity, newOpacity = 1 - min(1, p * 1.8), min(1, max(0, (p - 0.35) / 0.65))
        if self.frameClock.isRunning() and self._fromIndex >= 0:
            self._drawInfo(painter, self._items[self._fromIndex], oldOpacity, -120 * p)
        self._drawInfo(painter, self._items[self.currentIndex()], newOpacity, 40 * (1 - newOpacity))

    def _drawInfo(self, painter: QPainter, item: CardSliderItem, opacity: float, offsetY: float):
        if opacity <= 0:
            return

        rect = self._cardRect(0)
        sizeRatio = rect.width() / max(1, self.itemSize.width())
        baseX = self.width() / 2 - rect.width() * 1.5 + rect.width() / 1.5
        baseY = rect.bottom() - rect.height() / 8 + offsetY
        texts = [(item.title.upper(), 0, 0, 0.18, QFont.Bold),
                 (item.subtitle.upper(), 36 * sizeRatio, 40 * sizeRatio, 0.12, QFont.DemiBold),
                 (item.description, 88 * sizeRatio, 0, 0.065, QFont.Medium)]

        painter.save()
        painter.setOpacity(opacity)
        transform = QTransform()
        transform.translate(rect.center().x(), rect.center().y())
        transform.rotate(self._hoverAngle * 0.35, Qt.YAxis)
        transform.translate(-rect.center().x(), -rect.center().y())
        painter.setTransform(transform, True)
        painter.setPen(Qt.white)
        for text, dy, dx, scale, weight in texts:
            if not text:
                continue
            font = QFont('Montserrat', max(9, int(rect.width() * scale)), weight)
            font.setLetterSpacing(QFont.AbsoluteSpacing, 0)
            painter.setFont(font)
            painter.drawText(QPointF(baseX + dx, baseY + dy), text)
            if dx:
                painter.fillRect(QRectF(baseX + dx - 40 * sizeRatio, baseY + dy - 12 * sizeRatio,
                                        20 * sizeRatio, 5 * sizeRatio), Qt.white)
                painter.fillRect(QRectF(baseX + dx - 40 * sizeRatio, baseY + dy + 28 * sizeRatio,
                                        60 * sizeRatio, 2 * sizeRatio), Qt.white)
        painter.restore()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self._paintBackground(painter)
        for _, index, slot, opacity in sorted((self._cardState(s)[3], i, s, o) for s, i, o in self._visibleCards()):
            self._paintCard(painter, index, slot, opacity)
        self._paintInfo(painter)

    def wheelEvent(self, e: QWheelEvent):
        e.setAccepted(True)
        if e.angleDelta().y() < 0:
            self.scrollNext()
        else:
            self.scrollPrevious()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self.tiltEnabled:
            rect = self._cardRect(0)
            self._targetHoverAngle = max(-12, min(12, (e.pos().x() - rect.center().x()) / rect.width() * 24))
            if not self.tiltTimer.isActive():
                self.tiltTimer.start()

    def leaveEvent(self, e):
        self._targetHoverAngle = 0
        if not self.tiltTimer.isActive():
            self.tiltTimer.start()

    def _updateTilt(self):
        self._hoverAngle += (self._targetHoverAngle - self._hoverAngle) * 0.22
        if abs(self._hoverAngle - self._targetHoverAngle) < 0.05:
            self._hoverAngle = self._targetHoverAngle
            self.tiltTimer.stop()
        self.update()

    def getItemSize(self):
        return self._itemSize

    def setItemSize(self, size: QSize):
        if size == self.itemSize:
            return
        self._itemSize = size
        self._clearCache()
        self.update()

    def getBorderRadius(self):
        return self._borderRadius

    def setBorderRadius(self, radius: int):
        self._borderRadius = max(0, radius)
        self.update()

    def getDuration(self):
        return self._duration

    def setDuration(self, ms: int):
        self._duration = max(1, ms)

    def getInterval(self):
        return self._interval

    def setInterval(self, ms: int):
        self._interval = max(0, ms)
        self.playTimer.setInterval(self.interval)

    def getCardSpacing(self):
        return self._cardSpacing

    def setCardSpacing(self, spacing: int):
        self._cardSpacing = max(0, spacing)
        self.update()

    def isBackgroundEnabled(self):
        return self._backgroundEnabled

    def setBackgroundEnabled(self, isEnabled: bool):
        self._backgroundEnabled = isEnabled
        self.update()

    def isTiltEnabled(self):
        return self._tiltEnabled

    def setTiltEnabled(self, isEnabled: bool):
        self._tiltEnabled = isEnabled
        self._targetHoverAngle = 0
        self.update()

    def isAutoPlay(self):
        return self._autoPlay

    def setAutoPlay(self, isEnabled: bool):
        if isEnabled == self.autoPlay:
            return
        self._autoPlay = isEnabled
        self.playTimer.start() if isEnabled else self.playTimer.stop()

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
            item.clearCache()

    itemSize = pyqtProperty(QSize, getItemSize, setItemSize)
    borderRadius = pyqtProperty(int, getBorderRadius, setBorderRadius)
    duration = pyqtProperty(int, getDuration, setDuration)
    interval = pyqtProperty(int, getInterval, setInterval)
    cardSpacing = pyqtProperty(int, getCardSpacing, setCardSpacing)
    backgroundEnabled = pyqtProperty(bool, isBackgroundEnabled, setBackgroundEnabled)
    tiltEnabled = pyqtProperty(bool, isTiltEnabled, setTiltEnabled)
    autoPlay = pyqtProperty(bool, isAutoPlay, setAutoPlay)
    aspectRatioMode = pyqtProperty(Qt.AspectRatioMode, getAspectRatioMode, setAspectRatioMode)
