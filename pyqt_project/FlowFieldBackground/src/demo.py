# coding:utf-8
import sys
from typing import cast

from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QIcon, QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from flow_field_background import FlowFieldBackground
from qfluentwidgets import (BodyLabel, ColorPickerButton, FluentIcon, Slider,
                            SplitFluentWindow, SwitchButton, Theme, ToolButton,
                            ToolTipFilter, setTheme, setThemeColor, toggleTheme)


class FlowFieldWindow(QWidget):
    """ Borderless flow field window """

    def __init__(self):
        super().__init__()
        self.background = FlowFieldBackground(self)
        self.vBoxLayout = QVBoxLayout(self)
        self._dragPosition = QPoint()

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setWindowTitle('FlowFieldBackground')
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.resize(960, 540)
        self.setMinimumSize(480, 300)
        self.setStyleSheet('FlowFieldWindow{background: black}')

        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.addWidget(self.background)
        self.background.installEventFilter(self)

    def eventFilter(self, a0, a1):
        if a0 is self.background and a1 is not None:
            if a1.type() == QEvent.Type.MouseButtonPress:
                event = cast(QMouseEvent, a1)
                if event.button() == Qt.MouseButton.LeftButton:
                    self._dragPosition = event.globalPos() - self.frameGeometry().topLeft()
            elif a1.type() == QEvent.Type.MouseMove:
                event = cast(QMouseEvent, a1)
                if event.buttons() & Qt.MouseButton.LeftButton == Qt.MouseButton.LeftButton:
                    self.move(event.globalPos() - self._dragPosition)

        return super().eventFilter(a0, a1)

    def keyPressEvent(self, a0):
        if a0 is None:
            return

        event = cast(QKeyEvent, a0)
        if event.key() == Qt.Key.Key_Escape:
            self.showNormal() if self.isFullScreen() else self.close()
        elif event.key() == Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        else:
            super().keyPressEvent(event)


class FlowFieldControlInterface(QWidget):
    """ Flow field api control interface """

    def __init__(self, background: FlowFieldBackground):
        super().__init__()
        self.background = background
        self.pauseSwitch = SwitchButton(self.tr('Paused'), self)
        self.pointerSwitch = SwitchButton(self.tr('Mouse force'), self)
        self.themeButton = ToolButton(FluentIcon.CONSTRACT, self)
        self.particleColorButton = ColorPickerButton(background.color, self.tr('Particle'), self)
        self.backgroundColorButton = ColorPickerButton(background.backgroundColor, self.tr('Background'), self)

        self.vBoxLayout = QVBoxLayout(self)
        self.switchLayout = QHBoxLayout()
        self.colorLayout = QHBoxLayout()
        self.gridWidget = QWidget(self)
        self.gridLayout = QGridLayout(self.gridWidget)

        self.__initWidget()

    def __initWidget(self):
        self.setObjectName('flowFieldControlInterface')
        self.pointerSwitch.setChecked(self.background.pointerEnabled)
        for switch, text in ((self.pauseSwitch, 'Paused'), (self.pointerSwitch, 'Mouse force')):
            switch.setOnText(self.tr(text))
            switch.setOffText(self.tr(text))

        self.themeButton.setToolTip(self.tr('Toggle theme'))
        self.themeButton.installEventFilter(ToolTipFilter(self.themeButton))

        self._addSlider(0, 'Particles', 100, 2000, self.background.particleCount,
                        lambda v: str(v), self.background.setParticleCount)
        self._addSlider(1, 'Speed', 10, 300, round(self.background.speed * 100),
                        lambda v: f'{v / 100:.2f}', lambda v: self.background.setSpeed(v / 100))
        self._addSlider(2, 'Trail', 1, 60, round(self.background.trailOpacity * 100),
                        lambda v: f'{v / 100:.2f}', lambda v: self.background.setTrailOpacity(v / 100))
        self._addSlider(3, 'FPS', 30, 144, self.background.targetFps,
                        lambda v: str(v), self.background.setTargetFps)

        self.pauseSwitch.checkedChanged.connect(self.background.setPaused)
        self.pointerSwitch.checkedChanged.connect(self.background.setPointerEnabled)
        self.themeButton.clicked.connect(toggleTheme)
        self.particleColorButton.colorChanged.connect(self._setParticleColor)
        self.backgroundColorButton.colorChanged.connect(self.background.setBackgroundColor)

        self.switchLayout.addWidget(self.pauseSwitch)
        self.switchLayout.addWidget(self.pointerSwitch)
        self.switchLayout.addWidget(self.themeButton)
        self.switchLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for label, button in (('Particle', self.particleColorButton), ('Background', self.backgroundColorButton)):
            self.colorLayout.addWidget(BodyLabel(self.tr(label), self))
            self.colorLayout.addWidget(button)

        self.colorLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.colorLayout.setSpacing(12)
        self.gridLayout.setHorizontalSpacing(12)
        self.gridLayout.setVerticalSpacing(10)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)

        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addLayout(self.switchLayout)
        self.vBoxLayout.addWidget(self.gridWidget)
        self.vBoxLayout.addLayout(self.colorLayout)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.setSpacing(18)
        self.vBoxLayout.setContentsMargins(24, 48, 24, 16)

    def _addSlider(self, row: int, text: str, minimum: int, maximum: int, value: int, formatter, slot):
        label = BodyLabel(self.tr(text), self)
        valueLabel = BodyLabel(formatter(value), self)
        slider = Slider(Qt.Orientation.Horizontal, self)

        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.setMinimumWidth(240)
        slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        valueLabel.setFixedWidth(54)

        def onValueChanged(v):
            valueLabel.setText(formatter(v))
            slot(v)

        slider.valueChanged.connect(onValueChanged)
        self.gridLayout.addWidget(label, row, 0)
        self.gridLayout.addWidget(slider, row, 1)
        self.gridLayout.addWidget(valueLabel, row, 2)

    def _setParticleColor(self, color):
        self.background.setColor(color)
        setThemeColor(color)


