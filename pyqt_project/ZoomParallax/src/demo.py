# coding:utf-8
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, FluentIcon, Slider, SplitFluentWindow,
                            SwitchButton, Theme, ToolButton, ToolTipFilter,
                            setTheme, toggleTheme)

from zoom_parallax import ZoomParallax


class ZoomParallaxInterface(QWidget):

    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK)

        self.parallax = ZoomParallax(self)
        self.zoomLabel = BodyLabel(self.tr('Zoom intensity'), self)
        self.zoomSlider = Slider(Qt.Orientation.Horizontal, self)
        self.themeButton = ToolButton(FluentIcon.CONSTRACT, self)

        resourceDir = Path(__file__).resolve().parents[1] / 'resource'
        self.parallax.addImages([str(i) for i in sorted(resourceDir.glob('*.jpg'))])
        self.parallax.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.zoomSlider.setRange(0, 1000)
        self.zoomSlider.setValue(round(self.parallax.progress * 1000))
        self.zoomSlider.setFixedWidth(220)
        self.themeButton.setToolTip(self.tr('Toggle theme'))
        self.themeButton.installEventFilter(ToolTipFilter(self.themeButton))

        self.zoomSlider.valueChanged.connect(lambda v: self.parallax.setProgress(v / 1000))
        self.parallax.progressChanged.connect(self._syncZoomSlider)
        self.themeButton.clicked.connect(toggleTheme)

        self.controlWidget = QWidget(self)
        self.controlLayout = QHBoxLayout(self.controlWidget)
        self.vBoxLayout = QVBoxLayout(self)

        self.controlLayout.addWidget(self.zoomLabel)
        self.controlLayout.addWidget(self.zoomSlider)
        self.controlLayout.addWidget(self.themeButton)
        self.controlLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.controlLayout.setContentsMargins(0, 0, 0, 0)

        self.vBoxLayout.addWidget(self.parallax, 1)
        self.vBoxLayout.addWidget(self.controlWidget, 0, Qt.AlignmentFlag.AlignCenter)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vBoxLayout.setSpacing(16)
        self.vBoxLayout.setContentsMargins(0, 32, 0, 0)

        self.setObjectName('zoomParallaxInterface')

    def _syncZoomSlider(self, progress: float):
        value = round(progress * 1000)
        if self.zoomSlider.value() == value:
            return
        self.zoomSlider.blockSignals(True)
        self.zoomSlider.setValue(value)
        self.zoomSlider.blockSignals(False)
        self.zoomSlider._adjustHandlePos()
        self.zoomSlider.update()


class Window(SplitFluentWindow):

    def __init__(self):
        super().__init__()
        self.zoomParallaxInterface = ZoomParallaxInterface()
        self.initInterface()
        self.initWindow()

    def initInterface(self):
        self.stackedWidget.addWidget(self.zoomParallaxInterface)
        self.navigationInterface.hide()
        self.hBoxLayout.setStretchFactor(self.stackedWidget, 1)
        self.setMicaEffectEnabled(True)
        self.setCustomBackgroundColor(Qt.GlobalColor.transparent, Qt.GlobalColor.transparent)
        self.stackedWidget.setStyleSheet('StackedWidget{background: transparent}')
        self.zoomParallaxInterface.setStyleSheet('ZoomParallaxInterface{background: transparent}')
        self._adjustTitleBar()

    def initWindow(self):
        self.resize(720, 710)
        self.setMinimumSize(720, 710)
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('ZoomParallax')

        desktopWidget = QApplication.desktop()
        assert desktopWidget is not None
        desktop = desktopWidget.availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)
        self._adjustTitleBar()

    def _adjustTitleBar(self):
        self.titleBar.move(0, 0)
        self.titleBar.resize(self.width(), self.titleBar.height())

    def showEvent(self, e):
        super().showEvent(e)
        self._adjustTitleBar()

    def resizeEvent(self, e):
        super(SplitFluentWindow, self).resizeEvent(e)
        self._adjustTitleBar()


if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    w = Window()
    w.show()
    app.exec_() 
