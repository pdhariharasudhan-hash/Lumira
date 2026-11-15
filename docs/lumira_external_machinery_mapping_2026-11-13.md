# Lumira external machinery mapping
Date: 2026-11-13 | Host: HP 250R 15.6-inch G9 | Windows RAM: 7.7 GB total, 0.74–0.94 GB free observed.

Legend: PRESENT = directly observed; REPORTED = prior handoff/user context, not re-enumerated; UNKNOWN = not verified; BLOCKED = cannot accept yet.

## Computing
- Laptop: PRESENT (WMI model).
- RAM: PRESENT (7.7 GB total; under 1 GB free).
- CPU model/cores, GPU/VRAM, disk capacity/free space, thermals, external storage, NAS and UPS: UNKNOWN.
- Rule: no full suite, model inference, installer build or concurrent agents below 2 GB free RAM.

## Audio
- Built-in mic, USB mic, dedicated recorder, audio interface, mic array, speakers/headphones: UNKNOWN.
- Prior handoff reported audio endpoints enumerated, but no physical recording/playback acceptance.
- VAD/noise-reduction software: IN PROGRESS; hardware acceptance open.

## Embedded/electronics
- ESP32 DevKit, Raspberry Pi 5/4, Pico, Arduino-compatible boards: REPORTED/DISCUSSED, not confirmed connected.
- Sensors, actuators, motors/drivers, camera/display/relay/power: UNKNOWN.
- Breadboard, multimeter, soldering station, programmable PSU: previously discussed workshop inventory, not confirmed currently present.
- No device is PRESENT merely because it was discussed or planned.

## Robotics
- Robot arm/mobile base, servos/steppers/controllers, camera/depth/LiDAR/IMU/encoders, force/proximity sensors, controller/power: UNKNOWN.
- Emergency stop: REQUIRED but unverified.
- Simulator and hardware-in-loop acceptance: UNKNOWN.

## Network/connectivity
- Windows host and Desktop Commander remote connection: PRESENT.
- Wi-Fi/Ethernet details, Bluetooth, USB/serial device, IoT VLAN, UPS and network failover: UNKNOWN.
- Desktop Commander access is not proof of a production Lumira remote-access capability.

## OS and runtimes
- Windows: PRESENT.
- Python/Node/npm/Git: used in prior runs; versions not rechecked.
- FastAPI/Uvicorn/Pydantic and Electron/React/Vite: present in project/prior tests; current runtime versions not checked.
- SQLite/JSON persistence: source present; live runtime not revalidated.
- Docker CLI: ABSENT per prior handoff.
- Windows Sandbox provider/executable: prior provider-level live guest evidence; source exists.
- ProjectTerminalService integration: BLOCKED; sandbox not yet wired end-to-end.
- GPU drivers, WSL/Linux, containers and firmware toolchains: UNKNOWN.

## External providers and APIs
- Ollama local LLM/vision, Faster-Whisper, Windows SAPI English TTS: prior live evidence, not invoked in this audit.
- OpenAI-compatible and Tavily adapters: source present; config/consent/reachability unknown.
- Image generation, video, wake word, OCR, 3D, Tamil TTS, email/calendar/cloud storage connectors: BLOCKED or UNKNOWN pending configuration and live acceptance.
- REST HTTP(S): present in app; WebSocket/streaming, serial/USB, MQTT, Bluetooth, GPIO and robotics middleware require separate acceptance.
- Never print secret environment variables. Provider registration is not proof of reachability, successful inference or consent.

## Physical inventory needed
Owner must confirm what is actually available: mic/headphones/speakers/recorder; ESP32/Pi/Pico/Arduino and cables; sensors/actuators/motor drivers/cameras/power; breadboard/multimeter/soldering/safety equipment; robot platform/controller/e-stop/enclosure; router/switch/Bluetooth/UPS; CPU/GPU/SSD specs.

## Conclusion
The host is a low-memory development laptop. Most physical machinery is not currently verified. Hardware-dependent requirements remain BLOCKED/NOT VERIFIED until real devices are inventoried and acceptance-tested. This mapping does not recommend purchases.