class Window(SplitFluentWindow):
    """ Flow field api control window """

    def __init__(self, displayWindow: FlowFieldWindow):
        super().__init__()
        self.displayWindow = displayWindow
        self.flowFieldControlInterface = FlowFieldControlInterface(displayWindow.background)
        self.initInterface()
        self.initWindow()

    def initInterface(self):
        self.stackedWidget.addWidget(self.flowFieldControlInterface)
        self.navigationInterface.hide()
        self.hBoxLayout.setStretchFactor(self.stackedWidget, 1)
        self.setMicaEffectEnabled(True)
        self.setCustomBackgroundColor(Qt.GlobalColor.transparent, Qt.GlobalColor.transparent)
        self.stackedWidget.setStyleSheet('StackedWidget{background: transparent}')
        self.flowFieldControlInterface.setStyleSheet('FlowFieldControlInterface{background: transparent}')
        self._adjustTitleBar()

    def initWindow(self):
        self.resize(420, 720)
        self.setMinimumSize(480, 400)
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('FlowFieldBackground')

    def _adjustTitleBar(self):
        self.titleBar.move(0, 0)
        self.titleBar.resize(self.width(), self.titleBar.height())

    def closeEvent(self, e):
        self.displayWindow.close()
        super().closeEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        self._adjustTitleBar()

    def resizeEvent(self, e):
        super(SplitFluentWindow, self).resizeEvent(e)
        self._adjustTitleBar()


def moveWindows(displayWindow: FlowFieldWindow, controlWindow: Window):
    desktopWidget = QApplication.desktop()
    if desktopWidget is None:
        return

    desktop = desktopWidget.availableGeometry()
    x = desktop.x() + max(24, (desktop.width() - displayWindow.width() - controlWindow.width() - 24) // 2)
    y = desktop.y() + max(24, (desktop.height() - displayWindow.height()) // 2)
    displayWindow.move(x, y)
    controlWindow.move(min(x + displayWindow.width() + 24, desktop.right() - controlWindow.width()), y)


if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    setTheme(Theme.DARK)
    app = QApplication(sys.argv)
    display = FlowFieldWindow()
    w = Window(display)
    moveWindows(display, w)
    display.show()
    w.show()
    sys.exit(app.exec_())
