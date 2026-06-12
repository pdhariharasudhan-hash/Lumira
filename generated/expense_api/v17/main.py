
from fastapi import FastAPI




import sqlite3


connection = sqlite3.connect(
    "app.db"
)

cursor = connection.cursor()



app = FastAPI()




users = {}


@app.post(
    "/register"
)
def register(
    username: str,
    password: str
):

    users[
        username
    ] = password


    return {

        "success":
        True
    }


@app.post(
    "/login"
)
def login(
    username: str,
    password: str
):

    if users.get(
        username
    ) != password:

        return {

            "success":
            False
        }


    return {

        "success":
        True
    }



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


    expenses[item_id]={

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

    if item_id>=len(
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




@app.get(
    "/expenses/search"
)
def search_items(
    query: str
):

    return [

        item

        for item in expenses

        if query.lower()

        in str(
            item
        ).lower()
    ]






@app.get(
    "/expenses/page"
)
def paginate(
    page: int = 1,
    size: int = 5
):

    start = (
        page - 1
    ) * size


    end = (
        start + size
    )


    return expenses[
        start:end
    ]






import csv


@app.get(
    "/expenses/export"
)
def export_csv():

    with open(
        "expenses.csv",
        "w",
        newline=""
    ) as f:

        writer = csv.writer(
            f
        )


        writer.writerow(
            [
                "amount",
                "category"
            ]
        )


        for item in expenses:

            writer.writerow(
                [
                    item["amount"],
                    item["category"]
                ]
            )


    return {

        "success":
        True
    }



