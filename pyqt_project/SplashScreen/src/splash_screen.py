# coding:utf-8
import sys
from PyQt5.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QTimer, Qt, pyqtProperty, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QGraphicsOpacityEffect,
    QWidget,
)

from qfluentwidgets import CheckBox, SplashScreen as FluentSplashScreen
from qfluentwidgets.common.config import qconfig

from lottie_player import LottiePlayer


INTRO_FADE_DURATION = 750
INTRO_HOLD_DURATION = 250
TOGGLE_FADE_DURATION = 500
TOGGLE_IDLE_OPACITY = 0.25
TOGGLE_HOVER_OPACITY = 1.0
TOGGLE_MARGIN_RIGHT = 16
TOGGLE_MARGIN_BOTTOM = 24
TOGGLE_MARGIN_LEFT = 32
TOGGLE_MARGIN_TOP = 32


class SplashScreen(FluentSplashScreen):
    """ Collapse intro splash overlay """

    introFinished = pyqtSignal()

    def __init__(self, icon=None, parent=None, enableShadow=False):
        super().__init__(icon or '', parent, enableShadow)
        self._contentOpacity = 1.0
        self._introEnabled = True
        self._contentWidget = None
        self._contentEffect = None

        self.iconWidget.hide()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        self.lottiePlayer = LottiePlayer(parent=self)
        self.introToggle = CheckBox(self.tr('Use Intro Animation Sequence'), self)
        self.introToggle.setChecked(True)
        self.introToggle.setAttribute(Qt.WA_TranslucentBackground)
        self.introToggle.adjustSize()

        self.toggleEffect = QGraphicsOpacityEffect(self.introToggle)
        self.toggleEffect.setOpacity(TOGGLE_IDLE_OPACITY)
        self.introToggle.setGraphicsEffect(self.toggleEffect)

        self.toggleOpacityAni = QPropertyAnimation(self.toggleEffect, b'opacity', self)
        self.toggleOpacityAni.setDuration(TOGGLE_FADE_DURATION)
        self.toggleOpacityAni.setEasingCurve(QEasingCurve.OutCubic)

        self.opacityAni = QPropertyAnimation(self.lottiePlayer, b'fadeOpacity', self)
        self.opacityAni.setDuration(INTRO_FADE_DURATION)
        self.opacityAni.setEasingCurve(QEasingCurve.OutCubic)
        self.opacityAni.finished.connect(self._onFadeFinished)

        self.contentOpacityAni = QPropertyAnimation(self, b'contentOpacity', self)
        self.contentOpacityAni.setDuration(INTRO_FADE_DURATION)
        self.contentOpacityAni.setEasingCurve(QEasingCurve.OutCubic)

        self.lottiePlayer.finished.connect(self._startCrossFade)
        self.introToggle.toggled.connect(self._onIntroToggled)
        self.introToggle.installEventFilter(self)
        qconfig.themeChanged.connect(self.update)

        if parent is not None:
            self.resize(parent.size())
        self._hideParentTitleBar()
        self._layoutChildren()
        self._raiseChrome()

    def setContentWidget(self, widget: QWidget):
        self._contentWidget = widget
        if widget is None:
            self._contentEffect = None
            return

        self._contentEffect = QGraphicsOpacityEffect(widget)
        self._contentEffect.setOpacity(0)
        widget.setGraphicsEffect(self._contentEffect)

    def getContentOpacity(self):
        return self._contentOpacity

    def setContentOpacity(self, opacity: float):
        self._contentOpacity = opacity
        if self._contentEffect is not None:
            self._contentEffect.setOpacity(opacity)

    contentOpacity = pyqtProperty(float, getContentOpacity, setContentOpacity)

    def isIntroEnabled(self):
        return self._introEnabled

    def setIntroEnabled(self, enabled: bool):
        self._introEnabled = bool(enabled)
        if self.introToggle.isChecked() != self._introEnabled:
            self.introToggle.blockSignals(True)
            self.introToggle.setChecked(self._introEnabled)
            self.introToggle.blockSignals(False)

    def getPlaybackRate(self):
        return self.lottiePlayer.playbackRate

    def setPlaybackRate(self, rate: float):
        self.lottiePlayer.setPlaybackRate(rate)

    def play(self):
        self._stopFade()
        self.lottiePlayer.setFadeOpacity(1.0)
        self.toggleEffect.setOpacity(TOGGLE_IDLE_OPACITY)
        self.show()
        self.raise_()
        self.resize(self.parent().size() if self.parent() else self.size())
        self._layoutChildren()

        if self._contentEffect is not None:
            self._contentEffect.setOpacity(0)

        if not self._introEnabled:
            self._revealContent()
            self.finish()
            self.introFinished.emit()
            return

        self._hideParentTitleBar()
        if sys.platform != 'darwin':
            self.titleBar.show()
        self.introToggle.show()
        self.lottiePlayer.show()
        self.lottiePlayer.play()
        self._raiseChrome()

    def replay(self):
        self.setIntroEnabled(True)
        self.play()

    def eventFilter(self, obj, e: QEvent):
        introToggle = getattr(self, 'introToggle', None)
        if introToggle is not None and obj is introToggle:
            if e.type() == QEvent.Enter:
                self._animateToggleOpacity(TOGGLE_HOVER_OPACITY)
            elif e.type() == QEvent.Leave:
                self._animateToggleOpacity(TOGGLE_IDLE_OPACITY)

        result = super().eventFilter(obj, e)
        return result

    def _animateToggleOpacity(self, opacity: float):
        self.toggleOpacityAni.stop()
        self.toggleOpacityAni.setStartValue(self.toggleEffect.opacity())
        self.toggleOpacityAni.setEndValue(opacity)
        self.toggleOpacityAni.start()

    def _onIntroToggled(self, checked: bool):
        self._introEnabled = checked

    def _startCrossFade(self):
        self._stopFade()
        self.opacityAni.setStartValue(self.lottiePlayer.fadeOpacity)
        self.opacityAni.setEndValue(0.0)
        self._animateToggleOpacity(0.0)
        self.contentOpacityAni.setStartValue(
            self._contentEffect.opacity() if self._contentEffect else 0
        )
        self.contentOpacityAni.setEndValue(1)
        self.opacityAni.start()
        self.contentOpacityAni.start()

    def _stopFade(self):
        self.opacityAni.stop()
        self.contentOpacityAni.stop()
        self.toggleOpacityAni.stop()

    def _onFadeFinished(self):
        self.lottiePlayer.stop()
        self.finish()
        QTimer.singleShot(INTRO_HOLD_DURATION, self.introFinished.emit)

    def _revealContent(self):
        if self._contentEffect is not None:
            self._contentEffect.setOpacity(1)

    def finish(self):
        self.lottiePlayer.stop()
        self.lottiePlayer.setFadeOpacity(1.0)
        self.hide()
        self._revealContent()
        self._restoreParentTitleBar()

    def _layoutChildren(self):
        self.lottiePlayer.setGeometry(self.rect())
        self.lottiePlayer.lower()

        self.introToggle.adjustSize()
        hint = self.introToggle.sizeHint()
        if hint.width() <= 0 or hint.height() <= 0:
            hint = self.introToggle.size()

        x = max(TOGGLE_MARGIN_LEFT, self.width() - TOGGLE_MARGIN_RIGHT - hint.width())
        y = max(TOGGLE_MARGIN_TOP, self.height() - TOGGLE_MARGIN_BOTTOM - hint.height())
        self.introToggle.setGeometry(int(x), int(y), hint.width(), hint.height())
        self._raiseChrome()

    def _raiseChrome(self):
        self.introToggle.raise_()
        if sys.platform != 'darwin':
            self.titleBar.raise_()

    def _parentTitleBar(self):
        parent = self.parent()
        return getattr(parent, 'titleBar', None) if parent is not None else None

    def _hideParentTitleBar(self):
        titleBar = self._parentTitleBar()
        if titleBar is not None:
            titleBar.hide()

    def _restoreParentTitleBar(self):
        titleBar = self._parentTitleBar()
        if titleBar is not None:
            titleBar.show()
            titleBar.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layoutChildren()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawRect(self.rect())
