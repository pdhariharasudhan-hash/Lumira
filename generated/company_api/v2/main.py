
from fastapi import FastAPI



app = FastAPI()


companies = []








@app.get(
    "/companies"
)
def get_items():

    return companies


@app.post(
    "/companies"
)
def create_item(
    name: str
):

    companies.append(

        {
            "name": name
        }
    )

    return {

        "success":
        True,

        "companies":
        companies
    }


@app.put(
    "/companies/{item_id}"
)
def update_item(

    item_id: int,

    name: str
):

    if item_id >= len(
        companies
    ):

        return {

            "success":
            False
        }


    companies[item_id] = {

        "name": name
    }


    return {

        "success":
        True,

        "companies":
        companies
    }


@app.delete(
    "/companies/{item_id}"
)
def delete_item(
    item_id: int
):

    if item_id >= len(
        companies
    ):

        return {

            "success":
            False
        }


    companies.pop(
        item_id
    )


    return {

        "success":
        True
    }

