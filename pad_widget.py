from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
)


class PadWidget(QGroupBox):
    def __init__(self, pad_index: int, midi_engine, main_window):
        super().__init__(f"PAD {pad_index}")
        self.pad_index = pad_index
        self.midi = midi_engine
        self.main_window = main_window
        self.is_active = False
        self.learn_mode = False
        self.pad_name = ""
        self.midi_type = None
        self.midi_channel = None
        self.midi_note = None
        self.midi_cc = None
        self.toggle_state = False
        self.is_lit = False
        self._building = True
        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.timeout.connect(self._end_flash)
        self.build_ui()
        self.refresh_style()
        self._building = False

    def build_ui(self):
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 12, 8, 8)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Label")
        self.osc_edit = QLineEdit(f"/pad/{self.pad_index}")
        self.learn_btn = QPushButton("LEARN")
        self.learn_btn.setCheckable(True)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Trigger", "Momentary", "Toggle", "Velocity"])
        self.midi_label = QLabel("MIDI: -")
        self.test_btn = QPushButton("TEST")

        grid.addWidget(QLabel("NAME"), 0, 0)
        grid.addWidget(self.name_edit, 0, 1)
        grid.addWidget(self.learn_btn, 1, 0)
        grid.addWidget(self.mode_combo, 1, 1)
        grid.addWidget(QLabel("OSC"), 2, 0)
        grid.addWidget(self.osc_edit, 2, 1)
        grid.addWidget(self.midi_label, 3, 0)
        grid.addWidget(self.test_btn, 3, 1)

        self.name_edit.textChanged.connect(self.on_name_changed)
        self.learn_btn.clicked.connect(self.request_learn_toggle)
        self.mode_combo.currentIndexChanged.connect(self.on_config_changed)
        self.osc_edit.textChanged.connect(self.on_config_changed)
        self.test_btn.clicked.connect(self.trigger_from_ui)

        for widget in [self, self.name_edit, self.osc_edit, self.learn_btn, self.mode_combo, self.test_btn]:
            widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.FocusIn, QEvent.MouseButtonPress):
            self.mark_active()
        return super().eventFilter(watched, event)

    def refresh_style(self):
        border_color = "#4e8fff" if self.is_active else "#333333"
        border_width = "2px" if self.is_active else "1px"
        bg_color = "#18301d" if self.is_lit else "#151515"
        title_color = "#dcffe2" if self.is_lit else "#dddddd"
        control_bg = "#23452a" if self.is_lit else "#1c1c1c"
        control_border = "#4fb46a" if self.is_lit else "#333333"
        self.setStyleSheet(f"""
            QGroupBox {{
                border: {border_width} solid {border_color};
                border-radius: 10px;
                margin-top: 8px;
                padding-top: 12px;
                background-color: {bg_color};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px 0 4px;
                color: {title_color};
                font-weight: bold;
            }}
            QLabel {{ color: {title_color}; }}
            QPushButton, QLineEdit, QComboBox {{
                background-color: {control_bg};
                border: 1px solid {control_border};
                border-radius: 6px;
                padding: 5px 7px;
                color: #f0f0f0;
            }}
            QPushButton:hover {{ background-color: #2a5a34; }}
        """)
        if self.learn_mode:
            self.learn_btn.setStyleSheet("border: 2px solid #66aaff; background-color: #203247;")
        elif self.is_lit:
            self.learn_btn.setStyleSheet("background-color: #2f6a3d; border: 1px solid #6fd18c;")
        else:
            self.learn_btn.setStyleSheet("")

    def set_active(self, active: bool):
        active = bool(active)
        if self.is_active == active:
            return
        self.is_active = active
        self.refresh_style()

    def mark_active(self):
        if not self._building:
            self.main_window.set_active_pad(self)

    def notify_preset_change(self):
        if not self._building:
            self.main_window.schedule_preset_autosave()

    def set_lit(self, lit: bool, flash_ms: int | None = None):
        lit = bool(lit)
        if lit:
            self.flash_timer.stop()
            changed = (not self.is_lit)
            self.is_lit = True
            if changed:
                self.refresh_style()
            if flash_ms:
                self.flash_timer.start(int(flash_ms))
        else:
            self.flash_timer.stop()
            if self.is_lit:
                self.is_lit = False
                self.refresh_style()

    def _end_flash(self):
        if self.mode_combo.currentText() != "Toggle":
            self.set_lit(False)


    def on_name_changed(self, text):
        self.pad_name = text.strip()
        self.setTitle(f"PAD {self.pad_index} — {self.pad_name}" if self.pad_name else f"PAD {self.pad_index}")
        self.mark_active()
        self.notify_preset_change()

    def on_config_changed(self, *args):
        self.mark_active()
        self.notify_preset_change()

    def request_learn_toggle(self):
        self.mark_active()
        if self.learn_mode:
            self.learn_mode = False
            self.refresh_style()
            self.notify_preset_change()
            return
        self.main_window.activate_pad_learn_for(self)
        self.refresh_style()
        self.notify_preset_change()

    def set_learn_active(self, active: bool):
        self.learn_mode = bool(active)
        self.refresh_style()

    def update_midi_label(self):
        if self.midi_type == "note":
            text = f"MIDI: NOTE {self.midi_note} CH {self.midi_channel + 1}"
        elif self.midi_type == "cc":
            text = f"MIDI: CC {self.midi_cc} CH {self.midi_channel + 1}"
        else:
            text = "MIDI: -"
        self.midi_label.setText(text)

    def current_address(self):
        return self.osc_edit.text().strip() or f"/pad/{self.pad_index}"

    def fire_pad(self, velocity: int = 127, pressed: bool = True):
        address = self.current_address()
        mode = self.mode_combo.currentText()
        if mode == "Trigger":
            if pressed:
                self.set_lit(True, flash_ms=150)
                self.midi.send_osc_message(address, 1)
        elif mode == "Momentary":
            self.set_lit(pressed)
            self.midi.send_osc_message(address, 1 if pressed else 0)
        elif mode == "Toggle":
            if pressed:
                self.toggle_state = not self.toggle_state
                self.set_lit(self.toggle_state)
                self.midi.send_osc_message(address, 1 if self.toggle_state else 0)
        elif mode == "Velocity":
            if pressed:
                self.set_lit(True, flash_ms=150)
                self.midi.send_osc_message(address, max(0.0, min(1.0, velocity / 127.0)))
        self.main_window.log(f"[PAD{self.pad_index:02d}] OSC {address}")

    def trigger_from_ui(self):
        self.mark_active()
        self.fire_pad(127, True)
        if self.mode_combo.currentText() == "Momentary":
            self.fire_pad(0, False)

    def export_state(self):
        return {
            "pad_index": self.pad_index,
            "pad_name": self.pad_name,
            "osc_address": self.current_address(),
            "mode": self.mode_combo.currentText(),
            "midi_type": self.midi_type,
            "midi_channel": self.midi_channel,
            "midi_note": self.midi_note,
            "midi_cc": self.midi_cc,
            "toggle_state": self.toggle_state,
        }

    def apply_state(self, data):
        if not isinstance(data, dict):
            return
        name = str(data.get("pad_name", "") or "")
        self.name_edit.blockSignals(True)
        self.name_edit.setText(name)
        self.name_edit.blockSignals(False)
        self.pad_name = name.strip()
        self.setTitle(f"PAD {self.pad_index} — {self.pad_name}" if self.pad_name else f"PAD {self.pad_index}")
        addr = str(data.get("osc_address", self.current_address()) or self.current_address())
        self.osc_edit.blockSignals(True)
        self.osc_edit.setText(addr)
        self.osc_edit.blockSignals(False)
        mode = str(data.get("mode", "Trigger") or "Trigger")
        idx = self.mode_combo.findText(mode)
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(max(0, idx))
        self.mode_combo.blockSignals(False)
        self.midi_type = data.get("midi_type")
        self.midi_channel = data.get("midi_channel")
        self.midi_note = data.get("midi_note")
        self.midi_cc = data.get("midi_cc")
        self.toggle_state = bool(data.get("toggle_state", False))
        self.learn_mode = False
        self.is_lit = self.toggle_state if self.mode_combo.currentText() == "Toggle" else False
        self.update_midi_label()
        self.refresh_style()

    def handle_midi_message(self, msg):
        if self.learn_mode:
            if msg.type == "control_change":
                self.midi_type = "cc"
                self.midi_channel = msg.channel
                self.midi_cc = msg.control
                self.midi_note = None
            elif msg.type in ("note_on", "note_off"):
                self.midi_type = "note"
                self.midi_channel = msg.channel
                self.midi_note = msg.note
                self.midi_cc = None
            else:
                return
            self.learn_mode = False
            self.update_midi_label()
            self.refresh_style()
            self.mark_active()
            self.notify_preset_change()
            return

        if self.midi_type == "cc" and msg.type == "control_change":
            if msg.channel == self.midi_channel and msg.control == self.midi_cc:
                self.fire_pad(msg.value, msg.value > 0)
        elif self.midi_type == "note" and msg.type in ("note_on", "note_off"):
            if msg.channel == self.midi_channel and msg.note == self.midi_note:
                pressed = msg.type == "note_on" and getattr(msg, "velocity", 0) > 0
                velocity = getattr(msg, "velocity", 127)
                self.fire_pad(velocity, pressed)
