# app.py
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import uuid
from datetime import datetime
from firebase_config import db
import json
import hashlib
from functools import wraps
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this in production

# Simple user storage (in production, use database)
users = {
    'admin': hashlib.sha256('password123'.encode()).hexdigest()  # Change this!
}

# Helper functions for Firebase
def get_invoices_from_firebase():
    """Get all invoices from Firestore"""
    try:
        if db is None:
            return []
        
        invoices_ref = db.collection('invoices').order_by('createdAt', direction='DESCENDING')
        docs = invoices_ref.stream()
        invoices = []
        for doc in docs:
            invoice = doc.to_dict()
            invoice['id'] = doc.id
            invoices.append(invoice)
        return invoices
    except Exception as e:
        print(f"Error getting invoices: {e}")
        return []

def save_invoice_to_firebase(invoice_data):
    """Save invoice to Firestore"""
    try:
        if db is None:
            return None
            
        invoice_ref = db.collection('invoices').document()
        invoice_data['createdAt'] = datetime.now()
        invoice_ref.set(invoice_data)
        return invoice_ref.id
    except Exception as e:
        print(f"Error saving invoice: {e}")
        return None

def get_invoice_from_firebase(invoice_id):
    """Get single invoice from Firestore"""
    try:
        if db is None:
            return None
            
        doc = db.collection('invoices').document(invoice_id).get()
        if doc.exists:
            invoice = doc.to_dict()
            invoice['id'] = doc.id
            
            # Debug: Print the invoice structure
            print("Invoice data:", invoice)
            print("Items type:", type(invoice.get('items', 'N/A')))
            print("Items content:", invoice.get('items', 'N/A'))
            
            return invoice
        return None
    except Exception as e:
        print(f"Error getting invoice: {e}")
        return None

def update_invoice_status_firebase(invoice_id, status):
    """Update invoice status in Firestore"""
    try:
        if db is None:
            return False
            
        db.collection('invoices').document(invoice_id).update({
            'status': status,
            'updatedAt': datetime.now()
        })
        return True
    except Exception as e:
        print(f"Error updating invoice: {e}")
        return False

def hash_password(password):
    """Simple password hashing"""
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def is_overdue(invoice):
    """Check if invoice is overdue"""
    try:
        if invoice.get('status') in ['paid', 'draft']:
            return False
            
        due_date_str = invoice.get('dueDate')
        if due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            return datetime.now() > due_date
        return False
    except:
        return False

def get_dashboard_stats(invoices=None):
    """Get dashboard statistics"""
    try:
        if invoices is None:
            invoices = get_invoices_from_firebase()
        
        total_invoices = len(invoices)
        total_amount = sum(invoice.get('total', 0) for invoice in invoices)
        
        # Count by status
        draft_count = sum(1 for invoice in invoices if invoice.get('status') == 'draft')
        sent_count = sum(1 for invoice in invoices if invoice.get('status') == 'sent')
        paid_count = sum(1 for invoice in invoices if invoice.get('status') == 'paid')
        overdue_count = sum(1 for invoice in invoices if is_overdue(invoice))
        
        stats = {
            'total_invoices': total_invoices,
            'total_amount': total_amount,
            'draft_count': draft_count,
            'sent_count': sent_count,
            'paid_count': paid_count,
            'overdue_count': overdue_count
        }
        
        return stats
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        # Return default stats to prevent errors
        return {
            'total_invoices': 0,
            'total_amount': 0,
            'draft_count': 0,
            'sent_count': 0,
            'paid_count': 0,
            'overdue_count': 0
        }

def send_invoice_email(invoice_data):
    """Send invoice via email using Gmail SMTP"""
    try:
        # Get email credentials from environment variables
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        
        if not sender_email or not sender_password:
            print("Email credentials not configured")
            return False
        
        # For now, just print email details (implement real email later)
        print(f"Would send email to {invoice_data.get('clientEmail')}")
        print(f"Invoice: {invoice_data.get('invoiceNumber')}")
        return True
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in users and users[username] == hash_password(password):
            session['user'] = username
            return redirect('/')
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

@app.route('/')
@login_required
def index():
    try:
        invoices = get_invoices_from_firebase()
        stats = get_dashboard_stats(invoices)
        # Pass the is_overdue function to template context
        return render_template('index.html', invoices=invoices, stats=stats, is_overdue=is_overdue)
    except Exception as e:
        print(f"Error in index route: {e}")
        # Fallback to prevent crashes
        return render_template('index.html', invoices=[], stats={
            'total_invoices': 0,
            'total_amount': 0,
            'draft_count': 0,
            'sent_count': 0,
            'paid_count': 0,
            'overdue_count': 0
        }, is_overdue=is_overdue)

@app.route('/create-invoice')
@login_required
def create_invoice():
    return render_template('create_invoice.html')

