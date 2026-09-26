
from fastapi import FastAPI



app = FastAPI()


projects = []








@app.get(
    "/projects"
)
def get_items():

    return projects


@app.post(
    "/projects"
)
def create_item(
    name: str
):

    projects.append(

        {
            "name": name
        }
    )

    return {

        "success":
        True,

        "projects":
        projects
    }


@app.put(
    "/projects/{item_id}"
)
def update_item(

    item_id: int,

    name: str
):

    if item_id >= len(
        projects
    ):

        return {

            "success":
            False
        }


    projects[item_id] = {

        "name": name
    }


    return {

        "success":
        True,

        "projects":
        projects
    }


@app.delete(
    "/projects/{item_id}"
)
def delete_item(
    item_id: int
):

    if item_id >= len(
        projects
    ):

        return {

            "success":
            False
        }


    projects.pop(
        item_id
    )


    return {

        "success":
        True
    }

