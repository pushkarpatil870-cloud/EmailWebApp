import os
import socket
import smtplib
import mimetypes
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models import SMTPSettings, EmailHistory
from email.message import EmailMessage

routes = Blueprint('routes', __name__)

def send_email_func(smtp_server, smtp_port, sender_email, password, receiver, subject, body, cc="", bcc="", file_paths=[]):
    # Save original socket getaddrinfo to bypass IPv6 unreachability bugs on cloud hosts (Render)
    orig_getaddrinfo = socket.getaddrinfo
    try:
        # Temporarily force IPv4 (AF_INET) resolution safely with strict standard signature
        def forced_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        socket.getaddrinfo = forced_getaddrinfo

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = receiver
        if cc: msg['Cc'] = cc
        if bcc: msg['Bcc'] = bcc
        msg.set_content(body, subtype='html')

        for path in file_paths:
            if os.path.exists(path):
                ctype, encoding = mimetypes.guess_type(path)
                if ctype is None or encoding is not None:
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)
                with open(path, 'rb') as f:
                    msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(path))

        # Dynamic Connection Handler based on Port Number (SSL vs TLS)
        # We also enforce strict socket timeout to prevent Gunicorn force-kills (500 errors)
        port_num = int(smtp_port)
        if port_num == 465:
            with smtplib.SMTP_SSL(smtp_server, port_num, timeout=25) as smtp:
                smtp.login(sender_email, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, port_num, timeout=25) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(sender_email, password)
                smtp.send_message(msg)
        return True, "Success"
    except Exception as e:
        return False, str(e)
    finally:
        # Restore original getaddrinfo
        socket.getaddrinfo = orig_getaddrinfo

@routes.route('/dashboard')
@login_required
def dashboard():
    sent_emails = EmailHistory.query.filter_by(user_id=current_user.id, status='Sent').order_by(EmailHistory.date_sent.desc()).limit(5).all()
    drafts = EmailHistory.query.filter_by(user_id=current_user.id, status='Draft').count()
    total_sent = EmailHistory.query.filter_by(user_id=current_user.id, status='Sent').count()
    return render_template('dashboard.html', sent_emails=sent_emails, drafts=drafts, total_sent=total_sent)

@routes.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    settings = SMTPSettings.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        action = request.form.get('action') # 'send' or 'draft'
        receiver = request.form.get('receiver')
        cc = request.form.get('cc')
        bcc = request.form.get('bcc')
        subject = request.form.get('subject')
        body = request.form.get('body')
        
        # Handle file attachments
        files = request.files.getlist('attachments')
        saved_files = []
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                saved_files.append(filepath)

        if action == 'draft':
            email = EmailHistory(user_id=current_user.id, recipient=receiver, cc=cc, bcc=bcc, subject=subject, body=body, status='Draft')
            db.session.add(email)
            db.session.commit()
            flash('Draft saved successfully!', 'info')
            return redirect(url_for('routes.history'))

        if not settings or not settings.email_address or not settings.app_password:
            flash('Configure SMTP settings before sending email.', 'warning')
            return redirect(url_for('routes.settings'))

        success, msg = send_email_func(settings.smtp_server, settings.smtp_port, settings.email_address, settings.app_password, receiver, subject, body, cc, bcc, saved_files)
        
        # Clean up files
        for path in saved_files:
            if os.path.exists(path):
                os.remove(path)

        if success:
            try:
                email = EmailHistory(user_id=current_user.id, recipient=receiver, cc=cc, bcc=bcc, subject=subject, body=body, status='Sent')
                db.session.add(email)
                db.session.commit()
                flash('Email sent successfully!', 'success')
            except Exception as db_err:
                db.session.rollback()
                flash(f'Email sent successfully, but failed to log history: {str(db_err)}', 'warning', 'warning')
        else:
            flash(f'Failed to dispatch: {msg}', 'danger')
            
        return redirect(url_for('routes.compose'))

    return render_template('compose.html')

@routes.route('/history')
@login_required
def history():
    emails = EmailHistory.query.filter_by(user_id=current_user.id).order_by(EmailHistory.date_sent.desc()).all()
    return render_template('history.html', emails=emails)

@routes.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    setting = SMTPSettings.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        setting.smtp_server = request.form.get('smtp_server')
        setting.smtp_port = int(request.form.get('smtp_port'))
        setting.email_address = request.form.get('email_address')
        setting.app_password = request.form.get('app_password')
        db.session.commit()
        flash('SMTP Settings updated successfully!', 'success')
        return redirect(url_for('routes.settings'))
    return render_template('settings.html', setting=setting)
