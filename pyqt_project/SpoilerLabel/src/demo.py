import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    CaptionLabel,
    ComboBox,
    CompactDoubleSpinBox,
    CompactSpinBox,
    FluentIcon,
    GroupHeaderCardWidget,
    HeaderCardWidget,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SegmentedWidget,
    SwitchButton,
)

from spoiler_label import SpoilerLabel
from spoiler_media_widget import MediaRevealMode, SpoilerMediaWidget


COMPONENT_SOURCE_PATH = Path(__file__).resolve().with_name('spoiler_label.py')
PYQT_PROJECT_DIRECTORY = Path(__file__).resolve().parents[2]
MEDIA_IMAGE_PATH = (
    Path(__file__).resolve().parents[1] / 'resource' / 'miku.jpg'
)
TEXT_PREVIEW_ROUTE_KEY = 'textPreviewPage'
IMAGE_PREVIEW_ROUTE_KEY = 'imagePreviewPage'
LYRIC_LINES = (
    "Oh please don't let me die",
    'Waiting for your touch',
    "No don't give up on life",
    'This endless dead end',
)
AUTO_HIDE_DELAYS = (-1, 2000, 5000, 10000)
IMAGE_REVEAL_MODES = (
    MediaRevealMode.AUTO,
    MediaRevealMode.RADIAL,
    MediaRevealMode.FADE,
)
IMAGE_ASPECT_RATIO_MODES = (
    Qt.KeepAspectRatioByExpanding,
    Qt.KeepAspectRatio,
    Qt.IgnoreAspectRatio,
)


