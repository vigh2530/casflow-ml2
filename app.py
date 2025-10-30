# app.py
import os
import json
import random
import io
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import (
    Flask, render_template, request, redirect, url_for, flash, 
    session, send_from_directory, abort, jsonify, make_response, send_file, current_app
)
from config import SQLALCHEMY_DATABASE_URI, SECRET_KEY, UPLOAD_FOLDER
from models import db, User, Application, Document, Admin, EMI
from services import (
    auth_service, storage_service, advance_verification_service, 
    decision_service, notification_service, autofill_service
)
from functools import wraps
from services.ai_analysis_engine import CasaFlowAIAnalyzer
from decimal import Decimal

# PDF Generation imports
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

# Import advanced verification service
from services.advance_verification_service import AdvanceVerificationService

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)

# ===== MOVE AUTHENTICATION DECORATOR HERE - FIRST =====
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow both regular users and admin users
        if 'user_id' not in session and 'admin_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ===== SIMPLY IMPORT AND REGISTER THE BLUEPRINT =====
from admin.routes import admin_bp
app.register_blueprint(admin_bp)

def update_database_schema():
    """Add missing columns to existing database tables"""
    from sqlalchemy import text
    
    try:
        # Check if new columns exist, if not add them
        with app.app_context():
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('application')]
            
            new_columns = {
                'employment_verification_status': 'ALTER TABLE application ADD COLUMN employment_verification_status VARCHAR(50) DEFAULT "PENDING"',
                'employment_verification_report': 'ALTER TABLE application ADD COLUMN employment_verification_report TEXT',
                'document_verification_status': 'ALTER TABLE application ADD COLUMN document_verification_status VARCHAR(50) DEFAULT "PENDING"',
                'document_verification_report': 'ALTER TABLE application ADD COLUMN document_verification_report TEXT',
                'na_document_verification': 'ALTER TABLE application ADD COLUMN na_document_verification TEXT',
                'na_document_status': 'ALTER TABLE application ADD COLUMN na_document_status VARCHAR(50) DEFAULT "PENDING"',
                'na_document_risk_score': 'ALTER TABLE application ADD COLUMN na_document_risk_score FLOAT',
                'overall_risk_score': 'ALTER TABLE application ADD COLUMN overall_risk_score FLOAT',
                'verification_summary': 'ALTER TABLE application ADD COLUMN verification_summary TEXT',
                'emi_plan_generated': 'ALTER TABLE application ADD COLUMN emi_plan_generated BOOLEAN DEFAULT 0',
                'loan_disbursement_date': 'ALTER TABLE application ADD COLUMN loan_disbursement_date DATETIME',
                'first_emi_date': 'ALTER TABLE application ADD COLUMN first_emi_date DATETIME',
                'admin_review_notes': 'ALTER TABLE application ADD COLUMN admin_review_notes TEXT',
                'reviewed_by_admin_id': 'ALTER TABLE application ADD COLUMN reviewed_by_admin_id INTEGER',
                'reviewed_at': 'ALTER TABLE application ADD COLUMN reviewed_at DATETIME',
            }
            
            for column_name, alter_sql in new_columns.items():
                if column_name not in existing_columns:
                    print(f"Adding missing column: {column_name}")
                    db.session.execute(text(alter_sql))
            
            db.session.commit()
            print("Database schema updated successfully!")
            
    except Exception as e:
        print(f"Error updating database schema: {e}")
        db.session.rollback()

# Call the update function when app starts
with app.app_context():
    update_database_schema()

# Helper functions for EMI calculation
def calculate_emi(principal, annual_rate, tenure_months):
    """Calculate EMI using the standard formula"""
    try:
        monthly_rate = annual_rate / 12 / 100
        if monthly_rate == 0:  # Handle zero interest rate
            return principal / tenure_months
        
        emi = principal * monthly_rate * (1 + monthly_rate) ** tenure_months / ((1 + monthly_rate) ** tenure_months - 1)
        return round(emi, 2)
    except Exception as e:
        app.logger.error(f"Error calculating EMI: {e}")
        return 0

def calculate_total_interest(principal, annual_rate, tenure_months):
    """Calculate total interest payable"""
    emi = calculate_emi(principal, annual_rate, tenure_months)
    return round(emi * tenure_months - principal, 2)

def calculate_total_payment(principal, annual_rate, tenure_months):
    """Calculate total payment (principal + interest)"""
    emi = calculate_emi(principal, annual_rate, tenure_months)
    return round(emi * tenure_months, 2)

def generate_amortization_schedule(principal, annual_rate, tenure_months, emi):
    """Generate monthly amortization schedule"""
    try:
        schedule = []
        balance = principal
        monthly_rate = annual_rate / 12 / 100
        start_date = datetime.now()
        
        for month in range(1, tenure_months + 1):
            interest = balance * monthly_rate
            principal_component = emi - interest
            
            # Handle final payment adjustment
            if month == tenure_months:
                principal_component = balance
                emi_adjusted = principal_component + interest
                balance = 0
            else:
                emi_adjusted = emi
                balance -= principal_component
            
            schedule.append({
                'month': month,
                'date': (start_date + relativedelta(months=month)).strftime('%d-%b-%Y'),
                'emi': round(emi_adjusted, 2),
                'principal': round(principal_component, 2),
                'interest': round(interest, 2),
                'balance': max(round(balance, 2), 0)  # Ensure non-negative
            })
        
        return schedule
    except Exception as e:
        app.logger.error(f"Error generating amortization schedule: {e}")
        return []

# INSTANT LOAN DECISION FUNCTIONS
def instant_loan_decision(application, documents):
    """AI-powered instant loan decision making"""
    
    # Run all verifications in parallel (simulated)
    ai_analysis = instant_ai_analysis(application)
    employment_verification = instant_employment_verification(application, documents)
    document_verification = instant_document_verification(documents)
    financial_risk = calculate_financial_risk(application)
    fraud_risk = instant_fraud_detection(application)
    
    # Calculate instant risk score
    overall_risk_score = calculate_instant_risk_score(
        employment_verification, 
        document_verification, 
        financial_risk, 
        fraud_risk,
        ai_analysis
    )
    
    # Make instant decision
    decision_result = make_instant_decision(application, overall_risk_score, ai_analysis)
    
    # Generate instant verification summary
    verification_summary = {
        'timestamp': datetime.utcnow().isoformat(),
        'application_id': application.id,
        'processing_time': 'instant',
        'decision_engine': 'AI_Powered_Instant_Approval',
        'summary': {
            'employment_verification': employment_verification.get('employment_status', 'INSTANT_CHECK'),
            'document_verification': document_verification.get('overall_status', 'INSTANT_CHECK'),
            'overall_risk_score': overall_risk_score,
            'risk_level': get_risk_level(overall_risk_score),
            'ai_confidence': ai_analysis.get('confidence_score', 0.85)
        },
        'instant_checks': {
            'credit_check': 'COMPLETED',
            'employment_verification': 'COMPLETED',
            'document_validation': 'COMPLETED',
            'fraud_detection': 'COMPLETED'
        }
    }
    
    return {
        'status': decision_result['status'],
        'risk_score': overall_risk_score,
        'reason': decision_result['reason'],
        'interest_rate': decision_result.get('interest_rate'),
        'loan_term_years': decision_result.get('loan_term_years'),
        'emi_amount': decision_result.get('emi_amount'),
        'ai_analysis': ai_analysis,
        'employment_verification': employment_verification,
        'document_verification': document_verification,
        'verification_summary': verification_summary,
        'banking_report': instant_banking_analysis(application),
        'fraud_report': {'status': 'LOW_RISK', 'risk_score': fraud_risk}
    }

