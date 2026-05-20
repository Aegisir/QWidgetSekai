# coding:utf-8
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from ms_fluent_window import MSFluentWindow
from navigation_bar import NavigationBar
from qfluentwidgets import (FluentIcon, NavigationItemPosition, SwitchButton,
                            Theme, ToolButton, ToolTipFilter, setTheme,
                            toggleTheme)


class ContentPage(QWidget):

    def __init__(self, title: str, parent=None):
        super().__init__(parent=parent)
        self.setProperty('title', title)

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)


class ControlPanel(QWidget):

    def __init__(self, navigationBar: NavigationBar, parent=None):
        super().__init__(parent=parent)
        self.navigationBar = navigationBar
        self.textSwitch = SwitchButton(self.tr('Selected text'), self)
        self.animationSwitch = SwitchButton(self.tr('Item animation'), self)
        self.themeButton = ToolButton(FluentIcon.CONSTRACT, self)

        self.textSwitch.setChecked(self.navigationBar.isSelectedTextVisible())
        self.textSwitch.setOnText(self.tr('Selected text'))
        self.textSwitch.setOffText(self.tr('Selected text'))
        self.animationSwitch.setChecked(self.navigationBar.isItemAnimationEnabled())
        self.animationSwitch.setOnText(self.tr('Item animation'))
        self.animationSwitch.setOffText(self.tr('Item animation'))
        self.themeButton.setToolTip(self.tr('Toggle theme'))
        self.themeButton.installEventFilter(ToolTipFilter(self.themeButton))

        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.addWidget(self.textSwitch)
        self.hBoxLayout.addWidget(self.animationSwitch)
        self.hBoxLayout.addWidget(self.themeButton)
        self.hBoxLayout.setAlignment(Qt.AlignRight)
        self.hBoxLayout.setContentsMargins(16, 16, 16, 0)
        self.hBoxLayout.setSpacing(12)

        self.textSwitch.checkedChanged.connect(self.navigationBar.setSelectedTextVisible)
        self.animationSwitch.checkedChanged.connect(self.navigationBar.setItemAnimationEnabled)
        self.themeButton.clicked.connect(self._toggleTheme)

    def _toggleTheme(self):
        toggleTheme()
        self.navigationBar.update()


class PageWithControls(QWidget):

    def __init__(self, title: str, navigationBar: NavigationBar, parent=None):
        super().__init__(parent=parent)
        self.controlPanel = ControlPanel(navigationBar, self)
        self.contentPage = ContentPage(title, self)

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.addWidget(self.controlPanel)
        self.vBoxLayout.addWidget(self.contentPage, 1)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(0)


class Window(MSFluentWindow):

    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK)
        self.initInterface()
        self.initWindow()

    def initInterface(self):
        self.homePage = PageWithControls(self.tr('Home'), self.navigationInterface, self)
        self.appPage = ContentPage(self.tr('Application'), self)
        self.videoPage = ContentPage(self.tr('Video'), self)
        self.settingPage = ContentPage(self.tr('Settings'), self)

        self.homePage.setObjectName('homePage')
        self.appPage.setObjectName('appPage')
        self.videoPage.setObjectName('videoPage')
        self.settingPage.setObjectName('settingPage')

        self.addSubInterface(self.homePage, FluentIcon.HOME, self.tr('Home'), FluentIcon.HOME_FILL)
        self.addSubInterface(self.appPage, FluentIcon.APPLICATION, self.tr('Application'))
        self.addSubInterface(self.videoPage, FluentIcon.VIDEO, self.tr('Video'))
        self.addSubInterface(
            self.settingPage,
            FluentIcon.SETTING,
            self.tr('Settings'),
            position=NavigationItemPosition.BOTTOM,
        )

        self.setMicaEffectEnabled(True)
        self.setCustomBackgroundColor(Qt.transparent, Qt.transparent)

    def initWindow(self):
        self.resize(720, 500)
        self.setMinimumSize(560, 420)
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('NavigationBar')

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)


if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    w = Window()
    w.show()
    app.exec_()
