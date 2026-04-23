import time


class LoopEngine:
    def __init__(self):
        self.events = []

        self.recording = False
        self.playing = False
        self.paused = False

        self.record_start_time = None
        self.loop_duration = 0.0

        self.speed = 1.0

        self.playhead_offset = 0.0
        self.last_wall_time = None

    def clear(self):
        self.events = []
        self.recording = False
        self.playing = False
        self.paused = False

        self.record_start_time = None
        self.loop_duration = 0.0

        self.playhead_offset = 0.0
        self.last_wall_time = None

    def export_state(self):
        return {
            "events": [[float(event_time), int(value)] for event_time, value in self.events],
            "loop_duration": float(self.loop_duration),
            "speed": float(self.speed),
        }

    def import_state(self, data):
        self.clear()

        if not isinstance(data, dict):
            return

        raw_events = data.get("events", [])
        events = []
        for item in raw_events:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            try:
                event_time = float(item[0])
                value = int(item[1])
            except (TypeError, ValueError):
                continue
            events.append((max(0.0, event_time), max(0, min(127, value))))

        events.sort(key=lambda item: item[0])
        self.events = events

        try:
            self.loop_duration = max(0.0, float(data.get("loop_duration", 0.0)))
        except (TypeError, ValueError):
            self.loop_duration = 0.0

        try:
            speed = float(data.get("speed", 1.0))
        except (TypeError, ValueError):
            speed = 1.0
        self.speed = max(0.01, speed)

        if self.events and self.loop_duration <= 0.0:
            self.loop_duration = float(self.events[-1][0])

    def set_speed(self, speed: float):
        speed = max(0.01, float(speed))
        if self.playing:
            self._sync_playhead()
        self.speed = speed

    def start_recording(self):
        self.events = []
        self.recording = True
        self.playing = False
        self.paused = False

        self.record_start_time = time.perf_counter()
        self.loop_duration = 0.0

        self.playhead_offset = 0.0
        self.last_wall_time = None

    def record_value(self, value: int):
        if not self.recording or self.record_start_time is None:
            return

        now = time.perf_counter()
        offset = now - self.record_start_time
        self.events.append((offset, value))

    def stop_recording(self):
        if not self.recording:
            return

        self.recording = False

        if self.events:
            self.loop_duration = self.events[-1][0]
        else:
            self.loop_duration = 0.0

    def start_playback(self):
        if not self.events or self.loop_duration <= 0:
            return False

        self.recording = False
        self.playing = True
        self.paused = False

        self.playhead_offset = 0.0
        self.last_wall_time = time.perf_counter()
        return True

    def stop_playback(self):
        self.playing = False
        self.paused = False
        self.playhead_offset = 0.0
        self.last_wall_time = None

    def pause_playback(self):
        if not self.playing or self.loop_duration <= 0:
            return False

        self._sync_playhead()
        self.playing = False
        self.paused = True
        self.last_wall_time = None
        return True

    def resume_playback(self):
        if not self.paused or not self.events or self.loop_duration <= 0:
            return False

        self.playing = True
        self.paused = False
        self.last_wall_time = time.perf_counter()
        return True

    def _sync_playhead(self):
        if not self.playing or self.last_wall_time is None or self.loop_duration <= 0:
            return

        now = time.perf_counter()
        wall_delta = now - self.last_wall_time
        self.playhead_offset = (self.playhead_offset + wall_delta * self.speed) % self.loop_duration
        self.last_wall_time = now

    def get_current_elapsed(self):
        if self.loop_duration <= 0:
            return 0.0

        if self.playing:
            self._sync_playhead()
            return self.playhead_offset

        if self.paused:
            return self.playhead_offset % self.loop_duration

        return 0.0

    def get_playback_value(self):
        if self.loop_duration <= 0 or not self.events:
            return None

        if not self.playing and not self.paused:
            return None

        elapsed = self.get_current_elapsed()

        last_value = self.events[0][1]
        for event_time, value in self.events:
            if event_time <= elapsed:
                last_value = value
            else:
                break

        return last_value

    def get_progress(self):
        if self.recording and self.record_start_time is not None:
            return None

        if self.loop_duration <= 0:
            return 0.0

        if self.playing or self.paused:
            elapsed = self.get_current_elapsed()
            return elapsed / self.loop_duration

        return 0.0
