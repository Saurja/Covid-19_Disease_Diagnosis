import os
import requests
import csv
import traceback
import random
import string
import datetime
import sqlite3 as sql
import numpy as np
from skimage import io
import torch
import torchvision.models 
from PIL import Image
from torchvision import transforms
from models import UserModel,db,login

# Flask utils
from flask import Flask, redirect, url_for, request, render_template
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from gevent.pywsgi import WSGIServer

# Define a flask app
app = Flask(__name__)
app.secret_key = 'xyz'

# Code to create the database file before the first user request itself
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
@app.before_first_request
def create_table():
    db.create_all()

db.init_app(app)
login.init_app(app)
login.login_view = 'login'
 
@app.before_first_request
def create_all():
    db.create_all()

# Loading Saved model
model =torch.load('./SavedModel/CovidModelv1')
model.eval()

preprocess = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
def decode_img(x):
    input_image = Image.open(x)
    input_image = input_image.convert('RGB')
    input_tensor = preprocess(input_image)
    return input_tensor

def model_predict(img_path, model):
    img = decode_img(img_path)
    with torch.no_grad():
        preds = model(img.unsqueeze(0))
        return preds

# Route to Login Page
@app.route('/login', methods = ['POST', 'GET'])
def login():
    if current_user.is_authenticated:
        return redirect('/')
     
    if request.method == 'POST':

        req = request.form
        req = req.to_dict(flat=True)
        email = req['email']

        user = UserModel.query.filter_by(email = email).first()
        if user is not None and user.check_password(req['password']):
            print("Loggin in with: " + email + " " + req['password'])
            login_user(user)
            return redirect('/')
    return render_template('login.html')

# Route to Home Page
@app.route('/', methods=['GET'])
@login_required
def index():
    return render_template('index.html')

# Route to Register Page
@app.route('/register', methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        return redirect('/')
     
    if request.method == 'POST':

        req = request.form
        req = req.to_dict(flat=True)

        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        print(email)
        if UserModel.query.filter_by(email=email).first():
            return ('Email already Present')
             
        user = UserModel(email=email, username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return redirect('/login')
    return render_template('register.html')

# Route to Logout Page
@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')

# Route to Predict Result
@app.route('/predict', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        # Get the file from post request
        f = request.files['file']

        # Save the file to ./uploads
        basepath = os.path.dirname(__file__)
        file_path = os.path.join(
            basepath, 'uploads', secure_filename(f.filename))
        f.save(file_path)

        # Make prediction
        preds = model_predict(file_path, model)
        # x = x.reshape([64, 64]);
        disease_class = ['Non Covid','Covid']
        a = preds[0][0]
        ind= 0 if a <=0.5 else 1

        # Api request to get location data
        response = requests.get("https://ipinfo.io/json?token=6c70431184a111")
        curLoc = response.json()['region']

        # Save in Database
        if disease_class[ind] == 'Covid':
            con = sql.connect('locationHistory.db')
            with con:
                con.execute("UPDATE LocationHistory SET CovidCases = CovidCases + 1 WHERE State = (?)", [curLoc])
                con.commit()
        
        # Save data in from
        req = request.form
        req = req.to_dict(flat=True)
        try:
            patientName = req['patientName']
            patientMobile = req['patientMobile']
            patientAge = req['patientAge']
            patientGender = req['patientGender']
            reportDate =  datetime.datetime.now()
            patientResult = disease_class[ind]

            # Generate Client ID
            # printing uppercase
            letters = string.ascii_uppercase
            ClientID = ''.join(random.choice(letters) for i in range(16))
            con = sql.connect('patientData.db')
            with con:
                cur = con.cursor()
                cur.execute("INSERT INTO PatientRecords (Name,Mobile,Age,GENDER,Date,Result,ClientID) VALUES (?,?,?,?,?,?,?)",(patientName,patientMobile,patientAge,patientGender,reportDate,patientResult,ClientID) )
                con.commit()
                print("Record successfully added")
        except Exception as exception:
            con.rollback()
            traceback.print_exc()
        finally:
            con.close()
        
        # Print result in Webpage
        #print('Prediction:', disease_class[ind],' Confidence: ',a.numpy()) 
        result=disease_class[ind] + " | Confidence: " + str(a.numpy()) + " | Location: " + response.json()['region'] + " | ClientID: " +ClientID

        return result
    return None

# Route to Charts Page
@app.route("/chart", methods=['GET'])
@login_required
def chart():
    
    # Fetch data from SQL Server
    con = sql.connect('locationHistory.db')
    cursor = con.cursor()
    cursor.execute("SELECT * from LocationHistory")
    data=cursor.fetchall()
    con.close()
    

    legend = 'Covid-19 Cases Detected So Far'
    labels = [elt[1] for elt in data]
    values = [elt[2] for elt in data]

    # creating sum_list function
    def sumOfList(list, size):
        if (size == 0):
            return 0
        else:
            return list[size - 1] + sumOfList(list, size - 1)
    
    # Driver code    
    total = sumOfList(values, len(values))
 


    return render_template('chart.html', values=values, labels=labels, legend=legend, total=total)

# Route to Patient Data Page
@app.route('/patientData', methods=['GET'])
@login_required
def patientData():
    # Fetch data from SQL Server
    try:
        con = sql.connect('patientData.db')
        cursor = con.cursor()

        # Fetch Data Values
        cursor.execute("SELECT * from PatientRecords ORDER BY Date DESC LIMIT 10")
        data=cursor.fetchmany(10)
        # Fetch Column Names
        cursor.execute("SELECT * FROM PatientRecords")
        labels = [tuple[0] for tuple in cursor.description]
    except:
        print("Error! Data Fetch Failed")
    finally:
        con.close()

    return render_template('patientData.html', data = data, labels=labels)

# Route to About Page
@app.route('/about', methods=['GET'])
@login_required
def about():
    # Main page
    return render_template('about.html')

if __name__ == '__main__':
    # app.run(port=5002, debug=True)

    # Serve the app with gevent
    http_server = WSGIServer(('', 5000), app)
    http_server.serve_forever()
    app.run()
