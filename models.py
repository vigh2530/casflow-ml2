# models.py

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mobile_number = db.Column(db.String(15), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with applications
    applications = db.relationship('Application', backref='user', lazy=True, cascade='all, delete-orphan')

class Application(db.Model):
    id = db.Column(db.String(20), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Personal Information
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(10))
    current_address = db.Column(db.Text)
    
    # Residence Details
    is_rented = db.Column(db.Boolean, default=False)
    has_own_property = db.Column(db.Boolean, default=False)
    
    # Identification
    aadhar_number = db.Column(db.String(12), nullable=False)
    pan_number = db.Column(db.String(10), nullable=False)
    
    # Financial Information
    monthly_salary = db.Column(db.Float, nullable=False)
    company_name = db.Column(db.String(200))
    existing_emi = db.Column(db.Float, default=0)
    cibil_score = db.Column(db.Integer)
    
    # Loan Details
    loan_amount = db.Column(db.Float, nullable=False)
    property_valuation = db.Column(db.Float, nullable=False)
    property_address = db.Column(db.Text)
    is_non_agricultural = db.Column(db.Boolean, default=True)
    has_existing_mortgage = db.Column(db.Boolean, default=False)
    
    # Application Status
    status = db.Column(db.String(20), default='PENDING')
    employment_status = db.Column(db.String(20), default='PENDING')
    kyc_status = db.Column(db.String(20), default='PENDING')
    
    # Reports
    banking_analysis_report = db.Column(db.Text)
    fraud_detection_report = db.Column(db.Text)
    
    # Loan Terms (if approved)
    interest_rate = db.Column(db.Float)
    loan_term_years = db.Column(db.Integer)
    emi_amount = db.Column(db.Float)
    ai_analysis_report = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    na_document_verification = db.Column(db.Text)  # Store NA verification report as JSON
    na_document_status = db.Column(db.String(20), default='PENDING')
    na_document_risk_score = db.Column(db.Float, default=0.0)
    # Relationships
    documents = db.relationship('Document', backref='application', lazy=True, cascade='all, delete-orphan')
    emis = db.relationship('EMI', backref='application', lazy=True, cascade='all, delete-orphan')
    # models.py - Add these fields to your Application model


    employment_verification_status = db.Column(db.String(50), default='PENDING')
    employment_verification_report = db.Column(db.Text)  # Store detailed employment verification
    document_verification_status = db.Column(db.String(50), default='PENDING')
    document_verification_report = db.Column(db.Text)    # Store document verification details
    na_document_verification = db.Column(db.Text)        # Non-agricultural document verification
    overall_risk_score = db.Column(db.Float)             # Overall risk score 0-100
    verification_summary = db.Column(db.Text)            # Final verification summary
    
    # EMI and loan details
    emi_plan_generated = db.Column(db.Boolean, default=False)
    loan_disbursement_date = db.Column(db.DateTime)
    first_emi_date = db.Column(db.DateTime)
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.String(20), db.ForeignKey('application.id'), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)

class EMI(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.String(20), db.ForeignKey('application.id'), nullable=False)
    emi_number = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    amount_due = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='DUE')
    paid_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    