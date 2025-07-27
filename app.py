# app.py
from flask import Flask, render_template, request, jsonify
import uuid
from datetime import datetime
from firebase_config import db
import json

app = Flask(__name__)

# Helper function to convert Firestore datetime to string for JSON
def serialize_invoice(invoice):
    """Convert invoice data for JSON serialization"""
    if isinstance(invoice.get('createdAt'), datetime):
        invoice['createdAt'] = invoice['createdAt'].isoformat()
    return invoice

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

# Routes
@app.route('/')
def index():
    invoices = get_invoices_from_firebase()
    return render_template('index.html', invoices=invoices)

@app.route('/create-invoice')
def create_invoice():
    return render_template('create_invoice.html')

@app.route('/api/invoices', methods=['POST'])
def create_invoice_api():
    data = request.get_json()
    
    # Add metadata
    invoice_data = {
        'invoiceNumber': f"INV-{int(datetime.now().timestamp()) % 10000:04d}",
        'status': 'draft',
        **data
    }
    
    # Save to Firebase
    invoice_id = save_invoice_to_firebase(invoice_data)
    
    if invoice_id:
        invoice_data['id'] = invoice_id
        # Make it JSON serializable for the response
        serialized_invoice = invoice_data.copy()
        if isinstance(serialized_invoice.get('createdAt'), datetime):
            serialized_invoice['createdAt'] = serialized_invoice['createdAt'].isoformat()
        return jsonify({'success': True, 'invoice': serialized_invoice}), 201
    else:
        return jsonify({'success': False, 'error': 'Failed to save invoice'}), 500

@app.route('/api/invoices')
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
def view_invoice(invoice_id):
    invoice = get_invoice_from_firebase(invoice_id)
    if invoice:
        # Debug: Print what we're passing to template
        print("Passing to template:", invoice)
        print("Items in template:", invoice.get('items', 'No items'))
        if 'items' in invoice:
            print("Items type in template:", type(invoice['items']))
            print("Items length:", len(invoice['items']) if isinstance(invoice['items'], list) else 'Not a list')
        
        # Rename 'items' to 'invoice_items' to avoid conflict with dict.items() method
        template_data = invoice.copy()
        if 'items' in template_data:
            template_data['invoice_items'] = template_data.pop('items')
        
        return render_template('view_invoice.html', invoice=template_data)
    else:
        return "Invoice not found", 404
    
@app.route('/debug/invoice-full/<invoice_id>')
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)