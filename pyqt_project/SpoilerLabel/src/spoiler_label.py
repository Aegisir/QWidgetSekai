import math
from typing import List, Tuple

from PyQt5.QtCore import (QEasingCurve, QEvent, QPointF, QPropertyAnimation,
                          QRectF, QTimer, Qt,
                          pyqtProperty, pyqtSignal)
from PyQt5.QtGui import (QColor, QFontMetricsF, QKeyEvent, QMouseEvent,
                         QPainter, QPainterPath, QPalette, QPixmap,
                         QTextLayout, QTextOption)
from PyQt5.QtWidgets import QFrame, QStyle, QWidget

from qfluentwidgets import BodyLabel
from qfluentwidgets.common.config import qconfig
from qfluentwidgets.common.style_sheet import isDarkTheme

from spoiler_effect import (TEXT_PARTICLE_PROFILE, boundedPoint,
                            buildParticleProfileKey, createRevealGradient,
                            createWidgetPixmap, deactivateParticleWidget,
                            drawParticleTexture, effectiveDevicePixelRatio,
                            eraseRevealCircle, farthestCornerDistance,
                            particleClock, scheduleAutoHide,
                            setRevealedState, startRevealAnimation,
                            synchronizeParticleAnimation)


class SpoilerLabel(BodyLabel):
    spoilerFinished = pyqtSignal()
    revealedChanged = pyqtSignal(bool)
    spoilerEnabledChanged = pyqtSignal(bool)

    def __init__(self, text: str = '', parent: QWidget = None):
        if isinstance(text, QWidget) and parent is None:
            parent, text = text, ''

        self._spoilerEnabled = True
        self._revealed = False
        self._revealProgress = 0.0
        self._animationDuration = 0
        self._particleDensity = 1.0
        self._particleSpeed = 1.0
        self._blurRadius = -1.0
        self._maskRadius = 1.5
        self._autoHideDelay = 10000
        self._revealCenter = QPointF()
        self._maximumRevealDistance = 0.0
        self._isMaskFadingIn = False
        self._layoutCacheKey = None
        self._textLayouts: List[QTextLayout] = []
        self._lineRectCache: List[QRectF] = []
        self._overlay = QPixmap()
        self._overlayCacheKey = None
        self._lightParticleColor = QColor()
        self._darkParticleColor = QColor()
        self._animationTargetRevealed = False

        # BodyLabel's string overload calls self.__init__(), so initialize the
        # official label with the parent overload and set the text afterwards.
        super().__init__(parent)
        self.setText(text)

        self._revealEasing = self._createRevealEasing()
        self.revealAnimation = QPropertyAnimation(
            self,
            b'revealProgress',
            self
        )
        self.revealAnimation.setEasingCurve(self._revealEasing)
        self.revealAnimation.finished.connect(self._onAnimationFinished)

        self.autoHideTimer = QTimer(self)
        self.autoHideTimer.setSingleShot(True)
        self.autoHideTimer.timeout.connect(self.hideSpoiler)

        self.setTextFormat(Qt.PlainText)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        qconfig.themeChanged.connect(self._onThemeChanged)
        self.destroyed.connect(self._onDestroyed)

    @staticmethod
    def _createRevealEasing() -> QEasingCurve:
        easing = QEasingCurve(QEasingCurve.BezierSpline)
        easing.addCubicBezierSegment(
            QPointF(0.45, 0.37),
            QPointF(0.29, 1.0),
            QPointF(1.0, 1.0)
        )
        return easing

    def reveal(self, position: QPointF = None):
        if self.revealed:
            return

        if not self.spoilerEnabled:
            setRevealedState(self, True)
            self._setRevealProgress(1.0)
            self.spoilerFinished.emit()
            return

        lineRects = self._lineRects()
        if not lineRects:
            return

        if position is None:
            revealBounds = self._combinedRect(lineRects)
            position = revealBounds.center()

        self._setRevealGeometry(QPointF(position), lineRects)
        self._isMaskFadingIn = False
        self.autoHideTimer.stop()
        setRevealedState(self, True)

        duration = self._effectiveRevealDuration()
        startRevealAnimation(self, True, duration, self._revealEasing)

    def hideSpoiler(self):
        if not self.revealed:
            return

        if not self.spoilerEnabled:
            setRevealedState(self, False)
            self._setRevealProgress(0.0)
            return

        self.autoHideTimer.stop()
        setRevealedState(self, False)
        self._isMaskFadingIn = self.revealProgress >= 0.999
        duration = self.animationDuration or (
            400 if self._isMaskFadingIn else 200
        )
        startRevealAnimation(self, False, duration, QEasingCurve.InOutSine)

    def setRevealed(self, revealed: bool):
        if revealed:
            self.reveal()
        else:
            self.hideSpoiler()

    def isRevealed(self) -> bool:
        return self._revealed

    def setSpoilerEnabled(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self.spoilerEnabled:
            return

        self._spoilerEnabled = enabled
        self.revealAnimation.stop()
        self.autoHideTimer.stop()
        self._revealProgress = 1.0 if self.revealed else 0.0
        self._isMaskFadingIn = False
        self.spoilerEnabledChanged.emit(enabled)
        self._syncParticleAnimation()
        self._updateCursor()
        self.update()

    def isSpoilerEnabled(self) -> bool:
        return self._spoilerEnabled

    def setAnimationDuration(self, milliseconds: int):
        self._animationDuration = max(0, int(milliseconds))

    def getAnimationDuration(self) -> int:
        return self._animationDuration

    def setParticleDensity(self, density: float):
        density = max(0.0, min(2.5, float(density)))
        if math.isclose(density, self.particleDensity):
            return

        self._particleDensity = density
        self._refreshParticleProfile()

    def getParticleDensity(self) -> float:
        return self._particleDensity

    def setParticleSpeed(self, speed: float):
        speed = max(0.0, min(4.0, float(speed)))
        if math.isclose(speed, self.particleSpeed):
            return

        self._particleSpeed = speed
        self._refreshParticleProfile()

    def getParticleSpeed(self) -> float:
        return self._particleSpeed

    def setBlurRadius(self, radius: float):
        radius = max(-1.0, min(200.0, float(radius)))
        if math.isclose(radius, self.blurRadius):
            return

        self._blurRadius = radius
        self.update()

    def getBlurRadius(self) -> float:
        return self._blurRadius

    def setMaskRadius(self, radius: float):
        radius = max(0.0, min(100.0, float(radius)))
        if math.isclose(radius, self.maskRadius):
            return

        self._maskRadius = radius
        self.update()

    def getMaskRadius(self) -> float:
        return self._maskRadius

    def setRevealEasing(self, easing: QEasingCurve):
        self._revealEasing = QEasingCurve(easing)
        self.revealAnimation.setEasingCurve(self._revealEasing)

    def getRevealEasing(self) -> QEasingCurve:
        return QEasingCurve(self._revealEasing)

    def setAutoHideDelay(self, milliseconds: int):
        self._autoHideDelay = max(-1, int(milliseconds))
        if self.revealed and self.revealProgress >= 1.0:
            scheduleAutoHide(self)

    def getAutoHideDelay(self) -> int:
        return self._autoHideDelay

    def setParticleColor(self, light, dark=None):
        self._lightParticleColor = QColor(light)
        self._darkParticleColor = QColor(light if dark is None else dark)
        self._refreshParticleProfile()

    def resetParticleColor(self):
        self._lightParticleColor = QColor()
        self._darkParticleColor = QColor()
        self._refreshParticleProfile()

    def setText(self, text: str):
        super().setText(text)
        self._invalidateLayout()

    def setFont(self, font):
        super().setFont(font)
        self._invalidateLayout()

    def setAlignment(self, alignment: Qt.Alignment):
        super().setAlignment(alignment)
        self._invalidateLayout()

    def setWordWrap(self, enabled: bool):
        super().setWordWrap(enabled)
        self._invalidateLayout()

    def paintEvent(self, event):
        if not self.spoilerEnabled or not self.text():
            super().paintEvent(event)
            return

        QFrame.paintEvent(self, event)

        lineRects = self._lineRects()
        if not lineRects:
            return

        painter = QPainter(self)
        if self.revealProgress > 0:
            textLayer = self._renderTextLayer()
            if self._isMaskFadingIn:
                painter.setOpacity(self.revealProgress)
            elif self.revealProgress < 1.0:
                self._applyRevealMask(textLayer)
            painter.drawPixmap(0, 0, textLayer)
            painter.setOpacity(1.0)

        if self.revealProgress >= 1.0 and not self._isMaskFadingIn:
            return

        overlay = self._renderOverlay(lineRects)
        if overlay.isNull():
            return

        if self._isMaskFadingIn:
            painter.setOpacity(1.0 - self.revealProgress)
        painter.drawPixmap(0, 0, overlay)

    def mousePressEvent(self, event: QMouseEvent):
        if (
            event.button() == Qt.LeftButton and
            self.isEnabled() and
            self.spoilerEnabled and
            not self.revealed and
            self._positionHitsSpoiler(event.pos())
        ):
            self.reveal(QPointF(event.pos()))
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        self._updateCursor(event.pos())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if (
            event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and
            self.isEnabled() and
            self.spoilerEnabled and
            not self.revealed
        ):
            self.reveal()
            event.accept()
            return

        super().keyPressEvent(event)

    def resizeEvent(self, event):
        self._invalidateLayout()
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._syncParticleAnimation()

    def hideEvent(self, event):
        deactivateParticleWidget(self)
        super().hideEvent(event)

    def changeEvent(self, event: QEvent):
        if event.type() in (
            QEvent.FontChange,
            QEvent.PaletteChange,
            QEvent.StyleChange,
            QEvent.LayoutDirectionChange,
            QEvent.EnabledChange
        ):
            self._invalidateLayout()
            self._overlayCacheKey = None
            self._refreshParticleProfile()

        super().changeEvent(event)

    def _onAnimationFinished(self):
        if self._animationTargetRevealed:
            self._setRevealProgress(1.0)
            self._isMaskFadingIn = False
            self.spoilerFinished.emit()
            scheduleAutoHide(self)
        else:
            self._setRevealProgress(0.0)
            self._isMaskFadingIn = False

        self._syncParticleAnimation()
        self.update()

    def _getRevealProgress(self) -> float:
        return self._revealProgress

    def _setRevealProgress(self, progress: float):
        progress = max(0.0, min(1.0, float(progress)))
        if math.isclose(progress, self._revealProgress, abs_tol=1e-6):
            return

        wasFullyRevealed = self._revealProgress >= 0.999
        self._revealProgress = progress
        isFullyRevealed = progress >= 0.999
        if wasFullyRevealed != isFullyRevealed:
            self._syncParticleAnimation()
        self.update()

    def _effectiveRevealDuration(self) -> int:
        if self.animationDuration > 0:
            return self.animationDuration

        distance = max(1.0, self._maximumRevealDistance)
        return round(max(600.0, math.sqrt(distance / 160.0) * 350.0))

    def _renderOverlay(self, lineRects: List[QRectF]) -> QPixmap:
        overlay = self._overlayPixmap()
        overlay.fill(Qt.transparent)

        maskPath = self._createLineMaskPath(lineRects)

        painter = QPainter(overlay)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.particleDensity > 0:
            particleTexture = particleClock().textureFor(self)
            if not particleTexture.isNull():
                drawParticleTexture(
                    painter,
                    particleTexture,
                    QRectF(self.rect()),
                    maskPath,
                    self._revealCenter,
                    self.revealProgress,
                    0.4
                )

        if self.revealProgress > 0 and not self._isMaskFadingIn:
            eraseRevealCircle(
                painter,
                self._revealCenter,
                self._maximumRevealDistance,
                self.revealProgress,
                self.blurRadius
            )

        painter.end()
        return overlay

    def _createLineMaskPath(
        self,
        lineRects: List[QRectF]
    ) -> QPainterPath:
        maskPath = QPainterPath()
        maskPath.setFillRule(Qt.WindingFill)
        for lineRect in lineRects:
            if self.maskRadius > 0:
                maskPath.addRoundedRect(
                    lineRect,
                    self.maskRadius,
                    self.maskRadius
                )
            else:
                maskPath.addRect(lineRect)

        return maskPath

    def _renderTextLayer(self) -> QPixmap:
        textLayer = createWidgetPixmap(self)
        textLayer.fill(Qt.transparent)

        painter = QPainter(textLayer)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setFont(self.font())
        colorGroup = QPalette.Active if self.isEnabled() else QPalette.Disabled
        painter.setPen(self.palette().color(colorGroup, self.foregroundRole()))
        painter.setClipRect(self._textRect())

        for textLayout in self._ensureTextLayouts():
            textLayout.draw(painter, QPointF())
        painter.end()
        return textLayer

    def _applyRevealMask(self, textLayer: QPixmap):
        painter = QPainter(textLayer)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.fillRect(QRectF(self.rect()), createRevealGradient(
            self._revealCenter,
            self._maximumRevealDistance,
            self.revealProgress,
            self.blurRadius
        ))
        painter.end()

    def _overlayPixmap(self) -> QPixmap:
        dpr = effectiveDevicePixelRatio(self)
        physicalWidth = max(1, round(self.width() * dpr))
        physicalHeight = max(1, round(self.height() * dpr))
        cacheKey = (physicalWidth, physicalHeight, dpr)

        if self._overlayCacheKey != cacheKey:
            self._overlay = createWidgetPixmap(self)
            self._overlayCacheKey = cacheKey

        return self._overlay

    def _lineRects(self) -> List[QRectF]:
        self._ensureTextLayouts()
        return self._lineRectCache

    def _ensureTextLayouts(self) -> List[QTextLayout]:
        contentRect = self._textRect()
        cacheKey = (
            self.text(),
            self.font().toString(),
            round(contentRect.width(), 3),
            round(contentRect.height(), 3),
            int(self.alignment()),
            self.wordWrap(),
            int(self.layoutDirection()),
            self.indent(),
            effectiveDevicePixelRatio(self)
        )
        if cacheKey == self._layoutCacheKey:
            return self._textLayouts

        self._layoutCacheKey = cacheKey
        self._textLayouts = []
        self._lineRectCache = []
        if (
            not self.text() or
            contentRect.width() <= 0 or
            contentRect.height() <= 0
        ):
            return self._textLayouts

        textOption = QTextOption()
        textOption.setTextDirection(
            Qt.RightToLeft
            if self.layoutDirection() == Qt.RightToLeft
            else Qt.LeftToRight
        )
        textOption.setWrapMode(
            QTextOption.WrapAtWordBoundaryOrAnywhere
            if self.wordWrap()
            else QTextOption.NoWrap
        )
        visualAlignment = QStyle.visualAlignment(
            self.layoutDirection(),
            self.alignment()
        )
        textOption.setAlignment(
            Qt.Alignment(visualAlignment & Qt.AlignHorizontal_Mask)
        )

        availableWidth = max(1.0, contentRect.width())
        lines = []
        layoutHeight = 0.0
        emptyLineHeight = QFontMetricsF(self.font()).height()
        normalizedText = self.text().replace('\r\n', '\n').replace('\r', '\n')
        for logicalLine in normalizedText.split('\n'):
            if not logicalLine:
                layoutHeight += emptyLineHeight
                continue

            textLayout = QTextLayout(logicalLine, self.font())
            textLayout.setTextOption(textOption)
            textLayout.setCacheEnabled(True)
            textLayout.beginLayout()
            while True:
                line = textLayout.createLine()
                if not line.isValid():
                    break

                line.setLineWidth(availableWidth)
                lines.append((line, layoutHeight))
                layoutHeight += line.height()
            textLayout.endLayout()
            self._textLayouts.append(textLayout)

        if visualAlignment & Qt.AlignBottom:
            layoutTop = contentRect.bottom() - layoutHeight
        elif visualAlignment & Qt.AlignVCenter:
            layoutTop = contentRect.top() + (contentRect.height() - layoutHeight) / 2
        else:
            layoutTop = contentRect.top()

        lineRects = []
        for line, verticalOffset in lines:
            line.setPosition(QPointF(
                contentRect.left(),
                layoutTop + verticalOffset
            ))
            naturalRect = line.naturalTextRect()
            lineLeft = math.floor(naturalRect.left())
            lineTop = math.floor(naturalRect.top())
            lineRight = math.ceil(naturalRect.right() + 0.99)
            lineBottom = math.ceil(naturalRect.bottom() + 0.99)
            lineRect = QRectF(
                lineLeft,
                lineTop,
                lineRight - lineLeft,
                lineBottom - lineTop
            ).intersected(contentRect)
            if lineRect.width() > 0 and lineRect.height() > 0:
                lineRects.append(lineRect)

        self._lineRectCache = self._adjustLineGaps(lineRects)
        self._refreshRevealGeometry(self._lineRectCache)
        return self._textLayouts

    def _textRect(self) -> QRectF:
        textRect = QRectF(self.contentsRect())
        margin = max(0, self.margin())
        textRect.adjust(margin, margin, -margin, -margin)

        indent = self.indent()
        if indent <= 0:
            return textRect

        visualAlignment = QStyle.visualAlignment(
            self.layoutDirection(),
            self.alignment()
        )
        if visualAlignment & Qt.AlignLeft:
            textRect.adjust(indent, 0, 0, 0)
        elif visualAlignment & Qt.AlignRight:
            textRect.adjust(0, 0, -indent, 0)

        if visualAlignment & Qt.AlignTop:
            textRect.adjust(0, indent, 0, 0)
        elif visualAlignment & Qt.AlignBottom:
            textRect.adjust(0, 0, 0, -indent)

        return textRect

    @staticmethod
    def _adjustLineGaps(lineRects: List[QRectF]) -> List[QRectF]:
        adjustedRects = [QRectF(rect) for rect in lineRects]
        adjustedRects.sort(key=lambda rect: rect.top())

        for index in range(len(adjustedRects) - 1):
            currentRect = adjustedRects[index]
            nextRect = adjustedRects[index + 1]
            gap = nextRect.top() - currentRect.bottom()
            if 0 <= gap <= 2.0:
                currentGrowth = gap - math.floor(gap / 2.0)
                nextGrowth = math.floor(gap / 2.0)
                currentRect.setHeight(currentRect.height() + currentGrowth)
                nextRect.setTop(nextRect.top() - nextGrowth)

        return adjustedRects

    def _effectiveParticleColor(self) -> QColor:
        customColor = (
            self._darkParticleColor
            if isDarkTheme()
            else self._lightParticleColor
        )
        if customColor.isValid():
            return QColor(customColor)

        return QColor('#ffffff' if isDarkTheme() else '#101010')

    def _particleProfileKey(self) -> Tuple:
        return buildParticleProfileKey(
            self,
            TEXT_PARTICLE_PROFILE,
            self._effectiveParticleColor()
        )

    @staticmethod
    def _particleSimulationProfile():
        return TEXT_PARTICLE_PROFILE

    def _refreshParticleProfile(self):
        deactivateParticleWidget(self)
        self._syncParticleAnimation()
        self.update()

    def _syncParticleAnimation(self):
        synchronizeParticleAnimation(self)

    def _onThemeChanged(self, *args):
        self._overlayCacheKey = None
        self._refreshParticleProfile()

    def _onDestroyed(self, *args):
        deactivateParticleWidget(self)

    def _invalidateLayout(self):
        self._layoutCacheKey = None
        self._textLayouts = []
        self._lineRectCache = []
        self._overlayCacheKey = None
        self.update()

    def _positionHitsSpoiler(self, position) -> bool:
        point = QPointF(position)
        return any(lineRect.contains(point) for lineRect in self._lineRects())

    def _updateCursor(self, position=None):
        shouldShowPointer = (
            position is not None and
            self.isEnabled() and
            self.spoilerEnabled and
            not self.revealed and
            self._positionHitsSpoiler(position)
        )
        if shouldShowPointer:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()

    def _setRevealGeometry(
        self,
        position: QPointF,
        lineRects: List[QRectF]
    ):
        revealBounds = self._combinedRect(lineRects)
        self._revealCenter = boundedPoint(position, revealBounds)
        self._maximumRevealDistance = (
            farthestCornerDistance(self._revealCenter, lineRects) + 20.0
        )

    def _refreshRevealGeometry(self, lineRects: List[QRectF]):
        revealIsVisible = self.revealed or self.revealProgress > 0
        if revealIsVisible and lineRects:
            self._setRevealGeometry(self._revealCenter, lineRects)

    @staticmethod
    def _combinedRect(rects: List[QRectF]) -> QRectF:
        combinedRect = QRectF(rects[0])
        for rect in rects[1:]:
            combinedRect = combinedRect.united(rect)
        return combinedRect

    spoilerEnabled = pyqtProperty(
        bool,
        isSpoilerEnabled,
        setSpoilerEnabled,
        notify=spoilerEnabledChanged
    )
    revealed = pyqtProperty(
        bool,
        isRevealed,
        setRevealed,
        notify=revealedChanged
    )
    revealProgress = pyqtProperty(
        float,
        _getRevealProgress,
        _setRevealProgress
    )
    animationDuration = pyqtProperty(
        int,
        getAnimationDuration,
        setAnimationDuration
    )
    particleDensity = pyqtProperty(
        float,
        getParticleDensity,
        setParticleDensity
    )
    particleSpeed = pyqtProperty(
        float,
        getParticleSpeed,
        setParticleSpeed
    )
    blurRadius = pyqtProperty(float, getBlurRadius, setBlurRadius)
    maskRadius = pyqtProperty(float, getMaskRadius, setMaskRadius)
    autoHideDelay = pyqtProperty(
        int,
        getAutoHideDelay,
        setAutoHideDelay
    )
