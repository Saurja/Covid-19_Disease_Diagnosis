import os
import requests
import csv
import numpy as np
from skimage import io
import torch
import torchvision.models 
from PIL import Image
from torchvision import transforms




# Flask utils
from flask import Flask, redirect, url_for, request, render_template
from werkzeug.utils import secure_filename
from gevent.pywsgi import WSGIServer

# Define a flask app
app = Flask(__name__)

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


@app.route('/', methods=['GET'])
def index():
    # Main page
    return render_template('index.html')


@app.route('/predict', methods=['GET', 'POST'])
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

        # Print result in Webpage
        print('Prediction:', disease_class[ind],' Confidence: ',a.numpy()) 
        result=disease_class[ind] + " | Confidence : " + str(a.numpy()) + " | Location : " + response.json()['region']

        # Save in Database
        if disease_class[ind] == 'Covid':
            import sqlite3 as sl
            con = sl.connect('locationHistory.db')
            with con:
                con.execute("UPDATE LocationHistory SET CovidCases = CovidCases + 1 WHERE State = (?)", [curLoc])
                con.commit()
        
        return result
    return None


if __name__ == '__main__':
    # app.run(port=5002, debug=True)

    # Serve the app with gevent
    http_server = WSGIServer(('', 5000), app)
    http_server.serve_forever()
    app.run()
