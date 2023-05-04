import json
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import flask
from message_helper import get_templated_message_input, get_text_message_input, send_message, send_quick_reply_message, send_pulse_survey
from flights import get_flights
import hmac
import hashlib
from config import config
import traceback
import firebase_admin
from firebase_admin import auth, credentials, firestore
from google.auth import load_credentials_from_file
import google.auth
from google.cloud import firestore
from google.oauth2 import service_account
from datetime import datetime
import time
import re
from builtins import sum




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
ACTIVATION_KEY = '123456789'

 
with open('config.json') as f:
    config = json.load(f)
app.config.update(config)
app.config['ACCESS_TOKEN'] = os.environ['ACCESS_TOKEN']


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("employees"))
    return render_template('index.html', name=__name__)
#
#
# BACK
# END
# FUNCTIONS
#
#
@app.route('/webhook-activador', methods=['POST'])
async def webhook_activador():
    # Obtén la llave y el ID del cuerpo de la solicitud
    request_data = request.get_json()
    key = request_data.get('key')
    company_id = request_data.get('id')

    # Verifica si la llave proporcionada coincide con la llave definida
    if key == ACTIVATION_KEY:  # Si utilizas la llave definida directamente en el código
        await send_to_all_employees(company_id)
        return jsonify({'status': 'success', 'message': 'La función send_to_all_employees fue ejecutada correctamente'})
    else:
        return jsonify({'status': 'error', 'message': 'La llave proporcionada no coincide con la llave definida'}), 403


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
    
import re

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
                                    unique_message_id = None
                                    sent_message_id = None
                                    if 'text' in message:
                                        text = message['text']['body']
                                        if 'context' in message:
                                            unique_message_id = message['context']['id']
                                    elif 'button' in message:
                                        text = message['button']['text']
                                        if 'id' in message:
                                            unique_message_id = message['id']
                                        if 'context' in message:
                                            sent_message_id = message['context']['id']
                                    
                                    if text is not None:
                                        print(f'Mensaje recibido de {sender}: {text}')
                                        
                                        # Extract the name of the sender
                                        name = None
                                        company_id = None
                                        if '@' in text:
                                            print("Encontró arroba en el texto")
                                            match = re.search(r'@(\S+)\b', text)
                                            if match:
                                                company_id = match.group(1)
                                                print("company id seteado:", company_id)
                                            else:
                                                print("No se encontró el company id")
                                            if 'contacts' in value and len(value['contacts']) > 0:
                                                name = value['contacts'][0]['profile']['name']
                                                print("nombre seteado:", name)
                                            else:
                                                print("No se pudo establecer el nombre")
                                            print("arroba en texto")
                                        else:
                                            print("No se encontró arroba en el texto")

                                        if name and company_id:
                                            store_employee(company_id, name, sender)
                                            print("Guardando empleado")
                                        else:
                                            print("No se pudo guardar el empleado")

                                        if text[0].isdigit() and sent_message_id:
                                            print("Guardando survey answer")
                                            print("sent_message_id =", sent_message_id)
                                            store_survey_answer(sender, text, sent_message_id)
                                        else:
                                            print("No se pudo guardar la respuesta de la encuesta")




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



def store_employee(company_id, name, wa_id):
    # Reference to the company document and the employees collection
    company_ref = db.collection('companies').document(company_id)
    employees_ref = company_ref.collection('employees')
    
    # Check if the company document exists
    if not company_ref.get().exists:
        return

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


def store_survey_answer(wa_id, answer, sent_message_id):
    companies_ref = db.collection('companies')
    company_id = None
    for company in companies_ref.stream():
        employees_ref = db.collection('companies').document(company.id).collection('employees').where('wa_id', '==', wa_id)
        for employee in employees_ref.stream():
            company_id = company.id
    if company_id is not None:
        doc_ref = db.collection('companies').document(company_id).collection('survey answers')
        doc_ref.add({
            'wa_id': wa_id,
            'answer': answer,
            'message_id' : sent_message_id
        })
        
        # Call pulse_survey_results function to store survey results
        pulse_survey_results(company_id, answer, sent_message_id)

    else:
        print(f"No se encontró el empleado con el wa_id {wa_id} en ninguna empresa")