def instant_ai_analysis(application):
    """Instant AI analysis using ML models"""
    
    # Feature engineering for ML model
    features = {
        'debt_to_income': (application.existing_emi / application.monthly_salary) * 100 if application.monthly_salary > 0 else 100,
        'loan_to_value': (application.loan_amount / application.property_valuation) * 100 if application.property_valuation > 0 else 100,
        'cibil_score': application.cibil_score,
        'salary_adequacy': application.monthly_salary / (application.loan_amount / 100000),  # Salary per lakh loan
        'property_valuation_ratio': application.property_valuation / application.loan_amount,
        'existing_obligations': application.existing_emi > 0
    }
    
    # ML-based risk prediction (simplified)
    risk_factors = []
    
    # CIBIL score impact
    if application.cibil_score >= 800:
        risk_factors.append(0.1)  # Excellent credit
    elif application.cibil_score >= 750:
        risk_factors.append(0.3)  # Good credit
    elif application.cibil_score >= 700:
        risk_factors.append(0.5)  # Fair credit
    else:
        risk_factors.append(0.8)  # Poor credit
    
    # Debt-to-Income ratio
    dti = features['debt_to_income']
    if dti <= 30:
        risk_factors.append(0.2)
    elif dti <= 50:
        risk_factors.append(0.4)
    else:
        risk_factors.append(0.8)
    
    # Loan-to-Value ratio
    ltv = features['loan_to_value']
    if ltv <= 60:
        risk_factors.append(0.1)
    elif ltv <= 80:
        risk_factors.append(0.3)
    else:
        risk_factors.append(0.7)
    
    # Salary adequacy
    if features['salary_adequacy'] >= 5000:  # ₹5000 per lakh loan
        risk_factors.append(0.2)
    elif features['salary_adequacy'] >= 3000:
        risk_factors.append(0.4)
    else:
        risk_factors.append(0.8)
    
    # Calculate average risk
    avg_risk = sum(risk_factors) / len(risk_factors) * 100
    
    return {
        'risk_score': avg_risk,
        'confidence_score': 0.92,  # ML model confidence
        'key_factors': {
            'credit_quality': 'EXCELLENT' if application.cibil_score >= 750 else 'GOOD' if application.cibil_score >= 700 else 'FAIR',
            'debt_burden': 'LOW' if dti <= 40 else 'MODERATE' if dti <= 60 else 'HIGH',
            'property_coverage': 'STRONG' if ltv <= 70 else 'ADEQUATE' if ltv <= 85 else 'WEAK',
            'income_stability': 'STRONG' if features['salary_adequacy'] >= 4000 else 'ADEQUATE'
        },
        'recommendation': 'APPROVE' if avg_risk <= 40 else 'REVIEW' if avg_risk <= 70 else 'REJECT'
    }

def instant_employment_verification(application, documents):
    """Instant employment verification using company database"""
    
    # Use the enhanced verification service with company data
    employment_data = advance_verification_service.verify_employment_documents(application, documents)
    
    # Instant status determination
    if employment_data.get('data_source_match', False):
        employment_data['verification_speed'] = 'INSTANT'
        employment_data['verification_method'] = 'AUTOMATED_DATABASE_MATCH'
    else:
        employment_data['verification_speed'] = 'INSTANT_FALLBACK'
        employment_data['verification_method'] = 'AI_PATTERN_ANALYSIS'
    
    return employment_data

def instant_document_verification(documents):
    """Instant document verification including NA document"""
    
    # UPDATED: Include NA document in the verification
    doc_types = ['bank_statements', 'salary_slips', 'kyc_docs', 'property_valuation_doc', 'legal_clearance', 'na_document']
    verified_docs = {}
    
    for doc_type in doc_types:
        doc_present = any(doc_type in doc.document_type.lower() for doc in documents)
        verified_docs[doc_type] = {
            'status': 'VERIFIED' if doc_present else 'MISSING',
            'risk_score': 10 if doc_present else 80,
            'verification_time': 'INSTANT'
        }
    
    # Calculate overall document status
    missing_docs = [doc_type for doc_type, info in verified_docs.items() if info['status'] == 'MISSING']
    overall_status = 'VERIFIED' if len(missing_docs) == 0 else 'PARTIAL'
    avg_risk = sum(info['risk_score'] for info in verified_docs.values()) / len(verified_docs)
    
    return {
        'overall_status': overall_status,
        'risk_score': avg_risk,
        'verified_documents': verified_docs,
        'missing_documents': missing_docs,
        'processing_time': 'INSTANT'
    }

def instant_fraud_detection(application):
    """Instant fraud detection using pattern analysis"""
    
    fraud_indicators = []
    
    # Check for common fraud patterns
    # Salary consistency check
    if application.monthly_salary > 500000:  # Unusually high salary
        fraud_indicators.append(0.3)
    
    # Property valuation check
    if application.property_valuation / application.loan_amount > 10:  # Very high collateral
        fraud_indicators.append(0.2)
    
    # CIBIL score consistency
    if application.cibil_score >= 800 and application.monthly_salary < 50000:
        fraud_indicators.append(0.4)  # High credit score with low income
    
    # Calculate fraud risk
    fraud_risk = sum(fraud_indicators) / len(fraud_indicators) * 100 if fraud_indicators else 15
    
    return min(fraud_risk, 100)

def instant_banking_analysis(application):
    """Instant banking behavior analysis"""
    
    return {
        'status': 'HEALTHY' if application.existing_emi / application.monthly_salary <= 0.5 else 'MODERATE',
        'analysis': 'INSTANT_PATTERN_ANALYSIS',
        'debt_service_ratio': (application.existing_emi / application.monthly_salary) * 100,
        'recommendation': 'ACCEPTABLE' if application.existing_emi / application.monthly_salary <= 0.6 else 'REVIEW'
    }

def calculate_instant_risk_score(employment_data, document_data, financial_risk, fraud_risk, ai_analysis):
    """Calculate instant overall risk score"""
    
    weights = {
        'employment': 0.25,
        'documents': 0.15,
        'financial': 0.35,
        'fraud': 0.15,
        'ai_prediction': 0.10
    }
    
    weighted_score = (
        employment_data.get('risk_score', 50) * weights['employment'] +
        document_data.get('risk_score', 50) * weights['documents'] +
        financial_risk * weights['financial'] +
        fraud_risk * weights['fraud'] +
        ai_analysis.get('risk_score', 50) * weights['ai_prediction']
    )
    
    return min(100, weighted_score)

def make_instant_decision(application, overall_risk_score, ai_analysis):
    """Make instant loan decision based on risk score and AI analysis"""
    
    # Base decision on risk score
    if overall_risk_score <= 30:
        # Low risk - Auto approve with best terms
        interest_rate = 8.0  # Best rate
        loan_term = 20  # Maximum term
        emi = calculate_emi(application.loan_amount, interest_rate, loan_term * 12)
        
        return {
            'status': 'APPROVED',
            'reason': f'Excellent application! Low risk profile with {overall_risk_score:.1f}% risk score',
            'interest_rate': interest_rate,
            'loan_term_years': loan_term,
            'emi_amount': emi
        }
    
    elif overall_risk_score <= 50:
        # Medium risk - Approve with standard terms
        interest_rate = 10.5  # Standard rate
        loan_term = 15  # Standard term
        emi = calculate_emi(application.loan_amount, interest_rate, loan_term * 12)
        
        return {
            'status': 'APPROVED',
            'reason': f'Good application approved. Risk score: {overall_risk_score:.1f}%',
            'interest_rate': interest_rate,
            'loan_term_years': loan_term,
            'emi_amount': emi
        }
    
    elif overall_risk_score <= 70:
        # Higher risk - Approve with conservative terms
        interest_rate = 12.5  # Higher rate
        loan_term = 10  # Shorter term
        emi = calculate_emi(application.loan_amount, interest_rate, loan_term * 12)
        
        return {
            'status': 'APPROVED',
            'reason': f'Application approved with adjusted terms. Risk score: {overall_risk_score:.1f}%',
            'interest_rate': interest_rate,
            'loan_term_years': loan_term,
            'emi_amount': emi
        }
    
    else:
        # High risk - Reject
        return {
            'status': 'REJECTED',
            'reason': f'Application declined due to high risk profile. Risk score: {overall_risk_score:.1f}%'
        }

