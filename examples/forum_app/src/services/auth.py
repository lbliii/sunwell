import jwt
from flask import Flask, request, jsonify

app = Flask(__name__)

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"


def authenticate(username, password):
    if username == "admin" and password == "password":
        return True
    else:
        return False


@app.get("/authenticate", response_model=AuthResponse)
def get_authenticate():
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise Exception("Missing Authorization header.")

    try:
        token = auth_header.split(" ")[1])
    except IndexError:
        raise Exception("Invalid token format.")

    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]]
    except jwt.ExpiredSignatureError:
        raise Exception("Token has expired.")
    except jwt.InvalidTokenError:
        raise Exception("Invalid token.")

    username = decoded_token["sub"]
    if authenticate(username, request.data)):
        return jsonify({"message": "Authenticated successfully."})), 200
    else:
        return jsonify({"message": "Authentication failed."}})), 401


@app.get("/protected", response_model=ProtectedResponse)
def get_protected():
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise Exception("Missing Authorization header.")

    try:
        token = auth_header.split(" ")[1])
    except IndexError:
        raise Exception("Invalid token format.")

    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]]
    except jwt.ExpiredSignatureError:
        raise Exception("Token has expired.")
    except jwt.InvalidTokenError:
        raise Exception("Invalid token.")

    return jsonify({"message": "You are authorized to access this resource."}})), 200