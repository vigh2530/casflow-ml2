# admin/routes.py
import os
import json
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, session, jsonify, current_app
)
from models import db, Application, User, Document, Admin
from services import decision_service, notification_service
from functools import wraps

# Create admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please log in as admin to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function for EMI calculation (same as in app.py)
def calculate_emi(principal, annual_rate, tenure_months):
    """Calculate EMI using the standard formula"""
    try:
        monthly_rate = annual_rate / 12 / 100
        if monthly_rate == 0:  # Handle zero interest rate
            return principal / tenure_months
        
        emi = principal * monthly_rate * (1 + monthly_rate) ** tenure_months / ((1 + monthly_rate) ** tenure_months - 1)
        return round(emi, 2)
    except Exception as e:
        current_app.logger.error(f"Error calculating EMI: {e}")
        return 0

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard showing application statistics"""
    try:
        # Get application statistics
        total_applications = Application.query.count()
        approved_count = Application.query.filter_by(status='APPROVED').count()
        rejected_count = Application.query.filter_by(status='REJECTED').count()
        pending_count = Application.query.filter_by(status='PENDING').count()
        
        stats = {
            'total_applications': total_applications,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'pending_count': pending_count
        }
        
        # Get recent applications (last 20)
        recent_apps = Application.query.order_by(Application.created_at.desc()).limit(20).all()
        
        return render_template('admin/dashboard.html', 
                             stats=stats, 
                             applications=recent_apps)
    
    except Exception as e:
        current_app.logger.error(f"Error loading admin dashboard: {str(e)}")
        flash('Error loading dashboard.', 'error')
        return render_template('admin/dashboard.html', stats={}, applications=[])

@admin_bp.route('/application/<app_id>/review', methods=['GET', 'POST'])
@admin_required
def review_application(app_id):
    """Admin review and decision making for applications"""
    try:
        application = Application.query.filter_by(id=app_id).first_or_404()
        
        if request.method == 'POST':
            new_status = request.form.get('status')
            admin_notes = request.form.get('admin_notes')
            interest_rate = request.form.get('interest_rate')
            loan_term_years = request.form.get('loan_term_years')
            
            # Update application status
            application.status = new_status
            application.admin_review_notes = admin_notes
            
            if new_status == 'APPROVED' and interest_rate and loan_term_years:
                application.interest_rate = float(interest_rate)
                application.loan_term_years = int(loan_term_years)
                application.emi_amount = calculate_emi(
                    application.loan_amount, 
                    application.interest_rate, 
                    application.loan_term_years * 12
                )
            
            application.reviewed_by_admin_id = session['admin_id']
            application.reviewed_at = datetime.utcnow()
            
            db.session.commit()
            
            # Send notification to user
            notification_service.send_decision_notification(
                application, 
                f"Application reviewed by admin. Status: {new_status}. Notes: {admin_notes}"
            )
            
            flash(f'Application #{application.id} status updated to {new_status}', 'success')
            return redirect(url_for('admin.dashboard'))
        
        # GET request - load all reports for the review
        banking_report = json.loads(application.banking_analysis_report or '{}')
        fraud_report = json.loads(application.fraud_detection_report or '{}')
        credit_report = json.loads(application.ai_analysis_report or '{}') if application.ai_analysis_report else {}
        employment_report = json.loads(application.employment_verification_report or '{}')
        document_report = json.loads(application.document_verification_report or '{}')
        na_report = json.loads(application.na_document_verification or '{}')
        verification_summary = json.loads(application.verification_summary or '{}')
        
        return render_template('admin/application_review.html',
                             application=application,
                             banking_report=banking_report,
                             fraud_report=fraud_report,
                             credit_report=credit_report,
                             employment_report=employment_report,
                             document_report=document_report,
                             na_report=na_report,
                             verification_summary=verification_summary)
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in admin review for application {app_id}: {str(e)}")
        flash(f'Error reviewing application: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/applications')
@admin_required
def applications():
    """View all applications with filtering options"""
    try:
        status_filter = request.args.get('status', 'all')
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Build query based on filters
        if status_filter == 'all':
            applications_query = Application.query
        else:
            applications_query = Application.query.filter_by(status=status_filter.upper())
        
        # Paginate results
        applications_paginated = applications_query.order_by(
            Application.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        # Get counts for each status
        status_counts = {
            'all': Application.query.count(),
            'pending': Application.query.filter_by(status='PENDING').count(),
            'approved': Application.query.filter_by(status='APPROVED').count(),
            'rejected': Application.query.filter_by(status='REJECTED').count()
        }
        
        return render_template('admin/applications.html',
                             applications=applications_paginated,
                             status_counts=status_counts,
                             current_status=status_filter)
    
    except Exception as e:
        current_app.logger.error(f"Error loading applications list: {str(e)}")
        flash('Error loading applications.', 'error')
        return render_template('admin/applications.html', 
                             applications=[], 
                             status_counts={}, 
                             current_status='all')

@admin_bp.route('/logout')
def admin_logout():
    """Admin logout route"""
    session.pop('admin_id', None)
    session.pop('admin_logged_in', None)
    flash('You have been logged out from admin panel.', 'success')
    return redirect(url_for('login'))

# API endpoints for admin
@admin_bp.route('/api/applications/stats')
@admin_required
def api_application_stats():
    """API endpoint for application statistics"""
    try:
        # Weekly application counts
        from datetime import timedelta
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        
        weekly_stats = {
            'total': Application.query.count(),
            'last_week': Application.query.filter(Application.created_at >= one_week_ago).count(),
            'approved': Application.query.filter_by(status='APPROVED').count(),
            'pending': Application.query.filter_by(status='PENDING').count(),
            'rejected': Application.query.filter_by(status='REJECTED').count()
        }
        
        return jsonify(weekly_stats)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/application/<app_id>/update_status', methods=['POST'])
@admin_required
def api_update_application_status(app_id):
    """API endpoint to update application status"""
    try:
        application = Application.query.filter_by(id=app_id).first_or_404()
        data = request.get_json()
        
        new_status = data.get('status')
        notes = data.get('notes', '')
        
        if new_status not in ['APPROVED', 'REJECTED', 'PENDING']:
            return jsonify({'error': 'Invalid status'}), 400
        
        application.status = new_status
        application.admin_review_notes = notes
        application.reviewed_by_admin_id = session['admin_id']
        application.reviewed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Send notification
        notification_service.send_decision_notification(
            application, 
            f"Application status updated to {new_status}. {notes}"
        )
        
        return jsonify({'success': True, 'message': f'Status updated to {new_status}'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500