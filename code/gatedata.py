from flask.helpers import make_response
import requests
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from os import path

from flask import Flask, request, jsonify, abort

import string
from random import choice

# Url for user database
userDataUrl = "http://127.0.0.1:8001"

# Secret of the service registered beforehand
service_secret = "zQXtf6TcSmKHwrY8pry2VWNJ"

#### SLQ access layer initialization ####
DATABASE_FILE = "database_inter.sqlite"
db_exists = False
if path.exists(DATABASE_FILE):
    db_exists = True
    print("\t database already exists")

engine = create_engine('sqlite:///%s'%(DATABASE_FILE), echo=False, connect_args={'check_same_thread': False}) #echo = True shows all SQL calls

Base = declarative_base()
#Declaration of data
class Gate(Base):
    __tablename__ = 'gate'
    id = Column(Integer, primary_key=True)
    location = Column(String)
    secret = Column(String)
    n_activations = Column(Integer) 
    failed_attempts = Column(Integer) 

    def to_dictionary(self):
        return {"id": self.id, "location": self.location, "secret": self.secret,"n_activations":self.n_activations,"failed_attempts":self.failed_attempts}

# Create tables for the data models
Base.metadata.create_all(engine)

# Create session
Session = sessionmaker(bind=engine)
session = Session()

##### APP functions #####

# Generates response with necessary header for AJAX requests
def headeredResponse(data):
    response = make_response(data)
    response.headers.add('Access-Control-Allow-Origin', '*')

    return response

# Returns the list of gates in dictionary format
def listGates():
    return jsonify([item.to_dictionary() for item in session.query(Gate).all()])

# Adds a new gate to the database
def newGate(id , location, secret, activation,failed):
    gate = Gate(id = id, location = location, secret = secret, n_activations = activation, failed_attempts=failed)
    session.add(gate)
    try:
        session.commit()
    except:
        session.rollbacK()

# Checks if a gate is in the database
def existsGate(id):
    return bool(session.query(Gate).filter_by(id = id).first())

# Gets a gate from the database
def getGate(id):
    gate_return = session.query(Gate).filter(Gate.id == id).first()

    return gate_return.to_dictionary()

# Deletes a gate from the database
def deleteGate(id):
    session.query(Gate).filter(Gate.id == id).delete()
    try:
        session.commit()
    except:
        session.rollbacK()
    return "Gate deleted successfully"

# Registers successfu and unsuccessful accesses
def registerAccess(id, userCode, status, time):

    gate = session.query(Gate).filter(Gate.id == id).first()
    gate_location = gate.location

    # If access is successful increment n_activations and update the user's access history
    # Else increment faied_attempts
    if(status == "True"):
        gate.n_activations += 1

        requests.post(userDataUrl + "/users/history/update", params={"location": gate_location, "time": time, "userCode": userCode, "secret": service_secret})
    else:
        gate.failed_attempts += 1
    try:
        session.commit()
    except:
        session.rollback()
    return "Gate updated successfully"

# Generates a random 4 digit secret for a gate
def generateSecret():
    chars = string.digits
    secret =  ''.join(choice(chars) for _ in range(4))
    return secret
###########################

# Create flask app
app = Flask(__name__)

##### Service B Routes #####
@app.route("/")
def redirect():
      abort(404)

# Verifies if the gate's secret in the database matches with the input secret
@app.route("/gates/verify", methods=['GET'])
def accessGate():
    secret = request.args.get("secret")
    # Checks if id variable is an int. If not raises an error
    try:
        gateID = int(request.args.get("gateID"))
    except ValueError:
        return headeredResponse(""), 500
    # Ckecks if the gate exists
    if not existsGate(gateID):
        return headeredResponse(False)
    # Gets the gate secret and compares it with input secret
    realSecret = getGate(gateID).get("secret")
    secretValidity = str(secret == realSecret).rstrip('\n')

    response = headeredResponse(secretValidity)
    return response     
################################

## Function to administration ##
# Endpoint that manages administrators requests
@app.route("/gates/admin",  methods=['GET', 'POST', 'DELETE'])
def administerGates():
    # Returns list of gates in the database
    if request.method == 'GET':
        response = listGates()
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response 

    # Adds a new gate to the database
    elif request.method == 'POST':
        # Checks if id variable is an int returns 400 code otherwise
        try:
            id = int(request.form["gateID"])
        except ValueError:
            abort(400)

        location = request.form["gateLocation"]
        # If gate doesn't exist, adds it to the database
        if not existsGate(id):
            secret = generateSecret()
            newGate(id, location, secret, 0,0)

            return headeredResponse("Secret: " + secret)
        # The gate with that id already exists
        else:
            return headeredResponse("Gate already exists")
    # Deletes a specific gate
    elif request.method == 'DELETE':
        # Cheks if id variable is an Int if not raises an error
        try:
            id = int(request.data)
        except ValueError:
            abort(400)
        # Checks if the gate exists
        if not existsGate(id):

            return headeredResponse("Gate does not exist")
        else:
            # If the gate exists it gets deleted
            deleteGate(id)
            return headeredResponse("Gate deleted")
    else:
        abort(405)

# Endpoint that registers an access to the gate
@app.route("/gates/access", methods=['POST'])
def gateAccess():
    gateID = request.args["gateID"]
    status = request.args["status"]
    time = request.args["time"]
    userCode = request.args["userCode"]

    if not existsGate(gateID):
        abort(404)

    return registerAccess(gateID, userCode, status, time)
    
if __name__ == "__main__":
    app.secret_key = service_secret
    app.run(host='127.0.0.1', port=8002, debug=True)