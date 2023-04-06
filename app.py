import json
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import flask
from message_helper import get_templated_message_input, get_text_message_input, send_message, send_quick_reply_message, send_pulse_survey
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
import time
import re



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
        
        # Obtain the company_id by user email
        company_id = get_company_id_by_email(user.email)
        if company_id:
            session['company_id'] = company_id
            print ("company id is: ",company_id)
        else:
            print("No se encontró el company_id para el usuario.")
        
        return flask.redirect(flask.url_for('catalog'))
    except Exception as e:
        print(e)
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)

def get_company_id_by_email(user_email):
    companies_ref = db.collection("companies")
    query = companies_ref.where("email", "==", user_email).limit(1)
    result = query.stream()
    
    for doc in result:
        return doc.id

    return None


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
    company_id = session.get('company_id')
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

@app.route('/survey-answers')
def survey_answers():
    # Reemplaza 'Companies' y 'survey answers' con los nombres de tus colecciones en Firestore
    companies_ref = db.collection('companies')
    company_id = session.get('company_id')
    if company_id is None:
        return "No se encontró el company_id en la sesión.", 400

    survey_answers_ref = companies_ref.document(company_id).collection('survey answers')
    survey_answers_data = survey_answers_ref.stream()

    survey_answers = []
    for doc in survey_answers_data:
        answer_data = doc.to_dict()
        answer_data['id'] = doc.id
        survey_answers.append(answer_data)

    return render_template('survey_answers.html', survey_answers=survey_answers)


@app.route('/surveys-sent')
def surveys_sent():
    # Reemplaza 'Companies' y 'surveys sent' con los nombres de tus colecciones en Firestore
    companies_ref = db.collection('companies')
    company_id = session.get('company_id')
    if company_id is None:
        return "No se encontró el company_id en la sesión.", 400

    surveys_sent_ref = companies_ref.document(company_id).collection('surveys sent')
    surveys_sent_data = surveys_sent_ref.stream()

    surveys_sent = []
    for doc in surveys_sent_data:
        survey_data = doc.to_dict()
        survey_data['id'] = doc.id
        surveys_sent.append(survey_data)

    return render_template('surveys_sent.html', surveys_sent=surveys_sent)

@app.route('/surveys')
def surveys():
    companies_ref = db.collection('companies')
    company_id = session.get('company_id')
    if company_id is None:
        return "No se encontró el company_id en la sesión.", 400

    pulse_surveys_ref = companies_ref.document(company_id).collection('pulse surveys')
    pulse_surveys_data = pulse_surveys_ref.stream()

    pulse_surveys = []
    for doc in pulse_surveys_data:
        survey_data = doc.to_dict()
        survey_data['id'] = doc.id
        pulse_surveys.append(survey_data)

    return render_template('surveys.html', pulse_surveys=pulse_surveys)



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

    try:
        await send_message(data)
        print(f"Access token: {config['ACCESS_TOKEN']}")
        print(f"Recipient waid: {config['RECIPIENT_WAID']}")
        print(company_id)

        await store_sent_survey(company_id, template_name, recipient_phone_number)
    except Exception as e:
        traceback.print_exc()
        print(f"Error sending message: {e}")
        print(f"Access token: {config['ACCESS_TOKEN']}")

    return flask.redirect(flask.url_for('catalog'))


@app.route("/send-to-employee/<int:employee_wa_id>", methods=['POST'])
async def send_to_employee(employee_wa_id):
    recipient_phone_number = employee_wa_id
    data = send_pulse_survey(recipient_phone_number)
    template_name = "pulse_survey_1"  # Replace with the actual template name
    company_id = session.get('company_id')

    try:
        for i in range(3):
            await send_message(data)
            print(f"Access token: {config['ACCESS_TOKEN']}")
            print(f"Recipient waid: {recipient_phone_number}")

            await store_sent_survey(company_id, template_name, recipient_phone_number)

            # Wait for one minute before sending the next message
            time.sleep(30)
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
                                if 'from' in message:
                                    sender = message['from']
                                    text = None
                                    if 'text' in message:
                                        text = message['text']['body']
                                    elif 'button' in message:
                                        text = message['button']['text']

                                    if text is not None:
                                        print(f'Mensaje recibido de {sender}: {text}')
                                        
                                        # Extract the name of the sender
                                        name = None
                                        company_id = None
                                        if '@' in text:
                                            match = re.search(r'@([a-zA-Z]+)\b', text)
                                            if match:
                                                company_id = match.group(1)
                                                print ("company id seteado")
                                            else
                                                print ("no match")
                                            if 'contacts' in value and len(value['contacts']) > 0:
                                                name = value['contacts'][0]['profile']['name']
                                                print ("nombre seteado")
                                            print ("arroba en texto")
                                        # Find the company ID by looking for an existing employee with the wa_id
                                        if name and company_id:
                                            store_employee(company_id, name, sender)
                                            print ("Guardando empleado")
                                        if company_id and text[0].isdigit():
                                            store_survey_answer(company_id, sender, text)
                                            print ("Guardando survey answer")
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

def store_employee(company_id, name, wa_id):
    # Reference to the company document and the employees collection
    company_ref = db.collection('companies').document(company_id)
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
    doc_ref = db.collection('companies').document(company_id).collection('survey answers')
    doc_ref.add({
        'wa_id': wa_id,
        'answer': answer
    })

@app.route('/update-pulse-survey', methods=['POST'])
def update_pulse_survey():
    company_id = request.form['company_id']
    survey_id = request.form['survey_id']
    activo = request.form.get('activo') == 'on'

    company_ref = db.collection('companies').document(company_id)
    survey_ref = company_ref.collection('pulse surveys').document(survey_id)

    survey_ref.update({
        'activo': activo
    })

    return redirect(url_for('surveys'))
