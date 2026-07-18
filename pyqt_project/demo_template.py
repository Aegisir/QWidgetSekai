import sys
from pathlib import Path
from typing import Callable, Optional, Tuple

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import (
    QColor,
    QDesktopServices,
    QIcon,
    QPaintEvent,
    QPainter,
    QPen,
    QResizeEvent,
    QShowEvent,
)
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    FluentIcon,
    InfoBarIcon,
    PushButton,
    SplitFluentWindow,
    TeachingTip,
    TeachingTipTailPosition,
    TitleLabel,
    ToolButton,
    isDarkTheme,
    toggleTheme,
)


DEFAULT_REPOSITORY_URL = 'https://github.com/Aegisir/QWidgetSekai'
DEFAULT_COMPONENT_TITLE = 'Component name'
DEFAULT_COMPONENT_DESCRIPTION = 'Component description goes here.'


class DemoConfiguration:
    """Configuration values that distinguish one component demo."""

    def __init__(
        self,
        local_source_path: Path,
        window_title: str = 'Component Demo',
        component_title: str = DEFAULT_COMPONENT_TITLE,
        component_description: str = DEFAULT_COMPONENT_DESCRIPTION,
        repository_url: str = DEFAULT_REPOSITORY_URL,
        content_factory: Optional[Callable[[QWidget], QWidget]] = None,
        toolbar_widget_factory: Optional[Callable[[QWidget], QWidget]] = None,
        window_size: Tuple[int, int] = (600, 720),
        minimum_window_size: Tuple[int, int] = (600, 720),
    ):
        self.local_source_path = local_source_path.resolve()
        self.window_title = window_title
        self.component_title = component_title
        self.component_description = component_description
        self.repository_url = repository_url.rstrip('/')
        self.content_factory = content_factory
        self.toolbar_widget_factory = toolbar_widget_factory
        self.window_size = window_size
        self.minimum_window_size = minimum_window_size

    @property
    def stargazers_url(self) -> str:
        return f'{self.repository_url}/stargazers'


class SeparatorWidget(QWidget):


    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(6, 16)

    def paintEvent(self, paint_event: QPaintEvent):
        painter = QPainter(self)
        pen = QPen(1)
        pen.setCosmetic(True)
        pen.setColor(
            QColor(255, 255, 255, 21)
            if isDarkTheme()
            else QColor(0, 0, 0, 15)
        )
        painter.setPen(pen)

        horizontal_center = self.width() // 2
        painter.drawLine(
            horizontal_center,
            0,
            horizontal_center,
            self.height(),
        )


