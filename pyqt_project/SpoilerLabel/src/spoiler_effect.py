import math
import random
import weakref
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from PyQt5.QtCore import QElapsedTimer, QObject, QPointF, QRectF, QTimer, Qt
from PyQt5.QtGui import (QColor, QPainter, QPainterPath, QPen, QPixmap,
                         QPolygonF, QRadialGradient, QTransform)


_PARTICLE_LIFETIME_TABLE = tuple(
    math.sin(math.pi * index / 63) for index in range(64)
)


@dataclass(frozen=True)
class ParticleProfile:
    name: str
    width: int
    height: int
    baseParticleCount: int
    pointSize: float
    timeScale: float
    layerCount: int = 12


TEXT_PARTICLE_PROFILE = ParticleProfile('text', 240, 120, 4608, 1.8, 1.2)
MEDIA_PARTICLE_PROFILE = ParticleProfile('media', 480, 480, 9216, 1.6, 0.65)


class ParticleSimulation:
    def __init__(
        self,
        dpr: float,
        density: float,
        speed: float,
        color: QColor,
        profile: ParticleProfile = TEXT_PARTICLE_PROFILE
    ):
        self.dpr = dpr
        self.density = density
        self.speed = speed
        self.color = QColor(color)
        self.profile = profile
        self.elapsedTime = 0.0
        self.texture = QPixmap()
        self.isTextureDirty = True

        seed = (
            round(dpr * 1000) * 1000003 +
            round(density * 1000) * 9176 +
            round(speed * 1000) * 131 +
            color.rgba() +
            sum(ord(character) for character in profile.name) * 53
        )
        self.randomGenerator = random.Random(seed)
        particleCount = 0 if density <= 0 else max(
            64,
            round(profile.baseParticleCount * density)
        )
        self.layers = self._createParticleLayers(particleCount)

    def advance(self, elapsedSeconds: float):
        if self.speed <= 0 or not self.layers:
            return

        simulationDelta = (
            min(elapsedSeconds, 0.05) *
            self.profile.timeScale *
            self.speed
        )
        self.elapsedTime += simulationDelta
        self.isTextureDirty = True

    def currentTexture(self) -> QPixmap:
        if self.isTextureDirty:
            self._renderTexture()

        return self.texture

    def _createParticleLayers(self, particleCount: int):
        if particleCount <= 0:
            return []

        profile = self.profile
        physicalWidth = max(1, round(profile.width * self.dpr))
        physicalHeight = max(1, round(profile.height * self.dpr))
        baseCount, extraCount = divmod(particleCount, profile.layerCount)
        layerPointCounts = [
            baseCount + (layerIndex < extraCount)
            for layerIndex in range(profile.layerCount)
        ]

        layers = []
        for layerIndex, layerPointCount in enumerate(layerPointCounts):
            layer = QPixmap(physicalWidth, physicalHeight)
            layer.setDevicePixelRatio(self.dpr)
            layer.fill(Qt.transparent)

            points = QPolygonF()
            for _ in range(layerPointCount):
                points.append(QPointF(
                    self.randomGenerator.random() * profile.width,
                    self.randomGenerator.random() * profile.height
                ))

            opacityScale = (
                0.6 +
                0.4 * layerIndex / max(1, profile.layerCount - 1)
            )
            particleColor = QColor(self.color)
            particleColor.setAlpha(round(255 * opacityScale))

            painter = QPainter(layer)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(particleColor, profile.pointSize)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawPoints(points)
            painter.end()
            layers.append(layer)

        return layers

    def _renderTexture(self):
        profile = self.profile
        physicalWidth = max(1, round(profile.width * self.dpr))
        physicalHeight = max(1, round(profile.height * self.dpr))
        texture = QPixmap(physicalWidth, physicalHeight)
        texture.setDevicePixelRatio(self.dpr)
        texture.fill(Qt.transparent)

        painter = QPainter(texture)
        textureRect = QRectF(0, 0, profile.width, profile.height)
        fullTurn = math.pi * 2.0
        movementScale = min(profile.width, profile.height) / 120.0
        for layerIndex, layer in enumerate(self.layers):
            phase = fullTurn * layerIndex / profile.layerCount
            lifetime = (
                self.elapsedTime * (0.18 + layerIndex * 0.006) +
                layerIndex / profile.layerCount
            ) % 1.0
            lifetimeIndex = min(
                len(_PARTICLE_LIFETIME_TABLE) - 1,
                int(lifetime * len(_PARTICLE_LIFETIME_TABLE))
            )
            painter.setOpacity(_PARTICLE_LIFETIME_TABLE[lifetimeIndex])

            horizontalOffset = movementScale * (
                math.sin(self.elapsedTime * 0.92 + phase) * 8.0 +
                math.sin(self.elapsedTime * 0.37 - phase * 1.7) * 3.0
            )
            verticalOffset = movementScale * (
                math.cos(self.elapsedTime * 0.74 - phase) * 6.0 +
                math.sin(self.elapsedTime * 0.29 + phase * 1.3) * 2.0
            )
            painter.drawTiledPixmap(
                textureRect,
                layer,
                QPointF(horizontalOffset, verticalOffset)
            )

        painter.end()
        self.texture = texture
        self.isTextureDirty = False


