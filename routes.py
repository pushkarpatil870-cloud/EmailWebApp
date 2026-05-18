import os
import json
import socket
import smtplib
import mimetypes
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models import SMTPSettings, EmailHistory, EmailDraft
from email.message import EmailMessage

routes = Blueprint('routes', __name__)

@routes.app_template_filter('filename_only')
def filename_only(path):
    return os.path.basename(path)


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
    drafts = EmailDraft.query.filter_by(user_id=current_user.id).count()
    total_sent = EmailHistory.query.filter_by(user_id=current_user.id, status='Sent').count()
    return render_template('dashboard.html', sent_emails=sent_emails, drafts=drafts, total_sent=total_sent)

@routes.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    settings = SMTPSettings.query.filter_by(user_id=current_user.id).first()
    
    # GET Request: check if loading an existing draft
    if request.method == 'GET':
        draft_id = request.args.get('draft_id')
        if draft_id:
            draft = EmailDraft.query.filter_by(id=draft_id, user_id=current_user.id).first()
            if draft:
                draft_attachments = json.loads(draft.attachments) if draft.attachments else []
                return render_template('compose.html', draft=draft, draft_attachments=draft_attachments)
        return render_template('compose.html', draft=None, draft_attachments=[])
        
    # POST Request
    if request.method == 'POST':
        action = request.form.get('action') # 'send' or 'draft'
        draft_id = request.form.get('draft_id')
        receiver = request.form.get('receiver')
        cc = request.form.get('cc')
        bcc = request.form.get('bcc')
        subject = request.form.get('subject')
        body = request.form.get('body')
        
        # Retrieve list of previously uploaded files that the user wants to keep
        keep_attachments = request.form.getlist('keep_attachments')
        
        # Check if draft already exists
        existing_draft = None
        if draft_id:
            existing_draft = EmailDraft.query.filter_by(id=draft_id, user_id=current_user.id).first()
            
            # Clean up old attachments that were removed by the user
            if existing_draft:
                old_attachments = json.loads(existing_draft.attachments) if existing_draft.attachments else []
                for filepath in old_attachments:
                    if filepath not in keep_attachments and os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass
        
        # Handle newly uploaded attachments
        files = request.files.getlist('attachments')
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Avoid duplicate names by prefixing a unique tag if file already exists
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                counter = 1
                base, ext = os.path.splitext(filename)
                while os.path.exists(filepath):
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{base}_{counter}{ext}")
                    counter += 1
                
                file.save(filepath)
                keep_attachments.append(filepath)

        # Action: SAVE DRAFT
        if action == 'draft':
            if existing_draft:
                existing_draft.recipient = receiver
                existing_draft.cc = cc
                existing_draft.bcc = bcc
                existing_draft.subject = subject
                existing_draft.body = body
                existing_draft.attachments = json.dumps(keep_attachments)
                db.session.commit()
                flash('Draft updated successfully!', 'success')
            else:
                new_draft = EmailDraft(
                    user_id=current_user.id,
                    recipient=receiver,
                    cc=cc,
                    bcc=bcc,
                    subject=subject,
                    body=body,
                    attachments=json.dumps(keep_attachments)
                )
                db.session.add(new_draft)
                db.session.commit()
                flash('Draft saved successfully!', 'success')
            return redirect(url_for('routes.drafts'))

        # Action: SEND EMAIL
        if not settings or not settings.email_address or not settings.app_password:
            flash('Configure SMTP settings before sending email.', 'warning')
            return redirect(url_for('routes.settings'))

        success, msg = send_email_func(
            settings.smtp_server,
            settings.smtp_port,
            settings.email_address,
            settings.app_password,
            receiver,
            subject,
            body,
            cc,
            bcc,
            keep_attachments
        )
        
        if success:
            # Add to Outbox Activity Log
            try:
                email = EmailHistory(user_id=current_user.id, recipient=receiver, cc=cc, bcc=bcc, subject=subject, body=body, status='Sent')
                db.session.add(email)
                
                # If sending an existing draft, delete it from drafts list
                if existing_draft:
                    db.session.delete(existing_draft)
                
                # Clean up attachment files from the server's uploads folder after successful send
                for path in keep_attachments:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                
                db.session.commit()
                flash('Email sent successfully!', 'success')
            except Exception as db_err:
                db.session.rollback()
                flash(f'Email sent, but failed to log history: {str(db_err)}', 'warning')
            return redirect(url_for('routes.history'))
        else:
            flash(f'Failed to dispatch: {msg}', 'danger')
            # If sending failed, redirect back to compose with draft parameters to prevent data loss
            if existing_draft:
                return redirect(url_for('routes.compose', draft_id=existing_draft.id))
            return redirect(url_for('routes.compose'))

@routes.route('/drafts')
@login_required
def drafts():
    draft_list = EmailDraft.query.filter_by(user_id=current_user.id).order_by(EmailDraft.updated_at.desc()).all()
    # Format attachments count for each draft
    for d in draft_list:
        d.attach_count = len(json.loads(d.attachments)) if d.attachments else 0
    return render_template('drafts.html', drafts=draft_list)

@routes.route('/drafts/delete/<int:draft_id>', methods=['POST'])
@login_required
def delete_draft(draft_id):
    draft = EmailDraft.query.filter_by(id=draft_id, user_id=current_user.id).first_or_404()
    # Clean up attachment files from server
    attachments = json.loads(draft.attachments) if draft.attachments else []
    for path in attachments:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    
    db.session.delete(draft)
    db.session.commit()
    flash('Draft deleted successfully!', 'success')
    return redirect(url_for('routes.drafts'))

@routes.route('/drafts/duplicate/<int:draft_id>')
@login_required
def duplicate_draft(draft_id):
    draft = EmailDraft.query.filter_by(id=draft_id, user_id=current_user.id).first_or_404()
    
    # We duplicate the draft files under new unique names to prevent share collisions
    old_attachments = json.loads(draft.attachments) if draft.attachments else []
    new_attachments = []
    for old_path in old_attachments:
        if os.path.exists(old_path):
            try:
                base, ext = os.path.splitext(os.path.basename(old_path))
                new_filename = f"{base}_copy{ext}"
                new_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_filename)
                counter = 1
                while os.path.exists(new_path):
                    new_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{base}_copy_{counter}{ext}")
                    counter += 1
                
                # Copy file contents
                with open(old_path, 'rb') as f_src:
                    content = f_src.read()
                with open(new_path, 'wb') as f_dest:
                    f_dest.write(content)
                new_attachments.append(new_path)
            except Exception:
                pass
                
    new_draft = EmailDraft(
        user_id=current_user.id,
        recipient=draft.recipient,
        cc=draft.cc,
        bcc=draft.bcc,
        subject=f"Copy of {draft.subject or ''}" if draft.subject else "Copy of Draft",
        body=draft.body,
        attachments=json.dumps(new_attachments)
    )
    db.session.add(new_draft)
    db.session.commit()
    flash('Draft duplicated successfully!', 'success')
    return redirect(url_for('routes.drafts'))


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
