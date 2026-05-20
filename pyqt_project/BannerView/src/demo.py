# coding:utf-8
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout

from banner_view import BannerView
from qfluentwidgets import (PushButton, SwitchButton, Slider, BodyLabel,
                            SplitFluentWindow, setTheme, Theme)


class BannerInterface(QWidget):

    def __init__(self):
        super().__init__()
        # setTheme(Theme.DARK)

        self.bannerView = BannerView(self)
        self.perspectiveSwitch = SwitchButton(self.tr('Perspective'), self)
        self.scaleSwitch = SwitchButton(self.tr('Scale'), self)
        self.autoSwitch = SwitchButton(self.tr('Auto shuffle'), self)
        self.spacingSlider = Slider(Qt.Horizontal, self)
        self.spacingLabel = BodyLabel(self.tr('Spacing'), self)
        self.spacingWidget = QWidget(self)
        self.backwardButton = PushButton(self.tr('Play Backward'), self)
        self.stopButton = PushButton(self.tr('Stop'), self)
        self.forwardButton = PushButton(self.tr('Play Forward'), self)

        self.bannerView.setFixedSize(600, 300)
        resourceDir = Path(__file__).resolve().parents[1] / 'resource'
        self.bannerView.addImages([str(i) for i in resourceDir.glob('*')])

        self.scaleSwitch.setChecked(True)
        self.perspectiveSwitch.setOnText(self.tr('Perspective'))
        self.perspectiveSwitch.setOffText(self.tr('Perspective'))
        self.scaleSwitch.setOnText(self.tr('Scale'))
        self.scaleSwitch.setOffText(self.tr('Scale'))
        self.autoSwitch.setOnText(self.tr('Auto shuffle'))
        self.autoSwitch.setOffText(self.tr('Auto shuffle'))
        self.spacingWidget.setFixedWidth(600)
        self.spacingSlider.setFixedWidth(520)
        self.spacingSlider.setRange(0, 200)
        self.spacingSlider.setValue(self.bannerView.itemSpacing)

        self.perspectiveSwitch.checkedChanged.connect(self.bannerView.setPerspectiveEnabled)
        self.scaleSwitch.checkedChanged.connect(self.bannerView.setScaleEnabled)
        self.autoSwitch.checkedChanged.connect(self.bannerView.setAutoShuffle)
        self.spacingSlider.valueChanged.connect(self.bannerView.setItemSpacing)
        self.backwardButton.clicked.connect(self.bannerView.playShuffleBackward)
        self.stopButton.clicked.connect(self.bannerView.stopShuffle)
        self.forwardButton.clicked.connect(self.bannerView.playShuffleForward)

        self.hBoxLayout = QHBoxLayout()
        self.vBoxLayout = QVBoxLayout(self)
        self.buttonLayout = QHBoxLayout()
        self.sliderLayout = QHBoxLayout(self.spacingWidget)

        self.hBoxLayout.addWidget(self.perspectiveSwitch)
        self.hBoxLayout.addWidget(self.scaleSwitch)
        self.hBoxLayout.addWidget(self.autoSwitch)
        self.hBoxLayout.setAlignment(Qt.AlignCenter)

        self.buttonLayout.addWidget(self.backwardButton)
        self.buttonLayout.addWidget(self.stopButton)
        self.buttonLayout.addWidget(self.forwardButton)
        self.buttonLayout.setAlignment(Qt.AlignCenter)

        self.sliderLayout.addWidget(self.spacingLabel)
        self.sliderLayout.addWidget(self.spacingSlider)
        self.sliderLayout.setAlignment(Qt.AlignCenter)
        self.sliderLayout.setContentsMargins(0, 0, 0, 0)

        self.vBoxLayout.addWidget(self.bannerView, 0, Qt.AlignCenter)
        self.vBoxLayout.addLayout(self.hBoxLayout)
        self.vBoxLayout.addWidget(self.spacingWidget, 0, Qt.AlignCenter)
        self.vBoxLayout.addLayout(self.buttonLayout)
        self.vBoxLayout.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.setSpacing(16)
        self.vBoxLayout.setContentsMargins(0, 32, 0, 0)

        self.setObjectName('bannerInterface')


class Window(SplitFluentWindow):

    def __init__(self):
        super().__init__()
        self.bannerInterface = BannerInterface()
        self.initInterface()
        self.initWindow()

    def initInterface(self):
        self.stackedWidget.addWidget(self.bannerInterface)
        self.navigationInterface.hide()
        self.hBoxLayout.setStretchFactor(self.stackedWidget, 1)
        self.setMicaEffectEnabled(True)
        self.setCustomBackgroundColor(Qt.transparent, Qt.transparent)
        self.stackedWidget.setStyleSheet('StackedWidget{background: transparent}')
        self.bannerInterface.setStyleSheet('BannerInterface{background: transparent}')
        self._adjustTitleBar()

    def initWindow(self):
        self.resize(900, 700)
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('BannerView')

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
    # enable dpi scale
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    w = Window()
    w.show()
    app.exec_()
