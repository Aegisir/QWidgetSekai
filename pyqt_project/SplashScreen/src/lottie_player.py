# coding:utf-8
import json
from pathlib import Path

from PyQt5.QtCore import QElapsedTimer, QRectF, QSize, QTimer, Qt, pyqtProperty, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QWidget

from qfluentwidgets.common.config import qconfig
from qfluentwidgets.common.style_sheet import isDarkTheme
from thorvg_python import Colorspace, Engine, LottieAnimation, Result, SwCanvas


DEFAULT_LOTTIE_PATH = (
    Path(__file__).resolve().parents[1] / 'resource' / 'NewLogoTitleIntro.json'
)
DARK_FOREGROUND = QColor(255, 255, 255)
LIGHT_FOREGROUND = QColor(0x22, 0x22, 0x22)


class LottiePlayer(QWidget):
    """ ThorVG-backed Lottie player """

    finished = pyqtSignal()

    def __init__(self, filePath: str = None, parent=None):
        super().__init__(parent=parent)
        self._filePath = str(filePath or DEFAULT_LOTTIE_PATH)
        self._playbackRate = 1.5
        self._playing = False
        self._emittedFinished = False
        self._frameCount = 1
        self._frameRate = 60.0
        self._duration = 10.0
        self._compositionSize = QSize(1920, 1080)
        self._currentFrame = 0
        self._clockOriginMs = 0.0
        self._cacheKey = None
        self._frameImage = QImage()
        self._frameBuffer = b''
        self._themeIsDark = None
        self._fadeOpacity = 1.0
        self._engine = Engine(threads=0)
        self._canvas = SwCanvas(self._engine)
        self._animation = None
        self._picture = None
        self._pictureOnCanvas = False
        self._rawJson = Path(self._filePath).read_text(encoding='utf-8')

        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(8)
        self.timer.timeout.connect(self.update)

        self.setAttribute(Qt.WA_TranslucentBackground)
        self._loadAnimation()
        qconfig.themeChanged.connect(self._onThemeChanged)

    def _loadAnimation(self):
        if self._pictureOnCanvas:
            self._canvas.remove()
            self._pictureOnCanvas = False

        isDark = isDarkTheme()
        self._themeIsDark = isDark
        self._animation = LottieAnimation(self._engine)
        self._picture = self._animation.get_picture()
        payload = self._themedJson(isDark).encode('utf-8')
        loadResult = self._picture.load_data(payload, 'lottie', None, True)
        if loadResult != Result.SUCCESS:
            self._animation = None
            self._picture = None
            return

        _, totalFrame = self._animation.get_total_frame()
        _, duration = self._animation.get_duration()
        _, width, height = self._picture.get_size()
        self._frameCount = max(1.0, float(totalFrame) or 600.0)
        self._duration = float(duration) or 10.0
        self._frameRate = self._frameCount / max(self._duration, 1e-6)
        self._compositionSize = QSize(max(1, int(width)), max(1, int(height)))
        self._cacheKey = None

    def _onThemeChanged(self):
        if self._themeIsDark is isDarkTheme():
            return
        self._loadAnimation()
        self.update()

    def _themedJson(self, isDark: bool) -> str:
        color = DARK_FOREGROUND if isDark else LIGHT_FOREGROUND
        fill = [color.redF(), color.greenF(), color.blueF(), 1.0]
        data = json.loads(self._rawJson)

        def walk(node):
            if isinstance(node, dict):
                if node.get('ty') == 'fl':
                    value = node.get('c', {}).get('k')
                    if self._isWhiteFill(value):
                        node['c']['k'] = fill
                for child in node.values():
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(data)
        return json.dumps(data, separators=(',', ':'))

    @staticmethod
    def _isWhiteFill(value):
        return (
            isinstance(value, list) and
            len(value) >= 3 and
            all(abs(float(channel) - 1.0) < 1e-3 for channel in value[:3])
        )

    def getPlaybackRate(self):
        return self._playbackRate

    def setPlaybackRate(self, rate: float):
        rate = max(0.1, float(rate))
        if abs(rate - self._playbackRate) < 1e-6:
            return

        if self._playing:
            visualMs = self._elapsedMs() * self._playbackRate
            self.clock.start()
            self._clockOriginMs = visualMs / rate

        self._playbackRate = rate

    playbackRate = pyqtProperty(float, getPlaybackRate, setPlaybackRate)

    def getFadeOpacity(self):
        return self._fadeOpacity

    def setFadeOpacity(self, opacity: float):
        opacity = max(0.0, min(1.0, float(opacity)))
        if abs(opacity - self._fadeOpacity) < 1e-6:
            return

        self._fadeOpacity = opacity
        self.update()

    fadeOpacity = pyqtProperty(float, getFadeOpacity, setFadeOpacity)

    def isPlaying(self):
        return self._playing

    def play(self):
        self._playing = True
        self._emittedFinished = False
        self._currentFrame = 0
        self._clockOriginMs = 0.0
        self._cacheKey = None
        self.clock.start()
        self.timer.start()
        self.update()

    def stop(self):
        self._playing = False
        self.timer.stop()

    def duration(self):
        """ Nominal duration in milliseconds at 1x. """
        return int(self._duration * 1000)

    def compositionSize(self):
        return QSize(self._compositionSize)

    def _elapsedMs(self):
        elapsed = self.clock.elapsed() if self.clock.isValid() else 0
        return elapsed + self._clockOriginMs

    def _targetFrame(self):
        progress = self._progress()
        lastFrame = max(self._frameCount - 1e-3, 0.0)
        return min(max(progress, 0.0), 1.0) * lastFrame

    def _progress(self):
        duration = max(self._duration, 1e-6)
        return self._elapsedMs() / 1000.0 * self._playbackRate / duration

    def _renderSize(self):
        dpr = self.devicePixelRatioF() or 1.0
        widgetSize = self.size()
        if widgetSize.width() <= 0 or widgetSize.height() <= 0:
            return QSize(1, 1)

        pixelSize = QSize(
            max(1, round(widgetSize.width() * dpr)),
            max(1, round(widgetSize.height() * dpr)),
        )
        fitted = self._compositionSize.scaled(pixelSize, Qt.KeepAspectRatio)
        return QSize(max(1, fitted.width()), max(1, fitted.height()))

    def _destRect(self):
        widgetSize = self.size()
        if widgetSize.width() <= 0 or widgetSize.height() <= 0:
            return QRectF()

        fitted = self._compositionSize.scaled(widgetSize, Qt.KeepAspectRatio)
        x = (self.width() - fitted.width()) / 2
        y = (self.height() - fitted.height()) / 2
        return QRectF(x, y, fitted.width(), fitted.height())

    def _ensureFrame(self, frame: int):
        if self._animation is None or self._picture is None:
            return

        renderSize = self._renderSize()
        width, height = renderSize.width(), renderSize.height()
        frameKey = round(float(frame), 3)
        cacheKey = (frameKey, width, height, self._themeIsDark)
        if cacheKey == self._cacheKey and not self._frameImage.isNull():
            return

        if self._canvas.w != width or self._canvas.h != height:
            self._canvas.set_target(width, height, cs=Colorspace.ARGB8888)
        self._picture.set_size(float(width), float(height))
        if not self._pictureOnCanvas:
            self._canvas.add(self._picture)
            self._pictureOnCanvas = True

        self._animation.set_frame(frameKey)
        self._canvas.update()
        self._canvas.draw(True)
        self._canvas.sync()

        self._frameImage = QImage()
        self._frameBuffer = self._canvas.buffer_arr
        image = QImage(
            self._frameBuffer,
            width,
            height,
            width * 4,
            QImage.Format_ARGB32_Premultiplied,
        )
        self._frameImage = image
        self._cacheKey = cacheKey

    def paintEvent(self, e):
        if self._animation is None:
            return

        reachedEnd = False
        if self._playing:
            frame = self._targetFrame()
            reachedEnd = self._progress() >= 1.0
        else:
            frame = self._currentFrame

        self._ensureFrame(frame)
        self._currentFrame = frame

        if self._frameImage.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setOpacity(self._fadeOpacity)
        painter.drawImage(self._destRect(), self._frameImage)

        if self._playing and reachedEnd and not self._emittedFinished:
            self._emittedFinished = True
            self._playing = False
            self.timer.stop()
            QTimer.singleShot(0, self.finished.emit)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._cacheKey = None
        self.update()
