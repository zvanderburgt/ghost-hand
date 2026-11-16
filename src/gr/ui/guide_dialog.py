"""The 'how it works' guide, shown on first launch."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ..config import APP_NAME, GESTURES, Settings
from . import theme

TITLE = f"How {APP_NAME} works"


def _pages(settings: Settings) -> list[tuple[str, str]]:
    arm_id = str(settings.get("engine.arm_pose", "rock"))
    arm_pose = settings.gesture_label(arm_id)

    # Only list gestures that are actually bound, so the guide never shows rows
    # that do nothing.
    rows: list[str] = []
    for gesture_id, meta in GESTURES.items():
        if gesture_id == arm_id:
            continue
        action = settings.binding_for(gesture_id)
        if not action:
            continue
        target = settings.binding_target(gesture_id)
        rows.append(
            f"<tr><td style='padding:3px 14px 3px 0;color:{theme.ACCENT};'>"
            f"{meta['name']}</td>"
            f"<td style='padding:3px 0;color:{theme.TEXT_MUTED};'>"
            f"{settings.action_label(action, target)}</td></tr>"
        )
        if len(rows) >= 7:
            break
    gesture_rows = "".join(rows) or (
        f"<tr><td style='padding:3px 0;color:{theme.TEXT_MUTED};'>"
        f"nothing bound yet — open Bindings</td></tr>"
    )

    return [
        ("What it does", f"""
            <p><b>{APP_NAME}</b> watches your hand through the RealSense camera and turns
            hand shapes and motions into Windows actions.</p>
            <p>Every frame the camera image goes through a 21-point hand model. Those
            landmarks are measured against a library of poses — finger extension, thumb
            direction, palm motion — and whatever wins is turned into the action you
            assigned to it.</p>
            <p>The depth sensor is used to ignore hands that are too close or too far away
            (by default 0.20–2.00 m), so background movement and arms resting on the desk
            do not trigger anything.</p>
            <p style="color:{theme.TEXT_DIM};">Everything runs on this machine. No frames
            leave it.</p>
        """),
        ("Arming", f"""
            <p>Gestures are ignored until you <b>arm</b> the app, so ordinary hand
            movements can't fire shortcuts.</p>
            <p>Hold <b>{arm_pose}</b> towards the camera for about half a second. The
            status pill turns blue and the camera frame gets a blue border.</p>
            <p>It disarms itself after six seconds without a hand, and you can toggle it
            at any time from the tray menu.</p>
            <p style="color:{theme.TEXT_DIM};">The arming pose is a preference: any gesture
            in the library can be used instead, and it is never fired as an action.</p>
        """),
        ("Your gestures", f"""
            <p>Defaults, all remappable in <b>Bindings</b>:</p>
            <table style="border-collapse:collapse;">{gesture_rows}</table>
            <p style="margin-top:16px;"><b>Volume is the dial, not a button.</b> Pinch your
            thumb and index together like grabbing a small knob, then rotate your wrist —
            clockwise is louder, counter-clockwise quieter. It is continuous, so you can
            nudge it by a percent or sweep it across the whole range. Coarseness is
            adjustable in Bindings.</p>
            <p>By default the dial changes system volume. Under <b>Bindings → Volume
            dial</b> you can point it at one app instead — Spotify, for example — and
            it changes only that app's Windows volume while other audio stays put.
            <b>Mixer…</b> in that card shows every app's slider and a one-click
            <b>Use for dial</b> button.</p>
            <p>Thumbs up and thumbs down are left unbound on purpose. Give them whatever you
            like — or map one back to Volume Up/Down and it will ramp while you hold it.</p>
            <p>Other motion gestures: swipes with an open palm, two-hand chords, and your own
            shapes under <b>Bindings → Custom…</b>.</p>
        """),
        ("Practice vs live", f"""
            <p>The <b>Practice</b> switch is on by default. In practice mode the app logs
            what it <i>would</i> do and sends nothing to Windows — the event log line
            reads "Practice: would run «Play / Pause»".</p>
            <p>Turn it off when you are happy with detection. The footer tells you which
            mode you are in, and the tray menu can flip it too.</p>
            <p>Starting with <b>--demo</b> runs the same interface against a synthetic hand,
            handy for exploring without a camera. Demo mode never sends input.</p>
        """),
        ("Make it yours", f"""
            <p><b>Bindings</b> — pick a gesture, choose any action: media keys, copy/paste,
            show desktop, Alt+Tab, task manager, launch an app.</p>
            <p><b>Profiles…</b> — a binding set that applies while a chosen app is focused,
            e.g. override swipes to skip tracks when Spotify is in front.</p>
            <p><b>Macros…</b> — record keystrokes and clicks, then bind the recording to a
            gesture.</p>
            <p><b>Sounds…</b> — a soundboard. With mic routing on, sounds play into the
            virtual cable so call apps hear them.</p>
            <p><b>Custom…</b> — record a hand shape you invented and use it like any other
            gesture.</p>
            <p><b>Check</b> — scans for conflicts, such as one gesture bound to two
            actions or a binding pointing at a deleted macro.</p>
        """),
        ("Cursor", f"""
            <p>Turn on <b>Cursor</b> in the header and hold your index finger up; the
            Windows pointer follows it. Pinch thumb to index to click, and hold the pinch
            to drag.</p>
            <p><b>Calibrate</b> walks you through pointing at the four corners of your
            comfortable reach, then sets the depth window. Smoothing adapts to speed, so
            the pointer is steady when you hold still and responsive when you move.</p>
        """),
        ("Tray and startup", f"""
            <p>Closing the window hides it to the tray; the app keeps listening.</p>
            <p>The tray menu has: open the window, arm/disarm, practice mode, save a debug
            clip, reconnect the camera, start with Windows, and quit.</p>
            <p>Settings live in <b>config\\settings.json</b> next to the app — every
            threshold in this guide can be edited there. Debug clips land in
            <b>debug\\</b>.</p>
        """),
    ]


class GuideDialog(QDialog):
    changed = Signal()

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._pages = _pages(settings)
        self._index = 0

        self.setWindowTitle(TITLE)
        self.setModal(True)
        self.resize(880, 620)
        self._build()
        self._render()

    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        title = QLabel(TITLE)
        title.setProperty("role", "h1")
        root.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(16)

        self.steps = QListWidget()
        self.steps.setFixedWidth(230)
        self.steps.currentRowChanged.connect(self._select)
        body.addWidget(self.steps)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.RichText)
        self.text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.text.setStyleSheet(
            f"font-size: 13px; color: {theme.TEXT}; line-height: 150%;"
        )
        self.scroll.setWidget(self.text)
        body.addWidget(self.scroll, 1)

        root.addLayout(body, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)

        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self._back)
        self.next_btn = QPushButton("Next")
        self.next_btn.setProperty("variant", "accent")
        self.next_btn.clicked.connect(self._next)
        self.done_btn = QPushButton("Got it")
        self.done_btn.setProperty("variant", "accent")
        self.done_btn.clicked.connect(self._finish)
        bottom.addWidget(self.back_btn)
        bottom.addWidget(self.next_btn)
        bottom.addWidget(self.done_btn)
        root.addLayout(bottom)

    # ------------------------------------------------------------------ #

    def _render(self) -> None:
        self.steps.blockSignals(True)
        self.steps.clear()
        for index, (heading, _) in enumerate(self._pages, start=1):
            self.steps.addItem(f"{index}.  {heading}")
        self.steps.setCurrentRow(self._index)
        self.steps.blockSignals(False)

        heading, html = self._pages[self._index]
        last = self._index == len(self._pages) - 1
        self.back_btn.setEnabled(self._index > 0)
        self.next_btn.setVisible(not last)
        self.done_btn.setVisible(last)
        self.text.setText(html)

    def _select(self, row: int) -> None:
        if 0 <= row < len(self._pages) and row != self._index:
            self._index = row
            self._render()

    def _back(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._render()

    def _next(self) -> None:
        if self._index < len(self._pages) - 1:
            self._index += 1
            self._render()

    def _finish(self) -> None:
        try:
            self.settings.set("ui.guide_seen", True)
            self.settings.save()
        except OSError:
            pass
        self.changed.emit()
        self.accept()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        try:
            self.settings.set("ui.guide_seen", True)
            self.settings.save()
        except OSError:
            pass
        super().closeEvent(event)
