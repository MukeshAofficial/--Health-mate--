from flask import Flask, render_template, request, g
import openai
import PIL.Image
import textwrap
import os
from IPython.display import display, Markdown
import google.generativeai as genai
from collections import namedtuple
from datetime import datetime
import qrcode
from io import BytesIO
import base64
import sqlite3


app = Flask(__name__)

api_key1 = "API-KEY"
openai.api_key = api_key1


def to_markdown(text):
    text = text.replace('•', '  *')
    return Markdown(textwrap.indent(text, '> ', predicate=lambda _: True))

genai.configure(api_key="API_KEY")

model = genai.GenerativeModel('gemini-pro-vision')

@app.route('/recommend')
def recommend():
    return render_template('recommend.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return "No image uploaded"
    
    image = request.files['image']
    
    if image.filename == '':
        return "No selected file"
    
    img = PIL.Image.open(image)
    
    response = model.generate_content(["Based on the above injury image tell me some precautions and recommendations", img], stream=True)
    response.resolve()
    
    return render_template('rec-result.html', recommendation=response.text)



Doctor = namedtuple('Doctor', ['name', 'speciality', 'availability'])

doctors = [
    Doctor("Dr. Smith", "Cardiologist", "Monday, Wednesday, Friday"),
    Doctor("Dr. Johnson", "Dermatologist", "Tuesday, Thursday")
]

DATABASE = 'appointments.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/appointment', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        doctor_name = request.form['doctor']
        patient_name = request.form['patient']
        date = request.form['date']
        time = request.form['time']
        message, qr_code_data = book_appointment(doctor_name, patient_name, date, time)
        return render_template('appointment.html', doctors=doctors, message=message, qr_code_data=qr_code_data)
    return render_template('appointment.html', doctors=doctors)

def book_appointment(doctor_name, patient_name, date, time):
    doctor = next((doc for doc in doctors if doc.name == doctor_name), None)
    if doctor:
        appointment_date = datetime.strptime(date, "%Y-%m-%d").date()
        conn = get_db()
        c = conn.cursor()
        existing_appointments = c.execute('''SELECT * FROM appointments 
                                             WHERE doctor=? AND date=? AND time=?''', 
                                             (doctor_name, date, time)).fetchall()
        if existing_appointments:
            return "Appointment slot already booked. Available timings for this day.", None
        else:
            c.execute('''INSERT INTO appointments (doctor, patient, date, time) 
                         VALUES (?, ?, ?, ?)''', (doctor_name, patient_name, date, time))
            conn.commit()
            qr_code_data = generate_qr_code(patient_name, date, time)
            return "Appointment booked successfully!", qr_code_data
    else:
        return "Doctor not found.", None

def generate_qr_code(patient_name, date, time):
    data = f"Patient: {patient_name}\nDate: {date}\nTime: {time}"
    qr = qrcode.make(data)
    qr_bytes = BytesIO()
    qr.save(qr_bytes)
    qr_bytes.seek(0)
    qr_b64 = base64.b64encode(qr_bytes.read()).decode('utf-8')
    return qr_b64


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/consultation')
def consult():
    return render_template('consultation.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/pay')
def pay():
    # In a real application, you would retrieve the recipient address from a database or another secure source
    recipient_address = '0x3F3329F5B4280130a09b0d8FBE330d445AbF1F67'
    return render_template('pay.html', recipient_address=recipient_address)

@app.route('/medicines')
def medicines():
    return render_template('medicines.html')

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/ask', methods=['POST'])
def ask_question():
    user_question = request.form['question']

    # Generate response from OpenAI's GPT-3.5 model
    prompt = f"Answer for my question in short: {user_question}"
    completion = openai.Completion.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=150,
        stop=None,
        temperature=0.7
    )
    chatgpt_response = completion.choices[0].text.strip()

    return chatgpt_response

def generate_nutrition_plan(calories):
    # Define the prompt
    prompt = f"Generate a nutrition plan for {calories} calories per day."

    # Generate the completion
    completion = openai.Completion.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=350
    )

    # Extract and return the response
    return completion.choices[0].text.strip()

@app.route('/nutrition', methods=['GET', 'POST'])
def nutri():
    if request.method == 'POST':
        age = request.form['age']
        gender = request.form['gender']
        height_cm = request.form['height_cm']
        weight_kg = request.form['weight_kg']
        activity_level = request.form['activity_level']

        # Calculate BMR
        if gender == "Male":
            bmr = 10 * float(weight_kg) + 6.25 * float(height_cm) - 5 * float(age) + 5
        elif gender == "Female":
            bmr = 10 * float(weight_kg) + 6.25 * float(height_cm) - 5 * float(age) - 161

        # Calculate daily calorie requirements based on activity level
        activity_levels = {"Sedentary": 1.2, "Lightly active": 1.375, "Moderately active": 1.55, "Very active": 1.725, "Extra active": 1.9}
        calories = bmr * activity_levels[activity_level]

        # Generate nutrition plan
        nutrition_plan = generate_nutrition_plan(calories)

        return render_template('nutri-result.html', nutrition_plan=nutrition_plan)
    
    return render_template('nutri.html')


if __name__ == '__main__':
    app.run(debug=True)