# firebase_config.py
import firebase_admin
from firebase_admin import credentials, firestore
import os

def initialize_firebase():
    """Initialize Firebase with service account"""
    try:
        # Path to your service account key
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully!")
        return firestore.client()
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return None

# Initialize Firebase when module is imported
db = initialize_firebase()