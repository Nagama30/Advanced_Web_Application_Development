from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import RealDictCursor
import psycopg2
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flash messages
socketio = SocketIO(app)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
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

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM posts ORDER BY timestamp DESC')
    posts = cursor.fetchall()

    if not posts:
        flash('No posts found.', 'info')  # Flash a message if no posts are found
        return render_template('account.html', user_name=session['user_name'], posts=[])

    for post in posts:
        cursor.execute('SELECT * FROM comments WHERE post_id = %s ORDER BY timestamp DESC', (post['id'],))
        post['comments'] = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('account.html', user_name=session['user_name'], posts=posts)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_name' not in session:
        flash('Please log in to add a comment.', 'warning')
        return redirect(url_for('index'))
    
    comment_content = request.form['comment']
    user_name = session['user_name']
    timestamp = datetime.now()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO comments (post_id, user_name, content, timestamp) VALUES (%s, %s, %s, %s)',
        (post_id, user_name, comment_content, timestamp)
    )
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('account'))

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
        
        try:
            conn = get_db_connection()
            if conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    update_query = """UPDATE users SET first_last_name = %s, email = %s, phone = %s, dob = %s, gender = %s, city = %s, country = %s, about_me = %s WHERE user_name = %s"""
                    cursor.execute(update_query, (
                            first_last_name,
                            email,
                            phone,
                            dob,
                            gender,
                            city,
                            country,
                            about_me,
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

        return redirect(url_for('edit_profile_basic'), user_name=session['user_name'])  # Assuming there's a profile page to redirect to

    return render_template('edit_profile_basic.html', user_name=session['user_name'])


@app.route('/edit_password', methods=['GET', 'POST'])
def edit_password():
    if request.method == 'POST':
        user_name = session.get('user_name')  # Assuming user_name is stored in the session
        old_pass = request.form.get('old_pass')
        new_pass = request.form.get('new_pass')
        confirm_pass = request.form.get('confirm_pass')

        if new_pass != confirm_pass:
            flash('New password and confirmation do not match!', 'danger')
            return redirect(url_for('edit_password'), user_name=session['user_name'])

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

        return redirect(url_for('edit_password'), user_name=session['user_name'])  # Redirect to the password edit page

    return render_template('edit_password.html', user_name=session['user_name'])


@app.route('/create_project', methods=['GET', 'POST'])
def create_project():
    if request.method == 'POST':
        user_name = session.get('user_name')
        project_name = request.form.get('project_name')
        abstract = request.form.get('abstract')
        owner = session.get('user_name')  # Assuming user_name is stored in the session
        zip_file = request.files.get('zip_file')
        upload_date = datetime.now()
        visibility = request.form.get('visibility', 'Private')  # Default to 'Private' if not provided

        if zip_file and zip_file.filename != '':
            if zip_file.filename.endswith('.zip'):  # Ensure the uploaded file is a ZIP file
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

                # Save project information and file path to the database
                try:
                    conn = get_db_connection()
                    if conn:
                        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                            insert_query = """
                            INSERT INTO project_data (project_name, abstract, owner, zip_file, upload_date, visibility)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """
                            print(f"Inserting into database: {project_name}, {abstract}, {owner}, {file_path}, {upload_date}, {visibility}")
                            cursor.execute(insert_query, (project_name, abstract, owner, file_path, upload_date, visibility))
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
    return render_template('create_project.html', user_name=session['user_name'])


@app.route('/download_project/<int:project_id>')
def download_project(project_id):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = "SELECT zip_file FROM project_data WHERE id = %s"
            cursor.execute(query, (project_id,))
            project = cursor.fetchone()
            if project:
                file_path = project['zip_file']
                if os.path.exists(file_path):
                    return send_file(file_path, as_attachment=True)
                else:
                    flash('File not found', 'danger')
            else:
                flash('Project not found', 'danger')
    except Exception as e:
        print(f"Error fetching project data: {e}")
        flash('Error fetching project data', 'danger')
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('view_project'), user_name=session['user_name'])


@app.route('/view_project')
def view_project():
    user_name = session.get('user_name')  # Assuming user_name is stored in the session
    if not user_name:
        flash('User not logged in', 'danger')
        return redirect(url_for('login'))  # Redirect to the login page or appropriate page if the user is not logged in

    projects = []  # Initialize projects as an empty list
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = "SELECT id, project_name, abstract, owner, upload_date, likes FROM project_data WHERE owner = %s"
            cursor.execute(query, (user_name,))
            projects = cursor.fetchall()
            if not projects:
                flash('No projects found.', 'info')  # Flash a message if no projects are found
            # Format the upload_date in human-readable format
            for project in projects:
                project['upload_date'] = project['upload_date'].strftime('%Y-%m-%d %H:%M:%S')
            print(f"Projects fetched: {projects}")  # Debug: Print fetched projects
    except Exception as e:
        flash('Error fetching project data. Please try again later.', 'danger')
        print(f"Error fetching project data: {e}")
    finally:
        if conn:
            conn.close()

    return render_template('view_project.html', user_name=session['user_name'], projects=projects)

@app.route('/manage_project')
def manage_project():
    user_name = session.get('user_name')  # Assuming user_name is stored in the session
    if not user_name:
        flash('User not logged in', 'danger')
        return redirect(url_for('login'))  # Redirect to the login page or appropriate page if the user is not logged in

    projects = []  # Initialize projects as an empty list
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Fetch projects owned by the current user
            query = """
                SELECT id, project_name, abstract, owner, upload_date, likes, visibility 
                FROM project_data 
                WHERE owner = %s
            """
            cursor.execute(query, (user_name,))
            projects = cursor.fetchall()
            if not projects:
                flash('No projects found.', 'info')  # Flash a message if no projects are found
            # Format the upload_date in human-readable format
            for project in projects:
                # Ensure upload_date is a datetime object
                if isinstance(project['upload_date'], datetime):
                    project['upload_date'] = project['upload_date'].strftime('%Y-%m-%d %H:%M:%S')
            print(f"Projects fetched: {projects}")  # Debug: Print fetched projects
    except Exception as e:
        flash('Error fetching project data. Please try again later.', 'danger')
        print(f"Error fetching project data: {e}")
        print(traceback.format_exc())
    finally:
        if conn:
            conn.close()

    return render_template('manage_project.html', projects=projects)

@app.route('/delete_projects', methods=['POST'])
def delete_projects():
    project_ids = request.form.getlist('project_ids')
    if not project_ids:
        flash('No projects selected', 'danger')
        return redirect(url_for('manage_project'))  # Redirect to manage_project page if no projects are selected

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = "DELETE FROM project_data WHERE id = ANY(%s)"
            cursor.execute(query, (project_ids,))
            conn.commit()

            if cursor.rowcount == 0:
                flash('No projects were deleted. Please try again.', 'info')  # No rows affected
            else:
                flash('Selected projects have been deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting projects: {e}', 'danger')
        print(f"Error deleting projects: {e}")
    finally:
        if conn:
            conn.close()

    return redirect(url_for('manage_project'))

@app.route('/delete_project/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = "DELETE FROM project_data WHERE id = %s"
            cursor.execute(query, (project_id,))
            conn.commit()
            return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting project: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if conn:
            conn.close()


@app.route('/edit_projects', methods=['POST'])
def edit_projects():
    project_ids = request.form.getlist('project_ids')
    if not project_ids:
        flash('No projects selected.', 'danger')
        return redirect(url_for('manage_project'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            for project_id in project_ids:
                # Fetch form values for each project
                project_name = request.form.get(f'project_name_{project_id}')
                abstract = request.form.get(f'abstract_{project_id}')
                visibility = request.form.get(f'visibility_{project_id}')
                
                # Check if any field is missing
                if not project_name or not abstract or not visibility:
                    flash(f'Missing values for project ID {project_id}.', 'warning')
                    continue

                # Update the project in the database
                query = """UPDATE project_data 
                           SET project_name = %s, abstract = %s, visibility = %s
                           WHERE id = %s"""
                cursor.execute(query, (project_name, abstract, visibility, project_id))
            
            # Commit all updates
            conn.commit()
            flash('Selected projects have been updated.', 'success')
    except Exception as e:
        print(f"Error updating projects: {e}")
        flash(f'Error updating projects: {e}', 'danger')
    finally:
        if conn:
            conn.close()

    return redirect(url_for('manage_project'))


@app.route('/create_post', methods=['POST'])
def create_post():
    content = request.form['content']
    user_name = session.get('user_name')  # Assuming user_name is stored in the session

    if content:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO posts (user_name, content, timestamp) VALUES (%s, %s, %s)', (user_name, content, datetime.now()))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Post created successfully!', 'success')
        except Exception as e:
            flash(f'Error creating post: {e}', 'danger')
    else:
        flash('Content cannot be empty', 'warning')

    return redirect(url_for('account'))



if __name__ == '__main__':
    print("Starting Flask app...")
    app.run(debug=True)
