import mido
from pythonosc.udp_client import SimpleUDPClient


class MidiEngine:
    def __init__(self):
        self.input_port = None

        self.osc_client = None
        self.osc_ip = "127.0.0.1"
        self.osc_port = 8010

    def list_input_ports(self):
        try:
            return mido.get_input_names()
        except Exception:
            return []

    def open_input(self, port_name: str):
        self.close_input()
        if not port_name:
            raise ValueError("No MIDI input port provided")
        self.input_port = mido.open_input(port_name)

    def close_input(self):
        if self.input_port is not None:
            try:
                self.input_port.close()
            except Exception:
                pass
            self.input_port = None

    def is_input_open(self):
        return self.input_port is not None

    def setup_osc(self, ip: str, port: int):
        if not ip:
            raise ValueError("OSC IP is empty")

        self.osc_ip = ip.strip()
        self.osc_port = int(port)
        self.osc_client = SimpleUDPClient(self.osc_ip, self.osc_port)

    def is_osc_ready(self):
        return self.osc_client is not None

    def poll_messages(self):
        if self.input_port is None:
            return []

        try:
            return list(self.input_port.iter_pending())
        except Exception:
            return []

    def send_osc_value(self, address: str, value: int):
        if self.osc_client is None:
            return False

        normalized = max(0.0, min(1.0, float(value) / 127.0))
        self.osc_client.send_message(address, normalized)
        return True

    def send_osc_message(self, address: str, value):
        if self.osc_client is None:
            return False
        if not address:
            return False
        try:
            self.osc_client.send_message(address, value)
            return True
        except Exception:
            return False

