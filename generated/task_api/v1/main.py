
from fastapi import FastAPI



app = FastAPI()


tasks=[]








@app.get(
    "/tasks"
)
def get_items():

    return tasks


@app.post(
    "/tasks"
)
def create_item(
    name: str
):

    tasks.append(

        {
            "name": name
        }
    )

    return {

        "success":
        True,

        "tasks":
        tasks
    }


@app.put(
    "/tasks/{item_id}"
)
def update_item(

    item_id:int,

    name: str
):

    if item_id >= len(
        tasks
    ):

        return {

            "success":
            False
        }


    tasks[item_id] = {

        "name": name
    }


    return {

        "success":
        True,

        "tasks":
        tasks
    }


@app.delete(
    "/tasks/{item_id}"
)
def delete_item(
    item_id:int
):

    if item_id >= len(
        tasks
    ):

        return {

            "success":
            False
        }


    tasks.pop(
        item_id
    )


    return {

        "success":
        True
    }

