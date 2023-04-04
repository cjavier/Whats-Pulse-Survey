import json
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import flask
from message_helper import get_templated_message_input, get_text_message_input, send_message
from flights import get_flights
import hmac
import hashlib
from config import config
import traceback
import firebase_admin
from firebase_admin import auth, credentials
import google.auth
from google.cloud import firestore
from google.oauth2 import service_account



cred_dict = {
  "type": "service_account",
  "project_id": os.environ["PROJECT_ID"],
  "private_key_id": os.environ["PRIVATE_KEY_ID"],
    "private_key": os.environ["PRIVATE_KEY"].replace('\\n', '\n'),
    "client_email": os.environ["CLIENT_EMAIL"],
  "client_id": "115853760336082885268",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-ukg3l%40whats-pulse-survey.iam.gserviceaccount.com"
}
 
cred = credentials.Certificate(cred_dict)  # Reemplaza con la ruta al archivo de clave privada de Firebase.
firebase_admin.initialize_app(cred)

# Autentica y crea el cliente de Firestore
# Crea las credenciales a partir del diccionario
credentials = service_account.Credentials.from_service_account_info(cred_dict)
# Inicializa el cliente de Firestore
db = firestore.Client(credentials=credentials, project=credentials.project_id)


app = Flask(__name__)
app.secret_key = 'asdf93kasf83q98ccqh9'  # Reemplaza con una clave secreta para proteger las sesiones.
 
with open('config.json') as f:
    config = json.load(f)
app.config.update(config)
app.config['ACCESS_TOKEN'] = os.environ['ACCESS_TOKEN']

@app.route("/")
def index():
    return render_template('index.html', name=__name__)

#google firebase autentication
@app.route('/login', methods=['POST'])
def login():
    token = request.form.get('idtoken')
    if not token:
        print("Token vacío")
        return redirect(url_for('index'))
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        user = auth.get_user(uid)
        session['user_id'] = user.uid
        return flask.redirect(flask.url_for('catalog'))
    except Exception as e:
        print(e)
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)

#google firebase create new users
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        display_name = request.form['display_name']
        try:
            user = auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )
            return f"Usuario registrado con éxito: {user.uid}"
        except Exception as e:
            print(e)
            return "Error al registrar el usuario.", 400
    return render_template('register.html')
 
 
@app.route('/welcome', methods=['POST'])
async def welcome():
    data = get_text_message_input(app.config['RECIPIENT_WAID'], 'Welcome to the Flight Confirmation Demo App for Python!')
    try:
        await send_message(data)
    except Exception as e:
        traceback.print_exc()
        print(f"Error sending message: {e}")
    return flask.redirect(flask.url_for('catalog'))


@app.route("/catalog")
def catalog():
    return render_template('catalog.html', title='Flight Confirmation Demo for Python', flights=get_flights())

@app.route("/buy-ticket", methods=['POST'])
async def buy_ticket():
  flight_id = int(request.form.get("id"))
  flights = get_flights()
  flight = next(filter(lambda f: f['flight_id'] == flight_id, flights), None)
  data = get_templated_message_input(app.config['RECIPIENT_WAID'], flight)

  try:
      await send_message(data)
      print(f"Access token: {config['ACCESS_TOKEN']}")
      print(f"Recipient waid: {config['RECIPIENT_WAID']}")
  except Exception as e:
      traceback.print_exc()
      print(f"Error sending message: {e}")
      print(f"Access token: {config['ACCESS_TOKEN']}")

  
  return flask.redirect(flask.url_for('catalog'))

def handle_whatsapp_messages(message_data):
    if 'entry' in message_data:
        entries = message_data['entry']
        for entry in entries:
            if 'changes' in entry:
                changes = entry['changes']
                for change in changes:
                    if 'value' in change:
                        value = change['value']
                        if 'messages' in value:
                            messages = value['messages']
                            for message in messages:
                                if 'from' in message and 'text' in message:
                                    sender = message['from']
                                    text = message['text']['body']
                                    print(f'Mensaje recibido de {sender}: {text}')
                                    
                                    # Extract the name of the sender
                                    name = None
                                    if 'contacts' in value and len(value['contacts']) > 0:
                                        name = value['contacts'][0]['profile']['name']

                                    # Call store_employee_message to store the sender's information
                                    if name:
                                        company_id = 'eWLE0uvjozhAAq5giKIA'  # Replace this with the actual company ID
                                        store_employee_message(company_id, name, sender)
                                else:
                                    print('No se pudo procesar el mensaje:', message)

#@app.route('/webhook', methods=['GET'])
#def webhook_verification():
#    if request.args.get('hub.verify_token') == '12345':
#        return request.args.get('hub.challenge')
#    return "Error verifying token"

@app.route('/webhook', methods=['POST'])
def webhook_verification():
    message_data = request.get_json()
    print(f'Message data: {message_data}')  # Agrega esta línea para imprimir los datos del mensaje
    handle_whatsapp_messages(message_data)
    return "ok"

def store_employee_message(company_id, name, wa_id):
    # Reference to the company document and the employees collection
    company_ref = db.collection('companies').document("eWLE0uvjozhAAq5giKIA")
    employees_ref = company_ref.collection('employees')
    
    # Check if an employee with the given wa_id already exists
    existing_employee = employees_ref.where('wa_id', '==', wa_id).stream()

    # If the employee exists, we don't want to add them again, so just return
    for employee in existing_employee:
        return
    
    # If the employee does not exist, create a new employee document
    new_employee = {
        'name': name,
        'wa_id': wa_id
    }

    # Add the new employee document to the employees collection
    employees_ref.add(new_employee)