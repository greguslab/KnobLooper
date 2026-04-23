import time

from PySide6.QtCore import Qt, QRectF, Signal, QEvent
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QGroupBox,
    QLineEdit,
    QSizePolicy,
)

from loop_engine import LoopEngine


def safe_font_size(value, fallback=8):
    try:
        ivalue = int(value)
    except Exception:
        ivalue = fallback
    return max(1, ivalue, fallback)


class DonutWidget(QWidget):
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self._side = 144
        self.setMinimumSize(104, 104)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.mode = "idle"
        self.progress = 0.0
        self.duration = 0.0
        self.loop_active = False

    def set_side(self, side: int):
        side = max(96, min(210, int(side)))
        self._side = side
        self.setMinimumSize(side, side)
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        return self.minimumSize()

    def set_state(self, mode, progress, duration, loop_active=False, force=False):
        mode = mode or "idle"
        progress = max(0.0, min(1.0, progress if progress is not None else 0.0))
        duration = duration if duration is not None else 0.0
        loop_active = bool(loop_active)
        if not force:
            progress_epsilon = 0.002 if mode in ("playing", "paused") else 0.01
            duration_epsilon = 0.02 if mode in ("playing", "paused") else 0.05
            if (
                mode == self.mode
                and abs(progress - self.progress) < progress_epsilon
                and abs(duration - self.duration) < duration_epsilon
                and loop_active == self.loop_active
            ):
                return
        self.mode = mode
        self.progress = progress
        self.duration = duration
        self.loop_active = loop_active
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer_side = min(self.width(), self.height())
        thickness = max(8, int((outer_side - 20) * 0.10))
        pad = thickness / 2 + 6

        rect = QRectF(
            pad,
            pad,
            max(10.0, self.width() - 2 * pad),
            max(10.0, self.height() - 2 * pad),
        )
        start = 90 * 16

        bg_pen = QPen(QColor("#2a2a2a"), thickness)
        bg_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        if self.mode == "recording":
            pen = QPen(QColor("#ff4b4b"), thickness)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, start, -int(self.progress * 360 * 16))
        elif self.mode == "playing":
            pen = QPen(QColor("#66ffb3"), thickness)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, start - int(self.progress * 360 * 16), -int(28 * 16))
        elif self.mode == "paused":
            pen = QPen(QColor("#1f7f57"), thickness)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, start - int(self.progress * 360 * 16), -int(28 * 16))

        inner_side = max(1.0, min(rect.width(), rect.height()))

        painter.setPen(QColor("white"))
        state_font = QFont("Arial", safe_font_size(inner_side * 0.09, 8), QFont.Bold)
        painter.setFont(state_font)
        state_text = {"idle": "IDLE", "recording": "REC", "playing": "PLAY", "paused": "PAUSE"}.get(self.mode, "IDLE")
        painter.drawText(self.rect().adjusted(0, -int(inner_side * 0.08), 0, 0), Qt.AlignCenter, state_text)

        painter.setFont(QFont("Arial", safe_font_size(inner_side * 0.07, 7)))
        painter.drawText(self.rect().adjusted(0, int(inner_side * 0.10), 0, 0), Qt.AlignCenter, f"{self.duration:.2f}s")


