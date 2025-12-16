"""
Mock classifier API server for testing purposes.

This is a simple Flask server that mimics the KYC-AML classifier API
for development and testing when the real API is not available.
"""
from flask import Flask, request, jsonify
import random
from datetime import datetime
import hashlib

app = Flask(__name__)

# Mock document categories
DOCUMENT_CATEGORIES = {
    'passport': {'category': 'Identity Proof', 'type': 'Passport'},
    'license': {'category': 'Identity Proof', 'type': 'Driver License'},
    'national_id': {'category': 'Identity Proof', 'type': 'National ID'},
    'utility': {'category': 'Address Proof', 'type': 'Utility Bill'},
    'bank': {'category': 'Financial Document', 'type': 'Bank Statement'},
    'tax': {'category': 'Financial Document', 'type': 'Tax Return'},
    'lease': {'category': 'Address Proof', 'type': 'Lease Agreement'},
    'kyc_form': {'category': 'Regulatory Form', 'type': 'KYC Form'},
}


def generate_mock_classification(filename: str) -> dict:
    """Generate a mock classification based on filename."""
    # Try to detect document type from filename
    filename_lower = filename.lower()
    
    for keyword, category_info in DOCUMENT_CATEGORIES.items():
        if keyword in filename_lower:
            return {
                'category': category_info['category'],
                'type': category_info['type'],
                'confidence': round(random.uniform(0.85, 0.99), 2),
                'detected_fields': [
                    'document_number',
                    'name',
                    'date',
                    'signature'
                ],
                'classification_id': hashlib.md5(filename.encode()).hexdigest()[:12],
                'timestamp': datetime.now().isoformat()
            }
    
    # Default classification for unknown types
    return {
        'category': 'Other Document',
        'type': 'Unknown',
        'confidence': round(random.uniform(0.50, 0.75), 2),
        'detected_fields': [],
        'classification_id': hashlib.md5(filename.encode()).hexdigest()[:12],
        'timestamp': datetime.now().isoformat()
    }


@app.route('/api/kyc_document_classifier/v1/', methods=['GET'])
@app.route('/api/kyc_document_classifier/v1/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'KYC-AML Document Classifier (Mock)',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/kyc_document_classifier/v1/', methods=['POST'])
@app.route('/api/kyc_document_classifier/v1/classify', methods=['POST'])
def classify_document():
    """Classify a single document."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    
    # Generate mock classification
    classification = generate_mock_classification(file.filename)
    
    return jsonify({
        'success': True,
        'filename': file.filename,
        'classification': classification
    }), 200


@app.route('/api/kyc_document_classifier/v1/batch-classify', methods=['POST'])
def batch_classify():
    """Classify multiple documents in batch."""
    files = request.files
    
    if not files:
        return jsonify({'error': 'No files provided'}), 400
    
    results = []
    for key, file in files.items():
        if file.filename:
            classification = generate_mock_classification(file.filename)
            results.append({
                'filename': file.filename,
                'classification': classification
            })
    
    return jsonify({
        'success': True,
        'total_documents': len(results),
        'results': results,
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/kyc_document_classifier/v1/classifications/<classification_id>', methods=['GET'])
def get_classification(classification_id):
    """Get classification details by ID."""
    # Mock response
    return jsonify({
        'classification_id': classification_id,
        'category': 'Identity Proof',
        'type': 'Passport',
        'confidence': 0.95,
        'timestamp': datetime.now().isoformat(),
        'status': 'completed'
    }), 200


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Mock KYC-AML Classifier API Server")
    print("="*60)
    print("\n🚀 Starting server on http://localhost:8000")
    print("\n📋 Available Endpoints:")
    print("  • GET  /api/kyc_document_classifier/v1/")
    print("  • GET  /api/kyc_document_classifier/v1/health")
    print("  • POST /api/kyc_document_classifier/v1/")
    print("  • POST /api/kyc_document_classifier/v1/classify")
    print("  • POST /api/kyc_document_classifier/v1/batch-classify")
    print("  • GET  /api/kyc_document_classifier/v1/classifications/<id>")
    print("\n🌐 Production API: http://35.184.130.36/api/kyc_document_classifier/v1/")
    print("\n⚠️  This is a MOCK server for testing purposes only!")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=8000, debug=True)