def create_layout(layout_type, parent, spacing):
    layout = layout_type(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    return layout


def configure_spin_box(
    spin_box,
    value_range,
    step,
    decimals=None,
    suffix=None,
    special_text=None,
):
    spin_box.setRange(*value_range)
    spin_box.setSingleStep(step)
    if decimals is not None:
        spin_box.setDecimals(decimals)
    if suffix is not None:
        spin_box.setSuffix(suffix)
    if special_text is not None:
        spin_box.setSpecialValueText(special_text)


def add_control_groups(card, groups):
    for group in groups:
        card.addGroup(*group)


@contextmanager
def blocked_signals(*controls):
    previous_states = [control.blockSignals(True) for control in controls]
    try:
        yield
    finally:
        for control, previous_state in zip(controls, previous_states):
            control.blockSignals(previous_state)


class SpoilerLabelDemoWidget(ScrollArea):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._is_applying_shared_setting = False

        self.content_widget = QWidget(self)
        self.preview_navigation = SegmentedWidget(self.content_widget)
        self.preview_stack = QStackedWidget(self.content_widget)

        self.text_preview_card = HeaderCardWidget(self.preview_stack)
        self.text_preview_content_widget = QWidget(self.text_preview_card)
        self.independent_text_widget = QWidget(
            self.text_preview_content_widget
        )
        self.lyric_labels = [
            SpoilerLabel(self.tr(lyric_line), self.independent_text_widget)
            for lyric_line in LYRIC_LINES
        ]
        self.text_instruction_label = CaptionLabel(
            self.tr(
                'Click any covered line to reveal the entire block.'
            ),
            self.text_preview_content_widget,
        )
        self.text_status_label = CaptionLabel(
            self.tr('0 of 5 revealed'),
            self.text_preview_content_widget,
        )
        self.text_reveal_button = PrimaryPushButton(
            self.tr('Reveal all'),
            self.text_preview_content_widget,
        )
        self.text_hide_button = PushButton(
            self.tr('Hide all'),
            self.text_preview_content_widget,
        )

        self.multiline_text_widget = QWidget(
            self.text_preview_content_widget
        )
        self.multiline_label = SpoilerLabel(
            self.tr('\n'.join(LYRIC_LINES)),
            self.multiline_text_widget,
        )
        self.text_spoiler_widgets = (
            *self.lyric_labels,
            self.multiline_label,
        )

        self.image_preview_card = HeaderCardWidget(self.preview_stack)
        self.image_preview_content_widget = QWidget(self.image_preview_card)
        self.image_spoiler_widget = SpoilerMediaWidget(
            str(MEDIA_IMAGE_PATH),
            self.image_preview_content_widget,
        )
        self.image_spoiler_widget.setAspectRatioMode(Qt.KeepAspectRatio)
        self.image_spoiler_widget.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )
        self.image_instruction_label = CaptionLabel(
            self.tr(
                'Click the covered image to reveal it from that point'
            ),
            self.image_preview_content_widget,
        )
        self.image_status_label = CaptionLabel(
            self.tr('Hidden'),
            self.image_preview_content_widget,
        )
        self.image_reveal_button = PrimaryPushButton(
            self.tr('Reveal'),
            self.image_preview_content_widget,
        )
        self.image_hide_button = PushButton(
            self.tr('Hide'),
            self.image_preview_content_widget,
        )

        self.controls_card = GroupHeaderCardWidget(self.content_widget)
        self.enabled_switch = SwitchButton(self.controls_card)
        self.animation_duration_spin_box = CompactSpinBox(self.controls_card)
        self.particle_density_spin_box = CompactDoubleSpinBox(
            self.controls_card
        )
        self.particle_speed_spin_box = CompactDoubleSpinBox(
            self.controls_card
        )
        self.auto_hide_combo_box = ComboBox(self.controls_card)

        self.image_controls_card = GroupHeaderCardWidget(self.content_widget)
        self.image_reveal_mode_combo_box = ComboBox(self.image_controls_card)
        self.image_aspect_ratio_combo_box = ComboBox(self.image_controls_card)
        self.image_blur_radius_spin_box = CompactDoubleSpinBox(
            self.image_controls_card
        )
        self.image_border_radius_spin_box = CompactDoubleSpinBox(
            self.image_controls_card
        )

        self.preview_pages_by_route_key = {
            TEXT_PREVIEW_ROUTE_KEY: self.text_preview_card,
            IMAGE_PREVIEW_ROUTE_KEY: self.image_preview_card,
        }

        self._initialize_text_preview()
        self._initialize_image_preview()
        self._initialize_common_controls()
        self._initialize_image_controls()
        self._initialize_navigation()
        self._initialize_scroll_area()
        self._connect_signals()
        self._handle_preview_page_changed(self.preview_stack.currentIndex())

    def _initialize_text_preview(self):
        self.text_preview_card.setObjectName(TEXT_PREVIEW_ROUTE_KEY)
        self.text_preview_card.setTitle(self.tr('STYX HELIX - MYTH & ROID'))

        self.text_instruction_label.setWordWrap(True)
        self.text_instruction_label.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Preferred,
        )

        for example_widget in (
            self.independent_text_widget,
            self.multiline_text_widget,
        ):
            example_widget.setMinimumWidth(0)
            example_widget.setSizePolicy(
                QSizePolicy.Ignored,
                QSizePolicy.Preferred,
            )

        lyrics_layout = create_layout(
            QVBoxLayout,
            self.independent_text_widget,
            8,
        )
        for lyric_label in self.lyric_labels:
            lyric_label.setAutoHideDelay(2000)
            lyric_label.setWordWrap(False)
            lyric_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lyric_label.setMinimumHeight(28)
            lyric_label.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Fixed,
            )
            lyrics_layout.addWidget(lyric_label)

        instruction_widget = QWidget(self.text_preview_content_widget)
        instruction_layout = create_layout(QHBoxLayout, instruction_widget, 12)
        instruction_layout.addWidget(self.text_instruction_label, 1)
        instruction_layout.addWidget(
            self.text_status_label,
            0,
            Qt.AlignRight | Qt.AlignVCenter,
        )

        action_widget = QWidget(self.text_preview_content_widget)
        action_layout = create_layout(QHBoxLayout, action_widget, 8)
        action_layout.addWidget(
            self.text_reveal_button,
            0,
            Qt.AlignLeft,
        )
        action_layout.addWidget(
            self.text_hide_button,
            0,
            Qt.AlignLeft,
        )
        action_layout.addStretch(1)

        self.multiline_label.setAutoHideDelay(2000)
        self.multiline_label.setWordWrap(True)
        self.multiline_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.multiline_label.setMinimumHeight(136)
        self.multiline_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        multiline_layout = create_layout(
            QVBoxLayout,
            self.multiline_text_widget,
            12,
        )
        multiline_layout.addWidget(self.multiline_label)

        examples_widget = QWidget(self.text_preview_content_widget)
        examples_layout = create_layout(QHBoxLayout, examples_widget, 24)
        examples_layout.addWidget(self.independent_text_widget, 1)
        examples_layout.addWidget(self.multiline_text_widget, 1)

        preview_layout = create_layout(
            QVBoxLayout,
            self.text_preview_content_widget,
            12,
        )
        preview_layout.addWidget(examples_widget)
        preview_layout.addWidget(instruction_widget)
        preview_layout.addWidget(action_widget)

        self.text_preview_card.viewLayout.setContentsMargins(20, 16, 20, 18)
        self.text_preview_card.viewLayout.addWidget(
            self.text_preview_content_widget
        )

    def _initialize_image_preview(self):
        self.image_preview_card.setObjectName(IMAGE_PREVIEW_ROUTE_KEY)
        self.image_preview_card.setTitle(
            self.tr('Hatsune Miku - Project SEKAI')
        )
        self.image_spoiler_widget.setFixedHeight(320)
        self.image_spoiler_widget.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        action_widget = QWidget(self.image_preview_content_widget)
        action_layout = create_layout(QHBoxLayout, action_widget, 8)
        action_layout.addWidget(self.image_reveal_button)
        action_layout.addWidget(self.image_hide_button)
        action_layout.addStretch(1)
        action_layout.addWidget(self.image_status_label)

        preview_layout = create_layout(
            QVBoxLayout,
            self.image_preview_content_widget,
            12,
        )
        preview_layout.addWidget(self.image_spoiler_widget)
        preview_layout.addWidget(self.image_instruction_label)
        preview_layout.addWidget(action_widget)

        self.image_preview_card.viewLayout.setContentsMargins(20, 16, 20, 18)
        self.image_preview_card.viewLayout.addWidget(
            self.image_preview_content_widget
        )

    def _initialize_common_controls(self):
        self.controls_card.setTitle(self.tr('Controls'))
        self.controls_card.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Preferred,
        )

        configure_spin_box(
            self.animation_duration_spin_box,
            (0, 2000),
            50,
            suffix=self.tr(' ms'),
            special_text=self.tr('Auto'),
        )
        configure_spin_box(
            self.particle_density_spin_box,
            (0.1, 2.5),
            0.1,
            decimals=1,
        )
        configure_spin_box(
            self.particle_speed_spin_box,
            (0.0, 4.0),
            0.1,
            decimals=1,
        )

        self.auto_hide_combo_box.addItems([
            self.tr('Disabled'),
            self.tr('2 seconds'),
            self.tr('5 seconds'),
            self.tr('10 seconds'),
        ])

        add_control_groups(self.controls_card, (
            (
                FluentIcon.VIEW,
                self.tr('Spoiler enabled'),
                self.tr('Show or bypass the current particle cover.'),
                self.enabled_switch,
            ),
            (
                FluentIcon.STOP_WATCH,
                self.tr('Animation duration'),
                self.tr('Use Auto or select a fixed reveal duration.'),
                self.animation_duration_spin_box,
            ),
            (
                FluentIcon.TILES,
                self.tr('Particle density'),
                self.tr('Adjust the amount of particles over the current cover.'),
                self.particle_density_spin_box,
            ),
            (
                FluentIcon.SPEED_HIGH,
                self.tr('Particle speed'),
                self.tr('Adjust particle movement without changing reveal time.'),
                self.particle_speed_spin_box,
            ),
            (
                FluentIcon.HISTORY,
                self.tr('Auto hide'),
                self.tr('Choose when the current spoiler becomes hidden again.'),
                self.auto_hide_combo_box,
            ),
        ))

    def _initialize_image_controls(self):
        self.image_controls_card.setTitle(self.tr('Image controls'))
        self.image_controls_card.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Preferred,
        )

        self.image_reveal_mode_combo_box.addItems([
            self.tr('Auto'),
            self.tr('Radial'),
            self.tr('Fade'),
        ])
        self.image_aspect_ratio_combo_box.addItems([
            self.tr('Fill'),
            self.tr('Fit'),
            self.tr('Stretch'),
        ])

        configure_spin_box(
            self.image_blur_radius_spin_box,
            (-1.0, 400.0),
            1.0,
            decimals=1,
            suffix=self.tr(' px'),
            special_text=self.tr('Auto'),
        )
        configure_spin_box(
            self.image_border_radius_spin_box,
            (0.0, 200.0),
            1.0,
            decimals=1,
            suffix=self.tr(' px'),
        )

        add_control_groups(self.image_controls_card, (
            (
                FluentIcon.ASTERISK,
                self.tr('Reveal mode'),
                self.tr('Choose radial reveal or a full-image fade.'),
                self.image_reveal_mode_combo_box,
            ),
            (
                FluentIcon.FIT_PAGE,
                self.tr('Aspect ratio'),
                self.tr('Choose how the image fits inside the preview.'),
                self.image_aspect_ratio_combo_box,
            ),
            (
                FluentIcon.BRUSH,
                self.tr('Blur radius'),
                self.tr('Adjust the softness of the reveal boundary.'),
                self.image_blur_radius_spin_box,
            ),
            (
                FluentIcon.FULL_SCREEN,
                self.tr('Border radius'),
                self.tr('Adjust the image and overlay corner radius.'),
                self.image_border_radius_spin_box,
            ),
        ))

    def _initialize_navigation(self):
        self.preview_stack.setObjectName('spoilerPreviewStack')
        self.preview_stack.setStyleSheet(
            'QStackedWidget#spoilerPreviewStack {'
            'background: transparent; border: none;}'
        )
        self.preview_stack.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Fixed,
        )
        self.preview_stack.addWidget(self.text_preview_card)
        self.preview_stack.addWidget(self.image_preview_card)

        self.preview_navigation.addItem(
            routeKey=TEXT_PREVIEW_ROUTE_KEY,
            text=self.tr('Text'),
            icon=FluentIcon.FONT,
        )
        self.preview_navigation.addItem(
            routeKey=IMAGE_PREVIEW_ROUTE_KEY,
            text=self.tr('Image'),
            icon=FluentIcon.PHOTO,
        )
        self.preview_stack.setCurrentWidget(self.text_preview_card)
        self.preview_navigation.setCurrentItem(TEXT_PREVIEW_ROUTE_KEY)

    def _initialize_scroll_area(self):
        self.setObjectName('spoilerLabelDemoWidget')
        self.content_widget.setObjectName('spoilerLabelDemoContent')
        self.content_widget.setStyleSheet(
            'QWidget#spoilerLabelDemoContent {background: transparent;}'
        )

        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 12, 12)
        content_layout.setSpacing(16)
        content_layout.addWidget(self.preview_stack)
        content_layout.addWidget(self.controls_card)
        content_layout.addWidget(self.image_controls_card)
        content_layout.addStretch(1)

        self.setWidget(self.content_widget)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.enableTransparentBackground()

    def _connect_signals(self):
        for signal, handler in (
            (
                self.preview_navigation.currentItemChanged,
                self._switch_preview_page,
            ),
            (
                self.preview_stack.currentChanged,
                self._handle_preview_page_changed,
            ),
            (self.text_reveal_button.clicked, self._reveal_all_text),
            (self.text_hide_button.clicked, self._hide_all_text),
            (self.image_reveal_button.clicked, self._reveal_image),
            (self.image_hide_button.clicked, self._hide_image),
            (
                self.enabled_switch.checkedChanged,
                self._set_current_spoiler_enabled,
            ),
            (
                self.animation_duration_spin_box.valueChanged,
                self._set_current_animation_duration,
            ),
            (
                self.particle_density_spin_box.valueChanged,
                self._set_current_particle_density,
            ),
            (
                self.particle_speed_spin_box.valueChanged,
                self._set_current_particle_speed,
            ),
            (
                self.auto_hide_combo_box.currentIndexChanged,
                self._set_current_auto_hide_delay,
            ),
            (
                self.image_reveal_mode_combo_box.currentIndexChanged,
                self._set_image_reveal_mode,
            ),
            (
                self.image_aspect_ratio_combo_box.currentIndexChanged,
                self._set_image_aspect_ratio_mode,
            ),
            (
                self.image_blur_radius_spin_box.valueChanged,
                self.image_spoiler_widget.setBlurRadius,
            ),
            (
                self.image_border_radius_spin_box.valueChanged,
                self.image_spoiler_widget.setBorderRadius,
            ),
        ):
            signal.connect(handler)

        for spoiler_widget in self.text_spoiler_widgets:
            for signal in (
                spoiler_widget.revealedChanged,
                spoiler_widget.spoilerFinished,
                spoiler_widget.spoilerEnabledChanged,
            ):
                signal.connect(self._handle_spoiler_state_changed)

        for signal in (
            self.image_spoiler_widget.revealedChanged,
            self.image_spoiler_widget.spoilerFinished,
            self.image_spoiler_widget.spoilerEnabledChanged,
            self.image_spoiler_widget.mediaChanged,
        ):
            signal.connect(self._handle_spoiler_state_changed)

    def _switch_preview_page(self, route_key: str):
        target_page = self.preview_pages_by_route_key.get(route_key)
        if (
            target_page is not None and
            self.preview_stack.currentWidget() is not target_page
        ):
            self.preview_stack.setCurrentWidget(target_page)

    def _handle_preview_page_changed(self, page_index: int):
        current_page = self.preview_stack.widget(page_index)
        if current_page is None:
            return

        route_key = current_page.objectName()
        if self.preview_navigation.currentRouteKey() != route_key:
            self.preview_navigation.setCurrentItem(route_key)

        image_page_is_active = current_page is self.image_preview_card
        self.image_controls_card.setVisible(image_page_is_active)
        self._synchronize_common_controls_from_current_page()
        self._synchronize_image_controls()
        self._synchronize_spoiler_states()
        self._resize_preview_stack()

    def _resize_preview_stack(self):
        current_page = self.preview_stack.currentWidget()
        if current_page is None:
            return

        current_layout = current_page.layout()
        if current_layout is not None:
            current_layout.activate()

        available_width = max(1, self.preview_stack.width())
        page_height = (
            current_page.heightForWidth(available_width)
            if current_page.hasHeightForWidth()
            else current_page.sizeHint().height()
        )
        page_height = max(
            page_height,
            current_page.minimumSizeHint().height(),
        )
        if page_height > 0:
            self.preview_stack.setFixedHeight(page_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._resize_preview_stack)

    def _current_spoiler_widgets(self):
        if self.preview_stack.currentWidget() is self.image_preview_card:
            return (self.image_spoiler_widget,)

        return self.text_spoiler_widgets

    def _current_reference_widget(self):
        return self._current_spoiler_widgets()[0]

    def _apply_shared_setting(self, setter_name: str, value):
        self._is_applying_shared_setting = True
        try:
            for spoiler_widget in self._current_spoiler_widgets():
                setter = getattr(spoiler_widget, setter_name)
                setter(value)
        finally:
            self._is_applying_shared_setting = False

        self._synchronize_spoiler_states()

    def _set_current_spoiler_enabled(self, enabled: bool):
        self._apply_shared_setting('setSpoilerEnabled', enabled)

    def _set_current_animation_duration(self, milliseconds: int):
        self._apply_shared_setting('setAnimationDuration', milliseconds)

    def _set_current_particle_density(self, density: float):
        self._apply_shared_setting('setParticleDensity', density)

    def _set_current_particle_speed(self, speed: float):
        self._apply_shared_setting('setParticleSpeed', speed)

    def _set_current_auto_hide_delay(self, option_index: int):
        if 0 <= option_index < len(AUTO_HIDE_DELAYS):
            self._apply_shared_setting(
                'setAutoHideDelay',
                AUTO_HIDE_DELAYS[option_index],
            )

    def _set_image_reveal_mode(self, option_index: int):
        if 0 <= option_index < len(IMAGE_REVEAL_MODES):
            self.image_spoiler_widget.setRevealMode(
                IMAGE_REVEAL_MODES[option_index]
            )

    def _set_image_aspect_ratio_mode(self, option_index: int):
        if 0 <= option_index < len(IMAGE_ASPECT_RATIO_MODES):
            self.image_spoiler_widget.setAspectRatioMode(
                IMAGE_ASPECT_RATIO_MODES[option_index]
            )

    def _reveal_all_text(self):
        for text_spoiler_widget in self.text_spoiler_widgets:
            if not text_spoiler_widget.isRevealed():
                text_spoiler_widget.reveal()

    def _hide_all_text(self):
        for text_spoiler_widget in self.text_spoiler_widgets:
            if text_spoiler_widget.isRevealed():
                text_spoiler_widget.hideSpoiler()

    def _reveal_image(self):
        if not self.image_spoiler_widget.isRevealed():
            self.image_spoiler_widget.reveal()

    def _hide_image(self):
        if self.image_spoiler_widget.isRevealed():
            self.image_spoiler_widget.hideSpoiler()

    def _handle_spoiler_state_changed(self):
        self._synchronize_spoiler_states()

    def _synchronize_common_controls_from_current_page(self):
        reference_widget = self._current_reference_widget()
        auto_hide_delay = reference_widget.getAutoHideDelay()
        auto_hide_index = (
            AUTO_HIDE_DELAYS.index(auto_hide_delay)
            if auto_hide_delay in AUTO_HIDE_DELAYS
            else 0
        )

        controls = (
            self.enabled_switch,
            self.animation_duration_spin_box,
            self.particle_density_spin_box,
            self.particle_speed_spin_box,
            self.auto_hide_combo_box,
        )
        with blocked_signals(*controls):
            self.enabled_switch.setChecked(
                all(
                    spoiler_widget.isSpoilerEnabled()
                    for spoiler_widget in self._current_spoiler_widgets()
                )
            )
            self.animation_duration_spin_box.setValue(
                reference_widget.getAnimationDuration()
            )
            self.particle_density_spin_box.setValue(
                reference_widget.getParticleDensity()
            )
            self.particle_speed_spin_box.setValue(
                reference_widget.getParticleSpeed()
            )
            self.auto_hide_combo_box.setCurrentIndex(auto_hide_index)

    def _synchronize_image_controls(self):
        reveal_mode_index = IMAGE_REVEAL_MODES.index(
            self.image_spoiler_widget.revealMode()
        )
        aspect_ratio_index = IMAGE_ASPECT_RATIO_MODES.index(
            self.image_spoiler_widget.getAspectRatioMode()
        )
        controls = (
            self.image_reveal_mode_combo_box,
            self.image_aspect_ratio_combo_box,
            self.image_blur_radius_spin_box,
            self.image_border_radius_spin_box,
        )
        with blocked_signals(*controls):
            self.image_reveal_mode_combo_box.setCurrentIndex(
                reveal_mode_index
            )
            self.image_aspect_ratio_combo_box.setCurrentIndex(
                aspect_ratio_index
            )
            self.image_blur_radius_spin_box.setValue(
                self.image_spoiler_widget.getBlurRadius()
            )
            self.image_border_radius_spin_box.setValue(
                self.image_spoiler_widget.getBorderRadius()
            )

    def _synchronize_spoiler_states(self):
        self._update_text_state()
        self._update_image_state()

        if self._is_applying_shared_setting:
            return

        current_widgets = self._current_spoiler_widgets()
        all_current_widgets_enabled = all(
            spoiler_widget.isSpoilerEnabled()
            for spoiler_widget in current_widgets
        )
        if self.enabled_switch.isChecked() != all_current_widgets_enabled:
            with blocked_signals(self.enabled_switch):
                self.enabled_switch.setChecked(all_current_widgets_enabled)

    def _update_text_state(self):
        all_text_spoilers_enabled = all(
            text_spoiler_widget.isSpoilerEnabled()
            for text_spoiler_widget in self.text_spoiler_widgets
        )
        revealed_count = sum(
            text_spoiler_widget.isRevealed()
            for text_spoiler_widget in self.text_spoiler_widgets
        )
        if all_text_spoilers_enabled:
            self.text_status_label.setText(
                self.tr('{0} of {1} revealed').format(
                    revealed_count,
                    len(self.text_spoiler_widgets),
                )
            )
        else:
            self.text_status_label.setText(self.tr('Spoiler disabled'))

        self._update_action_button_pair(
            self.text_reveal_button,
            self.text_hide_button,
            all_text_spoilers_enabled and
            revealed_count < len(self.text_spoiler_widgets),
            all_text_spoilers_enabled and revealed_count > 0,
        )

    def _update_image_state(self):
        image_is_available = not self.image_spoiler_widget.image().isNull()
        spoiler_is_enabled = self.image_spoiler_widget.isSpoilerEnabled()
        image_is_revealed = self.image_spoiler_widget.isRevealed()

        if not image_is_available:
            self.image_status_label.setText(self.tr('Image unavailable'))
        elif not spoiler_is_enabled:
            self.image_status_label.setText(self.tr('Spoiler disabled'))
        elif image_is_revealed:
            self.image_status_label.setText(self.tr('Revealed'))
        else:
            self.image_status_label.setText(self.tr('Hidden'))

        self._update_action_button_pair(
            self.image_reveal_button,
            self.image_hide_button,
            image_is_available and spoiler_is_enabled and not image_is_revealed,
            image_is_available and spoiler_is_enabled and image_is_revealed,
        )

    @staticmethod
    def _update_action_button_pair(
        reveal_button: PushButton,
        hide_button: PushButton,
        reveal_enabled: bool,
        hide_enabled: bool,
    ):
        if reveal_button.hasFocus() and not reveal_enabled and hide_enabled:
            hide_button.setEnabled(True)
            hide_button.setFocus(Qt.OtherFocusReason)
        elif hide_button.hasFocus() and not hide_enabled and reveal_enabled:
            reveal_button.setEnabled(True)
            reveal_button.setFocus(Qt.OtherFocusReason)

        reveal_button.setEnabled(reveal_enabled)
        hide_button.setEnabled(hide_enabled)


def get_preview_navigation(content_widget: QWidget) -> QWidget:
    if not isinstance(content_widget, SpoilerLabelDemoWidget):
        raise TypeError('SpoilerLabelDemoWidget content is required')

    return content_widget.preview_navigation


def main() -> int:
    pyqt_project_path = str(PYQT_PROJECT_DIRECTORY)
    if pyqt_project_path not in sys.path:
        sys.path.insert(0, pyqt_project_path)

    # Direct script execution needs the shared template directory on sys.path.
    from demo_template import DemoConfiguration, run_demo

    configuration = DemoConfiguration(
        local_source_path=COMPONENT_SOURCE_PATH,
        window_title='SpoilerLabel',
        component_title='SpoilerLabel',
        component_description=(
            'Switch between interactive text and image spoiler previews.'
        ),
        content_factory=SpoilerLabelDemoWidget,
        toolbar_widget_factory=get_preview_navigation,
        window_size=(640, 680),
        minimum_window_size=(640, 680),
    )
    return run_demo(configuration)


if __name__ == '__main__':
    sys.exit(main())
