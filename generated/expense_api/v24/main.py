
from fastapi import FastAPI



app = FastAPI()


expenses=[]








@app.get(
    "/expenses"
)
def get_items():

    return expenses


@app.post(
    "/expenses"
)
def create_item(
    amount: str,
    category: str
):

    expenses.append(

        {
            "amount": amount,
            "category": category
        }
    )

    return {

        "success":
        True,

        "expenses":
        expenses
    }


@app.put(
    "/expenses/{item_id}"
)
def update_item(

    item_id:int,

    amount: str,
    category: str
):

    if item_id >= len(
        expenses
    ):

        return {

            "success":
            False
        }


    expenses[item_id] = {

        "amount": amount,
            "category": category
    }


    return {

        "success":
        True,

        "expenses":
        expenses
    }


@app.delete(
    "/expenses/{item_id}"
)
def delete_item(
    item_id:int
):

    if item_id >= len(
        expenses
    ):

        return {

            "success":
            False
        }


    expenses.pop(
        item_id
    )


    return {

        "success":
        True
    }

