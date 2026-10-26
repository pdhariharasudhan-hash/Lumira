from pathlib import Path
from typing import Dict, List
import json


class TemplateEngine:


    def get_sections(
        self,
        features: List[str]
    ) -> Dict[str, List[str]]:


        sections = {

            "imports": [],

            "globals": [],

            "routes": [],

            "requirements": []
        }


        template_folder = (
            Path(__file__).resolve().parents[3]
            / "generated_templates"
        )


        for feature in features:


            template_path = (

                template_folder
                / f"{feature}.json"
            )


            if not template_path.exists():

                continue


            with open(
                template_path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(
                    f
                )


            sections[
                "imports"
            ].extend(

                data.get(
                    "imports",
                    []
                )
            )


            sections[
                "globals"
            ].extend(

                data.get(
                    "globals",
                    []
                )
            )


            routes = data.get("routes", [])
            if isinstance(routes, str):
                routes = [routes]
            sections["routes"].extend(routes)
            # Older feature templates used a singular `route` key. Accept it
            # so those feature implementations actually reach generated apps.
            route = data.get("route")
            if isinstance(route, str) and route:
                sections["routes"].append(route)


            sections[
                "requirements"
            ].extend(

                data.get(
                    "requirements",
                    []
                )
            )


        return sections
