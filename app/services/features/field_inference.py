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
            ]
        }

        return field_map.get(
            entity,
            ["name"]
        )