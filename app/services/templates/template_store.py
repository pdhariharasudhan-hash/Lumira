from pathlib import Path
import json


class TemplateStore:


    def __init__(self):

        self.folder = Path(
            "generated_templates"
        )

        self.folder.mkdir(
            exist_ok=True
        )


    def save(
        self,
        feature:str,
        route:str
    ):

        path = (

            self.folder
            / f"{feature}.json"
        )


        data = {

            "feature":
            feature,

            "route":
            route
        }


        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4
            )


    def load(self):

        templates = {}


        for file in self.folder.glob(
            "*.json"
        ):

            with open(
                file,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(
                    f
                )


                templates[
                    data[
                        "feature"
                    ]
                ] = data


        return templates