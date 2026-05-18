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

@auth.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_pass = request.form.get('current_password')
    new_pass = request.form.get('new_password')
    confirm_pass = request.form.get('confirm_password')

    if not current_pass or not new_pass or not confirm_pass:
        flash('All password fields are required.', 'danger')
        return redirect(url_for('routes.settings'))

    if new_pass != confirm_pass:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('routes.settings'))

    if len(new_pass) < 6:
        flash('Password must be at least 6 characters long.', 'danger')
        return redirect(url_for('routes.settings'))

    user = User.query.get(current_user.id)
    if not bcrypt.check_password_hash(user.password, current_pass):
        flash('Incorrect current password.', 'danger')
        return redirect(url_for('routes.settings'))

    hashed_pw = bcrypt.generate_password_hash(new_pass).decode('utf-8')
    user.password = hashed_pw
    db.session.commit()

    flash('Your account password has been updated successfully!', 'success')
    return redirect(url_for('routes.settings'))
