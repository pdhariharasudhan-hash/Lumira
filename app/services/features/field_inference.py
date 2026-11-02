#app/services/field_inference.py
from typing import List


class FieldInference:

    def infer(
        self,
        entity: str
    ) -> List[str]:

        field_map = {

            "expense":[
                "amount",
                "category"
            ],

            "movie":[
                "title",
                "year"
            ],

            "book":[
                "title",
                "author"
            ],

            "recipe":[
                "ingredients",
                "prep_time"
            ],

            "stock":[
                "symbol",
                "price"
            ],

            "task":[
                "title",
                "status",
                "due_date"
            ],

            "project":[
                "name",
                "description",
                "status"
            ],

            "contact":[
                "name",
                "email"
            ],

            "idea":[
                "title",
                "description",
                "priority"
            ]
        }

        return field_map.get(
            entity,
            ["name"]
        )