class ParticleClock(QObject):
    def __init__(self):
        super().__init__(parent=None)
        self.profiles: Dict[Tuple, ParticleSimulation] = {}
        self.profileWidgets: Dict[Tuple, weakref.WeakSet] = {}
        self.widgetProfiles = weakref.WeakKeyDictionary()

        self.elapsedTimer = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def activate(self, widget):
        profileKey = widget._particleProfileKey()
        previousKey = self.widgetProfiles.get(widget)
        if previousKey != profileKey:
            self.deactivate(widget)
            self.widgetProfiles[widget] = profileKey
            self._profile(profileKey, widget)
        self.profileWidgets.setdefault(profileKey, weakref.WeakSet()).add(widget)
        self._updateTimerState()

    def deactivate(self, widget):
        profileKey = self.widgetProfiles.pop(widget, None)
        if profileKey is None:
            return

        widgets = self.profileWidgets.get(profileKey)
        if widgets is not None:
            widgets.discard(widget)

        self._pruneUnusedProfiles()
        self._updateTimerState()

    def textureFor(self, widget) -> QPixmap:
        profileKey = widget._particleProfileKey()
        registeredProfileKey = self.widgetProfiles.get(widget)
        if registeredProfileKey is None:
            return self._createSimulation(widget).currentTexture()

        if registeredProfileKey != profileKey:
            self.activate(widget)

        return self._profile(profileKey, widget).currentTexture()

    def _createSimulation(self, widget) -> ParticleSimulation:
        return ParticleSimulation(
            effectiveDevicePixelRatio(widget),
            widget.particleDensity,
            widget.particleSpeed,
            widget._effectiveParticleColor(),
            widget._particleSimulationProfile()
        )

    def _profile(self, profileKey: Tuple, widget) -> ParticleSimulation:
        profile = self.profiles.get(profileKey)
        if profile is None:
            profile = self._createSimulation(widget)
            self.profiles[profileKey] = profile

        return profile

    def _tick(self):
        elapsedSeconds = min(self.elapsedTimer.nsecsElapsed() / 1e9, 0.05)
        self.elapsedTimer.restart()

        for profileKey, widgets in tuple(self.profileWidgets.items()):
            activeWidgets = tuple(widgets)
            if not activeWidgets:
                continue

            profile = self.profiles.get(profileKey)
            if profile is None:
                continue

            profile.advance(elapsedSeconds)
            profile.currentTexture()
            for widget in activeWidgets:
                updateParticleFrame = getattr(
                    widget,
                    '_updateParticleFrame',
                    widget.update
                )
                updateParticleFrame()

        self._pruneUnusedProfiles()
        self._updateTimerState()

    def _hasAnimatedProfiles(self) -> bool:
        return any(
            widgets and
            (profile := self.profiles.get(profileKey)) is not None and
            profile.speed > 0
            for profileKey, widgets in self.profileWidgets.items()
        )

    def _updateTimerState(self):
        shouldRun = self._hasAnimatedProfiles()
        if shouldRun and not self.timer.isActive():
            self.elapsedTimer.restart()
            self.timer.start()
        elif not shouldRun and self.timer.isActive():
            self.timer.stop()

    def _pruneUnusedProfiles(self):
        for profileKey, widgets in tuple(self.profileWidgets.items()):
            if not widgets:
                self.profileWidgets.pop(profileKey, None)
                self.profiles.pop(profileKey, None)


_particleClockInstance: Optional[ParticleClock] = None


def particleClock() -> ParticleClock:
    global _particleClockInstance
    if _particleClockInstance is None:
        _particleClockInstance = ParticleClock()

    return _particleClockInstance


def existingParticleClock() -> Optional[ParticleClock]:
    return _particleClockInstance


def effectiveDevicePixelRatio(widget) -> float:
    dprGetter = getattr(widget, 'devicePixelRatioF', None)
    dpr = dprGetter() if dprGetter is not None else widget._effectiveDpr()
    return max(1.0, round(dpr, 3))


