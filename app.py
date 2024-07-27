from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flash messages

# Database configuration
DB_HOST = "localhost"
DB_NAME = "awd_project"
DB_USER = "postgres"
DB_PASS = "123"

def get_db_connection():
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
        return conn
    except Exception as e:
        print("Error connecting to the database:", e)
        return None

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/register', methods=['POST'])
def register():
    try:
        first_last_name = request.form['first_last_name']
        user_name = request.form['user_name']
        password = request.form['password']
        gender = request.form['gender']
        email = request.form['email']
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute('INSERT INTO users (first_last_name, user_name, password, gender, email) VALUES (%s, %s, %s, %s, %s)',
                        (first_last_name, user_name, generate_password_hash(password), gender, email))
            conn.commit()
            cur.close()
            conn.close()
            flash('Registration Completed!', 'success')
            return render_template('landing.html')
        else:
            flash('Failed to connect to the database.', 'danger')
    except Exception as e:
        flash('An error occurred during registration: ' + str(e), 'danger')
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_name = request.form['user_name']
        password = request.form['password']

        conn = get_db_connection()
        if conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute('SELECT * FROM users WHERE user_name = %s', (user_name,))
            user = cur.fetchone()
            cur.close()
            conn.close()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['user_name'] = user['user_name']
                flash('Login successful!', 'success')
                return redirect(url_for('account'))
            else:
                flash('Invalid username or password', 'danger')
        else:
            flash('Failed to connect to the database.', 'danger')

    return render_template('landing.html')

@app.route('/account')
def account():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('index'))
    return render_template('account.html', username=session['username'])

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/register', methods=['GET'])
def register_user():
    return render_template('reg.html')

if __name__ == '__main__':
    print("Starting Flask app...")
    app.run(debug=True)
