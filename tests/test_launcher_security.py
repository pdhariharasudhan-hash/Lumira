from pathlib import Path


def test_lumira_launcher_pins_services_to_loopback():
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "tools" / "start_lumira.ps1").read_text(encoding="utf-8")

    # Prevent inherited environment variables from exposing the backend to the LAN.
    assert "`$env:HOST='127.0.0.1'" in launcher
    assert "`$env:PORT='8000'" in launcher
    assert "`$env:RELOAD='false'" in launcher
    assert "--host 127.0.0.1 --port 5000" in launcher
