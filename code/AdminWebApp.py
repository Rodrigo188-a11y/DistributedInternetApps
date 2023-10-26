from flask import Flask, render_template, request, jsonify, abort, session, redirect, make_response, url_for, send_file, json
import os
import requests

import string
from random import choice

from requests_oauthlib import OAuth2Session

#Create flask app
app = Flask(__name__)

# Read file with the name of the admins
with open("admins.txt") as file:
    lines = lines = file.readlines()
    admins = [line.rstrip() for line in lines]

baseurl = "http://127.0.0.1:8000"
authorization_base_url = 'https://fenix.tecnico.ulisboa.pt/oauth/userdialog'
token_url = 'https://fenix.tecnico.ulisboa.pt/oauth/access_token'
userDataUrl = "http://127.0.0.1:8000"

# Client ID in FENIX for the app
client_id = "570015174623418"
# Client secret in FENIX for the app
client_secret = "43iAw6AGMPjenpTkPrKRRUXRSIfED6205LPIK/tPafzB8j94yXvFTIoLz/WfrK3Pw0cOfBdZ7VmlC9qcioYcGw=="

# Root endpoint redirects to login page
@app.route("/")
def redirectLogin():
    return redirect("/login")

# Admin's login page
@app.route("/login")
def login():
    return render_template("adminLoginPage.html")

# Endpoint for authentication identical to the one in service.py
@app.route("/admin/authentication")
def userAuth():
    fenix = OAuth2Session(client_id, redirect_uri="http://127.0.0.1:8003/callback")
    authorization_url, state = fenix.authorization_url(authorization_base_url)
    print(authorization_url)
    print(state)
    # State is used to prevent CSRF, keep this for later.
    session['oauth_state'] = state

    response = make_response(authorization_url)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# Callback endpoint identical to the one in service.py, except that it redirects to the admin page
@app.route("/callback", methods=["GET"])
def callback():
    """ Step 3: Retrieving an access token.

    The user has been redirected back from the provider to your registered
    callback URL. With this redirection comes an authorization code included
    in the redirect URL. We will use that to obtain an access token.
    """
    #state=session['oauth_state']
    print(request.url)
    fenix = OAuth2Session(client_id, redirect_uri="http://127.0.0.1:8003/callback")

    token = fenix.fetch_token(token_url, client_secret=client_secret,
                               authorization_response=request.url)
    # At this point you can fetch protected resources but lets save
    # the token and show how this is done from a persisted token
    # in /profile.
    session['oauth_token'] = token

    # Check if the authenticated user is an admin
    username = fenix.get('https://fenix.tecnico.ulisboa.pt/api/fenix/v1/person').json()["username"]
    # Check if the person who logged in through FENIX has his username in the admins.txt file
    if username not in admins:
        abort(401)

    if fenix.authorized is True:
        return redirect(url_for("adminPage"))

    abort(401)

# Endpoint that renders the admin's main page
@app.route("/admin", methods=["GET"])
def adminPage():
    fenix = OAuth2Session(client_id, token=session['oauth_token'])
    username = fenix.get('https://fenix.tecnico.ulisboa.pt/api/fenix/v1/person').json()["username"]

    return render_template("AdminWebApp.html", username = username)

# Route that retrieves the gates' history
@app.route("/gates/list", methods = ["GET","POST"]) 
def accesesTable():
    # Receives a Immutable Multi Dict
    accesses = request.args
    # Transforms it into a regural dict
    data = accesses.to_dict()
    # Check's the dict's size and divides it by the number of elements of the gate class so that it can be represented
    size = len(data)
    size = int(size/5)
    return render_template("gateListHistory.html", accesses = data, size = size)

if __name__ == "__main__":
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    app.secret_key = os.urandom(24)
    app.run(host='127.0.0.1', port=8003, debug=True)