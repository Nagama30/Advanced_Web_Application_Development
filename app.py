from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import RealDictCursor
import psycopg2
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import io
import base64
import matplotlib.pyplot as plt
import pandas as pd
from psycopg2.extras import RealDictCursor

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

def get_comments_count_for_user(user):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT COUNT(*) AS total_comments
        FROM comments c
        JOIN posts p ON c.post_id = p.id
        WHERE p.user_name = %s
          AND DATE_TRUNC('month', c.timestamp) = DATE_TRUNC('month', CURRENT_DATE);
    """, (user,))
    comments_count = cursor.fetchone()['total_comments']
    cursor.close()
    conn.close()
    return comments_count

def get_likes_count_for_user(user):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT SUM(likes) AS total_likes
        FROM project_data
        WHERE owner = %s
          AND DATE_TRUNC('month', upload_date) = DATE_TRUNC('month', CURRENT_DATE);
    """, (user,))
    likes_count = cursor.fetchone()['total_likes'] or 0  # Handle NULL by defaulting to 0
    cursor.close()
    conn.close()
    return likes_count

def get_followers_for_user(user):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT u.user_name, u.email 
        FROM followers f 
        JOIN users u ON f.follower_user_name = u.user_name 
        WHERE f.user_name = %s;
    """, (user,))
    my_followers = cursor.fetchall()
    cursor.close()
    conn.close()
    return my_followers

def get_friends_for_user(user):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT u.user_name AS friend, u.email
        FROM followers f1
        JOIN followers f2 ON f1.user_name = f2.follower_user_name AND f1.follower_user_name = f2.user_name
        JOIN users u ON f1.follower_user_name = u.user_name
        WHERE f1.user_name = %s
    """, (user,))
    friends_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return friends_list

@app.route('/account')
def account():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('index'))

    user = session['user_name']
    
    # Call helper functions
    comments_count = get_comments_count_for_user(user)
    likes_count = get_likes_count_for_user(user)
    friends_list = get_friends_for_user(user)
    my_followers = get_followers_for_user(user)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Fetch posts
    cursor.execute('SELECT * FROM posts ORDER BY timestamp DESC')
    posts = cursor.fetchall()
    
    if not posts:
        flash('No posts found.', 'info')
        cursor.close()
        conn.close()
        return render_template('account.html', user_name=session['user_name'], posts=[], followers_list=[], comments_count=comments_count, likes_count=likes_count, my_followers=my_followers)

    # Fetch comments for each post
    for post in posts:
        cursor.execute('SELECT * FROM comments WHERE post_id = %s ORDER BY timestamp DESC', (post['id'],))
        post['comments'] = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('account.html', user_name=session['user_name'], posts=posts, friends_list=friends_list, comments_count=comments_count, likes_count=likes_count, my_followers=my_followers)


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

    # Initialize default values
    comments_count = 0
    likes_count = 0
    friends_list = []
    my_followers = []
    
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

    elif request.method == 'GET':
        user_name = session.get('user_name')

        # Call helper functions
        comments_count = get_comments_count_for_user(user_name) or 0
        likes_count = get_likes_count_for_user(user_name) or 0
        friends_list = get_friends_for_user(user_name) or []
        my_followers = get_followers_for_user(user_name) or []


        # Debugging: print values to console
        print(f"Comments count: {comments_count}")
        print(f"Likes count: {likes_count}")
        print(f"Friends list: {friends_list}")
        print(f"My followers: {my_followers}")

    return render_template('edit_profile_basic.html', user_name=session['user_name'], friends_list=friends_list, comments_count=comments_count, likes_count=likes_count, my_followers=my_followers)


@app.route('/edit_password', methods=['GET', 'POST'])
def edit_password():
    # Initialize default values
    comments_count = 0
    likes_count = 0
    friends_list = []
    my_followers = []
    
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

    elif request.method == 'GET':
        user_name = session.get('user_name')

        # Call helper functions
        comments_count = get_comments_count_for_user(user_name) or 0
        likes_count = get_likes_count_for_user(user_name) or 0
        friends_list = get_friends_for_user(user_name) or []
        my_followers = get_followers_for_user(user_name) or []


        # Debugging: print values to console
        print(f"Comments count: {comments_count}")
        print(f"Likes count: {likes_count}")
        print(f"Friends list: {friends_list}")
        print(f"My followers: {my_followers}")

    return render_template('edit_password.html', user_name=session['user_name'], friends_list=friends_list, comments_count=comments_count, likes_count=likes_count, my_followers=my_followers)


