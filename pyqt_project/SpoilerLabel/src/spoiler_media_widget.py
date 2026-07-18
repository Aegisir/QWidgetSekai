import math
from enum import Enum
from typing import Optional, Union

from PyQt5.QtCore import (QEasingCurve, QEvent, QObject, QPointF,
                          QPropertyAnimation, QRectF, QSize, QTimer, Qt,
                          pyqtProperty, pyqtSignal)
from PyQt5.QtGui import (QColor, QImage, QImageReader, QKeyEvent,
                         QMouseEvent, QPainter, QPainterPath, QPixmap)
from PyQt5.QtWidgets import QStyle, QWidget

from qfluentwidgets.common.config import qconfig
from qfluentwidgets.common.style_sheet import isDarkTheme

from spoiler_effect import (MEDIA_PARTICLE_PROFILE, boundedPoint,
                            buildParticleProfileKey, createWidgetPixmap,
                            deactivateParticleWidget, drawParticleTexture,
                            effectiveDevicePixelRatio, eraseRevealCircle,
                            farthestCornerDistance, particleClock,
                            scheduleAutoHide, setRevealedState,
                            startRevealAnimation,
                            synchronizeParticleAnimation)


MediaImage = Union[QImage, QPixmap, str]


class MediaRevealMode(Enum):
    AUTO = 0
    RADIAL = 1
    FADE = 2


class _SpoilerMediaOverlay(QWidget):
    def __init__(self, host: 'SpoilerMediaWidget'):
        super().__init__(parent=host)
        self.host = host
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def paintEvent(self, event):
        self.host._paintOverlay(self)

    def mousePressEvent(self, event: QMouseEvent):
        if (
            event.button() == Qt.LeftButton and
            self.host.isEnabled() and
            self.host.spoilerEnabled and
            not self.host.revealed and
            self.host._coveragePath().contains(QPointF(event.pos()))
        ):
            self.host.reveal(QPointF(event.pos()))
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        isInteractive = (
            self.host.isEnabled() and
            self.host.spoilerEnabled and
            not self.host.revealed and
            self.host._coveragePath().contains(QPointF(event.pos()))
        )
        self.setCursor(
            Qt.PointingHandCursor if isInteractive else Qt.ArrowCursor
        )
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if (
            event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and
            self.host.isEnabled() and
            self.host.spoilerEnabled and
            not self.host.revealed
        ):
            self.host.reveal()
            event.accept()
            return

        super().keyPressEvent(event)


