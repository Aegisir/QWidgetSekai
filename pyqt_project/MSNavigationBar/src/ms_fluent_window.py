# coding:utf-8
from typing import Union

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from navigation_bar import NavigationBar, NavigationBarPushButton, NavigationItemPosition
from qfluentwidgets.common.icon import FluentIconBase
from qfluentwidgets.common.router import qrouter
from qfluentwidgets.window.fluent_window import FluentWindowBase, MSFluentTitleBar


class MSFluentWindow(FluentWindowBase):
    """ Fluent window in Microsoft Store style with local NavigationBar """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitleBar(MSFluentTitleBar(self))

        self.navigationInterface = NavigationBar(self)

        self.hBoxLayout.setContentsMargins(0, 48, 0, 0)
        self.hBoxLayout.addWidget(self.navigationInterface)
        self.hBoxLayout.addWidget(self.stackedWidget, 1)

        self.titleBar.raise_()
        self.titleBar.setAttribute(Qt.WA_StyledBackground)

    def addSubInterface(self, interface: QWidget, icon: Union[FluentIconBase, QIcon, str],
                        text: str, selectedIcon=None, position=NavigationItemPosition.TOP,
                        isTransparent=False) -> NavigationBarPushButton:
        """ add sub interface, the object name of `interface` should be set already """
        if not interface.objectName():
            raise ValueError("The object name of `interface` can't be empty string.")

        interface.setProperty("isStackedTransparent", isTransparent)
        self.stackedWidget.addWidget(interface)

        routeKey = interface.objectName()
        item = self.navigationInterface.addItem(
            routeKey=routeKey,
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(interface),
            selectedIcon=selectedIcon,
            position=position,
        )

        if self.stackedWidget.count() == 1:
            self.stackedWidget.currentChanged.connect(self._onCurrentInterfaceChanged)
            self.navigationInterface.setCurrentItem(routeKey)
            qrouter.setDefaultRouteKey(self.stackedWidget, routeKey)

        self._updateStackedBackground()

        return item

    def removeInterface(self, interface, isDelete=False):
        self.navigationInterface.removeWidget(interface.objectName())
        self.stackedWidget.removeWidget(interface)
        interface.hide()

        if isDelete:
            interface.deleteLater()