def pulse_survey_results(company_id, answer, sent_message_id):
    company_ref = db.collection('companies').document(company_id)
    surveys_sent_ref = company_ref.collection('surveys sent').where('message_id', '==', sent_message_id).get()
    
    for survey_sent_doc in surveys_sent_ref:
        survey_sent = survey_sent_doc.to_dict()
        timestamp = datetime.now()
        score = int(answer[0])
        survey_results_ref = company_ref.collection('survey results')
        survey_results_ref.add({
            'template name': survey_sent['template_name'],
            'answer': answer,
            'message_id': sent_message_id,
            'timestamp': timestamp,
            'score': score
        })

def get_company_id_by_email(user_email):
    companies_ref = db.collection("companies")
    query = companies_ref.where("email", "==", user_email).limit(1)
    result = query.stream()
    
    for doc in result:
        return doc.id

    return None

#
#
# FRONT
# END
# FUNCTIONS
#
#

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

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
        
        return flask.redirect(flask.url_for('employees'))
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
        handle = request.form['handle']
        business_name = request.form['business_name']
        try:
            user = auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )
            create_business(handle, email, business_name)
            # Login the user
            user = auth.sign_in_with_email_and_password(email, password)
            session['user'] = user
            return redirect(url_for('employees'))
        except Exception as e:
            print(e)
            return "Error al registrar el usuario.", 400
    return render_template('register.html')


@app.route('/create-business', methods=['POST'])
def create_business(email, handle, business_name):
    handle = request.form['handle']
    email = request.form['email']
    business_name = request.form['business_name']
    
    # Check if handle already exists
    company_ref = db.collection('companies').document(handle)
    if company_ref.get().exists:
        flash('Handle already exists. Please choose a different one.', 'error')
        return redirect(url_for('index'))

    # Create document in companies collection
    company_data = {'email': email, 'business_name': business_name}
    company_ref.set(company_data)

    # Copy documents from 'pulse surveys' to new collection
    pulse_surveys_ref = db.collection('pulse surveys')
    new_collection_ref = company_ref.collection('pulse surveys')
    for survey_doc in pulse_surveys_ref.stream():
        survey_data = survey_doc.to_dict()
        new_collection_ref.document(survey_doc.id).set(survey_data)

    flash('Business created successfully!', 'success')
    return redirect(url_for('index'))


 

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


async def store_sent_survey(company_id, template_name, recipient_wa_id, message_id):
    if message_id:
        try:
            doc_ref = db.collection('companies').document(company_id).collection('surveys sent').document()
            doc_ref.set({
                'template_name': template_name,
                'recipient_wa_id': recipient_wa_id,
                'timestamp': datetime.utcnow(),
                'message_id': message_id
            })
            print(f"Stored sent survey for {recipient_wa_id} in company {company_id}")
        except Exception as e:
            print(f"Error storing sent survey: {e}")
    else:
        print("Message ID is empty, nothing to store.")


#@app.route("/send-to-employee/<int:employee_wa_id>/<company_id>", methods=['POST'])
async def send_to_employee(employee_wa_id, company_id):
    print("sending started for ", employee_wa_id)
    recipient_phone_number = employee_wa_id

    try:
        # Get the reference to the pulse surveys collection
        pulse_surveys_ref = db.collection('companies').document(company_id).collection('pulse surveys')
        pulse_surveys_data = pulse_surveys_ref.stream()
        print("surveys found")

        # Iterate over the documents in the collection to send a message for each survey
        for doc in pulse_surveys_data:
            pulse_survey_id = doc.id
            template_name = doc.get('template')
            active = doc.get('active')
            print("survey cicly initiated")

            if active:
                print(f"Pulse survey ID: {pulse_survey_id}, template name: {template_name}")
                
                data = send_pulse_survey(recipient_phone_number, template_name)
                print('sending: ', data)
                message_id = await send_message(data)
                await store_sent_survey(company_id, template_name, recipient_phone_number, message_id)
                print(f"Access token: {config['ACCESS_TOKEN']}")
                print(f"Recipient waid: {recipient_phone_number}")
                print(f"message_is: {message_id}")

                # Wait for one minute before sending the next message
                time.sleep(1)

        return jsonify({"status": "success", "message": "Mensajes enviados correctamente"})

    except Exception as e:
        traceback.print_exc()
        print(f"Error sending message: {e}")
        print(f"Access token: {config['ACCESS_TOKEN']}")
        return jsonify({"status": "error", "message": "Ha ocurrido un error al enviar los mensajes"})



async def send_to_all_employees(company_id):
    print("sending to all employees of ", company_id)
    employees_list = get_company_employees(company_id)
    for employee in employees_list:
        wa_id = employee['wa_id']
        print("sending to ", wa_id)
        await send_to_employee(wa_id, company_id)