class SpoilerMediaWidget(QWidget):
    spoilerFinished = pyqtSignal()
    revealedChanged = pyqtSignal(bool)
    spoilerEnabledChanged = pyqtSignal(bool)
    mediaChanged = pyqtSignal()

    def __init__(self, image: MediaImage = None, parent: QWidget = None):
        if isinstance(image, QWidget) and parent is None:
            parent, image = image, None

        super().__init__(parent=parent)
        self._image = QImage()
        self._thumbnail = QImage()
        self._videoWidget: Optional[QWidget] = None
        self._mediaPlayer: Optional[QObject] = None
        self._spoilerEnabled = True
        self._revealed = False
        self._revealProgress = 0.0
        self._animationDuration = 0
        self._particleDensity = 1.0
        self._particleSpeed = 1.0
        self._blurRadius = -1.0
        self._borderRadius = 8.0
        self._autoHideDelay = -1
        self._aspectRatioMode = Qt.KeepAspectRatioByExpanding
        self._alignment = Qt.AlignCenter
        self._revealMode = MediaRevealMode.AUTO
        self._activeRevealMode = MediaRevealMode.RADIAL
        self._autoPlayOnReveal = True
        self._revealCenter = QPointF()
        self._maximumRevealDistance = 0.0
        self._lightParticleColor = QColor()
        self._darkParticleColor = QColor()
        self._lightOverlayColor = QColor()
        self._darkOverlayColor = QColor()
        self._thumbnailCache = QPixmap()
        self._thumbnailCacheKey = None
        self._overlayBuffer = QPixmap()
        self._overlayBufferKey = None
        self._animationTargetRevealed = False

        self.overlay = _SpoilerMediaOverlay(self)
        self.revealAnimation = QPropertyAnimation(
            self,
            b'revealProgress',
            self
        )
        self.revealAnimation.finished.connect(self._onAnimationFinished)
        self.autoHideTimer = QTimer(self)
        self.autoHideTimer.setSingleShot(True)
        self.autoHideTimer.timeout.connect(self.hideSpoiler)

        self.setMinimumSize(120, 90)
        self.setFocusProxy(self.overlay)
        self.setAttribute(Qt.WA_StyledBackground)
        qconfig.themeChanged.connect(self._onThemeChanged)
        self.destroyed.connect(self._onDestroyed)

        if image is not None:
            self.setImage(image)
        else:
            self._updateOverlayInteraction()

    def setImage(self, image: MediaImage):
        loadedImage = self._loadImage(image)
        if loadedImage.isNull():
            return

        self.takeVideoWidget()
        self._image = loadedImage
        self._thumbnail = self._createThumbnail(loadedImage)
        self._clearMediaCaches()
        self._resetSpoilerState()
        self.mediaChanged.emit()
        self.update()

    def image(self) -> QImage:
        return QImage(self._image)

    def setThumbnail(self, image: MediaImage):
        self._thumbnail = self._loadImage(image)
        self._clearMediaCaches()
        self.overlay.update()

    def thumbnail(self) -> QImage:
        return QImage(self._thumbnail)

    def setVideoWidget(self, widget: QWidget, mediaPlayer: QObject = None):
        """ Attach a caller-owned video view and optional player.

        The view becomes a child while attached and is therefore destroyed
        with this container unless ``takeVideoWidget()`` detaches it first.
        """
        previousWidget = self.takeVideoWidget()
        self._image = QImage()
        self._thumbnail = QImage()
        self._videoWidget = widget
        if widget is not None:
            widget.setParent(self)
            widget.setGeometry(self.contentsRect())
            widget.installEventFilter(self)
            widget.destroyed.connect(self._onVideoWidgetDestroyed)
            widget.show()
        self._setMediaPlayer(mediaPlayer)

        self._clearMediaCaches()
        self._resetSpoilerState()
        self._updateVideoVisibility()
        self._raiseOverlay()
        self.mediaChanged.emit()
        return previousWidget

    def videoWidget(self) -> Optional[QWidget]:
        return self._videoWidget

    def mediaPlayer(self) -> Optional[QObject]:
        return self._mediaPlayer

    def takeVideoWidget(self) -> Optional[QWidget]:
        widget = self._videoWidget
        if widget is None:
            self._setMediaPlayer(None)
            return None

        self._videoWidget = None
        try:
            widget.destroyed.disconnect(self._onVideoWidgetDestroyed)
            widget.removeEventFilter(self)
            widget.hide()
            widget.setParent(None)
        except RuntimeError:
            widget = None
        self._setMediaPlayer(None)
        self._updateOverlayInteraction()
        return widget

    def clearMedia(self):
        self.takeVideoWidget()
        self._image = QImage()
        self._thumbnail = QImage()
        self._clearMediaCaches()
        self._resetSpoilerState()
        self.mediaChanged.emit()
        self.update()

    def reveal(self, position: QPointF = None):
        if self.revealed or not self._hasMedia():
            return

        coverageRect = self._coverageRect()
        if position is None:
            position = coverageRect.center()

        self._revealCenter = boundedPoint(QPointF(position), coverageRect)
        self._maximumRevealDistance = (
            farthestCornerDistance(self._revealCenter, [coverageRect]) +
            50.0 / effectiveDevicePixelRatio(self)
        )
        self._activeRevealMode = self._effectiveRevealMode()
        self.autoHideTimer.stop()
        setRevealedState(self, True)
        self._playMediaIfNeeded()
        self._prepareOverlayForAnimation()

        duration = self._effectiveRevealDuration()
        startRevealAnimation(self, True, duration, self._mediaRevealEasing())

    def hideSpoiler(self):
        if not self.revealed:
            return

        self.autoHideTimer.stop()
        setRevealedState(self, False)
        self._activeRevealMode = self._effectiveRevealMode()
        self._prepareOverlayForAnimation()
        duration = self.animationDuration or (
            250 if self._activeRevealMode == MediaRevealMode.FADE else 400
        )
        startRevealAnimation(self, False, duration, QEasingCurve.InOutSine)

    def setRevealed(self, revealed: bool):
        self.reveal() if revealed else self.hideSpoiler()

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
        self.spoilerEnabledChanged.emit(enabled)
        self._syncParticleAnimation()
        self._updateOverlayInteraction()
        self._updateVideoVisibility()
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
        self._blurRadius = max(-1.0, min(400.0, float(radius)))
        self.overlay.update()

    def getBlurRadius(self) -> float:
        return self._blurRadius

    def setBorderRadius(self, radius: float):
        self._borderRadius = max(0.0, min(200.0, float(radius)))
        self._clearMediaCaches()
        self.update()
        self.overlay.update()

    def getBorderRadius(self) -> float:
        return self._borderRadius

    def setMaskRadius(self, radius: float):
        self.setBorderRadius(radius)

    def getMaskRadius(self) -> float:
        return self.getBorderRadius()

    def setAutoHideDelay(self, milliseconds: int):
        self._autoHideDelay = max(-1, int(milliseconds))
        if self.revealed and self.revealProgress >= 1.0:
            scheduleAutoHide(self)

    def getAutoHideDelay(self) -> int:
        return self._autoHideDelay

    def setAspectRatioMode(self, mode: Qt.AspectRatioMode):
        if mode == self.aspectRatioMode:
            return

        self._aspectRatioMode = mode
        self._clearMediaCaches()
        self.update()
        self.overlay.update()

    def getAspectRatioMode(self):
        return self._aspectRatioMode

    def setAlignment(self, alignment: Qt.Alignment):
        alignment = Qt.Alignment(alignment)
        if alignment == self.alignment:
            return

        self._alignment = alignment
        self._clearMediaCaches()
        self.update()
        self.overlay.update()

    def getAlignment(self):
        return self._alignment

    def setRevealMode(self, mode: MediaRevealMode):
        mode = MediaRevealMode(mode)
        if mode == self._revealMode:
            return

        self._revealMode = mode
        self._activeRevealMode = self._effectiveRevealMode()
        self._updateVideoVisibility()
        self._updateOverlayInteraction()
        self.overlay.update()

    def revealMode(self) -> MediaRevealMode:
        return self._revealMode

    def isUsingFadeFallback(self) -> bool:
        return self._effectiveRevealMode() == MediaRevealMode.FADE

    def setAutoPlayOnReveal(self, enabled: bool):
        self._autoPlayOnReveal = bool(enabled)

    def isAutoPlayOnReveal(self) -> bool:
        return self._autoPlayOnReveal

    def setParticleColor(self, light, dark=None):
        self._lightParticleColor = QColor(light)
        self._darkParticleColor = QColor(light if dark is None else dark)
        self._refreshParticleProfile()

    def resetParticleColor(self):
        self._lightParticleColor = QColor()
        self._darkParticleColor = QColor()
        self._refreshParticleProfile()

    def setOverlayColor(self, light, dark=None):
        self._lightOverlayColor = QColor(light)
        self._darkOverlayColor = QColor(light if dark is None else dark)
        self.overlay.update()

    def resetOverlayColor(self):
        self._lightOverlayColor = QColor()
        self._darkOverlayColor = QColor()
        self.overlay.update()

    def paintEvent(self, event):
        baseImage = self._image
        if baseImage.isNull() and self._shouldPaintVideoPoster():
            baseImage = self._thumbnail
        if baseImage.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )
        path = self._coveragePath()
        painter.setClipPath(path)
        self._drawImage(painter, baseImage)

    def resizeEvent(self, event):
        if self._videoWidget is not None:
            self._videoWidget.setGeometry(self.contentsRect())
        self.overlay.setGeometry(self.rect())
        self._clearMediaCaches()
        self._raiseOverlay()
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._syncParticleAnimation()
        self._updateVideoVisibility()
        self._raiseOverlay()

    def hideEvent(self, event):
        deactivateParticleWidget(self)
        super().hideEvent(event)

    def changeEvent(self, event: QEvent):
        if event.type() in (
            QEvent.PaletteChange,
            QEvent.StyleChange,
            QEvent.EnabledChange
        ):
            self._clearMediaCaches()
            self._refreshParticleProfile()
        super().changeEvent(event)

    def eventFilter(self, watched, event):
        if watched is self._videoWidget and event.type() in (
            QEvent.Show,
            QEvent.Resize,
            QEvent.Move,
            QEvent.ParentChange,
            QEvent.WinIdChange
        ):
            QTimer.singleShot(0, self._raiseOverlay)
        return super().eventFilter(watched, event)

    def _paintOverlay(self, target: QWidget):
        if not self.spoilerEnabled or not self._hasMedia():
            return

        coveragePath = self._coveragePath()
        coverageRect = self._coverageRect()
        buffer = self._overlayPixmap()
        buffer.fill(Qt.transparent)

        painter = QPainter(buffer)
        painter.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )
        painter.save()
        painter.setClipPath(coveragePath)
        thumbnail = self._thumbnailPixmap()
        if thumbnail.isNull():
            painter.fillPath(coveragePath, self._effectiveOverlayColor())
        else:
            painter.drawPixmap(QPointF(0, 0), thumbnail)
        painter.restore()

        if (
            self.particleDensity > 0 and
            self._activeRevealMode == MediaRevealMode.RADIAL
        ):
            particleTexture = particleClock().textureFor(self)
            drawParticleTexture(
                painter,
                particleTexture,
                QRectF(self.rect()),
                coveragePath,
                self._revealCenter,
                self.revealProgress,
                0.5
            )

        if (
            self._activeRevealMode == MediaRevealMode.RADIAL and
            self.revealProgress > 0
        ):
            eraseRevealCircle(
                painter,
                self._revealCenter,
                self._maximumRevealDistance,
                self.revealProgress,
                self.blurRadius
            )
        painter.end()

        targetPainter = QPainter(target)
        if self._activeRevealMode == MediaRevealMode.FADE:
            targetPainter.setOpacity(1.0 - self.revealProgress)
        targetPainter.drawPixmap(0, 0, buffer)

    def _onAnimationFinished(self):
        if self._animationTargetRevealed:
            self._setRevealProgress(1.0)
            self.spoilerFinished.emit()
            scheduleAutoHide(self)
        else:
            self._setRevealProgress(0.0)

        self._updateVideoVisibility()
        self._updateOverlayInteraction()
        self._syncParticleAnimation()

    def _prepareOverlayForAnimation(self):
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.overlay.show()
        if self._shouldPaintVideoPoster():
            self.repaint()
        self._updateVideoVisibility()
        self._raiseOverlay()

    def _updateOverlayInteraction(self):
        isFullyRevealed = (
            not self._hasMedia() or
            not self.spoilerEnabled or
            self.revealProgress >= 0.999
        )
        self.overlay.setAttribute(
            Qt.WA_TransparentForMouseEvents,
            isFullyRevealed
        )
        self.overlay.setFocusPolicy(
            Qt.NoFocus if isFullyRevealed else Qt.StrongFocus
        )
        self.overlay.setVisible(not isFullyRevealed)
        if not isFullyRevealed:
            self._raiseOverlay()

    def _getRevealProgress(self) -> float:
        return self._revealProgress

    def _setRevealProgress(self, progress: float):
        progress = max(0.0, min(1.0, float(progress)))
        if math.isclose(progress, self._revealProgress, abs_tol=1e-6):
            return

        self._revealProgress = progress
        self._updateVideoVisibility()
        self.overlay.update()
        self._syncParticleAnimation()

    def _resetSpoilerState(self):
        self.revealAnimation.stop()
        self.autoHideTimer.stop()
        self._revealed = False
        self._revealProgress = 0.0
        self._activeRevealMode = self._effectiveRevealMode()
        self._updateOverlayInteraction()
        self._syncParticleAnimation()

    def _effectiveRevealDuration(self) -> int:
        if self.animationDuration > 0:
            return self.animationDuration
        if self._activeRevealMode == MediaRevealMode.FADE:
            return 250

        distance = farthestCornerDistance(
            self._revealCenter,
            [self._coverageRect()]
        )
        return max(250, min(1200, round(1200.0 - distance)))

    @staticmethod
    def _mediaRevealEasing() -> QEasingCurve:
        easing = QEasingCurve(QEasingCurve.BezierSpline)
        easing.addCubicBezierSegment(
            QPointF(0.25, 0.1),
            QPointF(0.25, 1.0),
            QPointF(1.0, 1.0)
        )
        return easing

    def _effectiveRevealMode(self) -> MediaRevealMode:
        if self._revealMode != MediaRevealMode.AUTO:
            return self._revealMode
        if self._videoWidget is None:
            return MediaRevealMode.RADIAL
        if self._usesNativeVideoSurface(self._videoWidget):
            return MediaRevealMode.FADE
        return MediaRevealMode.RADIAL

    @staticmethod
    def _usesNativeVideoSurface(widget: QWidget) -> bool:
        if widget.testAttribute(Qt.WA_NativeWindow):
            return True

        metaObject = widget.metaObject()
        while metaObject is not None:
            if metaObject.className() == 'QVideoWidget':
                return True
            metaObject = metaObject.superClass()
        return False

    def _updateVideoVisibility(self):
        if self._videoWidget is None:
            return

        hidesVideoForFade = (
            self.spoilerEnabled and
            self._activeRevealMode == MediaRevealMode.FADE and
            (not self.revealed or self.revealProgress < 0.999)
        )
        try:
            self._videoWidget.setVisible(
                self.isVisible() and not hidesVideoForFade
            )
        except RuntimeError:
            self._onVideoWidgetDestroyed()
            return
        self.update()
        self._raiseOverlay()

    def _shouldPaintVideoPoster(self) -> bool:
        return (
            self._videoWidget is not None and
            self.spoilerEnabled and
            self._activeRevealMode == MediaRevealMode.FADE and
            (not self.revealed or self.revealProgress < 0.999)
        )

    def _setMediaPlayer(self, mediaPlayer: QObject):
        if self._mediaPlayer is not None:
            try:
                self._mediaPlayer.destroyed.disconnect(
                    self._onMediaPlayerDestroyed
                )
            except (RuntimeError, TypeError):
                pass

        self._mediaPlayer = mediaPlayer
        if mediaPlayer is not None:
            mediaPlayer.destroyed.connect(self._onMediaPlayerDestroyed)

    def _onVideoWidgetDestroyed(self, *arguments):
        self._videoWidget = None
        self._setMediaPlayer(None)
        self._clearMediaCaches()
        self._resetSpoilerState()
        self.mediaChanged.emit()
        self.update()

    def _onMediaPlayerDestroyed(self, *arguments):
        self._mediaPlayer = None

    def _playMediaIfNeeded(self):
        if not self.autoPlayOnReveal or self._mediaPlayer is None:
            return

        play = getattr(self._mediaPlayer, 'play', None)
        if callable(play):
            try:
                play()
            except RuntimeError:
                pass

    def _hasMedia(self) -> bool:
        return not self._image.isNull() or self._videoWidget is not None

    def _coverageRect(self) -> QRectF:
        if self._videoWidget is not None or self._image.isNull():
            return QRectF(self.contentsRect())
        if self.aspectRatioMode != Qt.KeepAspectRatio:
            return QRectF(self.contentsRect())

        sourceSize = self._image.size()
        targetSize = sourceSize.scaled(
            self.contentsRect().size(),
            Qt.KeepAspectRatio
        )
        targetRect = QStyle.alignedRect(
            self.layoutDirection(),
            self.alignment,
            targetSize,
            self.contentsRect()
        )
        return QRectF(targetRect)

    def _coveragePath(self) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(
            self._coverageRect(),
            self.borderRadius,
            self.borderRadius
        )
        return path

    def _drawImage(self, painter: QPainter, image: QImage):
        targetRect = self._coverageRect()
        sourceRect = QRectF(image.rect())
        if self.aspectRatioMode == Qt.KeepAspectRatioByExpanding:
            targetRatio = targetRect.width() / max(1.0, targetRect.height())
            sourceRatio = sourceRect.width() / max(1.0, sourceRect.height())
            if sourceRatio > targetRatio:
                croppedWidth = sourceRect.height() * targetRatio
                sourceRect.setLeft(
                    sourceRect.left() + (sourceRect.width() - croppedWidth) / 2
                )
                sourceRect.setWidth(croppedWidth)
            elif sourceRatio < targetRatio:
                croppedHeight = sourceRect.width() / targetRatio
                sourceRect.setTop(
                    sourceRect.top() +
                    (sourceRect.height() - croppedHeight) / 2
                )
                sourceRect.setHeight(croppedHeight)
        painter.drawImage(targetRect, image, sourceRect)

    def _thumbnailPixmap(self) -> QPixmap:
        if self._thumbnail.isNull():
            return QPixmap()

        dpr = effectiveDevicePixelRatio(self)
        cacheKey = (
            self._thumbnail.cacheKey(),
            round(self.width() * dpr),
            round(self.height() * dpr),
            dpr,
            int(self.aspectRatioMode),
            self.borderRadius
        )
        if cacheKey == self._thumbnailCacheKey:
            return self._thumbnailCache

        pixmap = createWidgetPixmap(self)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )
        painter.setClipPath(self._coveragePath())
        self._drawImage(painter, self._thumbnail)
        painter.end()
        self._thumbnailCache = pixmap
        self._thumbnailCacheKey = cacheKey
        return pixmap

    def _overlayPixmap(self) -> QPixmap:
        dpr = effectiveDevicePixelRatio(self)
        cacheKey = (
            round(self.width() * dpr),
            round(self.height() * dpr),
            dpr
        )
        if cacheKey != self._overlayBufferKey:
            self._overlayBuffer = createWidgetPixmap(self)
            self._overlayBufferKey = cacheKey
        return self._overlayBuffer

    @staticmethod
    def _loadImage(image: MediaImage) -> QImage:
        if isinstance(image, QImage):
            return QImage(image)
        if isinstance(image, QPixmap):
            return image.toImage()
        if isinstance(image, str):
            return QImageReader(image).read()
        return QImage()

    @staticmethod
    def _createThumbnail(image: QImage) -> QImage:
        return image.scaled(
            QSize(36, 36),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

    def _effectiveParticleColor(self) -> QColor:
        customColor = (
            self._darkParticleColor
            if isDarkTheme()
            else self._lightParticleColor
        )
        if customColor.isValid():
            return QColor(customColor)
        return QColor(Qt.white)

    def _effectiveOverlayColor(self) -> QColor:
        customColor = (
            self._darkOverlayColor
            if isDarkTheme()
            else self._lightOverlayColor
        )
        if customColor.isValid():
            return QColor(customColor)
        return QColor('#303030' if isDarkTheme() else '#d8d8d8')

    def _particleProfileKey(self):
        return buildParticleProfileKey(
            self,
            MEDIA_PARTICLE_PROFILE,
            self._effectiveParticleColor()
        )

    @staticmethod
    def _particleSimulationProfile():
        return MEDIA_PARTICLE_PROFILE

    def _refreshParticleProfile(self):
        deactivateParticleWidget(self)
        self._syncParticleAnimation()
        self.overlay.update()

    def _syncParticleAnimation(self):
        synchronizeParticleAnimation(
            self,
            self._activeRevealMode == MediaRevealMode.RADIAL
        )

    def _updateParticleFrame(self):
        self.overlay.update()

    def _onThemeChanged(self, *args):
        self._clearMediaCaches()
        self._refreshParticleProfile()

    def _onDestroyed(self, *args):
        deactivateParticleWidget(self)

    def _clearMediaCaches(self):
        self._thumbnailCache = QPixmap()
        self._thumbnailCacheKey = None
        self._overlayBuffer = QPixmap()
        self._overlayBufferKey = None

    def _raiseOverlay(self):
        if self.overlay.isVisible():
            self.overlay.raise_()

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
    borderRadius = pyqtProperty(float, getBorderRadius, setBorderRadius)
    autoHideDelay = pyqtProperty(
        int,
        getAutoHideDelay,
        setAutoHideDelay
    )
    aspectRatioMode = pyqtProperty(
        Qt.AspectRatioMode,
        getAspectRatioMode,
        setAspectRatioMode
    )
    alignment = pyqtProperty(
        Qt.Alignment,
        getAlignment,
        setAlignment
    )
    autoPlayOnReveal = pyqtProperty(
        bool,
        isAutoPlayOnReveal,
        setAutoPlayOnReveal
    )
