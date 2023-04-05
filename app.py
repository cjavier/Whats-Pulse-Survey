import json
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import flask
from message_helper import get_templated_message_input, get_text_message_input, send_message, send_quick_reply_message
from flights import get_flights
import hmac
import hashlib
from config import config
import traceback
import firebase_admin
from firebase_admin import auth, credentials
from google.auth import load_credentials_from_file
import google.auth
from google.cloud import firestore
from google.oauth2 import service_account
from datetime import datetime


cred_file_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

# Utiliza el archivo JSON para crear el objeto Certificate
cred = credentials.Certificate(cred_file_path)

# Inicializa Firebase
firebase_admin.initialize_app(cred)

# Autentica y crea el cliente de Firestore
# Carga las credenciales de google-auth
creds, _ = google.auth.load_credentials_from_file(cred_file_path)

# Inicializa el cliente de Firestore con las credenciales de google-auth
db = firestore.Client(credentials=creds)



app = Flask(__name__)
app.secret_key = 'asdf93kasf83q98ccqh9'  # Reemplaza con una clave secreta para proteger las sesiones.
 
with open('config.json') as f:
    config = json.load(f)
app.config.update(config)
app.config['ACCESS_TOKEN'] = os.environ['ACCESS_TOKEN']

@app.route("/")
def index():
    return render_template('index.html', name=__name__)

@app.route("/welcome")
def welcome():
    return render_template('welcome.html')

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
 

@app.route('/employees')
def employees():
    company_id = 'eWLE0uvjozhAAq5giKIA'  # Replace this with the actual company ID
    employees = get_company_employees(company_id)
    return render_template('employees.html', employees=employees)

def get_company_employees(company_id):
    db = firestore.Client()
    employees_ref = db.collection('companies').document(company_id).collection('employees')
    employees = employees_ref.stream()

    employees_list = []
    for employee in employees:
        employees_list.append(employee.to_dict())

    return employees_list


@app.route("/catalog")
def catalog():
    return render_template('catalog.html', title='Flight Confirmation Demo for Python', flights=get_flights())

async def store_sent_survey(company_id, template_name, recipient_wa_id):
    try:
        doc_ref = db.collection('companies').document(company_id).collection('surveys sent').document()
        doc_ref.set({
            'template_name': template_name,
            'recipient_wa_id': recipient_wa_id,
            'timestamp': datetime.utcnow()
        })
        print(f"Stored sent survey for {recipient_wa_id} in company {company_id}")
    except Exception as e:
        print(f"Error storing sent survey: {e}")

@app.route("/buy-ticket", methods=['POST'])
async def buy_ticket():
    recipient_phone_number = app.config['RECIPIENT_WAID']
    data = send_quick_reply_message(recipient_phone_number)
    template_name = "quick_reply_template"  # Replace with the actual template name
    company_id = "eWLE0uvjozhAAq5giKIA"  # Replace with the actual company ID

    try:
        await send_message(data)
        print(f"Access token: {config['ACCESS_TOKEN']}")
        print(f"Recipient waid: {config['RECIPIENT_WAID']}")

        await store_sent_survey(company_id, template_name, recipient_phone_number)
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
                                    # Find the company ID by looking for an existing employee with the wa_id
                                    company_id = find_company_id_by_wa_id(sender)
                                    print("name extracted")
                                    if company_id is None:
                                        print("company id not found")
                                        # Code to handle when the wa_id is not found in any company
                                        # Check if the text contains a company ID preceded by '@'
                                        company_id = None
                                        at_index = text.find('@')
                                        if at_index != -1:
                                            company_id_candidate = text[at_index + 1:]
                                            if company_id_candidate.isalnum():  # Check if the string after '@' is alphanumeric
                                                company_id = company_id_candidate
                                        # Call store_employee_message to store the sender's information
                                        if name and company_id:
                                            store_employee_message(company_id, name, sender)

                                    # Code to handle when the wa_id is found or not found, and the company_id is available
                                    if company_id:
                                        store_survey_answer(company_id, sender, text)
                                    
                                else:
                                    print('No se pudo procesar el mensaje:', message)



def find_company_id_by_wa_id(wa_id):
    db = firestore.Client()
    companies_ref = db.collection('companies')
    companies = companies_ref.stream()

    for company in companies:
        company_id = company.id
        employees_ref = db.collection('companies').document(company_id).collection('employees')
        employees = employees_ref.where('wa_id', '==', wa_id).stream()

        for employee in employees:
            return company_id

    return None


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

def store_survey_answer(company_id, wa_id, answer):
    db = firestore.Client()
    doc_ref = db.collection('companies').document(company_id).collection('survey_answers')
    doc_ref.add({
        'wa_id': wa_id,
        'answer': answer
    })