@app.route('/create_project', methods=['GET', 'POST'])
def create_project():
    # Initialize default values
    comments_count = 0
    likes_count = 0
    friends_list = []
    my_followers = []

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

    elif request.method == 'GET':

        user_name = session.get('user_name')

        # Call helper functions
        comments_count = get_comments_count_for_user(user_name) or 0
        likes_count = get_likes_count_for_user(user_name) or 0
        friends_list = get_friends_for_user(user_name) or []
        my_followers = get_followers_for_user(user_name) or []


        # Debugging: print values to console
        print(f"Comments count: {comments_count}")
        print(f"Likes count: {likes_count}")
        print(f"Friends list: {friends_list}")
        print(f"My followers: {my_followers}")

    return render_template('create_project.html', user_name=session.get('user_name', ''), friends_list=friends_list, comments_count=comments_count, likes_count=likes_count, my_followers=my_followers)


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
    user = session.get('user_name')
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
            
            cursor.execute('SELECT * FROM project_data')
            projects = cursor.fetchall()
            for project in projects:
                project['liked'] = get_project_likes_status(user, project['id'])

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


@app.route('/project/<int:project_id>')
def project_detail(project_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM project_data WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    cursor.close()
    conn.close()

    if not project:
        return "Project not found", 404

    return render_template('project_detail.html', project=project)

def get_project_likes_status(user, project_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) 
        FROM project_likes 
        WHERE project_id = %s AND users = %s
    """, (project_id, user))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] > 0


@app.route('/toggle_like', methods=['POST'])
def toggle_like():
    try:
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({'error': 'User not logged in'}), 401

        project_id = request.json.get('project_id')
        if not project_id:
            return jsonify({'error': 'No project ID provided'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the user already liked the project
        cursor.execute("""
            SELECT * FROM project_likes 
            WHERE project_id = %s AND users = %s
        """, (project_id, user_name))
        existing_like = cursor.fetchone()

        if existing_like:
            # User already liked, so remove the like
            cursor.execute("""
                DELETE FROM project_likes 
                WHERE project_id = %s AND users = %s
            """, (project_id, user_name))
            conn.commit()

            # Decrement like count in project_data table
            cursor.execute("""
                UPDATE project_data 
                SET likes = likes - 1 
                WHERE id = %s
            """, (project_id,))
            conn.commit()

            result = {'liked': False}
        else:
            # User has not liked yet, so add the like
            cursor.execute("""
                INSERT INTO project_likes (project_id, users) 
                VALUES (%s, %s)
            """, (project_id, user_name))
            conn.commit()

            # Increment like count in project_data table
            cursor.execute("""
                UPDATE project_data 
                SET likes = likes + 1 
                WHERE id = %s
            """, (project_id,))
            conn.commit()

            result = {'liked': True}

        cursor.close()
        conn.close()

        return jsonify(result)

    except Exception as e:
        print(f"Error: {e}")  # Print error message for debugging
        return jsonify({'error': 'Failed to toggle like'}), 500


@app.route('/search')
def search():
    user_name = session.get('user_name')  # Assuming user_name is stored in the session
    return render_template('search.html', user_name=session['user_name'])


@app.route('/search_users', methods=['POST'])
def search_users():
    search_term = request.form['search_term']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.first_last_name, u.user_name, u.email, 
               (SELECT COUNT(*) FROM project_data p WHERE p.owner = u.user_name) as total_projects,
               (SELECT COUNT(*) FROM posts po WHERE po.user_name = u.user_name) as total_posts
        FROM users u
        WHERE u.user_name ILIKE %s OR u.first_last_name ILIKE %s
    """, ('%' + search_term + '%', '%' + search_term + '%'))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([
        {
            'first_last_name': row[0], 
            'user_name': row[1], 
            'email': row[2],
            'total_projects': row[3],
            'total_posts': row[4]
        } 
        for row in results
    ])

@app.route('/send_follow_request', methods=['POST'])
def send_follow_request():
    to_user_name = request.form['user_name']
    from_user_name = session.get('user_name') # Replace with actual logged-in user logic

    if from_user_name == to_user_name:
        return jsonify({'success': False, 'message': 'Cannot follow yourself.'})

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO follow_requests (from_user_name, to_user_name) VALUES (%s, %s)", (from_user_name, to_user_name))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        print(f"Error sending follow request: {e}")
        return jsonify({'success': False})
    finally:
        cur.close()
        conn.close()

@app.route('/profile/<user_name>')
def profile(user_name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT first_last_name, user_name, email FROM users WHERE user_name = %s", (user_name,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user:
        return render_template('profile.html', user={'first_last_name': user[0], 'user_name': user[1], 'email': user[2]})
    else:
        return "User not found", 404


@app.route('/cancel_follow_request', methods=['POST'])
def cancel_follow_request():
    to_user_name = request.form['user_name']
    from_user_name = session.get('user_name')   # Replace with actual logged-in user logic

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM follow_requests WHERE from_user_name = %s AND to_user_name = %s", (from_user_name, to_user_name))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        print(f"Error canceling follow request: {e}")
        return jsonify({'success': False})
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    print("Starting Flask app...")
    app.run(debug=True)
