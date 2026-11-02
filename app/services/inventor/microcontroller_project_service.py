from __future__ import annotations


class MicrocontrollerProjectService:
    SUPPORTED = {"esp32", "raspberry_pi_pico", "arduino", "raspberry_pi", "other"}

    def scaffold(self, platform: str, objective: str, peripherals: list[str] | None = None) -> dict:
        if platform not in self.SUPPORTED:
            raise ValueError("unsupported platform")
        if not isinstance(objective, str) or not objective.strip() or len(objective.strip()) > 5000:
            raise ValueError("objective must contain 1 to 5000 characters")
        peripherals = peripherals or []
        if not isinstance(peripherals, list) or len(peripherals) > 50:
            raise ValueError("peripherals must contain at most 50 entries")
        return {
            "platform": platform,
            "objective": objective.strip(),
            "peripherals": [str(x).strip() for x in peripherals if str(x).strip()],
            "development_steps": ["confirm board and power requirements", "map pins and interfaces", "build a minimal hardware test", "implement firmware incrementally", "test failure states", "document connections"],
            "status": "scaffolded",
        }