class ComponentDemoInterface(QWidget):
    """Reusable component introduction page for QWidget demos."""

    def __init__(
        self,
        configuration: DemoConfiguration,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.configuration = configuration

        self.title_label = TitleLabel(
            self.tr(configuration.component_title),
            self,
        )
        self.description_label = BodyLabel(
            self.tr(configuration.component_description),
            self,
        )
        self.local_source_button = PushButton(
            self.tr('Local source'),
            self,
            FluentIcon.DOCUMENT,
        )
        self.source_button = PushButton(
            self.tr('Source'),
            self,
            FluentIcon.GITHUB,
        )
        self.theme_button = ToolButton(FluentIcon.CONSTRACT, self)
        self.link_button = ToolButton(FluentIcon.LINK, self)
        self.favorite_button = ToolButton(FluentIcon.HEART, self)
        self.separator = SeparatorWidget(self)
        self.content_widget = (
            configuration.content_factory(self)
            if configuration.content_factory is not None
            else None
        )
        self.toolbar_widget = (
            configuration.toolbar_widget_factory(self.content_widget)
            if (
                configuration.toolbar_widget_factory is not None and
                self.content_widget is not None
            )
            else None
        )
        if self.toolbar_widget is not None:
            self.toolbar_widget.setParent(self)

        self._initialize_layout()
        self._connect_signals()

    def _initialize_layout(self):
        self.setObjectName('componentDemoInterface')
        self.setStyleSheet(
            'QWidget#componentDemoInterface {'
            'background: transparent; border: none;}'
        )
        self.description_label.setWordWrap(True)
        self.theme_button.setToolTip('')

        self.title_label.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Fixed,
        )
        for text_button in (
            self.local_source_button,
            self.source_button,
        ):
            text_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        for icon_button in (
            self.theme_button,
            self.link_button,
            self.favorite_button,
        ):
            icon_button.setFixedSize(32, 32)

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)
        title_layout.addWidget(self.title_label, 0, Qt.AlignVCenter)
        title_layout.addStretch(1)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(4)
        action_layout.addWidget(self.local_source_button)
        action_layout.addWidget(self.source_button)
        if self.toolbar_widget is not None:
            action_layout.addWidget(self.toolbar_widget)
        action_layout.addStretch(1)
        action_layout.addWidget(self.theme_button)
        action_layout.addWidget(self.separator, 0, Qt.AlignVCenter)
        action_layout.addWidget(self.link_button)
        action_layout.addWidget(self.favorite_button)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(36, 46, 36, 12)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.addLayout(title_layout)
        main_layout.addSpacing(8)
        main_layout.addLayout(action_layout)
        main_layout.addSpacing(14)
        main_layout.addWidget(self.description_label)
        if self.content_widget is None:
            main_layout.addStretch(1)
        else:
            main_layout.addSpacing(18)
            main_layout.addWidget(self.content_widget, 1)

    def _connect_signals(self):
        self.local_source_button.clicked.connect(self._open_local_source)
        self.source_button.clicked.connect(
            lambda: self._open_external_url(self.configuration.repository_url)
        )
        self.theme_button.clicked.connect(toggleTheme)
        self.link_button.clicked.connect(self._copy_repository_link)
        self.favorite_button.clicked.connect(
            lambda: self._open_external_url(
                self.configuration.stargazers_url
            )
        )

    def _open_local_source(self):
        local_source_url = QUrl.fromLocalFile(
            str(self.configuration.local_source_path)
        )
        QDesktopServices.openUrl(local_source_url)

    @staticmethod
    def _open_external_url(url: str):
        QDesktopServices.openUrl(QUrl(url))

    def _copy_repository_link(self):
        QApplication.clipboard().setText(self.configuration.repository_url)
        TeachingTip.create(
            target=self.link_button,
            icon=InfoBarIcon.SUCCESS,
            title=self.tr('Link copied'),
            content=self.configuration.repository_url,
            isClosable=True,
            tailPosition=TeachingTipTailPosition.TOP,
            duration=2000,
            parent=self,
        )


class DemoWindow(SplitFluentWindow):


    def __init__(self, configuration: DemoConfiguration):
        super().__init__()
        self.configuration = configuration
        self.demo_interface = ComponentDemoInterface(configuration)

        self._initialize_interface()
        self._initialize_window()

    def _initialize_interface(self):
        self.stackedWidget.addWidget(self.demo_interface)
        self.stackedWidget.setCurrentWidget(self.demo_interface)
        self.navigationInterface.hide()
        self.hBoxLayout.setStretchFactor(self.stackedWidget, 1)
        self.setMicaEffectEnabled(True)
        self.setCustomBackgroundColor(Qt.transparent, Qt.transparent)
        self.stackedWidget.setStyleSheet(
            'StackedWidget{background: transparent}'
        )
        self._adjust_title_bar()

    def _initialize_window(self):
        self.resize(*self.configuration.window_size)
        self.setMinimumSize(*self.configuration.minimum_window_size)
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle(self.configuration.window_title)

        available_geometry = QApplication.desktop().availableGeometry(self)
        self.move(
            available_geometry.center().x() - self.width() // 2,
            available_geometry.center().y() - self.height() // 2,
        )
        self._adjust_title_bar()

    def _adjust_title_bar(self):
        self.titleBar.move(0, 0)
        self.titleBar.resize(self.width(), self.titleBar.height())

    def showEvent(self, show_event: QShowEvent):
        super().showEvent(show_event)
        self._adjust_title_bar()

    def resizeEvent(self, resize_event: QResizeEvent):
        super(SplitFluentWindow, self).resizeEvent(resize_event)
        self._adjust_title_bar()


def configure_high_dpi():

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)


def run_demo(configuration: DemoConfiguration) -> int:

    configure_high_dpi()
    application = QApplication(sys.argv)
    window = DemoWindow(configuration)
    window.show()
    return application.exec_()
