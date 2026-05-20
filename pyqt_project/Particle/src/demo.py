# coding:utf-8
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy

from particle import Particle
from qfluentwidgets import (BodyLabel, Slider, SplitFluentWindow,
                            SwitchButton, ToolButton, FluentIcon, ToolTipFilter,
                            setTheme, Theme, toggleTheme)


class ParticleInterface(QWidget):

    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK)

        self.particle = Particle(self)
        self.hoverSwitch = SwitchButton(self.tr('Mouse Hover'), self)
        self.pauseSwitch = SwitchButton(self.tr('Paused'), self)
        self.themeButton = ToolButton(FluentIcon.CONSTRACT, self)
        self.densityLabel = BodyLabel(self.tr('Density'), self)
        self.densitySlider = Slider(Qt.Horizontal, self)
        self.densityWidget = QWidget(self)

        self.particle.setFixedSize(600, 300)
        self.particle.setDensity(6)
        self.hoverSwitch.setChecked(True)
        self.hoverSwitch.setOnText(self.tr('Mouse Hover'))
        self.hoverSwitch.setOffText(self.tr('Mouse Hover'))
        self.pauseSwitch.setOnText(self.tr('Paused'))
        self.pauseSwitch.setOffText(self.tr('Paused'))
        self.densitySlider.setRange(1, 9)
        self.densitySlider.setValue(self.particle.density)
        self.densitySlider.setMaximumWidth(360)
        self.densitySlider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.themeButton.setToolTip(self.tr('Toggle theme'))
        self.themeButton.installEventFilter(ToolTipFilter(self.themeButton))

        self.hoverSwitch.checkedChanged.connect(self.particle.setPointerEnabled)
        self.pauseSwitch.checkedChanged.connect(self.particle.setPaused)
        self.themeButton.clicked.connect(self._toggleTheme)
        self.densitySlider.valueChanged.connect(self.particle.setDensity)

        self.vBoxLayout = QVBoxLayout(self)
        self.hBoxLayout = QHBoxLayout()
        self.sliderLayout = QHBoxLayout(self.densityWidget)

        self.hBoxLayout.addWidget(self.hoverSwitch)
        self.hBoxLayout.addWidget(self.pauseSwitch)
        self.hBoxLayout.addWidget(self.themeButton)
        self.hBoxLayout.setAlignment(Qt.AlignCenter)

        self.sliderLayout.addStretch(1)
        self.sliderLayout.addWidget(self.densityLabel)
        self.sliderLayout.addWidget(self.densitySlider, 1)
        self.sliderLayout.addStretch(1)
        self.sliderLayout.setContentsMargins(0, 0, 0, 0)
        self.sliderLayout.setSpacing(12)

        self.vBoxLayout.addWidget(self.particle, 0, Qt.AlignCenter)
        self.vBoxLayout.addLayout(self.hBoxLayout)
        self.vBoxLayout.addWidget(self.densityWidget)
        self.vBoxLayout.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.setSpacing(16)
        self.vBoxLayout.setContentsMargins(0, 32, 0, 0)

        self.setObjectName('particleInterface')

    def _toggleTheme(self):
        toggleTheme()
        self.particle.update()


class Window(SplitFluentWindow):

    def __init__(self):
        super().__init__()
        self.particleInterface = ParticleInterface()
        self.initInterface()
        self.initWindow()

    def initInterface(self):
        self.stackedWidget.addWidget(self.particleInterface)
        self.navigationInterface.hide()
        self.hBoxLayout.setStretchFactor(self.stackedWidget, 1)
        self.setMicaEffectEnabled(True)
        self.setCustomBackgroundColor(Qt.transparent, Qt.transparent)
        self.stackedWidget.setStyleSheet('StackedWidget{background: transparent}')
        self.particleInterface.setStyleSheet('ParticleInterface{background: transparent}')
        self._adjustTitleBar()

    def initWindow(self):
        self.resize(600, 400)
        self.setMinimumSize(300, 400)
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('Particle')

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)
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
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    w = Window()
    w.show()
    app.exec_()
