
from fastapi import FastAPI



app = FastAPI()


todos = []








@app.get(
    "/todos"
)
def get_items():

    return todos


@app.post(
    "/todos"
)
def create_item(
    name: str
):

    todos.append(

        {
            "name": name
        }
    )

    return {

        "success":
        True,

        "todos":
        todos
    }


@app.put(
    "/todos/{item_id}"
)
def update_item(

    item_id: int,

    name: str
):

    if item_id >= len(
        todos
    ):

        return {

            "success":
            False
        }


    todos[item_id] = {

        "name": name
    }


    return {

        "success":
        True,

        "todos":
        todos
    }


@app.delete(
    "/todos/{item_id}"
)
def delete_item(
    item_id: int
):

    if item_id >= len(
        todos
    ):

        return {

            "success":
            False
        }


    todos.pop(
        item_id
    )


    return {

        "success":
        True
    }