def createWidgetPixmap(widget) -> QPixmap:
    devicePixelRatio = effectiveDevicePixelRatio(widget)
    pixmap = QPixmap(
        max(1, round(widget.width() * devicePixelRatio)),
        max(1, round(widget.height() * devicePixelRatio))
    )
    pixmap.setDevicePixelRatio(devicePixelRatio)
    return pixmap


def buildParticleProfileKey(
    widget,
    profile: ParticleProfile,
    color: QColor
) -> Tuple:
    return (
        profile.name,
        effectiveDevicePixelRatio(widget),
        round(widget.particleDensity, 3),
        round(widget.particleSpeed, 3),
        color.rgba()
    )


def deactivateParticleWidget(widget):
    clock = existingParticleClock()
    if clock is not None:
        clock.deactivate(widget)


def synchronizeParticleAnimation(widget, enabled: bool = True):
    shouldAnimate = (
        enabled and widget.isVisible() and widget.spoilerEnabled and
        widget.revealProgress < 0.999 and widget.particleDensity > 0
    )
    if shouldAnimate:
        particleClock().activate(widget)
    else:
        deactivateParticleWidget(widget)


def startRevealAnimation(widget, revealed: bool, duration: int, easing):
    targetProgress = 1.0 if revealed else 0.0
    progressDistance = abs(targetProgress - widget.revealProgress)
    widget.revealAnimation.stop()
    widget._animationTargetRevealed = revealed
    if progressDistance <= 0.0001 or duration <= 0:
        widget._setRevealProgress(targetProgress)
        widget._onAnimationFinished()
        return

    widget.revealAnimation.setDuration(max(1, round(duration * progressDistance)))
    widget.revealAnimation.setEasingCurve(easing)
    widget.revealAnimation.setStartValue(widget.revealProgress)
    widget.revealAnimation.setEndValue(targetProgress)
    widget.revealAnimation.start()
    widget._syncParticleAnimation()


def scheduleAutoHide(widget):
    widget.autoHideTimer.stop()
    if widget.revealed and widget.autoHideDelay >= 0:
        widget.autoHideTimer.start(widget.autoHideDelay)


def setRevealedState(widget, revealed: bool):
    if revealed != widget._revealed:
        widget._revealed = revealed
        widget.revealedChanged.emit(revealed)


def boundedPoint(position: QPointF, bounds: QRectF) -> QPointF:
    return QPointF(
        max(bounds.left(), min(bounds.right(), position.x())),
        max(bounds.top(), min(bounds.bottom(), position.y()))
    )


def farthestCornerDistance(position: QPointF, rects: Iterable[QRectF]) -> float:
    maximumDistance = 0.0
    for rect in rects:
        for corner in (
            rect.topLeft(), rect.topRight(),
            rect.bottomLeft(), rect.bottomRight()
        ):
            maximumDistance = max(
                maximumDistance,
                math.hypot(
                    position.x() - corner.x(),
                    position.y() - corner.y()
                )
            )

    return maximumDistance


def createRevealGradient(
    center: QPointF,
    maximumDistance: float,
    progress: float,
    softness: float
):
    radius = maximumDistance * progress
    blurRadius = (
        maximumDistance / 3.5 * progress
        if softness < 0
        else softness * progress
    )
    outerRadius = max(0.01, radius + blurRadius)
    fullOpacityStop = min(1.0, radius / outerRadius)

    gradient = QRadialGradient(center, outerRadius)
    gradient.setColorAt(0.0, QColor(255, 255, 255, 255))
    gradient.setColorAt(fullOpacityStop, QColor(255, 255, 255, 255))
    gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
    return gradient


def eraseRevealCircle(
    painter: QPainter,
    center: QPointF,
    maximumDistance: float,
    progress: float,
    softness: float
):
    gradient = createRevealGradient(
        center,
        maximumDistance,
        progress,
        softness
    )
    painter.save()
    painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawEllipse(center, gradient.radius(), gradient.radius())
    painter.restore()


def drawParticleTexture(
    painter: QPainter,
    texture: QPixmap,
    targetRect: QRectF,
    clipPath: QPainterPath,
    revealCenter: QPointF,
    revealProgress: float,
    pushFactor: float
):
    if texture.isNull():
        return

    pushProgress = revealProgress ** 2 * pushFactor
    textureScale = max(1.0 - pushFactor, 1.0 - pushProgress)
    transform = QTransform()
    transform.translate(revealCenter.x(), revealCenter.y())
    transform.scale(1.0 / textureScale, 1.0 / textureScale)
    transform.translate(-revealCenter.x(), -revealCenter.y())

    painter.save()
    painter.setClipPath(clipPath)
    painter.setTransform(transform)
    inverseBounds = transform.inverted()[0].mapRect(targetRect)
    painter.drawTiledPixmap(inverseBounds, texture, QPointF(0, 0))
    painter.restore()
