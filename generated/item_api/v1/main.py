
from fastapi import FastAPI



app = FastAPI()


items=[]








@app.get(
    "/items"
)
def get_items():

    return items


@app.post(
    "/items"
)
def create_item(
    name: str
):

    items.append(

        {
            "name": name
        }
    )

    return {

        "success":
        True,

        "items":
        items
    }


@app.put(
    "/items/{item_id}"
)
def update_item(

    item_id:int,

    name: str
):

    if item_id >= len(
        items
    ):

        return {

            "success":
            False
        }


    items[item_id] = {

        "name": name
    }


    return {

        "success":
        True,

        "items":
        items
    }


@app.delete(
    "/items/{item_id}"
)
def delete_item(
    item_id:int
):

    if item_id >= len(
        items
    ):

        return {

            "success":
            False
        }


    items.pop(
        item_id
    )


    return {

        "success":
        True
    }

