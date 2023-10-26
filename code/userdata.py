from datetime import datetime
from flask.helpers import make_response
from flask.templating import render_template
import requests
from sqlalchemy import Column, Integer, String, DateTime, PickleType, create_engine
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


from os import path

import pickle

from flask import Flask, request, jsonify, abort,json

from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import Date

service_secret = "zQXtf6TcSmKHwrY8pry2VWNJ"

#### SLQ access layer initialization ####
DATABASE_FILE = "database_inter.sqlite"
db_exists = False
if path.exists(DATABASE_FILE):
    db_exists = True
    print("\t database already exists")

engine = create_engine('sqlite:///%s'%(DATABASE_FILE), echo=False, connect_args={'check_same_thread': False}) #echo = True shows all SQL

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String)
    userCode = Column(String)
    # Date at which the code was generated
    codeTimeStamp = Column(DateTime)
    # Column of PickleTypes each containing a list with the accesses
    # The accesses are strings with the location and time of access
    accesses = Column(MutableList.as_mutable(PickleType)) ## dictionary
    
    # Function to serialize data into dictionary
    def to_dictionary(self):
        return {"id": self.id, "username": self.username, "accesses": self.accesses,"usercode":self.userCode,"codetimestamp":self.codeTimeStamp}

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

app = Flask(__name__)

##### APP functions #####
# Check if the presented code is valid according to the database
def checkCode(code):

    # Check if the code belongs to any user in the database
    user = session.query(User).filter_by(userCode = code).first()
    if user == None:
        return jsonify("False")

    codeTime = user.codeTimeStamp
    response = user.userCode

    # if 60 seconds have passed since the code was generated, code is valid
    # Check code equality twice just to be sure
    if response == str(code):
        time = datetime.now() - codeTime
        if time.total_seconds() < 60:
            return jsonify("True")
        else:
                return jsonify("False")
    else:
        return jsonify("False")

# Gets the user's access list
def accessList(userID):
    if not existsUser(userID):
        print(userID)
        abort(404)

    user = session.query(User).filter_by(username = userID).first()

    response = user.accesses
    if response == None:
        return jsonify("ERRO")
    
    return jsonify(response)

# If the user doesn't exist, adds him to the database with the generated code.
# If he does exist, updates his code to the newly generated one
def updateCode(username, qrcode):

    if existsUser(username):
        user = session.query(User).filter_by(username = username).first()
        user.userCode = qrcode
        user.codeTimeStamp = datetime.now()
        try:
            session.commit()
            return True
        except:
            session.rollback()
            return False
    else:
        user = User(username = username , userCode = qrcode, codeTimeStamp = datetime.now())
        session.add(user)
        try:
            session.commit()
            return True
        except:
            session.rollback()
            return False

def existsUser(username):
    return bool(session.query(User).filter_by(username = username).first())
################

@app.route("/")
def index():
    abort(404)

# Endpoint to handle the user's access to the user app, requesting a QR code
@app.route("/users/access", methods=["POST"])
def registerAccess():
    secret = request.args["secret"]
    #Authenticate service
    if secret != service_secret:   
        abort(401)

    username = request.args["username"]
    userCode = request.args["userCode"]

    response = updateCode(username, userCode)
    if response:
        return ""
    else:
        abort(500)

# Endpoint to check the validity of a code according to the database
@app.route("/users/code", methods=["GET"])
def validateCode():
    secret = request.args["secret"]
    #Authenticate service
    if secret != service_secret:   
        abort(401)

    code = request.args["code"]

    return checkCode(code)

# Endpoint that returns the user's access list
@app.route("/users/history/view")
def getHistory():
    secret = request.args["secret"]
    #Authenticate service
    if secret != service_secret:   
        abort(401)

    username = request.args["username"]

    return accessList(username)

# Endpoint to update the user's access list when a new access happens
@app.route("/users/history/update", methods=["POST"])
def updateHistory():

    secret = request.args["secret"]
    #Authenticate service
    if secret != service_secret:   
        abort(401)

    location = request.args["location"]
    timeStamp = request.args["time"]
    userCode = request.args["userCode"]

    # Get the respective user
    user = session.query(User).filter_by(userCode = userCode).first()
    if user is None:
        return False
    history = user.accesses

    # Access format is location: "location" -> time: "time"
    access = "location: " + location + "-> time: " + str(timeStamp)

    # If there haven't been any accesses yet, create access list, else append access to list
    if history == None:
        history = []
        history.append(access)
        user.accesses = history
    else:
        history.append(access)
        user.accesses = history

    try:
        session.commit()
    except:
        session.rollback()
        abort(500)

    return "success"

    

if __name__ == "__main__":
    app.secret_key = service_secret
    app.run(host='127.0.0.1', port=8001, debug=True)