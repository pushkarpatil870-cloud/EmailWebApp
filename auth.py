from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, bcrypt
from models import User, SMTPSettings

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            # Session Fixation Protection: clear session before log in
            session.clear()
            
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('routes.dashboard'))
            
        flash('Login Unsuccessful. Please check your credentials.', 'danger')
    return render_template('login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('routes.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username is already registered.', 'danger')
            return redirect(url_for('auth.register'))
            
        # Password Strength validation (Basic)
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(url_for('auth.register'))
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        # Default SMTP Settings link
        default_settings = SMTPSettings(user_id=new_user.id)
        db.session.add(default_settings)
        db.session.commit()
        
        flash('Registration successful! You may now login.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('register.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    
    # Completely destroy the user session
    session.clear()
    
    flash('You have logged out successfully.', 'info')
    return redirect(url_for('auth.login'))