def get_risk_level(risk_score):
    """Convert risk score to risk level"""
    if risk_score <= 25:
        return 'VERY_LOW'
    elif risk_score <= 40:
        return 'LOW'
    elif risk_score <= 60:
        return 'MEDIUM'
    elif risk_score <= 75:
        return 'HIGH'
    else:
        return 'VERY_HIGH'

def calculate_financial_risk(application):
    """Calculate financial risk score"""
    try:
        risk_score = 0
        
        # Debt-to-income ratio
        dti = (application.existing_emi / application.monthly_salary) * 100 if application.monthly_salary > 0 else 100
        if dti > 50:
            risk_score += 40
        elif dti > 30:
            risk_score += 20
        else:
            risk_score += 10
        
        # Loan-to-value ratio
        ltv = (application.loan_amount / application.property_valuation) * 100 if application.property_valuation > 0 else 100
        if ltv > 80:
            risk_score += 30
        elif ltv > 60:
            risk_score += 15
        else:
            risk_score += 5
        
        # CIBIL score impact
        if application.cibil_score < 600:
            risk_score += 30
        elif application.cibil_score < 750:
            risk_score += 15
        else:
            risk_score += 5
        
        return min(100, risk_score)
        
    except Exception as e:
        return 50  # Default medium risk

def get_fraud_risk_score(application, fraud_report):
    """Extract fraud risk from fraud report"""
    try:
        if isinstance(fraud_report, dict):
            return fraud_report.get('risk_score', 50)
        elif isinstance(fraud_report, str):
            fraud_data = json.loads(fraud_report)
            return fraud_data.get('risk_score', 50)
        else:
            return 50
    except:
        return 50

def safe_json_loads(json_string, default=None):
    """Safely parse JSON string with error handling"""
    if default is None:
        default = {}
    try:
        return json.loads(json_string) if json_string else default
    except (json.JSONDecodeError, TypeError):
        return default

def get_credit_report(application):
    """Get credit risk analysis report"""
    try:
        # Your credit analysis logic here
        cibil_score = application.cibil_score or 0
        if cibil_score >= 750:
            risk_level = "LOW"
            risk_score = 20
        elif cibil_score >= 650:
            risk_level = "MEDIUM"
            risk_score = 40
        else:
            risk_level = "HIGH"
            risk_score = 70
            
        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'cibil_score': cibil_score,
            'key_factors': {
                'credit_quality': 'EXCELLENT' if cibil_score >= 750 else 'GOOD' if cibil_score >= 650 else 'FAIR',
                'payment_history': 'CLEAN',
                'credit_utilization': 'OPTIMAL'
            }
        }
    except Exception as e:
        app.logger.error(f"Error generating credit report: {e}")
        return {}

def get_banking_report(application):
    """Get banking behavior analysis report"""
    try:
        # Calculate debt-to-income ratio
        monthly_salary = application.monthly_salary or 0
        existing_emi = application.existing_emi or 0
        debt_service_ratio = (existing_emi / monthly_salary * 100) if monthly_salary > 0 else 0
        
        if debt_service_ratio <= 30:
            status = "HEALTHY"
        elif debt_service_ratio <= 50:
            status = "MODERATE"
        else:
            status = "HIGH_RISK"
            
        return {
            'status': status,
            'debt_service_ratio': debt_service_ratio,
            'monthly_salary': monthly_salary,
            'existing_obligations': existing_emi
        }
    except Exception as e:
        app.logger.error(f"Error generating banking report: {e}")
        return {}

def initialize_na_verification(application_id):
    """Initialize NA document verification process"""
    application = Application.query.get(application_id)
    if not application:
        return
    
    # Find NA document - check for both possible document types
    na_document = None
    for doc in application.documents:
        if doc.document_type in ['NON_AGRICULTURAL_DECLARATION', 'NA_DOCUMENT']:
            na_document = doc
            break
    
    if na_document:
        # Start verification process
        na_report = verify_na_document(na_document, application)
        application.na_document_verification = json.dumps(na_report)
        application.na_document_status = na_report.get('status', 'PENDING')
        application.na_document_risk_score = na_report.get('risk_score', 0.0)
        
        # If document is present and verified, update risk score
        if na_report.get('status') == 'VERIFIED':
            application.na_document_risk_score = 10.0  # Low risk for verified documents
        elif na_report.get('status') == 'VERIFIED_WITH_NOTES':
            application.na_document_risk_score = 30.0  # Medium risk
        else:
            application.na_document_risk_score = na_report.get('risk_score', 100.0)
    else:
        # No NA document found
        na_report = {
            'status': 'PENDING',
            'risk_score': 100.0,
            'details': 'Non-agricultural declaration document not uploaded',
            'issues': ['Document required for property classification verification'],
            'verification_steps': [
                {
                    'step': 'Document Upload',
                    'status': 'FAILED',
                    'details': 'No NA document found in uploaded documents'
                }
            ],
            'recommendation': 'Upload non-agricultural declaration certificate'
        }
        application.na_document_verification = json.dumps(na_report)
        application.na_document_status = 'PENDING'
        application.na_document_risk_score = 100.0
    
    db.session.commit()
    return na_report

