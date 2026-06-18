
from fastapi import FastAPI



app = FastAPI()


notess=[]








@app.get(
    "/notess"
)
def get_items():

    return notess


@app.post(
    "/notess"
)
def create_item(
    name: str
):

    notess.append(

        {
            "name": name
        }
    )

    return {

        "success":
        True,

        "notess":
        notess
    }


@app.put(
    "/notess/{item_id}"
)
def update_item(

    item_id:int,

    name: str
):

    if item_id >= len(
        notess
    ):

        return {

            "success":
            False
        }


    notess[item_id] = {

        "name": name
    }


    return {

        "success":
        True,

        "notess":
        notess
    }


@app.delete(
    "/notess/{item_id}"
)
def delete_item(
    item_id:int
):

    if item_id >= len(
        notess
    ):

        return {

            "success":
            False
        }


    notess.pop(
        item_id
    )


    return {

        "success":
        True
    }

