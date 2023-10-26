from json.decoder import JSONDecodeError
import re
from flask import Flask, render_template, request, jsonify, abort, session, redirect, make_response, url_for, send_file, json
import os
import requests

from datetime import datetime
import string
from random import choice

from werkzeug import datastructures

from requests_oauthlib import OAuth2Session

import qrcode
from PIL import Image

import io
import base64

import json

# Create flask app
app = Flask(__name__)

# Service url
baseurl = "http://127.0.0.1:8000"
# URL for FENIX authorization
authorization_base_url = 'https://fenix.tecnico.ulisboa.pt/oauth/userdialog'
# URL for fetching authorization token from FENIX
token_url = 'https://fenix.tecnico.ulisboa.pt/oauth/access_token'
# URL for the user database
userDataUrl = "http://127.0.0.1:8001"
# URL for the gate database
gateDataUrl = "http://127.0.0.1:8002"
# URL that allows the administrator to access the database(GateData.py)
adminUrl = "http://127.0.0.1:8002/gates/admin"

# Client ID in FENIX for the app
client_id = "851490151334145"
# Client secret in FENIX for the app
client_secret = "kOanuSjC5klSJWq2FhbtP2MTHC2pRCg0T2QwSfi1rpirpewau+/8ERwzvIJsvst1421UcnbHHq7qpNu6Y6GDEw=="

################
#FUNCTIONS
################

# Prepares response with necessary headers for JQuery
def headeredResponse(data):
    response = make_response(data)
    response.headers.add('Access-Control-Allow-Origin', '*')

    return response

# Creates the random user code for the gates
def createUsercode():
    chars = string.ascii_uppercase + string.digits
    code =  ''.join(choice(chars) for _ in range(6))
    # Sets code as the key and the value to the creation date
    return code
################

# Root endpoint redirects to user's initial page'
@app.route("/")
def redirectLogin():
    return redirect("/login")

# Initial page for the user
@app.route("/login")
def login():
    return render_template("userLoginPage.html")

# Endpoint that returns the URL for fenix authentication
@app.route("/users/authentication")
def userAuth():
    # Create OAuth2Session object and request authorization URL
    fenix = OAuth2Session(client_id, redirect_uri="http://127.0.0.1:8000/callback")
    authorization_url, state = fenix.authorization_url(authorization_base_url)
    print(authorization_url)
    print(state)

    # State is used to prevent CSRF, keep this for later.
    session['oauth_state'] = state

    # Return authorization URL
    response = headeredResponse(authorization_url)
    return response

# Callback URL registered in fenix. Fetches the authorization token
@app.route("/callback", methods=["GET"])
def callback():
    """ Step 3: Retrieving an access token.

    The user has been redirected back from the provider to your registered
    callback URL. With this redirection comes an authorization code included
    in the redirect URL. We will use that to obtain an access token.
    """
    print(request.url)
    try:
        fenix = OAuth2Session(client_id, state=session['oauth_state'], redirect_uri="http://127.0.0.1:8000/callback")
    except KeyError:
        abort(401)
    

    token = fenix.fetch_token(token_url, client_secret=client_secret,
                               authorization_response=request.url)
    # At this point you can fetch protected resources but lets save
    # the token and show how this is done from a persisted token
    # in /profile.
    # If failed to get token or if session expired, return 401 code
    session['oauth_token'] = token

    # Return URL for the user's main page if authorization is successful
    if fenix.authorized is True:
        return redirect(url_for("userPage"))

    abort(401)

@app.route("/users", methods=["GET"])
def userPage():

    fenix = OAuth2Session(client_id, token=session['oauth_token'])
    username = fenix.get('https://fenix.tecnico.ulisboa.pt/api/fenix/v1/person').json()["username"]

    return render_template("userWebApp.html", username = username)

@app.route("/users/<path:username>/access", methods=["GET"])
def generateQrCode(username):
    
    qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=10,
    border=4,
    )

    userCode = createUsercode() 

    requests.post("http://127.0.0.1:8001" + "/users/access", params={"username": username, "userCode": userCode, "secret": app.secret_key})

    #generate QR code
    qr.add_data(userCode)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    #Temporarily save image to send
    img_io = io.BytesIO()
    img.save(img_io, "png")
    #img_io.seek(0)
    encoded_img_data = base64.b64encode(img_io.getvalue())

    response = headeredResponse(encoded_img_data)
    return response

# Endpoint that returns the user's access history
@app.route("/users/<path:username>/history", methods=["GET"])
def showAccessHistory(username):
    # Request history from the user database
    history = requests.get("http://127.0.0.1:8001" + "/users/history/view", params={"username": username, "secret": app.secret_key})

    # build response
    try:
        response = jsonify(history.json())
    except JSONDecodeError:
        response = jsonify("")
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    response.headers.add('Access-Control-Allow-Origin', '*')

    return response

# Route to the gates list history accesses template
@app.route("/gates/list", methods = ["GET","POST"]) 
def accessTable():
    accesses = request.args
    for j in accesses:
        data = accesses.to_dict()
    print(accesses)
    return render_template("userAccessList.html", accesses = accesses)

# Endpoint for the gate login
@app.route("/gates/login")
def gateLogin():
    return render_template("gateLogin.html")

# Endpoint that renders the gate web app page
@app.route("/gates/")
def gateApp():
    # Deal with exceptions if gateID can's be converted to int
    try:
        gateID = request.args["gateID"]
    except KeyError:
        abort(401)

    return render_template("gateWebApp.html", gateID = gateID)

# Endpoint that registers accesses
@app.route("/gates/access")
def gateAccess():
    # Get parameters for the access
    # Access code
    userCode = request.args["userCode"]
    gateID = request.args["gateID"]
    # Time of access
    accessTime = datetime.now()

    # Send request to the user database to check if the code is in the database and, therefore, valid
    codeAuth = requests.get(userDataUrl + "/users/code", params={"code":userCode, "secret":app.secret_key}).json()

    # Update the gate database which will also update user database
    requests.post(gateDataUrl + "/gates/access", params={"gateID":gateID, "userCode": userCode, "status":codeAuth, "time": accessTime, "secret": app.secret_key})

    response = headeredResponse(str(codeAuth).rstrip('\n'))
    return response


# Route that deletes the gate (it receives a POST method from the "/admin/delete" since html doesn't allow the DELETE method)
@app.route("/admin/deleter", methods=["POST"])
def gateDeleter():

    # ID of the gate to be eliminated
    id = request.form["gateID"] 
    # Checks if id variable is an Int. If not returns code 400
    try:
        int(id) 
    except ValueError:
        abort(400)

    # Sends a request to delete a specific gate or returns code 500
    try:
        verification = requests.delete(adminUrl, data=id)
    except requests.exceptions.RequestException as e:
            abort(500)
    
    # Checks if the HTTP status code is successful (200 -299) and returns code 500 if not
    if not verification.status_code // 100 == 2:
        abort(verification.status_code)
    # Sends information about gate deletion depending on it's previous existence 
    return headeredResponse(verification.text)

if __name__ == "__main__":
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    # App key for app validation on requests
    app.secret_key = "zQXtf6TcSmKHwrY8pry2VWNJ"
    app.run(host='127.0.0.1', port=8000, debug=True)