from collections import deque
from math import cos, exp, floor, fmod, radians, sin
from typing import Deque, Iterable, List, Optional, Tuple, Union

from PyQt5.QtCore import (
    QElapsedTimer,
    QEvent,
    QRectF,
    QSize,
    QTimer,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QFont,
    QImage,
    QImageReader,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PyQt5.QtWidgets import QApplication, QWidget

from qfluentwidgets.common.font import getFont

ImageSource = Union[QImage, QPixmap, str]

CARD_CACHE_PADDING = 2

CARD_SIZE = QSize(256, 384)

DISTANCE_DIVISOR = 200
VELOCITY_DIVISOR = 800

DRAG_SENSITIVITY = 250

HORIZONTAL_OFFSET = 170
VERTICAL_OFFSET = 40
ROTATION_ANGLE = 12
SCALE_REDUCTION = 0.12

TITLE_BOTTOM = 40
TITLE_SIZE = 20

CANDIDATE_RADIUS = 9


def _physicalSize(size: QSize, devicePixelRatio: float) -> QSize:
    return QSize(
        max(1, round(size.width() * devicePixelRatio)),
        max(1, round(size.height() * devicePixelRatio)),
    )

def _transparentImage(size: QSize, devicePixelRatio: float) -> QImage:
    image = QImage(
        _physicalSize(size, devicePixelRatio),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(Qt.GlobalColor.transparent)
    image.setDevicePixelRatio(devicePixelRatio)
    return image

class StackedCardCarouselItem:

    def __init__(self, image: ImageSource, title: str = ''):
        self.title = title

        self._imagePath = ''
        self._sourceImage = QImage()

        self._cardCache = QImage()
        self._titleCache = QImage()

        self._cardCacheKey: Optional[Tuple[int, int, int, float]] = None
        self._titleCacheKey: Optional[Tuple[str, str, int, int, float, float]] = None
        self.setImage(image)

    def setImage(self, image: ImageSource):
        if isinstance(image, QPixmap):
            image = image.toImage()

        if isinstance(image, QImage):
            self._sourceImage = image
            self._imagePath = ''
        else:
            self._sourceImage = QImage()
            self._imagePath = image or ''

        self.clearCache()
    def image(self) -> QImage:
        if self._sourceImage.isNull() and self._imagePath:
            reader = QImageReader(self._imagePath)
            reader.setAutoTransform(True)
            self._sourceImage = reader.read()

        return self._sourceImage
    def cardImage(self, size: QSize, devicePixelRatio: float) -> QImage:
        image = self.image()
        if image.isNull():
            return QImage()
        contentSize = _physicalSize(size, devicePixelRatio)
        cacheKey = (
            image.cacheKey(),
            contentSize.width(),
            contentSize.height(),
            devicePixelRatio,
        )
        if self._cardCacheKey == cacheKey:
            return self._cardCache
        scaledImage = image.scaled(
            contentSize,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        cropX = max(0, (scaledImage.width() - contentSize.width()) // 2)
        cropY = max(0, (scaledImage.height() - contentSize.height()) // 2)
        scaledImage = scaledImage.copy(
            cropX,
            cropY,
            contentSize.width(),
            contentSize.height(),
        )
        scaledImage.setDevicePixelRatio(devicePixelRatio)
        padding = CARD_CACHE_PADDING
        cacheSize = size + QSize(padding * 2, padding * 2)
        cardImage = _transparentImage(cacheSize, devicePixelRatio)
        cardRect = QRectF(padding, padding, size.width(), size.height())
        painter = QPainter(cardImage)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clipPath = QPainterPath()
        clipPath.addRoundedRect(cardRect, 16, 16)
        painter.setClipPath(clipPath)
        painter.drawImage(cardRect, scaledImage)
        gradient = QLinearGradient(cardRect.topLeft(), cardRect.bottomLeft())
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.5, QColor(0, 0, 0, 51))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 204))
        painter.fillRect(cardRect, gradient)
        painter.end()

        self._cardCache = cardImage
        self._cardCacheKey = cacheKey
        return cardImage
    def titleImage(
        self,
        size: QSize,
        font: QFont,
        bottomMargin: float,
        devicePixelRatio: float,
    ) -> QImage:
        physicalSize = _physicalSize(size, devicePixelRatio)
        cacheKey = (
            self.title,
            font.toString(),
            physicalSize.width(),
            physicalSize.height(),
            bottomMargin,
            devicePixelRatio,
        )
        if self._titleCacheKey == cacheKey:
            return self._titleCache
        titleImage = _transparentImage(size, devicePixelRatio)
        painter = QPainter(titleImage)
        painter.setFont(font)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(
            QRectF(0, 0, size.width(), size.height() - bottomMargin),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
            self.title,
        )
        painter.end()
        self._titleCache = titleImage
        self._titleCacheKey = cacheKey
        return titleImage
    def clearCache(self):
        self._cardCache = QImage()
        self._titleCache = QImage()
        self._cardCacheKey = None
        self._titleCacheKey = None

class StackedCardCarousel(QWidget):

    currentIndexChanged = pyqtSignal(int)
    animationStarted = pyqtSignal(int, int)
    animationFinished = pyqtSignal(int)

    _springRestSpeed = 0.01
    _springRestDistance = 0.005

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._items: List[StackedCardCarouselItem] = []
        self._currentIndex = -1
        self._scrollProgress = 0.0
        self._animationEnabled = True
        self._pressPosition: Optional[float] = None
        self._lastPointerPosition = 0.0
        self._dragStartProgress = 0.0
        self._pointerSamples: Deque[Tuple[int, float]] = deque()
        self._springTarget = 0.0
        self._springFirstCoefficient = 0.0
        self._springSecondCoefficient = 0.0
        self._overlayCache = QImage()
        self._overlayCacheKey: Optional[Tuple[int, int, float]] = None
        self._eventClock = QElapsedTimer()
        self._springClock = QElapsedTimer()
        self._eventClock.start()
        self._animationTimer = QTimer(self)
        self._animationTimer.setTimerType(Qt.TimerType.PreciseTimer)
        self._animationTimer.setInterval(16)
        self._animationTimer.timeout.connect(self._advanceSpring)

        self._titleFont = getFont(TITLE_SIZE, QFont.Bold)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMinimumSize(self.minimumSizeHint())
    def addItem(self, image: ImageSource, title: str = ''):
        self.addItems([StackedCardCarouselItem(image, title)])

    def addItems(self, items: Iterable[StackedCardCarouselItem]):
        newItems = list(items)
        if not all(isinstance(item, StackedCardCarouselItem) for item in newItems):
            raise TypeError('items must contain StackedCardCarouselItem values')

        self._items.extend(newItems)
        if self._currentIndex < 0 and self._items:
            self._currentIndex = 0
            self._scrollProgress = 0.0
            self.currentIndexChanged.emit(0)
        self.update()
    def setItem(
        self,
        index: int,
        image: Optional[ImageSource] = None,
        title: Optional[str] = None,
    ):
        if not 0 <= index < self.count():
            return

        item = self._items[index]
        if image is not None:
            item.setImage(image)
        if title is not None:
            item.title = title
        self.update()
    def removeItem(self, index: int):
        if not 0 <= index < self.count():
            return

        previousIndex = self._currentIndex
        self._stopInteraction()
        del self._items[index]
        if not self._items:
            self._currentIndex = -1
            self._scrollProgress = 0.0
        elif index < previousIndex:
            self._currentIndex = previousIndex - 1
            self._scrollProgress = float(self._currentIndex)
        else:
            self._currentIndex = min(previousIndex, self.count() - 1)
            self._scrollProgress = float(self._currentIndex)

        if self._currentIndex != previousIndex:
            self.currentIndexChanged.emit(self._currentIndex)
        self.update()
    def clear(self):
        if not self._items:
            return

        self._stopInteraction()
        self._items.clear()
        self._currentIndex = -1
        self._scrollProgress = 0.0
        self.currentIndexChanged.emit(-1)
        self.update()

    def count(self) -> int:
        return len(self._items)

    def item(self, index: int) -> Optional[StackedCardCarouselItem]:
        return self._items[index] if 0 <= index < self.count() else None

    def image(self, index: int) -> QImage:
        item = self.item(index)
        return item.image() if item is not None else QImage()

    def currentIndex(self) -> int:
        return self._currentIndex
    def setCurrentIndex(self, index: int):
        self.scrollToIndex(index)

    def scrollToIndex(self, index: int):
        if not 0 <= index < self.count():
            return
        nearestCycle = self._roundLikeJavaScript(
            (self._scrollProgress - index) / self.count()
        )
        targetProgress = index + nearestCycle * self.count()
        self._startSpring(float(targetProgress), 0.0)

    def scrollNext(self):
        if self.count() > 1:
            self.scrollToIndex((self.currentIndex() + 1) % self.count())

    def scrollPrevious(self):
        if self.count() > 1:
            self.scrollToIndex((self.currentIndex() - 1) % self.count())

    def isAnimationEnabled(self) -> bool:
        return self._animationEnabled

    def setAnimationEnabled(self, enabled: bool):
        self._animationEnabled = bool(enabled)
        if not self._animationEnabled and self._animationTimer.isActive():
            self._finishSpring()

    def sizeHint(self) -> QSize:
        return QSize(1120, 512)

    def minimumSizeHint(self) -> QSize:
        return QSize(320, 320)
    def paintEvent(self, event):
        del event
        if not self._items:
            return

        cardStates = []
        for index in self._visibleIndices():
            offset = self._wrappedOffset(index)
            opacity = self._cardOpacity(offset)
            if opacity > 0 and self._cardIntersectsViewport(offset):
                zIndex = self._roundLikeJavaScript(100 - abs(offset) * 10)
                cardStates.append((zIndex, index, offset, opacity))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for _, index, offset, opacity in sorted(cardStates):
            self._paintCard(painter, self._items[index], offset, opacity)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.count() > 1:
            self._beginDrag(event.localPos().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            int(event.buttons()) & int(Qt.MouseButton.LeftButton) != 0
            and self._pressPosition is not None
        ):
            self._updateDrag(event.localPos().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._pressPosition is not None
        ):
            self._completeDrag(event.localPos().x())
            event.accept()
            return
        super().mouseReleaseEvent(event)
    def event(self, event: QEvent) -> bool:
        if event.type() not in (
            QEvent.Type.TouchBegin,
            QEvent.Type.TouchUpdate,
            QEvent.Type.TouchEnd,
            QEvent.Type.TouchCancel,
        ):
            return super().event(event)

        touchPoints = event.touchPoints()
        pointerPosition = (
            touchPoints[0].pos().x()
            if touchPoints
            else self._lastPointerPosition
        )
        if event.type() == QEvent.Type.TouchBegin and self.count() > 1:
            self._beginDrag(pointerPosition)
        elif (
            event.type() == QEvent.Type.TouchUpdate
            and self._pressPosition is not None
        ):
            self._updateDrag(pointerPosition)
        elif self._pressPosition is not None:
            self._completeDrag(pointerPosition)

        event.accept()
        return True
    def _visibleIndices(self) -> List[int]:
        candidateCount = CANDIDATE_RADIUS * 2 + 1
        if self.count() <= candidateCount:
            return list(range(self.count()))

        centerProgress = self._roundLikeJavaScript(self._scrollProgress)
        offsets = range(-CANDIDATE_RADIUS, CANDIDATE_RADIUS + 1)
        return [(centerProgress + offset) % self.count() for offset in offsets]
    def _cardIntersectsViewport(self, offset: float) -> bool:
        distance = abs(offset)
        scale = max(0.0, 1 - distance * SCALE_REDUCTION)
        if scale == 0:
            return False

        rotation = radians(0 if distance < 0.05 else offset * ROTATION_ANGLE)
        halfWidth = CARD_SIZE.width() * scale / 2
        halfHeight = CARD_SIZE.height() * scale / 2
        cosine, sine = abs(cos(rotation)), abs(sin(rotation))
        horizontalExtent = cosine * halfWidth + sine * halfHeight
        verticalExtent = sine * halfWidth + cosine * halfHeight
        centerX = self.width() / 2 + offset * HORIZONTAL_OFFSET
        centerY = self.height() / 2 + (
            0 if distance < 0.05 else distance * VERTICAL_OFFSET
        )
        return (
            centerX + horizontalExtent >= 0
            and centerX - horizontalExtent <= self.width()
            and centerY + verticalExtent >= 0
            and centerY - verticalExtent <= self.height()
        )
    def _wrappedOffset(self, index: int) -> float:
        offset = fmod(index - self._scrollProgress, self.count())
        halfCount = self.count() / 2
        if offset > halfCount:
            offset -= self.count()
        elif offset < -halfCount:
            offset += self.count()
        return offset
    def _cardOpacity(self, offset: float) -> float:
        if self.count() <= 1:
            return 1.0

        fadeEnd = self.count() / 2
        fadeStart = max(0.0, fadeEnd - 0.5)
        distance = abs(offset)
        if distance <= fadeStart:
            return 1.0
        if distance >= fadeEnd:
            return 0.0
        return 1.0 - (distance - fadeStart) / (fadeEnd - fadeStart)
    def _paintCard(
        self,
        painter: QPainter,
        item: StackedCardCarouselItem,
        offset: float,
        opacity: float,
    ):
        distance = abs(offset)
        horizontalPosition = self.width() / 2 + offset * HORIZONTAL_OFFSET
        verticalPosition = self.height() / 2 + (
            0 if distance < 0.05 else distance * VERTICAL_OFFSET
        )
        rotation = 0 if distance < 0.05 else offset * ROTATION_ANGLE
        scale = max(0.0, 1 - distance * SCALE_REDUCTION)
        cardRect = QRectF(
            -CARD_SIZE.width() / 2,
            -CARD_SIZE.height() / 2,
            CARD_SIZE.width(),
            CARD_SIZE.height(),
        )
        painter.save()
        painter.setOpacity(opacity)
        painter.translate(horizontalPosition, verticalPosition)
        painter.rotate(rotation)
        painter.scale(scale, scale)

        devicePixelRatio = self.devicePixelRatioF()
        cacheRect = cardRect.adjusted(
            -CARD_CACHE_PADDING,
            -CARD_CACHE_PADDING,
            CARD_CACHE_PADDING,
            CARD_CACHE_PADDING,
        )
        image = item.cardImage(CARD_SIZE, devicePixelRatio)
        if image.isNull():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(48, 48, 48))
            painter.drawRoundedRect(cardRect, 16, 16)
        else:
            painter.drawImage(cacheRect, image)
        overlayOpacity = round(255 * self._overlayOpacity(offset))
        if overlayOpacity:
            painter.setOpacity(opacity * overlayOpacity / 255)
            painter.drawImage(cacheRect, self._overlayImage(CARD_SIZE, devicePixelRatio))
        titleOpacity = max(0.0, 1 - distance / 0.5)
        if titleOpacity:
            titleImage = item.titleImage(
                CARD_SIZE,
                self._titleFont,
                TITLE_BOTTOM,
                devicePixelRatio,
            )
            painter.setOpacity(opacity * titleOpacity)
            painter.drawImage(cardRect, titleImage)
        painter.restore()
    def _overlayImage(self, size: QSize, devicePixelRatio: float) -> QImage:
        padding = CARD_CACHE_PADDING
        cacheSize = size + QSize(padding * 2, padding * 2)
        physicalSize = _physicalSize(cacheSize, devicePixelRatio)
        cacheKey = (physicalSize.width(), physicalSize.height(), devicePixelRatio)
        if self._overlayCacheKey == cacheKey:
            return self._overlayCache

        overlay = _transparentImage(cacheSize, devicePixelRatio)
        painter = QPainter(overlay)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.black)
        painter.drawRoundedRect(
            QRectF(padding, padding, size.width(), size.height()),
            16,
            16,
        )
        painter.end()
        self._overlayCache = overlay
        self._overlayCacheKey = cacheKey
        return overlay
    @staticmethod
    def _overlayOpacity(offset: float) -> float:
        distance = abs(offset)
        if distance <= 0.5:
            return distance * 0.4
        if distance >= 2:
            return 0.5
        return 0.2 + (distance - 0.5) * 0.2
    def _beginDrag(self, pointerPosition: float):
        self._interruptAnimation()
        self._pressPosition = pointerPosition
        self._lastPointerPosition = pointerPosition
        self._dragStartProgress = self._scrollProgress
        self._pointerSamples.clear()
        self._recordPointerPosition(pointerPosition)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
    def _updateDrag(self, pointerPosition: float):
        pointerDelta = pointerPosition - self._lastPointerPosition
        self._scrollProgress -= pointerDelta / DRAG_SENSITIVITY
        self._lastPointerPosition = pointerPosition
        self._recordPointerPosition(pointerPosition)
        self.update()
    def _completeDrag(self, pointerPosition: float):
        if self._pressPosition is None:
            return

        self._recordPointerPosition(pointerPosition)
        dragDistance = pointerPosition - self._pressPosition
        pointerVelocity = self._pointerVelocity()
        totalShift = self._roundLikeJavaScript(
            -dragDistance / DISTANCE_DIVISOR
            - pointerVelocity / VELOCITY_DIVISOR
        )
        totalShift = max(-3, min(3, totalShift))
        targetProgress = (
            self._roundLikeJavaScript(self._dragStartProgress) + totalShift
        )
        progressVelocity = -pointerVelocity / DRAG_SENSITIVITY

        self._pressPosition = None
        self._pointerSamples.clear()
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._startSpring(float(targetProgress), progressVelocity)
    def _recordPointerPosition(self, pointerPosition: float):
        timestamp = self._eventClock.elapsed()
        self._pointerSamples.append((timestamp, pointerPosition))
        while (
            len(self._pointerSamples) > 2
            and timestamp - self._pointerSamples[0][0] > 200
        ):
            self._pointerSamples.popleft()
    def _pointerVelocity(self) -> float:
        if len(self._pointerSamples) < 2:
            return 0.0

        latestTime, latestPosition = self._pointerSamples[-1]
        referenceTime, referencePosition = self._pointerSamples[0]
        for sampleTime, samplePosition in reversed(self._pointerSamples):
            referenceTime, referencePosition = sampleTime, samplePosition
            if latestTime - sampleTime > 100:
                break

        elapsedSeconds = (latestTime - referenceTime) / 1000
        if elapsedSeconds <= 0:
            return 0.0
        return (latestPosition - referencePosition) / elapsedSeconds
    def _startSpring(self, targetProgress: float, initialVelocity: float):
        if not self._items:
            return

        self._interruptAnimation()
        targetIndex = self._roundLikeJavaScript(targetProgress) % self.count()
        previousIndex = self._currentIndex
        if targetIndex != previousIndex:
            self._currentIndex = targetIndex
            self.currentIndexChanged.emit(targetIndex)

        displacement = self._scrollProgress - targetProgress
        if (
            abs(displacement) <= self._springRestDistance
            and abs(initialVelocity) <= self._springRestSpeed
        ):
            self._scrollProgress = targetProgress
            self.update()
            return

        if not self._animationEnabled:
            self._scrollProgress = targetProgress
            self.update()
            return
        self._springFirstCoefficient = (initialVelocity + 20 * displacement) / 10
        self._springSecondCoefficient = displacement - self._springFirstCoefficient
        self._springTarget = targetProgress
        self._updateAnimationInterval()
        self._springClock.restart()
        self._animationTimer.start()
        self.animationStarted.emit(previousIndex, targetIndex)
        self._advanceSpring()
    def _advanceSpring(self):
        elapsedSeconds = self._springClock.nsecsElapsed() / 1_000_000_000
        firstTerm = self._springFirstCoefficient * exp(-10 * elapsedSeconds)
        secondTerm = self._springSecondCoefficient * exp(-20 * elapsedSeconds)
        displacement = firstTerm + secondTerm
        velocity = -10 * firstTerm - 20 * secondTerm
        self._scrollProgress = self._springTarget + displacement

        if (
            abs(velocity) <= self._springRestSpeed
            and abs(displacement) <= self._springRestDistance
        ):
            self._finishSpring()
        else:
            self.update()
    def _finishSpring(self):
        wasRunning = self._animationTimer.isActive()
        self._animationTimer.stop()
        self._scrollProgress = self._springTarget
        self.update()
        if wasRunning:
            self.animationFinished.emit(self.currentIndex())
    def _stopInteraction(self):
        self._interruptAnimation()
        self._pressPosition = None
        self._pointerSamples.clear()
        self.setCursor(Qt.CursorShape.OpenHandCursor)
    def _interruptAnimation(self):
        if not self._animationTimer.isActive():
            return

        self._animationTimer.stop()
        self.animationFinished.emit(self.currentIndex())
    def _updateAnimationInterval(self):
        window = self.window()
        windowHandle = window.windowHandle() if window is not None else None
        screen = windowHandle.screen() if windowHandle is not None else None
        if screen is None:
            screen = QApplication.primaryScreen()
        refreshRate = screen.refreshRate() if screen is not None else 60.0
        self._animationTimer.setInterval(max(1, round(1000 / refreshRate)))

    @staticmethod
    def _roundLikeJavaScript(value: float) -> int:
        return floor(value + 0.5)
    animationEnabled = pyqtProperty(
        bool,
        isAnimationEnabled,
        setAnimationEnabled,
    )