def verify_na_document(document, application):
    """Verify Non-Agricultural document with improved logic"""
    verification_steps = []
    issues = []
    risk_score = 0.0
    
    try:
        # Step 1: Document Presence Check
        verification_steps.append({
            'step': 'Document Presence',
            'status': 'PASSED',
            'details': 'NA document found in uploaded documents'
        })
        
        # Step 2: Document Format Check
        if document.filename and document.filename.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
            verification_steps.append({
                'step': 'Format Check',
                'status': 'PASSED',
                'details': 'Document format is acceptable'
            })
        else:
            verification_steps.append({
                'step': 'Format Check',
                'status': 'FAILED',
                'details': 'Unsupported document format'
            })
            issues.append('Document format not supported')
            risk_score += 30
        
        # Step 3: Document Size Check (if file_data exists)
        if hasattr(document, 'file_data') and document.file_data:
            if len(document.file_data) < 10 * 1024 * 1024:  # 10MB limit
                verification_steps.append({
                    'step': 'Size Check',
                    'status': 'PASSED',
                    'details': 'Document size is within limits'
                })
            else:
                verification_steps.append({
                    'step': 'Size Check',
                    'status': 'FAILED',
                    'details': 'Document exceeds size limits'
                })
                issues.append('Document size too large')
                risk_score += 20
        else:
            # If no file_data, assume size is acceptable
            verification_steps.append({
                'step': 'Size Check',
                'status': 'PASSED',
                'details': 'Document size assumed acceptable'
            })
        
        # Step 4: Cross-verification with other property documents
        property_docs = [doc for doc in application.documents 
                        if doc.document_type in ['PROPERTY_VALUATION', 'LEGAL_CLEARANCE', 'PROPERTY_VALUATION_DOC']]
        
        if property_docs:
            verification_steps.append({
                'step': 'Cross-Verification',
                'status': 'PASSED',
                'details': f'Found {len(property_docs)} related property documents'
            })
        else:
            verification_steps.append({
                'step': 'Cross-Verification',
                'status': 'WARNING',
                'details': 'No related property documents found for cross-verification'
            })
            issues.append('Missing supporting property documents')
            risk_score += 15
        
        # Step 5: Property Type Validation
        if application.is_non_agricultural:
            verification_steps.append({
                'step': 'Property Type Validation',
                'status': 'PASSED',
                'details': 'Property marked as non-agricultural in application'
            })
        else:
            verification_steps.append({
                'step': 'Property Type Validation',
                'status': 'WARNING',
                'details': 'Property type not specified as non-agricultural'
            })
            risk_score += 10
        
        # Step 6: Basic Content Validation
        verification_steps.append({
            'step': 'Content Validation',
            'status': 'PENDING_MANUAL_REVIEW',
            'details': 'Requires manual review for content accuracy and validity'
        })
        
        # Calculate final status based on risk score
        if risk_score == 0:
            status = 'VERIFIED'
            details = 'Non-agricultural declaration document verified successfully'
            final_risk_score = 10.0  # Low risk for fully verified
        elif risk_score <= 25:
            status = 'VERIFIED_WITH_NOTES'
            details = 'Document verified with minor issues requiring attention'
            final_risk_score = 25.0
        elif risk_score <= 50:
            status = 'REVIEW_NEEDED'
            details = 'Document requires manual review due to moderate issues'
            final_risk_score = 50.0
        else:
            status = 'PENDING'
            details = 'Document verification pending due to significant issues'
            final_risk_score = min(risk_score, 100.0)
        
        return {
            'status': status,
            'risk_score': final_risk_score,
            'details': details,
            'issues': issues,
            'verification_steps': verification_steps,
            'document_id': document.id,
            'document_type': document.document_type,
            'filename': document.filename,
            'verified_at': datetime.utcnow().isoformat(),
            'recommendation': 'Document appears valid but requires final manual confirmation'
        }
        
    except Exception as e:
        app.logger.error(f"Error verifying NA document: {e}")
        return {
            'status': 'ERROR',
            'risk_score': 100.0,
            'details': f'Error during verification: {str(e)}',
            'issues': ['Verification process failed - system error'],
            'verification_steps': [{
                'step': 'System Verification',
                'status': 'ERROR',
                'details': f'System error: {str(e)}'
            }],
            'recommendation': 'Retry verification or contact support'
        }

def verify_single_document(document, doc_type):
    """Verify a single document"""
    try:
        # Basic verification logic for each document type
        risk_score = 10  # Default low risk for present documents
        issues = []
        
        # Type-specific validations
        if doc_type == 'NON_AGRICULTURAL_DECLARATION':
            # NA document specific checks
            if not document.filename.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                issues.append('Invalid file format')
                risk_score = 50
            if len(document.file_data) > 10 * 1024 * 1024:
                issues.append('File size too large')
                risk_score = 40
        
        return {
            'document_type': doc_type,
            'name': document.document_type.replace('_', ' ').title(),
            'status': 'VERIFIED' if risk_score <= 20 else 'REVIEW_NEEDED',
            'risk_score': risk_score,
            'issues': issues,
            'verified_at': datetime.utcnow().isoformat()
        }
    except Exception as e:
        app.logger.error(f"Error verifying document {doc_type}: {e}")
        return {
            'document_type': doc_type,
            'name': doc_type.replace('_', ' ').title(),
            'status': 'ERROR',
            'risk_score': 100.0,
            'issues': ['Verification error'],
            'verified_at': datetime.utcnow().isoformat()
        }

def verify_all_documents(application):
    """Verify all documents including NA document"""
    documents_report = {
        'overall_status': 'PENDING',
        'overall_risk_score': 0.0,
        'documents': [],
        'verification_summary': '',
        'issues_found': 0
    }
    
    total_risk = 0
    document_count = 0
    verified_count = 0
    
    # Verify each document type
    document_types = {
        'BANK_STATEMENTS': 'Bank Statements',
        'SALARY_SLIPS': 'Salary Slips', 
        'KYC_DOCS': 'KYC Documents',
        'PROPERTY_VALUATION': 'Property Valuation',
        'LEGAL_CLEARANCE': 'Legal Clearance',
        'NON_AGRICULTURAL_DECLARATION': 'Non-Agricultural Declaration'
    }
    
    for doc_type, doc_name in document_types.items():
        document = next((doc for doc in application.documents if doc.document_type == doc_type), None)
        
        if document:
            doc_report = verify_single_document(document, doc_type)
            documents_report['documents'].append(doc_report)
            total_risk += doc_report.get('risk_score', 0)
            document_count += 1
            if doc_report.get('status') == 'VERIFIED':
                verified_count += 1
        else:
            # Document missing
            documents_report['documents'].append({
                'document_type': doc_type,
                'name': doc_name,
                'status': 'MISSING',
                'risk_score': 100.0,
                'issues': ['Document not uploaded']
            })
            total_risk += 100
            document_count += 1
    
    # Calculate overall status
    if document_count > 0:
        documents_report['overall_risk_score'] = total_risk / document_count
        
        if verified_count == document_count:
            documents_report['overall_status'] = 'VERIFIED'
            documents_report['verification_summary'] = 'All documents verified successfully'
        elif verified_count >= document_count * 0.7:
            documents_report['overall_status'] = 'VERIFIED_WITH_NOTES'
            documents_report['verification_summary'] = 'Most documents verified, minor issues found'
        else:
            documents_report['overall_status'] = 'PENDING'
            documents_report['verification_summary'] = 'Multiple documents require verification'
    
    documents_report['issues_found'] = len([doc for doc in documents_report['documents'] 
                                          if doc.get('issues')])
    
    return documents_report

def generate_verification_summary(application):
    """Generate comprehensive verification summary including NA document"""
    # Get all verification reports
    employment_report = safe_json_loads(application.employment_verification_report) or {}
    document_report = safe_json_loads(application.document_verification_report) or {}
    na_report = safe_json_loads(application.na_document_verification) or {}
    
    # Calculate overall risk score (weighted average)
    weights = {
        'employment': 0.3,
        'documents': 0.4,
        'na_document': 0.3
    }
    
    employment_risk = employment_report.get('risk_score', 0) or 0
    document_risk = document_report.get('overall_risk_score', 0) or 0
    na_risk = na_report.get('risk_score', 0) or 0
    
    overall_risk = (
        employment_risk * weights['employment'] +
        document_risk * weights['documents'] + 
        na_risk * weights['na_document']
    )
    
    # Determine overall status
    if overall_risk <= 25:
        risk_level = 'VERY_LOW'
        status = 'APPROVED'
    elif overall_risk <= 50:
        risk_level = 'LOW'
        status = 'APPROVED'
    elif overall_risk <= 75:
        risk_level = 'MEDIUM'
        status = 'UNDER_REVIEW'
    else:
        risk_level = 'HIGH'
        status = 'PENDING'
    
    summary = {
        'overall_risk_score': overall_risk,
        'risk_level': risk_level,
        'recommended_status': status,
        'component_scores': {
            'employment': employment_risk,
            'documents': document_risk,
            'na_document': na_risk
        },
        'verification_status': {
            'employment': employment_report.get('status', 'PENDING'),
            'documents': document_report.get('overall_status', 'PENDING'),
            'na_document': na_report.get('status', 'PENDING')
        },
        'summary_text': f"Overall risk: {risk_level}. Employment: {employment_report.get('status')}, "
                       f"Documents: {document_report.get('overall_status')}, "
                       f"NA Document: {na_report.get('status')}",
        'timestamp': datetime.utcnow().isoformat()
    }
    
    return summary

