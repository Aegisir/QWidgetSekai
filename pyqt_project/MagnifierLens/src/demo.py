# coding:utf-8
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QPointF, QEvent
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout

from magnifier_lens import MagnifierLens
from qfluentwidgets import (BodyLabel, FluentIcon, Slider, SplitFluentWindow,
                            SwitchButton, ToolButton, setTheme, Theme, isDarkTheme)


class MagnifierLensInterface(QWidget):

    def __init__(self):
        super().__init__()
        # setTheme(Theme.DARK)

        self.lens = MagnifierLens(self)
        self.staticSwitch = SwitchButton(self.tr('Static'), self)
        self.cursorSwitch = SwitchButton(self.tr('Hide cursor'), self)
        self.sizeLabel = BodyLabel(self.tr('Lens size'), self)
        self.zoomLabel = BodyLabel(self.tr('Zoom'), self)
        self.sizeSlider = Slider(Qt.Horizontal, self)
        self.zoomSlider = Slider(Qt.Horizontal, self)
        self.themeButton = ToolButton(FluentIcon.CONSTRACT, self)

        image = Path(__file__).resolve().parents[1] / 'resource' / 'miku.png'
        self.lens.setImage(str(image))
        self.lens.setFixedSize(405, 614)
        self.lens.setZoomFactor(2.5)
        self.lens.setLensSize(180)
        self.lens.setLensPosition(QPointF(140, 120))
        self.lens.installEventFilter(self)

        self.cursorSwitch.setChecked(True)
        for switch, text in ((self.staticSwitch, 'Static'), (self.cursorSwitch, 'Hide cursor')):
            switch.setOnText(self.tr(text))
            switch.setOffText(self.tr(text))

        self.sizeSlider.setRange(90, 260)
        self.sizeSlider.setValue(self.lens.lensSize)
        self.zoomSlider.setRange(10, 40)
        self.zoomSlider.setValue(round(self.lens.zoomFactor * 10))
        for slider in (self.sizeSlider, self.zoomSlider):
            slider.setFixedWidth(240)

        self.staticSwitch.checkedChanged.connect(self._setStaticMode)
        self.cursorSwitch.checkedChanged.connect(self.lens.setCursorHidden)
        self.sizeSlider.valueChanged.connect(self.lens.setLensSize)
        self.zoomSlider.valueChanged.connect(lambda v: self.lens.setZoomFactor(v / 10))
        self.themeButton.clicked.connect(self._toggleTheme)

        self.controlWidget = QWidget(self)
        self.sizeWidget = QWidget(self)
        self.zoomWidget = QWidget(self)
        self.controlLayout = QHBoxLayout()
        self.sizeLayout = QHBoxLayout()
        self.zoomLayout = QHBoxLayout()
        self.vBoxLayout = QVBoxLayout(self)

        self.controlLayout.addWidget(self.staticSwitch)
        self.controlLayout.addWidget(self.cursorSwitch)
        self.controlLayout.addWidget(self.themeButton)
        self.controlLayout.setAlignment(Qt.AlignCenter)
        self.controlLayout.setContentsMargins(0, 0, 0, 0)

        self.sizeLayout.addWidget(self.sizeLabel)
        self.sizeLayout.addWidget(self.sizeSlider)
        self.sizeLayout.setSpacing(12)
        self.sizeLayout.setAlignment(Qt.AlignCenter)
        self.sizeLayout.setContentsMargins(0, 0, 0, 0)
        self.zoomLayout.addWidget(self.zoomLabel)
        self.zoomLayout.addWidget(self.zoomSlider)
        self.zoomLayout.setSpacing(12)
        self.zoomLayout.setAlignment(Qt.AlignCenter)
        self.zoomLayout.setContentsMargins(0, 0, 0, 0)

        self.controlWidget.setLayout(self.controlLayout)
        self.sizeWidget.setLayout(self.sizeLayout)
        self.zoomWidget.setLayout(self.zoomLayout)
        self.controlWidget.setFixedWidth(330)
        self.sizeWidget.setFixedWidth(360)
        self.zoomWidget.setFixedWidth(360)

        self.vBoxLayout.addWidget(self.lens, 0, Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.controlWidget, 0, Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.sizeWidget, 0, Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.zoomWidget, 0, Qt.AlignCenter)
        self.vBoxLayout.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.setSpacing(14)
        self.vBoxLayout.setContentsMargins(0, 24, 0, 0)

        self.setObjectName('magnifierLensInterface')

    def eventFilter(self, obj, e):
        if obj is self.lens and e.type() == QEvent.MouseButtonPress and e.button() == Qt.LeftButton:
            self._setStaticMode(not self.lens.static)
            return True

        return super().eventFilter(obj, e)

    def _setStaticMode(self, isStatic: bool):
        if isStatic == self.lens.static and self.staticSwitch.isChecked() == isStatic:
            return

        self.lens.setStatic(isStatic)
        if self.staticSwitch.isChecked() != isStatic:
            self.staticSwitch.blockSignals(True)
            self.staticSwitch.setChecked(isStatic)
            self.staticSwitch.blockSignals(False)

        if not isStatic:
            pos = self.lens.mapFromGlobal(QCursor.pos())
            if self.lens.rect().contains(pos):
                self.lens.setLensPosition(pos)
                self.lens.setHovering(True)

    def _toggleTheme(self):
        setTheme(Theme.LIGHT if isDarkTheme() else Theme.DARK)


class Window(SplitFluentWindow):

    def __init__(self):
        super().__init__()
        self.magnifierLensInterface = MagnifierLensInterface()
        self.initInterface()
        self.initWindow()

    def initInterface(self):
        self.stackedWidget.addWidget(self.magnifierLensInterface)
        self.navigationInterface.hide()
        self.hBoxLayout.setStretchFactor(self.stackedWidget, 1)
        self.setMicaEffectEnabled(True)
        self.setCustomBackgroundColor(Qt.transparent, Qt.transparent)
        self.stackedWidget.setStyleSheet('StackedWidget{background: transparent}')
        self.magnifierLensInterface.setStyleSheet('MagnifierLensInterface{background: transparent}')
        self._adjustTitleBar()

    def initWindow(self):
        self.resize(400, 790)
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('MagnifierLens')

        desktop = QApplication.desktop().availableGeometry()
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
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    w = Window()
    w.show()
    app.exec_()
