
# Open Source Social Network Platform

## Introduction
The Open Source Social Network Platform aims to develop a comprehensive social media system to facilitate and enhance open collaboration on projects. This platform provides features for user authentication, project management, and social interaction.

## Prerequisites
Before you begin, ensure you have met the following requirements:
- Python 3.8 or later
- PostgreSQL 12 or later
- Node.js and npm (for managing JavaScript dependencies)

## Installation

### Clone the Repository
```bash
git clone https://github.com/yourusername/opensource-social-network.git
cd opensource-social-network
```

### Create a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Install JavaScript Dependencies
```bash
npm install
```

### Set Up the Database
1. Start PostgreSQL server and create a database:
```sql
CREATE DATABASE awd_project;
CREATE USER postgres WITH PASSWORD '123';
GRANT ALL PRIVILEGES ON DATABASE awd_project TO postgres;
```

## Running the Application
1. Start the Flask development server:
```bash
python app.py
```

2. Open your web browser and go to `http://127.0.0.1:5000`.

## Features
- **User Authentication and Management**
  - User registration, login, and profile management.
  - Password management including password changes.
  - Integration with third-party authentication to allow users to log in using their existing social media accounts.

- **Project Management**
  - Create, manage, and view projects.
  - File uploads and storage in designated directories.
  - Display project details such as abstracts, upload dates, and like counts.
  - Manage project visibility and set permissions.

- **Social Features**
  - Like projects and see like counts.
  - Friend suggestions and follower lists.
  - Users can share posts, add comments to the post and communicate.

## Folder Structure
```
opensource-social-network/
├── app.py              # The main Flask application
├── requirements.txt    # Python dependencies
├── static/             # Static files (CSS, JS, images)
      |---css
      |---fonts
      |---images
      |---js
├── templates/          # HTML templates
└── README.md           # This file
```

## Technologies Used
- **Frontend Technologies**
  - HTML5, CSS3, JavaScript (ES6+)
  - Bootstrap 4 for responsive design and UI components
  - jQuery for enhanced interactivity

- **Backend Technologies**
  - Python with Flask framework
  - PostgreSQL for the database
  - `psycopg2` for database interaction

## Citation and References
- [Flask Documentation](https://flask.palletsprojects.com/en/2.0.x/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Bootstrap Documentation](https://getbootstrap.com/docs/4.6/getting-started/introduction/)
- [https://wpkixx.com/html/winku-land/]

---

This README provides the necessary steps and dependencies required to run the Open Source Social Network Platform. For detailed code and implementation, please refer to the individual HTML, CSS, and JavaScript files included in the project.