def get_fraud_report(application):
    """Get fraud detection analysis report"""
    try:
        # Simple fraud detection logic
        risk_factors = []
        
        # Check for basic fraud indicators
        if application.cibil_score and application.cibil_score < 300:
            risk_factors.append("Unusually low CIBIL score")
            
        if application.monthly_salary and application.monthly_salary > 500000:
            risk_factors.append("Unusually high salary declaration")
            
        risk_score = min(len(risk_factors) * 25, 100)
        
        return {
            'status': 'LOW_RISK' if risk_score < 50 else 'MEDIUM_RISK' if risk_score < 75 else 'HIGH_RISK',
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'verification_status': 'PASSED' if risk_score < 50 else 'REVIEW_NEEDED'
        }
    except Exception as e:
        app.logger.error(f"Error generating fraud report: {e}")
        return {}

def convert_to_old_format(new_analysis):
    """Convert new instant decision format to old template-compatible format"""
    old_format = {}
    
    # Map risk_score to financial_health_score (inverted)
    if 'risk_score' in new_analysis:
        # Convert risk score (0-100, lower is better) to health score (0-100, higher is better)
        old_format['financial_health_score'] = max(0, 100 - new_analysis['risk_score'])
    
    # Map key_factors to risk_factors
    if 'key_factors' in new_analysis:
        risk_factors = []
        for factor, rating in new_analysis['key_factors'].items():
            risk_factors.append(f"{factor.replace('_', ' ').title()}: {rating}")
        old_format['risk_factors'] = risk_factors
    
    # Map recommendation
    if 'recommendation' in new_analysis:
        old_format['recommendation'] = new_analysis['recommendation']
    
    # Add confidence score if available
    if 'confidence_score' in new_analysis:
        old_format['confidence_score'] = new_analysis['confidence_score']
    
    # Ensure we have all required fields with defaults
    old_format.setdefault('financial_health_score', 75)
    old_format.setdefault('risk_factors', ['No risk factors identified'])
    old_format.setdefault('recommendation', 'REVIEW')
    old_format.setdefault('confidence_score', 0.85)
    
    return old_format

def format_data_for_application(parsed_data):
    """Convert parsed data to match your application form fields"""
    formatted = {}
    
    # Direct mappings
    direct_mappings = {
        'first_name': 'first_name',
        'last_name': 'last_name',
        'email': 'email',
        'gender': 'gender',
        'address': 'current_address',
        'aadhaar': 'aadhar_number',
        'pan': 'pan_number',
        'salary': 'monthly_salary',
        'company': 'company_name',
        'existing_loan': 'existing_emi',
        'cibil': 'cibil_score',
        'loan_amount': 'loan_amount',
        'property_value': 'property_valuation',
        'property_address': 'property_address'
    }
    
    for source_key, target_key in direct_mappings.items():
        if source_key in parsed_data and parsed_data[source_key] is not None:
            formatted[target_key] = parsed_data[source_key]
    
    # Boolean field conversions
    if 'residence_status' in parsed_data:
        residence_status = parsed_data['residence_status'].lower()
        formatted['is_rented'] = residence_status == 'rent'
        formatted['has_own_property'] = residence_status == 'owned'
    
    if 'other_properties' in parsed_data:
        formatted['has_own_property'] = parsed_data['other_properties']
    
    if 'non_agricultural' in parsed_data:
        formatted['is_non_agricultural'] = parsed_data['non_agricultural']
    
    if 'mortgage' in parsed_data:
        formatted['has_existing_mortgage'] = parsed_data['mortgage']
    
    return formatted

def reprocess_old_application(application):
    """Reprocess old applications to generate missing verification data"""
    try:
        app.logger.info(f"Reprocessing old application: {application.id}")
        
        # Get documents for the application
        documents = application.documents
        
        # Initialize NA document verification if missing
        if application.na_document_verification is None:
            initialize_na_verification(application.id)
        
        # Generate missing verification data using instant processing
        decision_result = instant_loan_decision(application, documents)
        
        # Update application with new data
        if application.overall_risk_score is None:
            application.overall_risk_score = decision_result['risk_score']
        
        if application.ai_analysis_report is None:
            application.ai_analysis_report = json.dumps(decision_result['ai_analysis'])
        
        if application.employment_verification_report is None:
            application.employment_verification_report = json.dumps(decision_result['employment_verification'])
            application.employment_verification_status = decision_result['employment_verification'].get('employment_status', 'PROCESSED')
        
        if application.document_verification_report is None:
            application.document_verification_report = json.dumps(decision_result['document_verification'])
            application.document_verification_status = decision_result['document_verification'].get('overall_status', 'PROCESSED')
        
        if application.verification_summary is None:
            application.verification_summary = json.dumps(decision_result['verification_summary'])
        
        # Generate comprehensive verification summary
        verification_summary = generate_verification_summary(application)
        application.verification_summary = json.dumps(verification_summary)
        
        db.session.commit()
        app.logger.info(f"Successfully reprocessed application: {application.id}")
        
        return True
        
    except Exception as e:
        app.logger.error(f"Error reprocessing application {application.id}: {str(e)}")
        db.session.rollback()
        return False

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        if form_type == 'admin':
            username = request.form.get('username')
            password = request.form.get('password')
            admin = Admin.query.filter_by(username=username).first()
            if admin and admin.check_password(password):
                session['admin_id'] = admin.id
                session['admin_logged_in'] = True
                flash('Admin login successful!', 'success')
                return redirect(url_for('admin.dashboard'))
            else:
                flash('Invalid admin credentials.', 'danger')
        elif form_type == 'user':
            if 'mobile_number' in request.form:
                mobile = request.form['mobile_number']
                otp = auth_service.generate_and_store_otp(mobile)
                auth_service.send_otp_via_sms(mobile, otp)
                session['mobile_for_verification'] = mobile
                return render_template('login.html', mobile_sent=True, mobile=mobile)
            elif 'otp' in request.form:
                mobile = session.get('mobile_for_verification')
                otp = request.form['otp']
                if mobile and auth_service.verify_otp(mobile, otp):
                    user = User.query.filter_by(mobile_number=mobile).first()
                    if not user:
                        user = User(mobile_number=mobile)
                        db.session.add(user)
                        db.session.commit()
                    session['user_id'] = user.id
                    session['user_logged_in'] = True
                    session.pop('mobile_for_verification', None)
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid OTP.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Check if user is admin and redirect to admin dashboard
    if 'admin_id' in session:
        return redirect(url_for('admin.dashboard'))
    
    # Regular user dashboard
    user_id = session['user_id']
    user_applications = Application.query.filter_by(user_id=user_id).order_by(Application.created_at.desc()).all()
    return render_template('dashboard.html', applications=user_applications)

