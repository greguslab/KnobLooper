# KnobLooper

KnobLooper is a desktop tool for recording and looping MIDI knob gestures, then sending them out as OSC data for live audiovisual workflows.

It is designed for performance-oriented setups where you want to capture manual controller movements and replay them as continuous automation. A typical use case is a MIDI controller driving parameters in visual software such as MadMapper.

> Current status: **early alpha / work in progress**. The app is functional and already useful, but it is still evolving.

## Features

- **16 loop channels**, displayed 4 at a time for a lighter UI
- **16 pad slots** with Trigger / Momentary / Toggle / Velocity modes
- **MIDI learn** for knob channels and pads
- **OSC output** to external software
- **Per-channel speed control**
- **Record / play / pause** loop workflow from the donut control
- **Preset system** stored as JSON
- **Autosave** for the current preset state
- **Global log** for quick monitoring

## What it is for

KnobLooper sits between a MIDI controller and an OSC-compatible application.

Typical workflow:

1. Connect a MIDI input.
2. Connect an OSC destination.
3. Use **LEARN** on a channel.
4. Move a hardware knob to bind a MIDI CC.
5. Record a gesture.
6. Let KnobLooper loop and resend the movement as OSC.

This makes it possible to create repeatable parameter animations from live controller gestures instead of drawing automation curves by hand.

## Current implementation

This public version includes:

- loop channels with MIDI CC learn
- donut-based record / playback state display
- pad page with configurable OSC addresses and modes
- preset save / load / autosave
- paging system for channels 1-16

## Planned / likely next steps

- cleaner packaging and releases
- better external feedback handling
- more testing across different controllers
- UI cleanup and refinement
- easier distribution for non-technical users

## Requirements

- Python 3.11+ recommended
- A MIDI controller or virtual MIDI source
- An OSC-compatible target application

Python packages:

- PySide6
- mido
- python-rtmidi
- python-osc

## Installation

```bash
git clone https://github.com/YOUR-USERNAME/KnobLooper.git
cd KnobLooper
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### macOS / Linux

```bash
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Usage

### Loop channels

Each loop channel can:

- learn a MIDI CC
- record incoming knob motion
- replay it as a loop
- change playback speed
- send normalized OSC values from 0.0 to 1.0

Default OSC addresses are:

- `/knoblooper/1`
- `/knoblooper/2`
- ...
- `/knoblooper/16`

### Pads

Each pad can:

- learn a note or CC
- send its own OSC address
- operate in Trigger / Momentary / Toggle / Velocity mode

Default pad addresses are:

- `/pad/1`
- `/pad/2`
- ...
- `/pad/16`

## Presets

Presets are stored as JSON files in the `presets/` folder.

They currently contain:

- OSC connection settings
- selected MIDI input
- channel assignments
- pad assignments
- loop data
- active page / active tab / some UI state

## Project structure

```text
main.py
ui_main.py
midi_engine.py
loop_engine.py
channel_widget.py
pad_widget.py
requirements.txt
presets/
```

## Known limitations

- no packaged installer yet
- no formal release build yet
- still being tested in real live setups
- codebase is functional but not fully cleaned up yet

## Contributing

This repository is being published first as a shareable working version.

Bug reports, tests, and workflow feedback are welcome.

## License

This project is licensed under the MIT License. See the `LICENSE` file.
