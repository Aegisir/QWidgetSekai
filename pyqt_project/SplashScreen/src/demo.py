# coding:utf-8
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    GroupHeaderCardWidget,
    HeaderCardWidget,
    PrimaryPushButton,
    ScrollArea,
    Slider,
    Theme,
    setTheme,
)

from splash_screen import SplashScreen


COMPONENT_DIRECTORY = Path(__file__).resolve().parents[1]
PYQT_PROJECT_DIRECTORY = COMPONENT_DIRECTORY.parent
COMPONENT_SOURCE_PATH = Path(__file__).with_name('splash_screen.py')


class SplashScreenDemo(ScrollArea):
    """ Replay and playback-rate controls """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        setTheme(Theme.DARK)

        self.contentWidget = QWidget(self)
        self.previewCard = HeaderCardWidget(self.contentWidget)
        self.previewContentWidget = QWidget(self.previewCard)
        self.instructionLabel = CaptionLabel(
            self.tr('Replay the Collapse intro overlay after it finishes.'),
            self.previewContentWidget,
        )
        self.replayButton = PrimaryPushButton(
            self.tr('Replay'),
            self.previewContentWidget,
        )
        self.controlsCard = GroupHeaderCardWidget(self.contentWidget)
        self.rateSlider = Slider(Qt.Horizontal, self.controlsCard)

        self._initializePreviewCard()
        self._initializeControlsCard()
        self._initializeScrollArea()

    def _initializePreviewCard(self):
        self.previewCard.setTitle(self.tr('Collapse intro'))
        self.instructionLabel.setWordWrap(True)
        self.instructionLabel.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Preferred,
        )
        self.replayButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        actionWidget = QWidget(self.previewContentWidget)
        actionLayout = QHBoxLayout(actionWidget)
        actionLayout.setContentsMargins(0, 0, 0, 0)
        actionLayout.setSpacing(8)
        actionLayout.addWidget(self.replayButton, 0, Qt.AlignLeft)
        actionLayout.addStretch(1)

        previewLayout = QVBoxLayout(self.previewContentWidget)
        previewLayout.setContentsMargins(0, 0, 0, 0)
        previewLayout.setSpacing(12)
        previewLayout.addWidget(self.instructionLabel)
        previewLayout.addWidget(actionWidget)

        self.previewCard.viewLayout.setContentsMargins(20, 16, 20, 18)
        self.previewCard.viewLayout.addWidget(self.previewContentWidget)

    def _initializeControlsCard(self):
        self.controlsCard.setTitle(self.tr('Controls'))
        self.controlsCard.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Preferred,
        )
        self.rateSlider.setRange(10, 30)
        self.rateSlider.setValue(15)
        self.rateSlider.setFixedWidth(240)
        self.controlsCard.addGroup(
            FluentIcon.SPEED_HIGH,
            self.tr('Playback rate'),
            self.tr('Adjust how fast the intro sequence plays.'),
            self.rateSlider,
        )

    def _initializeScrollArea(self):
        self.setObjectName('splashScreenDemo')
        self.contentWidget.setObjectName('splashScreenDemoContent')
        self.contentWidget.setStyleSheet(
            'QWidget#splashScreenDemoContent {background: transparent;}'
        )

        contentLayout = QVBoxLayout(self.contentWidget)
        contentLayout.setContentsMargins(0, 0, 12, 12)
        contentLayout.setSpacing(16)
        contentLayout.addWidget(self.previewCard)
        contentLayout.addWidget(self.controlsCard)
        contentLayout.addStretch(1)

        self.setWidget(self.contentWidget)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.enableTransparentBackground()


def main() -> int:
    pyqtProjectPath = str(PYQT_PROJECT_DIRECTORY)
    if pyqtProjectPath not in sys.path:
        sys.path.insert(0, pyqtProjectPath)

    from demo_template import DemoConfiguration, DemoWindow, configure_high_dpi

    configuration = DemoConfiguration(
        local_source_path=COMPONENT_SOURCE_PATH,
        window_title='SplashScreen',
        component_title='SplashScreen',
        component_description=(
            'Collapse intro overlay. Replay to play it again.'
        ),
        content_factory=SplashScreenDemo,
        window_size=(1024, 576),
        minimum_window_size=(1024, 576),
    )

    configure_high_dpi()
    application = QApplication(sys.argv)
    window = DemoWindow(configuration)
    contentWidget = window.demo_interface.content_widget
    splashScreen = SplashScreen(window.windowIcon(), window)
    splashScreen.setContentWidget(window.demo_interface)
    splashScreen.setPlaybackRate(1.5)
    contentWidget.replayButton.clicked.connect(splashScreen.replay)
    contentWidget.rateSlider.valueChanged.connect(
        lambda value: splashScreen.setPlaybackRate(value / 10)
    )

    window.show()
    splashScreen.play()
    return application.exec_()


if __name__ == '__main__':
    sys.exit(main())
