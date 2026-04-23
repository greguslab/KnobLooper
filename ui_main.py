import json
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from midi_engine import MidiEngine
from channel_widget import LoopChannelWidget
from pad_widget import PadWidget

NUM_CHANNELS = 16
NUM_PADS = 16
PAGE_SIZE = 4
NUM_PAGES = NUM_CHANNELS // PAGE_SIZE
PRESETS_DIRNAME = "presets"
DEFAULT_PRESET_NAME = "default.json"
TAB_LOOPS = 0
TAB_PADS = 1


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KnobLooper v16.5.4 - Loops + Pads")
        self.resize(1280, 900)
        self.setMinimumSize(940, 720)
        self.midi = MidiEngine()
        self.max_log_lines = 22
        self.channels = []
        self.pads = []
        self.current_page = 0
        self.active_channel = None
        self.active_pad = None
        self.is_loading_preset = False

        self.presets_dir = Path(__file__).resolve().with_name(PRESETS_DIRNAME)
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        self.current_preset_path = self.presets_dir / DEFAULT_PRESET_NAME

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self.autosave_preset)

        self.build_ui()
        self.refresh_ports()
        self.refresh_preset_list(select_name=self.current_preset_path.name)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_app)
        self.timer.start(40)

        if self.current_preset_path.exists():
            self.load_preset(self.current_preset_path, silent=True)
        else:
            if self.channels:
                self.set_active_channel(self.channels[0], autosave=False)
            if self.pads:
                self.set_active_pad(self.pads[0], autosave=False)
            self.save_preset(self.current_preset_path, silent=True)

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        midi_row = QHBoxLayout()
        self.in_combo = QComboBox()
        self.refresh_btn = QPushButton("Rescan")
        self.connect_btn = QPushButton("Connect MIDI")
        midi_row.addWidget(QLabel("MIDI IN"))
        midi_row.addWidget(self.in_combo, 1)
        midi_row.addWidget(self.refresh_btn)
        midi_row.addWidget(self.connect_btn)

        osc_row = QHBoxLayout()
        self.ip = QLineEdit("127.0.0.1")
        self.port = QLineEdit("8010")
        self.osc_btn = QPushButton("Connect OSC")
        osc_row.addWidget(QLabel("OSC IP"))
        osc_row.addWidget(self.ip)
        osc_row.addWidget(QLabel("PORT"))
        osc_row.addWidget(self.port)
        osc_row.addWidget(self.osc_btn)

        preset_row = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(220)
        self.preset_load_btn = QPushButton("Load")
        self.preset_save_btn = QPushButton("Save")
        self.preset_save_as_btn = QPushButton("Save As")
        self.preset_refresh_btn = QPushButton("↻")
        preset_row.addWidget(QLabel("Preset"))
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(self.preset_load_btn)
        preset_row.addWidget(self.preset_save_btn)
        preset_row.addWidget(self.preset_save_as_btn)
        preset_row.addWidget(self.preset_refresh_btn)

        self.status_label = QLabel("Status: idle")

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_loops_tab(), "LOOPS")
        self.tabs.addTab(self.build_pads_tab(), "PADS")

        self.global_log = QTextEdit()
        self.global_log.setReadOnly(True)
        self.global_log.setMinimumHeight(64)

        self.log_panel = QWidget()
        log_layout = QVBoxLayout(self.log_panel)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)
        log_layout.addWidget(QLabel("Global Log"))
        log_layout.addWidget(self.global_log, 1)

        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.addWidget(self.log_panel)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        root.addLayout(midi_row)
        root.addLayout(osc_row)
        root.addLayout(preset_row)
        root.addWidget(self.status_label)
        root.addWidget(self.main_splitter, 1)

        self.setStyleSheet("""
            QWidget { background-color: #111111; color: #dddddd; }
            QLabel { color: #dddddd; }
            QComboBox, QPushButton, QLineEdit, QTextEdit {
                background-color: #1c1c1c;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 4px 6px;
            }
            QPushButton:hover { background-color: #262626; }
            QTextEdit { font-family: Consolas, monospace; }
            QStackedWidget, QTabWidget::pane {
                border: 1px solid #222222;
                border-radius: 8px;
                background-color: #101010;
            }
            QTabBar::tab {
                background: #1a1a1a;
                color: #cccccc;
                border: 1px solid #2b2b2b;
                border-bottom: none;
                padding: 8px 14px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected { background: #222222; color: #ffffff; border-color: #4e8fff; }
        """)

        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.connect_btn.clicked.connect(self.connect_midi)
        self.osc_btn.clicked.connect(self.connect_osc)
        self.prev_btn.clicked.connect(self.go_prev_page)
        self.next_btn.clicked.connect(self.go_next_page)
        self.preset_refresh_btn.clicked.connect(lambda: self.refresh_preset_list(select_name=self.current_preset_path.name))
        self.preset_save_btn.clicked.connect(self.save_current_preset)
        self.preset_save_as_btn.clicked.connect(self.save_preset_as)
        self.preset_load_btn.clicked.connect(self.load_selected_preset)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.update_page_ui()
        QTimer.singleShot(0, self.apply_default_splitter_sizes)

    def build_loops_tab(self):
        tab = QWidget()
        root = QVBoxLayout(tab)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        nav_row = QHBoxLayout()
        self.prev_btn = QPushButton("← Prev 4")
        self.next_btn = QPushButton("Next 4 →")
        self.page_buttons = []
        self.page_label = QLabel()
        nav_row.addWidget(self.prev_btn)
        for page_index in range(NUM_PAGES):
            btn = QPushButton(f"{page_index * PAGE_SIZE + 1}-{(page_index + 1) * PAGE_SIZE}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, idx=page_index: self.set_page(idx))
            self.page_buttons.append(btn)
            nav_row.addWidget(btn)
        nav_row.addStretch()
        nav_row.addWidget(self.page_label)
        nav_row.addWidget(self.next_btn)

        self.pages = QStackedWidget()
        for page_index in range(NUM_PAGES):
            page = QWidget()
            grid = QGridLayout(page)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(8)
            grid.setRowStretch(0, 1)
            grid.setRowStretch(1, 1)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            for local_index in range(PAGE_SIZE):
                channel_index = page_index * PAGE_SIZE + local_index + 1
                widget = LoopChannelWidget(channel_index, f"/knoblooper/{channel_index}", self.midi, self)
                self.channels.append(widget)
                row = local_index // 2
                col = local_index % 2
                grid.addWidget(widget, row, col)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidget(page)
            self.pages.addWidget(scroll)
        root.addLayout(nav_row)
        root.addWidget(self.pages, 1)
        return tab

    def build_pads_tab(self):
        tab = QWidget()
        root = QVBoxLayout(tab)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        root.addWidget(QLabel("BeatStep pads → learn, custom label, mode, MadMapper OSC."))
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for pad_index in range(1, NUM_PADS + 1):
            widget = PadWidget(pad_index, self.midi, self)
            self.pads.append(widget)
            grid.addWidget(widget, (pad_index - 1) // 4, (pad_index - 1) % 4)
        root.addLayout(grid, 1)
        return tab

    def on_tab_changed(self, index: int):
        if index == TAB_LOOPS:
            self.update_page_ui()
        self.schedule_preset_autosave()

    def preset_path_from_name(self, name: str) -> Path:
        safe_name = (name or "").strip() or DEFAULT_PRESET_NAME
        if not safe_name.lower().endswith(".json"):
            safe_name += ".json"
        return self.presets_dir / safe_name

    def preset_names(self):
        names = sorted(path.name for path in self.presets_dir.glob("*.json"))
        if DEFAULT_PRESET_NAME not in names:
            names.insert(0, DEFAULT_PRESET_NAME)
        return names

    def apply_default_splitter_sizes(self):
        total = max(400, self.height() - 180)
        log_h = 120
        self.main_splitter.setSizes([max(260, total - log_h), log_h])

    def refresh_preset_list(self, select_name: str | None = None):
        current = select_name or self.current_preset_path.name
        names = self.preset_names()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItems(names)
        idx = self.preset_combo.findText(current)
        if idx < 0 and names:
            idx = 0
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        self.preset_combo.blockSignals(False)

    def selected_preset_path(self) -> Path:
        return self.preset_path_from_name(self.preset_combo.currentText().strip())

    def visible_channels(self):
        start = self.current_page * PAGE_SIZE
        return self.channels[start:start + PAGE_SIZE]

    def is_channel_visible(self, channel_widget) -> bool:
        return channel_widget in self.visible_channels()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for widget in self.visible_channels():
            widget.update_compact_layout()

    def update_page_ui(self):
        self.pages.setCurrentIndex(self.current_page)
        start = self.current_page * PAGE_SIZE + 1
        end = start + PAGE_SIZE - 1
        self.page_label.setText(f"Visible modules: {start}-{end}")
        for idx, btn in enumerate(self.page_buttons):
            btn.blockSignals(True)
            btn.setChecked(idx == self.current_page)
            btn.blockSignals(False)
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < NUM_PAGES - 1)
        for widget in self.visible_channels():
            widget.refresh_ui()

    def set_page(self, page_index, autosave=True):
        page_index = max(0, min(NUM_PAGES - 1, int(page_index)))
        if page_index == self.current_page:
            return
        self.current_page = page_index
        self.update_page_ui()
        if autosave:
            self.schedule_preset_autosave()

    def go_prev_page(self):
        self.set_page(self.current_page - 1)

    def go_next_page(self):
        self.set_page(self.current_page + 1)

    def set_active_channel(self, target_widget, autosave=True):
        if target_widget is None:
            return
        if self.active_channel is target_widget:
            return
        previous = self.active_channel
        self.active_channel = target_widget
        if previous is not None:
            previous.set_active(False)
        target_widget.set_active(True)
        if autosave:
            self.schedule_preset_autosave()

    def set_active_pad(self, target_widget, autosave=True):
        if target_widget is None:
            return
        if self.active_pad is target_widget:
            return
        previous = self.active_pad
        self.active_pad = target_widget
        if previous is not None:
            previous.set_active(False)
        target_widget.set_active(True)
        if autosave:
            self.schedule_preset_autosave()

    def log(self, text):
        lines = self.global_log.toPlainText().splitlines()
        lines.append(text)
        lines = lines[-self.max_log_lines:]
        self.global_log.setPlainText("\n".join(lines))
        self.global_log.moveCursor(QTextCursor.End)

    def refresh_ports(self):
        current_text = self.in_combo.currentText().strip()
        self.in_combo.clear()
        ports = self.midi.list_input_ports()
        self.in_combo.addItems(ports)
        if current_text:
            restored = self.in_combo.findText(current_text)
            if restored >= 0:
                self.in_combo.setCurrentIndex(restored)
        self.status_label.setText("Status: MIDI ports rescanned" if ports else "Status: no MIDI port found")
        self.log("[SYS] MIDI ports rescanned." if ports else "[SYS] No MIDI port found.")

    def connect_midi(self):
        port_name = self.in_combo.currentText().strip()
        if not port_name:
            self.status_label.setText("Status: no MIDI port selected")
            self.log("[SYS] No MIDI port selected.")
            return
        try:
            self.midi.open_input(port_name)
            self.status_label.setText(f"Status: MIDI connected to {port_name}")
            self.log(f"[SYS] MIDI connected to {port_name}")
            self.schedule_preset_autosave()
        except Exception as e:
            self.status_label.setText(f"Status: MIDI error: {e}")
            self.log(f"[SYS] MIDI error: {e}")

    def connect_osc(self):
        try:
            ip = self.ip.text().strip()
            port = int(self.port.text().strip())
            self.midi.setup_osc(ip, port)
            self.status_label.setText(f"Status: OSC connected to {ip}:{port}")
            self.log(f"[SYS] OSC connected to {ip}:{port}")
            self.schedule_preset_autosave()
        except Exception as e:
            self.status_label.setText(f"Status: OSC error: {e}")
            self.log(f"[SYS] OSC error: {e}")

    def clear_all_learn_modes(self):
        for widget in self.channels:
            widget.set_learn_active(False)
        for pad in self.pads:
            pad.set_learn_active(False)

    def activate_learn_for(self, target_widget):
        self.clear_all_learn_modes()
        self.set_active_channel(target_widget, autosave=False)
        target_widget.set_learn_active(True)
        self.schedule_preset_autosave()

    def activate_pad_learn_for(self, target_widget):
        self.clear_all_learn_modes()
        self.set_active_pad(target_widget, autosave=False)
        target_widget.set_learn_active(True)
        self.schedule_preset_autosave()

    def schedule_preset_autosave(self):
        if self.is_loading_preset:
            return
        self.autosave_timer.start(400)

    def autosave_preset(self):
        try:
            self.save_preset(self.current_preset_path, silent=True)
        except Exception as e:
            self.log(f"[SYS] Autosave error: {e}")

    def collect_preset_data(self):
        return {
            "app": "knoblooper-v16.5.4",
            "version": "16.5.4",
            "current_page": self.current_page,
            "current_tab": self.tabs.currentIndex(),
            "active_channel_index": self.active_channel.channel_index if self.active_channel else 1,
            "active_pad_index": self.active_pad.pad_index if self.active_pad else 1,
            "osc": {"ip": self.ip.text().strip(), "port": self.port.text().strip()},
            "midi": {"selected_input": self.in_combo.currentText().strip()},
            "channels": [channel.export_state() for channel in self.channels],
            "pads": [pad.export_state() for pad in self.pads],
            "ui": {"splitter_sizes": self.main_splitter.sizes()},
        }

    def apply_preset_data(self, data):
        if not isinstance(data, dict):
            raise ValueError("Invalid preset format")
        self.is_loading_preset = True
        try:
            osc = data.get("osc", {})
            self.ip.setText(str(osc.get("ip", self.ip.text())).strip())
            self.port.setText(str(osc.get("port", self.port.text())).strip())

            selected_input = str(data.get("midi", {}).get("selected_input", "") or "")
            if selected_input:
                idx = self.in_combo.findText(selected_input)
                if idx >= 0:
                    self.in_combo.setCurrentIndex(idx)

            channels_by_index = {}
            for item in data.get("channels", []):
                if isinstance(item, dict):
                    try:
                        channels_by_index[int(item.get("channel_index"))] = item
                    except (TypeError, ValueError):
                        pass
            for channel in self.channels:
                channel.apply_state(channels_by_index.get(channel.channel_index, {}))

            pads_by_index = {}
            for item in data.get("pads", []):
                if isinstance(item, dict):
                    try:
                        pads_by_index[int(item.get("pad_index"))] = item
                    except (TypeError, ValueError):
                        pass
            for pad in self.pads:
                pad.apply_state(pads_by_index.get(pad.pad_index, {}))

            ui_state = data.get("ui", {}) if isinstance(data.get("ui", {}), dict) else {}
            try:
                splitter_sizes = ui_state.get("splitter_sizes")
                if isinstance(splitter_sizes, list) and len(splitter_sizes) == 2:
                    self.main_splitter.setSizes([max(200, int(splitter_sizes[0])), max(64, int(splitter_sizes[1]))])
            except Exception:
                pass

            try:
                self.current_page = max(0, min(NUM_PAGES - 1, int(data.get("current_page", 0))))
            except (TypeError, ValueError):
                self.current_page = 0
            self.update_page_ui()

            try:
                current_tab = int(data.get("current_tab", TAB_LOOPS))
            except (TypeError, ValueError):
                current_tab = TAB_LOOPS
            self.tabs.setCurrentIndex(current_tab if current_tab in (TAB_LOOPS, TAB_PADS) else TAB_LOOPS)

            active_channel_index = int(data.get("active_channel_index", 1))
            active_channel = next((c for c in self.channels if c.channel_index == active_channel_index), self.channels[0])
            self.set_active_channel(active_channel, autosave=False)

            active_pad_index = int(data.get("active_pad_index", 1))
            active_pad = next((p for p in self.pads if p.pad_index == active_pad_index), self.pads[0])
            self.set_active_pad(active_pad, autosave=False)
        finally:
            self.is_loading_preset = False

    def save_preset(self, path: Path, silent=False):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.collect_preset_data(), f, indent=2, ensure_ascii=False)
        self.current_preset_path = path
        self.refresh_preset_list(select_name=path.name)
        if not silent:
            self.status_label.setText(f"Status: preset saved to {path.name}")
            self.log(f"[SYS] Preset saved -> {path}")

    def load_preset(self, path: Path, silent=False):
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self.apply_preset_data(data)
        self.current_preset_path = path
        self.refresh_preset_list(select_name=path.name)
        if not silent:
            self.status_label.setText(f"Status: preset loaded from {path.name}")
            self.log(f"[SYS] Preset loaded -> {path}")

    def save_current_preset(self):
        try:
            self.save_preset(self.selected_preset_path(), silent=False)
        except Exception as e:
            self.status_label.setText(f"Status: preset save error: {e}")
            self.log(f"[SYS] Preset save error: {e}")

    def save_preset_as(self):
        suggested = self.current_preset_path.stem if self.current_preset_path else "preset"
        name, ok = QInputDialog.getText(self, "Save preset as", "Preset JSON name", text=suggested)
        if not ok or not (name or "").strip():
            return
        try:
            self.save_preset(self.preset_path_from_name(name), silent=False)
        except Exception as e:
            self.status_label.setText(f"Status: preset save error: {e}")
            self.log(f"[SYS] Preset save error: {e}")

    def load_selected_preset(self):
        path = self.selected_preset_path()
        if not path.exists():
            self.status_label.setText(f"Status: preset not found: {path.name}")
            self.log(f"[SYS] Preset not found: {path}")
            return
        try:
            self.load_preset(path, silent=False)
        except Exception as e:
            self.status_label.setText(f"Status: preset load error: {e}")
            self.log(f"[SYS] Preset load error: {e}")

    def update_app(self):
        msgs = self.midi.poll_messages()
        for msg in msgs:
            for widget in self.channels:
                widget.handle_midi_message(msg)
            for pad in self.pads:
                pad.handle_midi_message(msg)
        visible = set(self.visible_channels())
        for widget in self.channels:
            widget.tick(update_ui=(widget in visible))