@app.route('/apply', methods=['GET', 'POST'])
@login_required
def apply():
    # Only regular users can apply
    if 'admin_id' in session:
        flash('Admin users cannot submit applications.', 'error')
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        try:
            # Process form submission
            is_rented = request.form.get('is_rented') == 'True'
            has_own_property = request.form.get('has_own_property') == 'True'
            is_non_agricultural = request.form.get('is_non_agricultural') == 'True'
            has_existing_mortgage = request.form.get('has_existing_mortgage') == 'True'
            
            new_app = Application(
                id=storage_service.generate_unique_app_id(),
                user_id=session['user_id'],
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                email=request.form['email'],
                gender=request.form.get('gender'),
                current_address=request.form.get('current_address'),
                is_rented=is_rented,
                has_own_property=has_own_property,
                aadhar_number=request.form['aadhar_number'],
                pan_number=request.form['pan_number'],
                monthly_salary=float(request.form['monthly_salary']),
                company_name=request.form.get('company_name'),
                existing_emi=float(request.form['existing_emi']),
                cibil_score=int(request.form['cibil_score']),
                loan_amount=float(request.form['loan_amount']),
                property_valuation=float(request.form['property_valuation']),
                property_address=request.form.get('property_address'),
                is_non_agricultural=is_non_agricultural,
                has_existing_mortgage=has_existing_mortgage
            )
            db.session.add(new_app)
            
            user = User.query.get(session['user_id'])
            if user is None:
                flash('Your session has expired. Please log out and log in again.', 'danger')
                return redirect(url_for('user_logout'))

            # Updated document list including NA document
            files_to_upload = {
                'bank_statements': request.files.get('bank_statements'),
                'salary_slips': request.files.get('salary_slips'),
                'kyc_docs': request.files.get('kyc_docs'),
                'property_valuation_doc': request.files.get('property_valuation_doc'),
                'legal_clearance': request.files.get('legal_clearance'),
                'na_document': request.files.get('na_document'),  # NEW: NA document
            }
            saved_docs = storage_service.save_application_documents(user.mobile_number, new_app.id, files_to_upload)
            for doc in saved_docs:
                db.session.add(doc)
                
            db.session.commit()

            # Initialize NA document verification
            initialize_na_verification(new_app.id)
            
            # INSTANT AI-POWERED DECISION MAKING
            decision_result = instant_loan_decision(new_app, saved_docs)
            
            # Update application with instant decision
            new_app.status = decision_result['status']
            new_app.overall_risk_score = decision_result['risk_score']
            new_app.interest_rate = decision_result.get('interest_rate')
            new_app.loan_term_years = decision_result.get('loan_term_years')
            new_app.emi_amount = decision_result.get('emi_amount')
            
            # Save AI analysis and verification reports
            new_app.ai_analysis_report = json.dumps(decision_result['ai_analysis'])
            new_app.employment_verification_report = json.dumps(decision_result['employment_verification'])
            new_app.document_verification_report = json.dumps(decision_result['document_verification'])
            new_app.verification_summary = json.dumps(decision_result['verification_summary'])
            
            # Set verification statuses
            new_app.employment_verification_status = decision_result['employment_verification'].get('employment_status', 'PENDING')
            new_app.document_verification_status = decision_result['document_verification'].get('overall_status', 'PENDING')
            
            # Save banking and fraud reports
            new_app.banking_analysis_report = json.dumps(decision_result.get('banking_report', {}))
            new_app.fraud_detection_report = json.dumps(decision_result.get('fraud_report', {}))
            
            # Generate comprehensive verification summary
            verification_summary = generate_verification_summary(new_app)
            new_app.verification_summary = json.dumps(verification_summary)
            
            # Create EMI records if approved
            if new_app.status == 'APPROVED' and new_app.emi_amount:
                EMI.query.filter_by(application_id=new_app.id).delete()
                for i in range(1, new_app.loan_term_years * 12 + 1):
                    due_date = datetime.utcnow().date() + relativedelta(months=i)
                    new_emi_record = EMI(
                        application_id=new_app.id,
                        emi_number=i,
                        due_date=due_date,
                        amount_due=new_app.emi_amount,
                        status='DUE'
                    )
                    db.session.add(new_emi_record)
            
            db.session.commit()
            
            # Send instant notification
            notification_service.send_decision_notification(new_app, decision_result['reason'])
            
            flash(f'Application #{new_app.id} processed instantly! Decision: {new_app.status}', 'success')
            return redirect(url_for('application_result', app_id=new_app.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting application: {str(e)}', 'error')
            return render_template('apply.html')

    # GET request - render the form
    return render_template('apply.html')

@app.route('/auto-fill', methods=['POST'])
@login_required
def auto_fill():
    """Handle auto-fill form request"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if file and file.filename.endswith('.txt'):
            content = file.read().decode('utf-8')
            parsed_data = autofill_service.parse_text_data(content)
            
            # Convert to your application model format
            formatted_data = format_data_for_application(parsed_data)
            
            return jsonify({
                'success': True, 
                'data': formatted_data,
                'message': 'Form auto-filled successfully!'
            })
        else:
            return jsonify({'success': False, 'error': 'Please upload a text file (.txt)'})
            
    except Exception as e:
        app.logger.error(f"Auto-fill error: {str(e)}")
        return jsonify({'success': False, 'error': f'Error processing file: {str(e)}'})

@app.route('/status/<app_id>')
@login_required
def status(app_id):
    try:
        # Check if current user is admin
        is_admin = 'admin_id' in session or session.get('admin_logged_in', False)
        
        # Fetch application based on user type
        if is_admin:
            # Admin can view any application
            application = Application.query.filter_by(id=app_id).first()
            if not application:
                flash('Application not found.', 'error')
                return redirect(url_for('admin.dashboard'))
        else:
            # Regular user can only view their own applications
            application = Application.query.filter_by(id=app_id, user_id=session['user_id']).first()
            if not application:
                flash('Application not found or you do not have permission to view it.', 'error')
                return redirect(url_for('dashboard'))
        
        # Safely load reports with comprehensive error handling
        def safe_json_loads(json_string, default=None):
            """Safely parse JSON strings with error handling"""
            if default is None:
                default = {}
            try:
                if json_string and json_string.strip():
                    return json.loads(json_string)
                else:
                    return default
            except (json.JSONDecodeError, TypeError, AttributeError):
                return default
        
        # Load all reports with safe defaults
        banking_report = safe_json_loads(application.banking_analysis_report)
        fraud_report = safe_json_loads(application.fraud_detection_report)
        credit_report = safe_json_loads(application.ai_analysis_report)
        
        # Load enhanced verification reports (might not exist for older applications)
        employment_report = safe_json_loads(application.employment_verification_report)
        document_report = safe_json_loads(application.document_verification_report)
        na_report = safe_json_loads(application.na_document_verification)
        verification_summary = safe_json_loads(application.verification_summary)

        # Calculate amortization schedule if approved
        amortization_schedule = []
        if application.status == 'APPROVED' and application.interest_rate:
            try:
                tenure_months = application.loan_term_years * 12
                emi = application.emi_amount or calculate_emi(application.loan_amount, application.interest_rate, tenure_months)
                amortization_schedule = generate_amortization_schedule(
                    application.loan_amount, application.interest_rate, tenure_months, emi
                )
            except Exception as e:
                app.logger.error(f"Error generating amortization schedule: {e}")
                amortization_schedule = []

        return render_template('status.html', 
                               application=application,
                               banking_report=banking_report,
                               fraud_report=fraud_report,
                               credit_report=credit_report,
                               employment_report=employment_report,
                               document_report=document_report,
                               na_report=na_report,
                               verification_summary=verification_summary,
                               amortization_schedule=amortization_schedule,
                               is_admin=is_admin)
    
    except Exception as e:
        app.logger.error(f"Error loading application {app_id}: {str(e)}")
        flash('Error loading application details. Please try again.', 'error')
        if 'admin_id' in session:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('dashboard'))

@app.route('/fix-application/<app_id>')
@login_required
def fix_application(app_id):
    """Route to manually fix old applications"""
    try:
        # Check if current user is admin or owns the application
        is_admin = 'admin_id' in session or session.get('admin_logged_in', False)
        
        if is_admin:
            application = Application.query.filter_by(id=app_id).first()
        else:
            application = Application.query.filter_by(id=app_id, user_id=session['user_id']).first()
        
        if not application:
            flash('Application not found.', 'error')
            return redirect(url_for('dashboard'))
        
        # Reprocess the application
        success = reprocess_old_application(application)
        
        if success:
            flash(f'Application #{application.id} has been updated with new verification data!', 'success')
        else:
            flash(f'Failed to update application #{application.id}.', 'error')
        
        return redirect(url_for('status', app_id=app_id))
        
    except Exception as e:
        flash(f'Error fixing application: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/fix-all-pending')
@login_required
def fix_all_pending():
    """Fix all pending applications (admin only)"""
    try:
        if 'admin_id' not in session:
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        
        pending_apps = Application.query.filter_by(status='PENDING').all()
        fixed_count = 0
        
        for app in pending_apps:
            if app.overall_risk_score is None:
                if reprocess_old_application(app):
                    fixed_count += 1
        
        flash(f'Successfully updated {fixed_count} pending applications with AI verification data!', 'success')
        return redirect(url_for('admin.dashboard'))
        
    except Exception as e:
        flash(f'Error fixing applications: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@app.route('/debug-application/<app_id>')
@login_required
def debug_application(app_id):
    """Debug route to check application data"""
    application = Application.query.filter_by(id=app_id, user_id=session['user_id']).first()
    if not application:
        return "Application not found", 404
    
    debug_info = {
        'app_id': application.id,
        'status': application.status,
        'has_ai_analysis': bool(application.ai_analysis_report),
        'has_banking_report': bool(application.banking_analysis_report),
        'has_employment_report': bool(application.employment_verification_report),
        'created_at': application.created_at,
        'loan_amount': application.loan_amount,
        'interest_rate': getattr(application, 'interest_rate', 'Not set'),
        'emi_amount': getattr(application, 'emi_amount', 'Not set')
    }
    
    return jsonify(debug_info)

@app.route('/generate_loan_document/<app_id>')
@login_required
def generate_loan_document(app_id):
    """Generate printable PDF loan document"""
    try:
        # Check if user is admin
        is_admin = 'admin_id' in session
        
        if is_admin:
            # Admin can generate document for any application
            application = Application.query.filter_by(id=app_id).first()
        else:
            # Regular user can only generate for their own applications
            application = Application.query.filter_by(id=app_id, user_id=session['user_id']).first()
        
        if not application:
            return "Application not found", 404
        
        if application.status != 'APPROVED':
            return "Loan not approved", 400

        # Calculate loan details
        loan_amount = application.loan_amount
        interest_rate = getattr(application, 'interest_rate', 8.5)
        tenure_months = getattr(application, 'loan_term_years', 5) * 12
        emi = application.emi_amount or calculate_emi(loan_amount, interest_rate, tenure_months)
        total_interest = calculate_total_interest(loan_amount, interest_rate, tenure_months)
        total_payment = calculate_total_payment(loan_amount, interest_rate, tenure_months)

        # Create PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.darkblue,
            spaceAfter=30,
            alignment=1  # Center
        )
        
        heading_style = ParagraphStyle(
            'Heading2',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.darkblue,
            spaceAfter=12
        )
        
        # Header
        elements.append(Paragraph("LOAN APPROVAL AGREEMENT", title_style))
        elements.append(Spacer(1, 10))
        
        # Agreement Details
        elements.append(Paragraph("Agreement Details", heading_style))
        agreement_data = [
            ['Loan Agreement Number:', f'LA-{application.id}-{datetime.now().strftime("%Y%m%d")}'],
            ['Date of Approval:', datetime.now().strftime('%d-%b-%Y')],
            ['', ''],
        ]
        
        agreement_table = Table(agreement_data, colWidths=[2.5*inch, 3*inch])
        agreement_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(agreement_table)
        elements.append(Spacer(1, 15))
        
        # Borrower Information
        elements.append(Paragraph("Borrower Information", heading_style))
        borrower_data = [
            ['Full Name:', f'{application.first_name} {application.last_name}'],
            ['Email Address:', application.email],
            ['PAN Number:', application.pan_number],
            ['Aadhar Number:', application.aadhar_number],
            ['Address:', application.current_address],
            ['', ''],
        ]
        
        borrower_table = Table(borrower_data, colWidths=[2.5*inch, 3*inch])
        borrower_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ]))
        elements.append(borrower_table)
        elements.append(Spacer(1, 15))
        
        # Loan Terms
        elements.append(Paragraph("Loan Terms & Conditions", heading_style))
        loan_data = [
            ['Description', 'Details'],
            ['Loan Amount:', f'₹{loan_amount:,.2f}'],
            ['Interest Rate:', f'{interest_rate}% per annum'],
            ['Loan Tenure:', f'{tenure_months} months ({tenure_months//12} years)'],
            ['Monthly EMI:', f'₹{emi:,.2f}'],
            ['Total Interest Payable:', f'₹{total_interest:,.2f}'],
            ['Total Payment:', f'₹{total_payment:,.2f}'],
            ['Processing Fees:', '₹0 (Waived)'],
            ['Prepayment Charges:', '1% after 12 months'],
        ]
        
        loan_table = Table(loan_data, colWidths=[2.5*inch, 3*inch])
        loan_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(loan_table)
        elements.append(Spacer(1, 20))
        
        # Important Notes
        elements.append(Paragraph("Important Notes", heading_style))
        notes = [
            "1. This loan agreement is subject to the terms and conditions mentioned herein.",
            "2. The borrower agrees to pay the EMI on or before the due date each month.",
            "3. Late payments will attract a penalty of 2% per month on the overdue amount.",
            "4. The borrower can prepay the loan after 12 months with applicable charges.",
            "5. This agreement is governed by the laws of India.",
        ]
        
        for note in notes:
            elements.append(Paragraph(note, styles['Normal']))
            elements.append(Spacer(1, 5))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Return PDF response
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'Loan_Agreement_{application.id}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        app.logger.error(f"Error generating PDF: {e}")
        return f"Error generating document: {str(e)}", 500
@app.route('/force-na-verification/<app_id>')
@login_required
def force_na_verification(app_id):
    """Force NA document verification for an application"""
    try:
        # Check if current user is admin or owns the application
        is_admin = 'admin_id' in session or session.get('admin_logged_in', False)
        
        if is_admin:
            application = Application.query.filter_by(id=app_id).first()
        else:
            application = Application.query.filter_by(id=app_id, user_id=session['user_id']).first()
        
        if not application:
            flash('Application not found.', 'error')
            return redirect(url_for('dashboard'))
        
        # Force NA verification
        na_report = initialize_na_verification(application.id)
        
        if na_report:
            flash(f'NA document verification completed for application #{application.id}. Status: {na_report.get("status")}', 'success')
        else:
            flash('Failed to verify NA document.', 'error')
        
        return redirect(url_for('verification_report', app_id=app_id))
        
    except Exception as e:
        flash(f'Error verifying NA document: {str(e)}', 'error')
        return redirect(url_for('verification_report', app_id=app_id))
@app.route('/verification_report/<app_id>')
@login_required
def verification_report(app_id):
    """Display comprehensive verification report"""
    # Check if user is admin
    is_admin = 'admin_id' in session
    
    if is_admin:
        # Admin can view any application
        application = Application.query.filter_by(id=app_id).first()
        if not application:
            flash('Application not found.', 'error')
            return redirect(url_for('admin.dashboard'))
    else:
        # Regular user can only view their own applications
        application = Application.query.filter_by(id=app_id, user_id=session['user_id']).first_or_404()
    
    # Use safe JSON loading function for existing reports
    def safe_json_loads(json_string, default=None):
        if default is None:
            default = {}
        try:
            if json_string and json_string.strip():
                return json.loads(json_string)
            else:
                return default
        except (json.JSONDecodeError, TypeError, AttributeError):
            return default
    
    # Parse existing verification reports with safe loading
    employment_report = safe_json_loads(application.employment_verification_report)
    document_report = safe_json_loads(application.document_verification_report)
    verification_summary = safe_json_loads(application.verification_summary)
    
    # Get new verification reports from helper functions
    credit_report = get_credit_report(application) or {}
    banking_report = get_banking_report(application) or {}
    fraud_report = get_fraud_report(application) or {}
    
    # Handle NA document verification - use existing if available, otherwise create default
    na_report = safe_json_loads(application.na_document_verification)
    if not na_report:
        na_report = {
            'status': 'PENDING',
            'risk_score': 0.0,
            'details': 'Non-agricultural document verification pending',
            'issues': ['Document not uploaded or processed yet']
        }
    
    # Get amortization schedule for approved loans
    amortization_schedule = []
    if application.status == 'APPROVED' and application.interest_rate:
        try:
            tenure_months = application.loan_term_years * 12
            emi = application.emi_amount or calculate_emi(application.loan_amount, application.interest_rate, tenure_months)
            amortization_schedule = generate_amortization_schedule(
                application.loan_amount, application.interest_rate, tenure_months, emi
            )
        except Exception as e:
            app.logger.error(f"Error generating amortization schedule: {e}")
            amortization_schedule = []
    
    return render_template('verification_report.html',
                         application=application,
                         employment_report=employment_report,
                         document_report=document_report,
                         verification_summary=verification_summary,
                         credit_report=credit_report,
                         banking_report=banking_report,
                         fraud_report=fraud_report,
                         na_report=na_report,
                         amortization_schedule=amortization_schedule)

@app.route('/upload-na-document/<app_id>', methods=['POST'])
@login_required
def upload_na_document(app_id):
    """Handle NA document upload"""
    try:
        # Only regular users can upload documents
        if 'admin_id' in session:
            flash('Admin users cannot upload documents.', 'error')
            return redirect(url_for('admin.dashboard'))
        
        application = Application.query.filter_by(id=app_id, user_id=session['user_id']).first_or_404()
        
        if 'na_document' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('verification_report', app_id=app_id))
        
        file = request.files['na_document']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('verification_report', app_id=app_id))
        
        if file:
            # Save NA document
            user = User.query.get(session['user_id'])
            doc_info = storage_service.save_single_document(
                user.mobile_number, application.id, file, 'na_document'
            )
            
            if doc_info:
                # FIXED: Use correct document type
                new_doc = Document(
                    application_id=application.id,
                    document_type='NON_AGRICULTURAL_DECLARATION',  # CORRECTED
                    file_path=doc_info['file_path'],
                    file_name=doc_info['file_name'],
                    uploaded_at=datetime.utcnow()
                )
                db.session.add(new_doc)
                
                # Re-verify NA document using our new function
                na_report = verify_na_document(new_doc, application)
                application.na_document_verification = json.dumps(na_report)
                application.na_document_status = na_report.get('status', 'PENDING')
                application.na_document_risk_score = na_report.get('risk_score', 0.0)
                
                db.session.commit()
                flash('NA document uploaded and verified successfully!', 'success')
            else:
                flash('Error uploading document', 'error')
        
        return redirect(url_for('verification_report', app_id=app_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error uploading document: {str(e)}', 'error')
        return redirect(url_for('verification_report', app_id=app_id))

@app.route('/logout')
def logout():
    """Unified logout endpoint that handles both user and admin logout"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/user_logout')
def user_logout():
    """Legacy user logout endpoint - redirects to main logout"""
    return redirect(url_for('logout'))

@app.route('/view_document/<int:doc_id>')
@login_required
def view_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    application = doc.application
    
    is_owner = 'user_id' in session and application.user_id == session['user_id']
    is_admin = 'admin_id' in session

    if not is_owner and not is_admin:
        abort(403)
            
    try:
        directory = os.path.dirname(doc.file_path)
        filename = os.path.basename(doc.file_path)
        return send_from_directory(directory, filename, as_attachment=False)
    except FileNotFoundError:
        abort(404)

@app.route('/check_cibil', methods=['POST'])
@login_required
def check_cibil():
    # Only regular users can check CIBIL
    if 'admin_id' in session:
        return jsonify({'error': 'Admin users cannot check CIBIL scores'}), 403
    
    simulated_score = random.randint(300, 900)
    return jsonify({'cibil_score': simulated_score})

@app.route('/chatbot', methods=['POST'])
def chatbot():
    user_message = request.json['message'].lower()
    reply = "I'm sorry, I don't understand."
    if 'document' in user_message:
        reply = "You'll need salary slips, bank statements, and KYC documents."
    elif 'interest' in user_message:
        reply = "Interest rates start from 8.5% p.a."
    return jsonify({'reply': reply})

@app.route('/prefill-from-document', methods=['POST'])
@login_required
def prefill_from_document():
    # Only regular users can use this feature
    if 'admin_id' in session:
        return jsonify({"error": "Admin users cannot use this feature"}), 403
    
    if 'master_document' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['master_document']
    if file:
        file_content = file.read().decode('utf-8')
        extracted_data = advance_verification_service.parse_master_document(file_content)
        return jsonify(extracted_data)
        
    return jsonify({"error": "File processing failed"}), 500

@app.route('/analyze-application', methods=['POST'])
@login_required
def analyze_application():
    try:
        # Only regular users can use this feature
        if 'admin_id' in session:
            return jsonify({"error": "Admin users cannot use this feature"}), 403
        
        # Get form data for AI analysis
        application_data = {
            'first_name': request.form.get('first_name'),
            'last_name': request.form.get('last_name'),
            'monthly_salary': float(request.form.get('monthly_salary', 0)),
            'existing_emi': float(request.form.get('existing_emi', 0)),
            'cibil_score': int(request.form.get('cibil_score', 0)),
            'loan_amount': float(request.form.get('loan_amount', 0)),
            'property_valuation': float(request.form.get('property_valuation', 0)),
            'is_rented': request.form.get('is_rented') == 'True',
            'is_non_agricultural': request.form.get('is_non_agricultural') == 'True',
            'company_name': request.form.get('company_name', ''),
            'has_own_property': request.form.get('has_own_property') == 'True',
            'has_existing_mortgage': request.form.get('has_existing_mortgage') == 'True'
        }
        
        # Initialize AI analyzer
        analyzer = CasaFlowAIAnalyzer()
        
        # Perform analysis
        analysis = analyzer.analyze_application(application_data)
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Analysis failed: {str(e)}'
        }), 500

