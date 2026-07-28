import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from stacked_card_carousel import StackedCardCarousel


COMPONENT_DIRECTORY = Path(__file__).resolve().parents[1]
PYQT_PROJECT_DIRECTORY = COMPONENT_DIRECTORY.parent
COMPONENT_SOURCE_PATH = Path(__file__).with_name('stacked_card_carousel.py')
RESOURCE_DIRECTORY = COMPONENT_DIRECTORY / 'resource'


class StackedCardCarouselDemo(QWidget):

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.carousel = StackedCardCarousel(self)

        slides = (
            ('mfy.jpg', 'Asahina Mafuyu'),
            ('ena.jpg', 'Shinonome Ena'),
            ('tks.jpg', 'Tenma Tsukasa'),
            ('saki.jpg', 'Tenma Saki'),
            ('miku.jpg', 'Hatsune Miku'),
        )
        for fileName, title in slides:  
            self.carousel.addItem(str(RESOURCE_DIRECTORY / fileName), title)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.carousel, 1, Qt.AlignmentFlag.AlignCenter)


def main() -> int:
    pyqtProjectPath = str(PYQT_PROJECT_DIRECTORY)
    if pyqtProjectPath not in sys.path:
        sys.path.insert(0, pyqtProjectPath)

    from demo_template import DemoConfiguration, run_demo

    configuration = DemoConfiguration(
        local_source_path=COMPONENT_SOURCE_PATH,
        window_title='StackedCardCarousel',
        component_title='Stacked Card Carousel',
        component_description=(
            'Drag anywhere to fan through responsive image cards.'
        ),
        content_factory=StackedCardCarouselDemo,
        window_size=(715, 700),
        minimum_window_size=(715, 700),
    )
    return run_demo(configuration)


if __name__ == '__main__':
    sys.exit(main())
