from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from flask_mysqldb import MySQL
import MySQLdb.cursors
import pickle
import os
import nltk
import pdfkit
from objective import ObjectiveTest
from subjective import SubjectiveTest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('wordnet')

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # Set your MySQL password here
app.config['MYSQL_DB'] = 'mydatabase'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

REFERENCE_FILE = "reference_answers.txt"

mysql = MySQL(app)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    message = ''
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        username = request.form['username']
        email = request.form['email'] 
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            message = 'Username already exists! Please enter a different one.'
        else:
            cursor.execute('INSERT INTO users (first_name, last_name, username, email, password) VALUES (%s, %s, %s, %s, %s)',
                           (first_name, last_name, username, email, password))
            mysql.connection.commit()
            cursor.close()
            return redirect(url_for('login'))

        cursor.close()
    return render_template('signup.html', message=message)


@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()
        cursor.close()
        
        if user:
            session['loggedin'] = True
            session['username'] = user['username']
            session['first_name'] = user['first_name']  # ✅ This line is what was missing
            return redirect(url_for('user_dashboard'))
        else:
            message = 'Invalid username or password!'
    return render_template('login.html', message=message, forgot_password_url=url_for('forgot_password'))

@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    username = session['username']
    message = ''
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        profile_image = request.files.get('profile_image')

        if profile_image and profile_image.filename:
            filename = secure_filename(profile_image.filename)
            image_folder = 'static/profile_images'
            os.makedirs(image_folder, exist_ok=True)
            image_path = os.path.join(image_folder, filename)
            profile_image.save(image_path)

            relative_path = os.path.join('profile_images', filename)

            cursor.execute("""
                UPDATE users
                SET first_name=%s, last_name=%s, email=%s, profile_image=%s
                WHERE username=%s
            """, (first_name, last_name, email, relative_path, username))

            session['profile_image'] = relative_path  # ✅ Save to session
        else:
            cursor.execute("""
                UPDATE users
                SET first_name=%s, last_name=%s, email=%s
                WHERE username=%s
            """, (first_name, last_name, email, username))

        mysql.connection.commit()
        cursor.close()

        session['first_name'] = first_name
        message = 'Profile updated successfully!'

        return render_template('update_profile.html',
                               message=message,
                               first_name=first_name,
                               last_name=last_name,
                               email=email,
                               profile_image=url_for('static', filename=session.get('profile_image', 'profile_images/default.png')))

    # GET request
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()

    # Store image in session for navbar use
    # session['profile_image'] = user.get('profile_image', 'profile_images/default.png')
    session['profile_image'] = user.get('profile_image') or 'profile_images/default.png'

    return render_template('update_profile.html',
                           message=message,
                           first_name=user['first_name'],
                           last_name=user['last_name'],
                           email=user['email'],
                           profile_image=url_for('static', filename=session.get('profile_image', 'profile_images/default.png')))

                        #    url_for('static', filename=session['profile_image']))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_user_by_id(session['user_id'])  # Your database fetch logic
    profile_image = user.get("profile_image") or url_for('static', filename='default_profile.png')

    return render_template('user_dashboard.html',
                           first_name=user['first_name'],
                           profile_image=profile_image)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    message = ''
    if request.method == 'POST':
        email = request.form['email']
        new_password = request.form['new_password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()

        if user:
            cursor.execute('UPDATE users SET password = %s WHERE email = %s', (new_password, email))
            mysql.connection.commit()
            message = 'Password has been successfully reset!'
        else:
            message = 'No user found with this email!'
        cursor.close()

    return render_template('forgot_password.html', message=message)


@app.route('/user_dashboard', methods=['GET'])
def user_dashboard():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE username = %s", (session['username'],))
        user = cursor.fetchone()
        cursor.close()

        session['profile_image'] = user.get('profile_image') or 'profile_images/default.png'
        return render_template('user_dashboard.html',
                               first_name=user['first_name'],
                               profile_image=url_for('static', filename=session['profile_image']))
    return redirect(url_for('login'))


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'loggedin' in session:
        if request.method == 'POST':
            file = request.files['file']
            if file:
                filepath = os.path.join('static/uploads', file.filename)
                file.save(filepath)
                session['uploaded_file'] = filepath
                return redirect(url_for('train_model'))
        return render_template('upload.html')#upload.html
    return redirect(url_for('login'))

# @app.route('/train_model', methods=['GET', 'POST'])
# def train_model():
#     if 'loggedin' in session and 'uploaded_file' in session:
#         if request.method == 'POST':
#             model = pickle.load(open('AI_model.pkl', 'rb'))  # Replace with real training logic if needed
#             return " Model Trained Successfully"  # Used by frontend to detect success

#         if request.headers.get("X-Requested-With") == "XMLHttpRequest":
#             return render_template('partials/train_model_form.html')

#         return render_template('train_model.html')
#     return redirect(url_for('login'))

@app.route('/train_model', methods=['GET', 'POST'])
def train_model():
    if 'loggedin' in session and 'uploaded_file' in session:
        if request.method == 'POST':
            model = pickle.load(open('AI_model.pkl', 'rb'))  # Replace with real training logic if needed
            return '', 204  # ✅ Return empty success response (no message)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render_template('partials/train_model_form.html')

        return render_template('train_model.html')
    return redirect(url_for('login'))


@app.route('/question_generation', methods=['GET', 'POST'])
def question_generation():
    if request.method == "POST":
        inputText = request.form.get("itext")
        testType = request.form.get("test_type")
        noOfQues = request.form.get("noq")

        if testType == "objective":
            objective_generator = ObjectiveTest(inputText, noOfQues)
            question_list, answer_list = objective_generator.generate_test()
        elif testType == "subjective":
            subjective_generator = SubjectiveTest(inputText, noOfQues)
            question_list, answer_list = subjective_generator.generate_test()
        else:
            flash("Invalid test type selected!", "error")
            return redirect(url_for('question_generation'))

        testgenerate = zip(question_list, answer_list)
        return render_template('generatedtestdata.html', cresults=testgenerate)

    return render_template('index.html')

@app.route("/eval_upload", methods=["GET", "POST"])
def eval_upload():
    if request.method == "POST":
        file = request.files["file"]
        if file:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(file_path)
            with open(file_path, "r",encoding='iso-8859-1') as f:
                student_answer = f.read().strip()
            reference_answer = load_reference_answer()
            score = calculate_similarity(student_answer, reference_answer)
            return render_template("result.html", student_answer=student_answer, reference_answer=reference_answer, score=score)
    return render_template("eval_ans_upload.html")

import pdfkit

config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")

@app.route("/download")
def download_result():
    student_answer = request.args.get("student_answer", "No answer provided.")
    reference_answer = request.args.get("reference_answer", "Reference answer not found.")
    score = request.args.get("score", "0")

    rendered_html = render_template("result.html", student_answer=student_answer, reference_answer=reference_answer, score=score)
    pdf_path = "evaluation_result.pdf"
    options = {"page-size": "A4", "encoding": "UTF-8", "enable-local-file-access": None}

    pdfkit.from_string(rendered_html, pdf_path, options=options, configuration=config)
    return send_file(pdf_path, as_attachment=True)



@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('username', None)
    return redirect(url_for('home'))

def load_reference_answer():
    if os.path.exists(REFERENCE_FILE):
        with open(REFERENCE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "Error: Reference answer file not found!"

def calculate_similarity(student_answer, reference_answer):
    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform([student_answer, reference_answer])
    similarity_score = cosine_similarity(vectors[0], vectors[1])[0][0]
    return round(similarity_score * 10, 2)

def get_user_by_id(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    return user

def update_user(user_id, first_name, last_name, email, profile_image):
    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE users SET first_name=%s, last_name=%s, email=%s, profile_image=%s WHERE id=%s
    """, (first_name, last_name, email, profile_image, user_id))
    mysql.connection.commit()
    cursor.close()

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
