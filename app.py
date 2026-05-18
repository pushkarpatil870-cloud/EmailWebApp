import os
from flask import Flask, request, redirect, url_for
from datetime import timedelta
from extensions import db, bcrypt, login_manager
from models import User
from auth import auth as auth_blueprint
from routes import routes as routes_blueprint

app = Flask(__name__)

# Security & Session Configurations
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super_secret_key')

db_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url

app.config['UPLOAD_FOLDER'] = 'uploads'

# Session Expiration Control
app.config['USE_SESSION_FOR_NEXT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15) # Expire after 15 mins of inactivity
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True # Protect against XSS session theft
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Bind Extensions
db.init_app(app)
bcrypt.init_app(app)
login_manager.init_app(app)

# Register Blueprints
app.register_blueprint(auth_blueprint)
app.register_blueprint(routes_blueprint)

# User loader setup
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Core Security: Prevent Back Button & Cache Page Loading
@app.after_request
def prevent_caching(response):
    # Only apply to dynamic routes, not static assets (CSS, JS)
    if request.endpoint and not request.endpoint.startswith('static'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# Handle root routing
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
