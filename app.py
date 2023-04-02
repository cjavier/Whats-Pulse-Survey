import json
from flask import Flask, render_template
import flask
from message_helper import get_text_message_input, send_message
 
app = Flask(__name__)
 
with open('config.json') as f:
    config = json.load(f)
 
app.config.update(config)
 
@app.route("/")
def index():
    return render_template('index.html', name=__name__)
 
@app.route('/welcome', methods=['POST'])
async def welcome():
  data = get_text_message_input(app.config['RECIPIENT_WAID']
                                , 'Welcome to the Flight Confirmation Demo App for Python!');
  await send_message(data)
  return flask.redirect(flask.url_for('index'))