@app.route('/application-result')
@login_required
def application_result():
    # Only regular users can view application results
    if 'admin_id' in session:
        flash('Admin users cannot view application results.', 'error')
        return redirect(url_for('admin.dashboard'))
    
    app_id = request.args.get('app_id')
    if not app_id:
        flash('No application specified', 'error')
        return redirect(url_for('dashboard'))
    
    application = Application.query.filter_by(id=app_id, user_id=session['user_id']).first()
    if not application:
        flash('Application not found', 'error')
        return redirect(url_for('dashboard'))
    
    # Parse AI analysis from JSON and handle both old and new formats
    ai_analysis = None
    if application.ai_analysis_report:
        try:
            ai_analysis = json.loads(application.ai_analysis_report)
            
            # Convert new instant decision format to old template format if needed
            if 'risk_score' in ai_analysis:
                # This is the new instant decision format - convert to old format for template compatibility
                ai_analysis = convert_to_old_format(ai_analysis)
                
        except json.JSONDecodeError:
            ai_analysis = {'error': 'Unable to parse AI analysis'}
    
    return render_template('application_result.html', 
                        application=application, 
                        analysis=ai_analysis)

@app.route('/debug-session')
def debug_session():
    """Debug route to check session variables"""
    return f"""
    <pre>
    Session data: {dict(session)}
    User ID: {session.get('user_id')}
    Admin ID: {session.get('admin_id')}
    Admin Logged In: {session.get('admin_logged_in')}
    User Logged In: {session.get('user_logged_in')}
    </pre>
    """

@app.route('/debug-routes')
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': rule.rule
        })
    return jsonify(routes)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)