
from fastapi import FastAPI



app = FastAPI()


calculators=[]








@app.get(
    "/calculators"
)
def get_items():

    return calculators


@app.post(
    "/calculators"
)
def create_item(
    name: str
):

    calculators.append(

        {
            "name": name
        }
    )

    return {

        "success":
        True,

        "calculators":
        calculators
    }


@app.put(
    "/calculators/{item_id}"
)
def update_item(

    item_id:int,

    name: str
):

    if item_id >= len(
        calculators
    ):

        return {

            "success":
            False
        }


    calculators[item_id] = {

        "name": name
    }


    return {

        "success":
        True,

        "calculators":
        calculators
    }


@app.delete(
    "/calculators/{item_id}"
)
def delete_item(
    item_id:int
):

    if item_id >= len(
        calculators
    ):

        return {

            "success":
            False
        }


    calculators.pop(
        item_id
    )


    return {

        "success":
        True
    }

