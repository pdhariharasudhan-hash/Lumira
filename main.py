from fastapi import FastAPI

app = FastAPI()

users = {}


@app.post("/register")
def register(
    username: str,
    password: str
):

    users[username] = password

    return {
        "success": True,
        "message": "User registered"
    }


@app.post("/login")
def login(
    username: str,
    password: str
):

    stored_password = users.get(
        username
    )

    if stored_password != password:

        return {
            "success": False,
            "message": "Invalid credentials"
        }

    return {
        "success": True,
        "message": "Login successful"
    }
