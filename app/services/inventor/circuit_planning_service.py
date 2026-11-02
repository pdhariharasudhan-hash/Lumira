from __future__ import annotations


class CircuitPlanningService:
    """Structured circuit planning without pretending to electrically verify a design."""

    def plan(self, title: str, supply_voltage: float | None, components: list[str], requirements: list[str] | None = None) -> dict:
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 300:
            raise ValueError("title must contain 1 to 300 characters")
        if supply_voltage is not None and (not isinstance(supply_voltage, (int, float)) or not 0 < supply_voltage <= 1000):
            raise ValueError("supply_voltage must be between 0 and 1000 volts")
        if not isinstance(components, list) or not 1 <= len(components) <= 100:
            raise ValueError("provide 1 to 100 components")
        cleaned = [x.strip() for x in components if isinstance(x, str) and x.strip() and len(x.strip()) <= 200]
        if len(cleaned) != len(components):
            raise ValueError("components must contain valid names")
        requirements = requirements or []
        return {
            "title": title.strip(),
            "supply_voltage": supply_voltage,
            "components": cleaned,
            "requirements": requirements,
            "checklist": ["verify component ratings", "define power budget", "map interfaces and pin compatibility", "check protection requirements", "prototype", "measure before final assembly"],
            "status": "planning_only",
            "safety_note": "Do not treat this output as a verified schematic. Validate calculations, ratings and connections before powering hardware.",
        }
