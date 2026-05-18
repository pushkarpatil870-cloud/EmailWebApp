from datetime import datetime
from flask_login import UserMixin
from extensions import db

class User(db.Model, UserMixin):
    __tablename__ = 'app_user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)

class SMTPSettings(db.Model):
    __tablename__ = 'smtp_settings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'))
    smtp_server = db.Column(db.String(150), default='smtp.gmail.com')
    smtp_port = db.Column(db.Integer, default=465)
    email_address = db.Column(db.String(150))
    app_password = db.Column(db.String(150))

class EmailHistory(db.Model):
    __tablename__ = 'email_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'))
    subject = db.Column(db.String(200))
    recipient = db.Column(db.String(200))
    cc = db.Column(db.String(200))
    bcc = db.Column(db.String(200))
    body = db.Column(db.Text)
    status = db.Column(db.String(50)) # 'Sent', 'Draft'
    date_sent = db.Column(db.DateTime, default=datetime.utcnow)

class EmailDraft(db.Model):
    __tablename__ = 'email_draft'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'))
    recipient = db.Column(db.String(200))
    cc = db.Column(db.String(200))
    bcc = db.Column(db.String(200))
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    attachments = db.Column(db.Text) # JSON serialized list of file paths
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(50), default='Draft')
