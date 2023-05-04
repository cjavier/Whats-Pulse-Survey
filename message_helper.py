import aiohttp
import json
from flask import current_app

async def send_message(data):
    session = aiohttp.ClientSession()
    
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }
    
    url = 'https://graph.facebook.com' + f"/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
    try:
        async with session.post(url, data=data, headers=headers) as response:
            if response.status == 200:
                print("Status:", response.status)
                print("Content-type:", response.headers['content-type'])

                json_response = await response.json()
                message_id = json_response['messages'][0]['id']
                print("Message ID:", message_id)
                return message_id
            else:
                print(response.status)        
                print(response)        
    except aiohttp.ClientConnectorError as e:
        print('Connection Error', str(e))
    finally:
        await session.close()

# Rest of the code remains the same

def get_text_message_input(recipient, text):
  return json.dumps({
    "messaging_product": "whatsapp",
    "preview_url": False,
    "recipient_type": "individual",
    "to": recipient,
    "type": "text",
    "text": {
        "body": text
    }
  })
  
def get_templated_message_input(recipient, flight):
  return json.dumps(
    {
    "messaging_product": "whatsapp",
    "to": recipient,
    "type": "template",
    "template": {
        "name": "hello_world",
        "language": {
            "code": "en_US"
        }
    }
}
  )

def send_quick_reply_message(to_phone_number):
    return json.dumps(
    {
   "messaging_product": "whatsapp",
   "to": to_phone_number,
   "type": "template",
   "template": {
       "name": "sample_issue_resolution",
       "language": {
           "code": "en_US",
           "policy": "deterministic"
       },
       "components": [
           {
               "type": "body",
               "parameters": [
                   {
                       "type": "text",
                       "text": "*Mr. Jones*"
                   }
               ]
           },
           {
               "type": "button",
               "sub_type": "quick_reply",
               "index": 0,
               "parameters": [
                   {
                       "type": "text",
                       "text": "Yes"
                   }
               ]
           },
           {
               "type": "button",
               "sub_type": "quick_reply",
               "index": 1,
               "parameters": [
                   {
                       "type": "text",
                       "text": "No"
                   }
               ]
           }
       ]
   }
}
  )
async def close_session():
    await session.close()

def send_pulse_survey(to_phone_number, template_name):
    return json.dumps(
    {
   "messaging_product": "whatsapp",
   "to": to_phone_number,
   "type": "template",
   "template": {
       "name": template_name,
       "language": {
           "code": "es_MX",
           "policy": "deterministic"
       },
       "components": [
           {
               "type": "body",
               "parameters": [
                   {
                       "type": "text",
                       "text": "impactum"
                   }
               ]
           },
           {
               "type": "button",
               "sub_type": "quick_reply",
               "index": 0,
               "parameters": [
                   {
                       "type": "text",
                       "text": "Yes"
                   }
               ]
           },
           {
               "type": "button",
               "sub_type": "quick_reply",
               "index": 1,
               "parameters": [
                   {
                       "type": "text",
                       "text": "No"
                   }
               ]
           }
       ]
   }
}
  )