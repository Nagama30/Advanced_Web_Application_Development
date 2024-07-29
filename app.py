from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import RealDictCursor
import psycopg2
import os
from werkzeug.utils import secure_filename
from datetime import datetime


app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flash messages

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

PROFILE_PIC_FOLDER = 'profile_pic'
if not os.path.exists(PROFILE_PIC_FOLDER):
    os.makedirs(PROFILE_PIC_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROFILE_PIC_FOLDER'] = PROFILE_PIC_FOLDER 
app.config['ALLOWED_EXTENSIONS'] = {'zip'}


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

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

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
    return render_template('account.html', user_name=session['user_name'])

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/register', methods=['GET'])
def register_user():
    return render_template('reg.html')

@app.route('/logout')
def logout():
    print("Logout route accessed")
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('landing'))

def allowed_file_img(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/edit_profile_basic', methods=['GET', 'POST'])
def edit_profile_basic():
    if request.method == 'POST':
        user_name = session.get('user_name')  # Assuming user_name is stored in the session
        first_last_name = request.form.get('first_last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        dob = request.form.get('dob')
        gender = request.form.get('gender')
        city = request.form.get('city')
        country = request.form.get('country')
        about_me = request.form.get('about_me')
        
        # Handle profile photo upload
        profile_photo = request.files.get('profilePhotoInput')
        profile_photo_path = None

        if profile_photo and profile_photo.filename != '':
            if allowed_file_img(profile_photo.filename):
                # Create a directory for the user if it doesn't exist
                user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_name)
                if not os.path.exists(user_folder):
                    os.makedirs(user_folder)

        # Generate a unique filename with current date and time
                original_filename = secure_filename(profile_photo.filename)
                curr_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{curr_time}_{original_filename}"
                file_path = os.path.join(user_folder, filename)
                print(file_path)
                profile_photo.save(file_path)
                profile_photo_path = file_path
                

        try:
            conn = get_db_connection()
            if conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    update_query = """UPDATE users SET first_last_name = %s, email = %s, phone = %s, dob = %s, gender = %s, city = %s, country = %s, about_me = %s, profile_photo = %s WHERE user_name = %s"""
                    cursor.execute(update_query, (
                            first_last_name,
                            email,
                            phone,
                            dob,
                            gender,
                            city,
                            country,
                            about_me,
                            profile_photo_path,
                            user_name
                    ))           
                    conn.commit()
                    flash('Profile updated successfully!', 'success')
        except Exception as e:
            if conn:
                conn.rollback()
            flash(f'Error updating profile: {e}', 'danger')
        finally:
            if conn:
                conn.close()

        return redirect(url_for('edit_profile_basic'))  # Assuming there's a profile page to redirect to

    return render_template('edit_profile_basic.html')


@app.route('/edit_password', methods=['GET', 'POST'])
def edit_password():
    if request.method == 'POST':
        user_name = session.get('user_name')  # Assuming user_name is stored in the session
        old_pass = request.form.get('old_pass')
        new_pass = request.form.get('new_pass')
        confirm_pass = request.form.get('confirm_pass')

        if new_pass != confirm_pass:
            flash('New password and confirmation do not match!', 'danger')
            return redirect(url_for('edit_password'))

        try:
            conn = get_db_connection()
            if conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Check if the old password matches the one in the database
                    cursor.execute("SELECT password FROM users WHERE user_name = %s", (user_name,))
                    user = cursor.fetchone()
                    if user and check_password_hash(user['password'], old_pass):
                        # Update the password
                        new_pass_hashed = generate_password_hash(new_pass)
                        cursor.execute("UPDATE users SET password = %s WHERE user_name = %s", (new_pass_hashed, user_name))
                        conn.commit()
                        flash('Password updated successfully!', 'success')
                    else:
                        flash('Old password is incorrect!', 'danger')
        except Exception as e:
            if conn:
                conn.rollback()
            flash(f'Error updating password: {e}', 'danger')
        finally:
            if conn:
                conn.close()

        return redirect(url_for('edit_password'))  # Redirect to the password edit page

    return render_template('edit_password.html')


@app.route('/create_project', methods=['GET', 'POST'])
def create_project():
    if request.method == 'POST':
        project_name = request.form.get('project_name')
        abstract = request.form.get('abstract')
        owner = session.get('user_name')  # Assuming user_name is stored in the session
        zip_file = request.files.get('zip_file')
        upload_date = datetime.now()

        if zip_file and zip_file.filename != '':
            if (zip_file.filename):
                # Create a directory for the user if it doesn't exist
                user_folder = os.path.join(app.config['UPLOAD_FOLDER'], owner)
                if not os.path.exists(user_folder):
                    os.makedirs(user_folder)

                # Create a timestamp-based subdirectory under the user's folder
                timestamp_folder = upload_date.strftime("%Y%m%d_%H%M%S")
                timestamp_folder_path = os.path.join(user_folder, timestamp_folder)
                if not os.path.exists(timestamp_folder_path):
                    os.makedirs(timestamp_folder_path)

                # Generate filename and save path
                original_filename = secure_filename(zip_file.filename)
                file_path = os.path.join(timestamp_folder_path, original_filename)
                print(f"File path: {file_path}")
                zip_file.save(file_path)

                # Print debug information
                print(f"File path: {file_path}")

                # Save project information and file path to the database
                try:
                    conn = get_db_connection()
                    if conn:
                        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                            insert_query = """
                            INSERT INTO project_data (project_name, abstract, owner, zip_file, upload_date)
                            VALUES (%s, %s, %s, %s, %s)
                            """
                            print(f"Inserting into database: {project_name}, {abstract}, {owner}, {file_path}, {upload_date}")
                            cursor.execute(insert_query, (project_name, abstract, owner, file_path, upload_date))
                            conn.commit()
                            flash('Project created and file uploaded successfully!', 'success')
                except Exception as e:
                    print(f"Error: {e}")  # Print error message for debugging
                    if conn:
                        conn.rollback()
                        flash(f'Error saving project: {e}', 'danger')
                finally:
                    if conn:
                        conn.close()
            else:
                flash('Invalid file type. Only ZIP files are allowed.', 'danger')
        else:
            flash('No file selected or file is empty.', 'danger')

    return render_template('create_project.html')


@app.route('/view_project', methods=['GET'])
def view_project():
    return render_template('view_project.html')

@app.route('/view_project')
def project_page():
    user_name = session.get('user_name')  # Assuming user_name is stored in the session
    if not user_name:
        flash('User not logged in', 'danger')
        return redirect(url_for('login'))  # Redirect to the login page or appropriate page if the user is not logged in

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = "SELECT project_name, abstract, owner, upload_date, likes FROM project_data WHERE owner = %s"
            cursor.execute(query, (user_name,))
            projects = cursor.fetchall()
            print(f"Projects fetched: {projects}")  # Debug: Print fetched projects
    except Exception as e:
        projects = []
        print(f"Error fetching project data: {e}")
    finally:
        if conn:
            conn.close()

    return render_template('view_project.html', projects=projects)


if __name__ == '__main__':
    print("Starting Flask app...")
    app.run(debug=True)