@app.route('/api/invoices', methods=['POST'])
def create_invoice_api():
    try:
        data = request.get_json()
        print("Received invoice data:", data)  # Debug print
        
        # Add metadata
        invoice_data = {
            'invoiceNumber': f"INV-{int(datetime.now().timestamp()) % 10000:04d}",
            'status': 'draft',
            **data
        }
        
        print("Saving invoice data:", invoice_data)  # Debug print
        
        # Save to Firebase
        invoice_id = save_invoice_to_firebase(invoice_data)
        print("Invoice saved with ID:", invoice_id)  # Debug print
        
        if invoice_id:
            invoice_data['id'] = invoice_id
            # Make it JSON serializable for the response
            serialized_invoice = invoice_data.copy()
            if isinstance(serialized_invoice.get('createdAt'), datetime):
                serialized_invoice['createdAt'] = serialized_invoice['createdAt'].isoformat()
            return jsonify({'success': True, 'invoice': serialized_invoice}), 201
        else:
            return jsonify({'success': False, 'error': 'Failed to save invoice'}), 500
    except Exception as e:
        print(f"Error creating invoice: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/invoices')
@login_required
def get_invoices_api():
    invoices = get_invoices_from_firebase()
    # Make invoices JSON serializable
    serialized_invoices = []
    for invoice in invoices:
        serialized = invoice.copy()
        if isinstance(serialized.get('createdAt'), datetime):
            serialized['createdAt'] = serialized['createdAt'].isoformat()
        serialized_invoices.append(serialized)
    return jsonify({'invoices': serialized_invoices})

@app.route('/api/invoices/<invoice_id>')
@login_required
def get_invoice_api(invoice_id):
    invoice = get_invoice_from_firebase(invoice_id)
    if invoice:
        # Make it JSON serializable
        serialized_invoice = invoice.copy()
        if isinstance(serialized_invoice.get('createdAt'), datetime):
            serialized_invoice['createdAt'] = serialized_invoice['createdAt'].isoformat()
        return jsonify(serialized_invoice)
    return jsonify({'error': 'Invoice not found'}), 404

@app.route('/invoice/<invoice_id>')
@login_required
def view_invoice(invoice_id):
    invoice = get_invoice_from_firebase(invoice_id)
    if invoice:
        # Rename 'items' to 'invoice_items' to avoid conflict with dict.items() method
        template_data = invoice.copy()
        if 'items' in template_data:
            template_data['invoice_items'] = template_data.pop('items')
        
        return render_template('view_invoice.html', invoice=template_data, is_overdue=is_overdue)
    else:
        return "Invoice not found", 404

@app.route('/debug/invoice-full/<invoice_id>')
@login_required
def debug_invoice_full(invoice_id):
    invoice = get_invoice_from_firebase(invoice_id)
    if invoice:
        import json
        from datetime import datetime
        
        # Make it JSON serializable for debugging
        debug_invoice = {}
        for key, value in invoice.items():
            if isinstance(value, datetime):
                debug_invoice[key] = value.isoformat()
            elif hasattr(value, '__dict__'):
                debug_invoice[key] = str(value)
            else:
                debug_invoice[key] = value
                
        html = f"""
        <h3>Invoice Debug Info</h3>
        <pre>{json.dumps(debug_invoice, indent=2, default=str)}</pre>
        <h4>Items Structure:</h4>
        <p>Type: {type(invoice.get('items', 'N/A'))}</p>
        """
        if 'items' in invoice:
            html += f"<pre>{json.dumps(invoice['items'], indent=2, default=str)}</pre>"
        return html
    else:
        return "Invoice not found", 404

@app.route('/api/invoices/<invoice_id>/status', methods=['PUT'])
@login_required
def update_invoice_status(invoice_id):
    data = request.get_json()
    new_status = data.get('status')
    
    if update_invoice_status_firebase(invoice_id, new_status):
        invoice = get_invoice_from_firebase(invoice_id)
        if invoice:
            # Make it JSON serializable
            serialized_invoice = invoice.copy()
            if isinstance(serialized_invoice.get('createdAt'), datetime):
                serialized_invoice['createdAt'] = serialized_invoice['createdAt'].isoformat()
            if isinstance(serialized_invoice.get('updatedAt'), datetime):
                serialized_invoice['updatedAt'] = serialized_invoice['updatedAt'].isoformat()
        return jsonify({'success': True, 'invoice': serialized_invoice})
    else:
        return jsonify({'success': False, 'error': 'Failed to update invoice'}), 500

@app.route('/api/invoices/<invoice_id>/send-email', methods=['POST'])
@login_required
def send_invoice_email_route(invoice_id):
    """Send invoice via email"""
    invoice = get_invoice_from_firebase(invoice_id)
    if invoice:
        # Send email
        if send_invoice_email(invoice):
            # Update status to sent
            if update_invoice_status_firebase(invoice_id, 'sent'):
                return jsonify({'success': True, 'message': 'Invoice sent successfully!'})
            else:
                return jsonify({'success': True, 'message': 'Email sent but status update failed'})
        else:
            return jsonify({'success': False, 'error': 'Failed to send email'}), 500
    else:
        return jsonify({'success': False, 'error': 'Invoice not found'}), 404
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Basic validation
        if not username or not email or not password:
            return render_template('login.html', error='All fields are required')
        
        if password != confirm_password:
            return render_template('login.html', error='Passwords do not match')
        
        if len(password) < 6:
            return render_template('login.html', error='Password must be at least 6 characters')
        
        # Check if user already exists
        if username in users:
            return render_template('login.html', error='Username already exists')
        
        # Add new user (in production, save to database)
        users[username] = hash_password(password)
        
        # Redirect to login with success message
        return render_template('login.html', error='Account created successfully! Please login.')
    
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)