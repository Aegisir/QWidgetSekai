# coding:utf-8
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from switch_button import IndicatorPosition, SwitchButton
from qfluentwidgets import (BodyLabel, FluentIcon, PushButton, SplitFluentWindow,
                            Theme, ToolButton, ToolTipFilter, setTheme, toggleTheme)


class SwitchButtonInterface(QWidget):
    """ Switch button interface """

    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK)

        self.defaultSwitch = SwitchButton(self.tr('Default'), self)
        self.rightSwitch = SwitchButton(self.tr('Right indicator'), self, IndicatorPosition.RIGHT)
        self.disabledSwitch = SwitchButton(self.tr('Disabled'), self)
        self.colorSwitch = SwitchButton(self.tr('Accent color'), self)
        self.themeButton = ToolButton(FluentIcon.CONSTRACT, self)
        self.resetButton = PushButton(self.tr('Reset'), self)

        self.defaultLabel = BodyLabel(self.tr('Default'), self)
        self.rightLabel = BodyLabel(self.tr('Right indicator'), self)
        self.disabledLabel = BodyLabel(self.tr('Disabled'), self)
        self.colorLabel = BodyLabel(self.tr('Custom color'), self)

        self.defaultSwitch.setOnText(self.tr('On'))
        self.defaultSwitch.setOffText(self.tr('Off'))
        self.rightSwitch.setChecked(True)
        self.rightSwitch.setOnText(self.tr('On'))
        self.rightSwitch.setOffText(self.tr('Off'))
        self.disabledSwitch.setChecked(True)
        self.disabledSwitch.setEnabled(False)
        self.disabledSwitch.setOnText(self.tr('On'))
        self.disabledSwitch.setOffText(self.tr('Off'))
        self.colorSwitch.setOnText(self.tr('On'))
        self.colorSwitch.setOffText(self.tr('Off'))
        self.colorSwitch.setCheckedIndicatorColor('#0f6cbd', '#4cc2ff')

        self.themeButton.setToolTip(self.tr('Toggle theme'))
        self.themeButton.installEventFilter(ToolTipFilter(self.themeButton))

        self.themeButton.clicked.connect(self._toggleTheme)
        self.resetButton.clicked.connect(self._resetSwitches)

        self._initLayout()
        self.setObjectName('switchButtonInterface')

    def _initLayout(self):
        self.vBoxLayout = QVBoxLayout(self)
        self.gridLayout = QGridLayout()
        self.controlLayout = QHBoxLayout()

        for row, (label, switch) in enumerate([
            (self.defaultLabel, self.defaultSwitch),
            (self.rightLabel, self.rightSwitch),
            (self.disabledLabel, self.disabledSwitch),
            (self.colorLabel, self.colorSwitch),
        ]):
            self.gridLayout.addWidget(label, row, 0, Qt.AlignRight | Qt.AlignVCenter)
            self.gridLayout.addWidget(switch, row, 1, Qt.AlignLeft | Qt.AlignVCenter)

        self.gridLayout.setHorizontalSpacing(24)
        self.gridLayout.setVerticalSpacing(24)

        self.controlLayout.addWidget(self.resetButton)
        self.controlLayout.addWidget(self.themeButton)
        self.controlLayout.setAlignment(Qt.AlignCenter)
        self.controlLayout.setSpacing(12)

        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addLayout(self.gridLayout)
        self.vBoxLayout.addSpacing(12)
        self.vBoxLayout.addLayout(self.controlLayout)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.setContentsMargins(24, 32, 24, 24)
        self.vBoxLayout.setSpacing(16)

    def _toggleTheme(self):
        toggleTheme()
        self.update()

    def _resetSwitches(self):
        self.defaultSwitch.setChecked(False)
        self.rightSwitch.setChecked(True)
        self.colorSwitch.setChecked(False)


class Window(SplitFluentWindow):
    """ Demo window """

    def __init__(self):
        super().__init__()
        self.switchButtonInterface = SwitchButtonInterface()
        self.initInterface()
        self.initWindow()

    def initInterface(self):
        self.stackedWidget.addWidget(self.switchButtonInterface)
        self.navigationInterface.hide()
        self.hBoxLayout.setStretchFactor(self.stackedWidget, 1)
        self.setMicaEffectEnabled(True)
        self.setCustomBackgroundColor(Qt.transparent, Qt.transparent)
        self.stackedWidget.setStyleSheet('StackedWidget{background: transparent}')
        self.switchButtonInterface.setStyleSheet('SwitchButtonInterface{background: transparent}')
        self._adjustTitleBar()

    def initWindow(self):
        self.resize(560, 400)
        self.setMinimumSize(420, 340)
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('SwitchButton')

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
