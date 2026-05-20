# coding:utf-8
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout

from card_slider import CardSlider
from qfluentwidgets import (BodyLabel, FluentIcon, PushButton, Slider, SplitFluentWindow,
                            SwitchButton, ToolButton, setTheme, Theme, isDarkTheme)


class CardSliderInterface(QWidget):

    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK)

        self.cardSlider = CardSlider(self)
        self.tiltSwitch = SwitchButton(self.tr('Tilt'), self)
        self.bgSwitch = SwitchButton(self.tr('Background'), self)
        self.autoSwitch = SwitchButton(self.tr('Auto play'), self)
        self.durationLabel = BodyLabel(self.tr('Duration'), self)
        self.durationSlider = Slider(Qt.Horizontal, self)
        self.previousButton = PushButton(self.tr('Previous'), self)
        self.nextButton = PushButton(self.tr('Next'), self)
        self.themeButton = ToolButton(FluentIcon.CONSTRACT, self)

        resourceDir = Path(__file__).resolve().parents[1] / 'resource'
        data = [
            ('Mafuyu', 'Asahina', 'A perfect mask, softly cracking.'),
            ('Airi', 'Momoi', 'Idol grit with a bright grin.'),
            ('Emu', 'Otori', 'Wonderhoy, loud and fearless.'),
            ('Saki', 'Tenma', 'A bright melody after the rain.'),
        ]
        self.cardSlider.addItems((str(image), *text) for image, text in zip(sorted(resourceDir.glob('*.jpg')), data))
        self.cardSlider.setFixedSize(900, 560)

        self.tiltSwitch.setChecked(True)
        self.bgSwitch.setChecked(True)
        for switch, text in ((self.tiltSwitch, 'Tilt'), (self.bgSwitch, 'Background'), (self.autoSwitch, 'Auto play')):
            switch.setOnText(self.tr(text))
            switch.setOffText(self.tr(text))

        self.durationSlider.setRange(300, 1200)
        self.durationSlider.setValue(self.cardSlider.duration)
        self.durationSlider.setFixedWidth(360)

        self.tiltSwitch.checkedChanged.connect(self.cardSlider.setTiltEnabled)
        self.bgSwitch.checkedChanged.connect(self.cardSlider.setBackgroundEnabled)
        self.autoSwitch.checkedChanged.connect(self.cardSlider.setAutoPlay)
        self.durationSlider.valueChanged.connect(self.cardSlider.setDuration)
        self.previousButton.clicked.connect(self.cardSlider.scrollPrevious)
        self.nextButton.clicked.connect(self.cardSlider.scrollNext)
        self.themeButton.clicked.connect(self._toggleTheme)

        self.hBoxLayout = QHBoxLayout()
        self.buttonLayout = QHBoxLayout()
        self.durationWidget = QWidget(self)
        self.sliderLayout = QHBoxLayout()
        self.vBoxLayout = QVBoxLayout(self)

        self.hBoxLayout.addWidget(self.tiltSwitch)
        self.hBoxLayout.addWidget(self.bgSwitch)
        self.hBoxLayout.addWidget(self.autoSwitch)
        self.hBoxLayout.addWidget(self.themeButton)
        self.hBoxLayout.setAlignment(Qt.AlignCenter)

        self.sliderLayout.addWidget(self.durationLabel)
        self.sliderLayout.addWidget(self.durationSlider)
        self.sliderLayout.setAlignment(Qt.AlignCenter)
        self.sliderLayout.setContentsMargins(0, 0, 0, 0)

        self.durationWidget.setLayout(self.sliderLayout)
        self.durationWidget.setFixedWidth(460)

        self.buttonLayout.addWidget(self.previousButton)
        self.buttonLayout.addWidget(self.nextButton)
        self.buttonLayout.setAlignment(Qt.AlignCenter)

        self.vBoxLayout.addWidget(self.cardSlider, 0, Qt.AlignCenter)
        self.vBoxLayout.addLayout(self.hBoxLayout)
        self.vBoxLayout.addWidget(self.durationWidget, 0, Qt.AlignCenter)
        self.vBoxLayout.addLayout(self.buttonLayout)
        self.vBoxLayout.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.setSpacing(16)
        self.vBoxLayout.setContentsMargins(0, 32, 0, 0)

        self.setObjectName('cardSliderInterface')

    def _toggleTheme(self):
        setTheme(Theme.LIGHT if isDarkTheme() else Theme.DARK)


class Window(SplitFluentWindow):

    def __init__(self):
        super().__init__()
        self._firstFrameReady = False
        self._targetSize = (1100, 760)
        self.setWindowOpacity(0)
        self.cardSliderInterface = CardSliderInterface()
        self.initInterface()
        self.initWindow()

    def initInterface(self):
        self.stackedWidget.addWidget(self.cardSliderInterface)
        self.navigationInterface.hide()
        self.hBoxLayout.setStretchFactor(self.stackedWidget, 1)
        self.setCustomBackgroundColor(Qt.transparent, Qt.transparent)
        self.setMicaEffectEnabled(True)
        self.setStyleSheet('Window{background: transparent}')
        self.stackedWidget.setStyleSheet('StackedWidget{background: transparent}')
        self.cardSliderInterface.setStyleSheet('CardSliderInterface{background: transparent}')
        self._adjustTitleBar()

    def initWindow(self):
        self.resize(1, 1)
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('CardSlider')

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self._targetSize[0] // 2, h // 2 - self._targetSize[1] // 2)
        self._adjustTitleBar()

    def _adjustTitleBar(self):
        self.titleBar.move(0, 0)
        self.titleBar.resize(self.width(), self.titleBar.height())

    def showEvent(self, e):
        super().showEvent(e)
        self._adjustTitleBar()
        if not self._firstFrameReady:
            self._firstFrameReady = True
            QTimer.singleShot(0, self._showReadyWindow)

    def _showReadyWindow(self):
        self.resize(*self._targetSize)
        self._adjustTitleBar()
        self.setWindowOpacity(1)

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