class LoopChannelWidget(QGroupBox):
    def __init__(self, channel_index: int, osc_address: str, midi_engine, main_window):
        self.channel_index = channel_index
        self.osc_name = ""
        super().__init__(f"CH {channel_index}")
        self.osc_address = osc_address
        self.midi = midi_engine
        self.main_window = main_window
        self.loop = LoopEngine()
        self.learn_mode = False
        self.learned_cc = None
        self.learned_channel = None
        self.is_active = False
        self.base_bg = "#151515"
        self.last_live_value = "-"
        self.last_live_cc = "-"
        self.last_live_channel = "-"
        self.last_sent_value = None
        self._building = True
        self._last_midi_focus_ts = 0.0

        self.build_ui()
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.refresh_card_style()
        self.update_title()
        self.update_button_states()
        self.update_monitor_labels()
        self.update_donut(force=True)
        self._building = False
        self.update_compact_layout()

    def build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        top_row.addWidget(QLabel("NAME"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Module name")
        self.name_edit.setClearButtonEnabled(True)
        top_row.addWidget(self.name_edit, 1)

        body = QHBoxLayout()
        body.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        self.top_info = QLabel(f"OSC → {self.osc_address}")
        self.learn_btn = QPushButton("LEARN")
        self.rec_btn = QPushButton("REC")
        self.clear_btn = QPushButton("CLEAR")
        self.learn_btn.setCheckable(True)
        self.rec_btn.setCheckable(True)
        self.speed_label = QLabel("x1.00")
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(25)
        self.speed_slider.setMaximum(400)
        self.speed_slider.setValue(100)
        speed_row = QHBoxLayout()
        speed_row.setSpacing(6)
        speed_row.addWidget(QLabel("SPD"))
        speed_row.addWidget(self.speed_slider, 1)
        speed_row.addWidget(self.speed_label)
        left_col.addWidget(self.top_info)
        left_col.addWidget(self.learn_btn)
        left_col.addWidget(self.rec_btn)
        left_col.addWidget(self.clear_btn)
        left_col.addLayout(speed_row)
        left_col.addStretch(1)

        center_col = QVBoxLayout()
        center_col.setContentsMargins(10, 0, 10, 0)
        center_col.setSpacing(2)
        self.donut = DonutWidget()
        center_col.addWidget(self.donut, 1, Qt.AlignCenter)

        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        self.learned_label = QLabel("Learned: CC -, CH -")
        self.live_label = QLabel("Live: value -, CC -, CH -")
        self.loop_label = QLabel("Loop: idle")
        self.value_label = QLabel("Value: -")
        right_col.addWidget(self.learned_label)
        right_col.addWidget(self.live_label)
        right_col.addWidget(self.loop_label)
        right_col.addWidget(self.value_label)
        right_col.addStretch(1)

        body.addLayout(left_col, 3)
        body.addLayout(center_col, 6)
        body.addLayout(right_col, 3)

        root.addLayout(top_row)
        root.addLayout(body)
        self.setLayout(root)

        self.learn_btn.clicked.connect(self.request_learn_toggle)
        self.rec_btn.clicked.connect(self.toggle_record)
        self.clear_btn.clicked.connect(self.clear_loop)
        self.speed_slider.valueChanged.connect(self.change_speed)
        self.donut.clicked.connect(self.on_donut_clicked)
        self.name_edit.textChanged.connect(self.on_name_changed)

        for widget in [self, self.name_edit, self.learn_btn, self.rec_btn, self.clear_btn, self.speed_slider, self.donut]:
            widget.installEventFilter(self)

        self.change_speed(notify=False)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.FocusIn, QEvent.MouseButtonPress):
            self.mark_active()
        return super().eventFilter(watched, event)

    def update_compact_layout(self):
        parent = self.parentWidget()
        available_w = self.width() or (parent.width() if parent else 540)
        available_h = self.height() or (parent.height() if parent else 320)
        side = 170
        if available_h < 300 or available_w < 500:
            side = 116
        elif available_h < 340 or available_w < 560:
            side = 132
        elif available_h < 390 or available_w < 640:
            side = 148
        elif available_w > 760 and available_h > 420:
            side = 182
        self.donut.set_side(side)

    def default_title(self):
        return f"CH {self.channel_index}"

    def update_title(self):
        self.setTitle(f"CH {self.channel_index} — {self.osc_name}" if self.osc_name else self.default_title())

    def refresh_card_style(self):
        border_color = "#4e8fff" if self.is_active else "#333333"
        border_width = "2px" if self.is_active else "1px"
        self.setStyleSheet(f"""
            QGroupBox {{
                border: {border_width} solid {border_color};
                border-radius: 10px;
                margin-top: 8px;
                padding-top: 12px;
                background-color: {self.base_bg};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px 0 4px;
                color: #dddddd;
                font-weight: bold;
            }}
            QLabel {{
                color: #dddddd;
            }}
            QPushButton, QLineEdit {{
                background-color: #1c1c1c;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 5px 7px;
                color: #dddddd;
            }}
            QPushButton:hover {{ background-color: #262626; }}
            QPushButton:checked {{ background-color: #2a2a2a; }}
            QSlider::groove:horizontal {{
                height: 6px; background: #2a2a2a; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 14px; margin: -5px 0; border-radius: 7px; background: #aaaaaa;
            }}
        """)
        self.update_button_states()

    def set_active(self, active: bool):
        active = bool(active)
        if self.is_active == active:
            return
        self.is_active = active
        self.refresh_card_style()

    def mark_active(self, autosave=True):
        if not self._building and hasattr(self.main_window, "set_active_channel"):
            self.main_window.set_active_channel(self, autosave=autosave)

    def mark_active_from_midi(self):
        if self._building:
            return
        if hasattr(self.main_window, "is_channel_visible") and not self.main_window.is_channel_visible(self):
            return
        now = time.perf_counter()
        if self.main_window.active_channel is self and (now - self._last_midi_focus_ts) < 0.12:
            return
        self._last_midi_focus_ts = now
        self.mark_active(autosave=False)

    def notify_preset_change(self):
        if not self._building and hasattr(self.main_window, "schedule_preset_autosave"):
            self.main_window.schedule_preset_autosave()

    def on_name_changed(self, text):
        self.osc_name = text.strip()
        self.update_title()
        self.mark_active()
        self.notify_preset_change()

    def prefix(self, text):
        return f"[CH{self.channel_index:02d}] {text}"

    def log(self, text):
        self.main_window.log(self.prefix(text))

    def has_loop(self):
        return bool(self.loop.events) and self.loop.loop_duration > 0

    def refresh_ui(self):
        self.update_compact_layout()
        self.update_button_states()
        self.update_monitor_labels()
        self.update_donut(force=True)

    def set_learn_active(self, active: bool):
        self.learn_mode = bool(active)
        if active:
            self.mark_active()
        self.update_button_states()

    def request_learn_toggle(self):
        self.mark_active()
        if self.learn_mode:
            self.learn_mode = False
            self.log("LEARN disabled.")
            self.update_button_states()
            self.notify_preset_change()
            return
        self.main_window.activate_learn_for(self)
        self.log("LEARN active: move a knob.")
        self.notify_preset_change()

    def update_button_states(self):
        self.learn_btn.blockSignals(True)
        self.rec_btn.blockSignals(True)
        self.learn_btn.setChecked(self.learn_mode)
        self.rec_btn.setChecked(self.loop.recording)
        self.learn_btn.blockSignals(False)
        self.rec_btn.blockSignals(False)
        self.learn_btn.setStyleSheet("border: 2px solid #66aaff;" if self.learn_mode else "")
        self.rec_btn.setStyleSheet("border: 2px solid #ff4b4b;" if self.loop.recording else "")

    def update_monitor_labels(self):
        learned_cc = self.learned_cc if self.learned_cc is not None else "-"
        learned_ch = self.learned_channel + 1 if self.learned_channel is not None else "-"
        self.learned_label.setText(f"Learned: CC {learned_cc}, CH {learned_ch}")
        self.live_label.setText(f"Live: value {self.last_live_value}, CC {self.last_live_cc}, CH {self.last_live_channel}")
        self.value_label.setText(f"Value: {self.last_live_value}")

    def update_donut(self, force=False):
        has_loop = self.has_loop()
        if self.loop.recording:
            t = time.perf_counter() - self.loop.record_start_time if self.loop.record_start_time else 0.0
            prog = (t % 5.0) / 5.0
            self.donut.set_state("recording", prog, t, loop_active=has_loop, force=force)
        elif self.loop.playing:
            self.donut.set_state("playing", self.loop.get_progress(), self.loop.loop_duration, loop_active=has_loop, force=force)
        elif self.loop.paused:
            self.donut.set_state("paused", self.loop.get_progress(), self.loop.loop_duration, loop_active=has_loop, force=force)
        else:
            self.donut.set_state("idle", 0.0, self.loop.loop_duration, loop_active=has_loop, force=force)

    def toggle_record(self):
        self.mark_active()
        if self.loop.recording:
            self.loop.stop_recording()
            ok = self.loop.start_playback()
            if ok:
                self.loop_label.setText(f"Loop: playing ({self.loop.loop_duration:.2f}s)")
                self.log(f"AUTO LOOP ({self.loop.loop_duration:.2f}s)")
            else:
                self.loop_label.setText("Loop: empty")
                self.log("Empty loop.")
            self.update_button_states()
            self.update_donut(force=True)
            self.notify_preset_change()
            return
        if self.learned_cc is None or self.learned_channel is None:
            self.log("No learned CC yet. Use LEARN first.")
            self.update_button_states()
            return
        self.loop.start_recording()
        self.last_sent_value = None
        self.loop_label.setText("Loop: recording")
        self.log("REC start")
        self.update_button_states()
        self.update_donut(force=True)

    def clear_loop(self):
        self.mark_active()
        self.loop.clear()
        self.last_sent_value = None
        self.loop_label.setText("Loop: cleared")
        self.log("CLEAR")
        self.update_button_states()
        self.update_donut(force=True)
        self.notify_preset_change()

    def on_donut_clicked(self):
        self.mark_active()
        self.toggle_loop_from_donut()

    def toggle_loop_from_donut(self):
        if self.loop.recording:
            self.log("Unavailable while recording.")
            return
        if not self.has_loop():
            self.log("No loop to start.")
            return
        if self.loop.playing:
            if self.loop.pause_playback():
                self.loop_label.setText("Loop: paused")
                self.log("Loop paused.")
            self.update_donut(force=True)
            self.notify_preset_change()
            return
        if self.loop.paused:
            if self.loop.resume_playback():
                self.loop_label.setText("Loop: playing")
                self.log("Loop resumed.")
            self.update_donut(force=True)
            self.notify_preset_change()
            return
        ok = self.loop.start_playback()
        if ok:
            self.last_sent_value = None
            self.loop_label.setText("Loop: playing")
            self.log("Loop started.")
        else:
            self.log("Could not start the loop.")
        self.update_donut(force=True)
        self.notify_preset_change()

    def change_speed(self, notify: bool = True):
        speed = self.speed_slider.value() / 100.0
        self.loop.set_speed(speed)
        self.speed_label.setText(f"x{speed:.2f}")
        if notify and not self._building:
            self.mark_active()
            self.notify_preset_change()

    def matches_message(self, msg):
        return (
            msg.type == "control_change"
            and self.learned_cc is not None
            and self.learned_channel is not None
            and msg.control == self.learned_cc
            and msg.channel == self.learned_channel
        )

    def export_state(self):
        return {
            "channel_index": self.channel_index,
            "osc_name": self.osc_name,
            "osc_address": self.osc_address,
            "learned_cc": self.learned_cc,
            "learned_channel": self.learned_channel,
            "speed_slider": self.speed_slider.value(),
            "loop": self.loop.export_state(),
        }

    def apply_state(self, data):
        if not isinstance(data, dict):
            return
        self.learn_mode = False
        self.learned_cc = data.get("learned_cc")
        self.learned_channel = data.get("learned_channel")
        name = str(data.get("osc_name", "") or "")
        self.name_edit.blockSignals(True)
        self.name_edit.setText(name)
        self.name_edit.blockSignals(False)
        self.osc_name = name.strip()
        self.update_title()
        speed_value = data.get("speed_slider", 100)
        try:
            speed_value = int(speed_value)
        except (TypeError, ValueError):
            speed_value = 100
        speed_value = max(self.speed_slider.minimum(), min(self.speed_slider.maximum(), speed_value))
        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(speed_value)
        self.speed_slider.blockSignals(False)
        self.change_speed(notify=False)
        self.loop.import_state(data.get("loop", {}))
        self.last_sent_value = None
        self.loop_label.setText(f"Loop: loaded ({self.loop.loop_duration:.2f}s)" if self.has_loop() else "Loop: idle")
        self.update_button_states()
        self.update_monitor_labels()
        self.update_donut(force=True)

    def handle_midi_message(self, msg):
        if msg.type != "control_change":
            return
        if self.learn_mode:
            self.learned_cc = msg.control
            self.learned_channel = msg.channel
            self.learn_mode = False
            self.log(f"Learned knob: CC {msg.control}, CH {msg.channel + 1}")
            self.update_button_states()
            self.update_monitor_labels()
            self.mark_active()
            self.notify_preset_change()
            return
        if self.matches_message(msg):
            self.last_live_value = msg.value
            self.last_live_cc = msg.control
            self.last_live_channel = msg.channel + 1
            self.update_monitor_labels()
            self.mark_active_from_midi()
            if not self.loop.playing:
                self.midi.send_osc_value(self.osc_address, msg.value)
            if self.loop.recording:
                self.loop.record_value(msg.value)
                if self.loop.events:
                    self.loop_label.setText(f"Loop: recording {self.loop.events[-1][0]:.2f}s")

    def tick(self, update_ui=True):
        if self.loop.playing:
            value = self.loop.get_playback_value()
            if value is not None and value != self.last_sent_value:
                self.midi.send_osc_value(self.osc_address, value)
                self.last_sent_value = value
        if update_ui:
            self.update_donut()
