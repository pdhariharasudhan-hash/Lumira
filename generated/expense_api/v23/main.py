
from fastapi import FastAPI

import sqlite3

app = FastAPI()


expenses=[]


users={}
connection=sqlite3.connect("app.db")
cursor=connection.cursor()


@app.post("/register")
def register(username:str,password:str):

    users[username]=password

    return {
        "success":True
    }

@app.post("/login")
def login(username:str,password:str):

    if users.get(username)!=password:

        return {
            "success":False
        }

    return {
        "success":True
    }

@app.get("/expenses/sort")
def sort_items():

    return sorted(
        expenses,
        key=lambda x:x.get("amount")
    )


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

