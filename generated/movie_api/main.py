
from fastapi import FastAPI

app = FastAPI()

movies = []


@app.get("/movies")
def get_items():

    return movies


@app.post("/movies")
def create_item(
    title: str,
    year: str
):

    movies.append(
        {
            "title": title,
            "year": year
        }
    )

    return {
        "success": True,
        "movies": movies
    }


@app.put("/movies/{item_id}")
def update_item(
    item_id: int,
    title: str,
    year: str
):

    if item_id >= len(
        movies
    ):

        return {
            "success": False
        }

    movies[item_id] = {
        "title": title,
            "year": year
    }

    return {
        "success": True,
        "movies": movies
    }


@app.delete("/movies/{item_id}")
def delete_item(
    item_id: int
):

    if item_id >= len(
        movies
    ):

        return {
            "success": False
        }

    movies.pop(
        item_id
    )

    return {
        "success": True
    }
