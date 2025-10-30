# services/application_processor.py
from services.credit_risk_service import CreditRiskService
from services.ai_analysis_engine import ai_analyzer  # NEW: AI integration
from models import Application, AIAnalysisReport, db
import logging
import asyncio  # NEW: For async AI operations

logger = logging.getLogger(__name__)

class ApplicationProcessor:
    def __init__(self):
        self.credit_service = CreditRiskService()
        self.ai_analyzer = ai_analyzer  # NEW: AI analyzer instance
    
    async def process_application(self, application_id):  # CHANGED: Made async
        """
        Process application with enhanced credit risk assessment and AI analysis
        """
        try:
            application = Application.query.get(application_id)
            if not application:
                return {'success': False, 'error': 'Application not found'}
            
            # Step 1: Perform credit risk assessment
            credit_risk_result = self.credit_service.calculate_credit_risk(application)
            
            # Step 2: NEW - Perform AI-powered analysis
            ai_analysis_result = await self._perform_ai_analysis(application, credit_risk_result)
            
            # Step 3: Update application with credit risk data
            self._update_application_risk(application, credit_risk_result, ai_analysis_result)
            
            # Step 4: Generate comprehensive AI analysis report
            ai_report = self._generate_ai_analysis(application, credit_risk_result, ai_analysis_result)
            
            # Step 5: Make final decision using both traditional and AI insights
            decision = self._make_decision(application, credit_risk_result, ai_report, ai_analysis_result)
            
            # Step 6: Save all changes
            db.session.commit()
            
            return {
                'success': True,
                'application_id': application_id,
                'decision': decision,
                'credit_risk': credit_risk_result,
                'ai_analysis': ai_analysis_result,  # NEW: Include AI results
                'ai_report_id': ai_report.id if ai_report else None
            }
            
        except Exception as e:
            logger.error(f"Application processing failed: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _perform_ai_analysis(self, application, credit_risk_result):
        """NEW: Perform AI-powered analysis using LLM"""
        try:
            # Prepare application data for AI analysis
            application_data = self._prepare_application_data(application, credit_risk_result)
            
            # Run AI analysis
            ai_result = await self.ai_analyzer.analyze_application(application_data)
            
            logger.info(f"AI analysis completed for application {application.id}")
            return ai_result
            
        except Exception as e:
            logger.error(f"AI analysis failed: {str(e)}")
            # Return fallback analysis
            return {
                'analysis_type': 'rule_based_fallback',
                'error': str(e),
                'executive_summary': 'AI analysis unavailable - using traditional assessment'
            }
    
    def _prepare_application_data(self, application, credit_risk_result):
        """NEW: Prepare comprehensive data for AI analysis"""
        return {
            # Basic application info
            'application_id': application.id,
            'first_name': application.first_name,
            'last_name': application.last_name,
            'monthly_salary': application.monthly_salary,
            'loan_amount': application.loan_amount,
            'property_valuation': application.property_valuation,
            
            # Credit information
            'cibil_score': application.cibil_score,
            'existing_emi': application.existing_emi,
            'banking_behavior': application.banking_behavior,
            'fraud_risk': application.fraud_risk,
            
            # Employment details
            'company_name': application.company_name,
            'employment_type': getattr(application, 'employment_type', None),
            
            # Property details
            'is_non_agricultural': getattr(application, 'is_non_agricultural', None),
            'is_rented': getattr(application, 'is_rented', None),
            
            # Credit risk results
            'credit_risk_assessment': credit_risk_result,
            
            # Additional financial data (if available)
            'other_income': getattr(application, 'other_income', 0),
            'total_assets': getattr(application, 'total_assets', 0),
            'total_liabilities': getattr(application, 'total_liabilities', 0)
        }
    
    def _update_application_risk(self, application, credit_risk_result, ai_analysis_result):
        """Enhanced: Update application with both credit risk and AI analysis information"""
        if credit_risk_result.get('success'):
            application.credit_risk_score = credit_risk_result.get('risk_score')
            
            # Map risk category to banking_behavior if not set
            if not application.banking_behavior:
                risk_category = credit_risk_result.get('risk_category', 'FAIR')
                application.banking_behavior = risk_category
            
            # Update fraud risk based on AI analysis if available
            if not application.fraud_risk and ai_analysis_result.get('risk_level'):
                application.fraud_risk = ai_analysis_result.get('risk_level', 'LOW')
            
            # NEW: Store AI insights if available
            if ai_analysis_result.get('financial_health_score'):
                application.ai_health_score = ai_analysis_result['financial_health_score']
                
        else:
            # Mark for manual review if credit assessment failed
            application.status = 'MANUAL_REVIEW'
            application.credit_risk_score = None
    
    def _generate_ai_analysis(self, application, credit_risk_result, ai_analysis_result):
        """Enhanced: Generate comprehensive AI analysis report"""
        try:
            # Create or update AI analysis report
            ai_report = AIAnalysisReport.query.filter_by(application_id=application.id).first()
            if not ai_report:
                ai_report = AIAnalysisReport(application_id=application.id)
                db.session.add(ai_report)
            
            # NEW: Store raw AI analysis results
            if ai_analysis_result:
                ai_report.ai_analysis_raw = ai_analysis_result
            
            # Use AI-generated insights if available, otherwise use traditional methods
            if ai_analysis_result and ai_analysis_result.get('analysis_type') != 'rule_based_fallback':
                # Use AI-generated content
                ai_report.set_rejection_reasons(ai_analysis_result.get('rejection_reasons', []))
                ai_report.set_recommendations(ai_analysis_result.get('recommendations', []))
                ai_report.set_alternative_offers(ai_analysis_result.get('alternative_offers', []))
                ai_report.financial_health_score = ai_analysis_result.get('financial_health_score', 50)
                ai_report.generated_explanation = ai_analysis_result.get('generated_explanation', '')
                
                # NEW: Store additional AI insights
                if ai_analysis_result.get('llm_enhanced_insights'):
                    ai_report.llm_enhanced_insights = ai_analysis_result['llm_enhanced_insights']
                
            else:
                # Fallback to traditional analysis
                rejection_reasons = self._assess_rejection_reasons(application, credit_risk_result)
                ai_report.set_rejection_reasons(rejection_reasons)
                
                recommendations = self._generate_recommendations(application, credit_risk_result)
                ai_report.set_recommendations(recommendations)
                
                if rejection_reasons:
                    alternative_offers = self._generate_alternative_offers(application)
                    ai_report.set_alternative_offers(alternative_offers)
                
                ai_report.financial_health_score = credit_risk_result.get('risk_score', 50)
                ai_report.generated_explanation = self._generate_explanation(
                    application, credit_risk_result, rejection_reasons
                )
            
            return ai_report
            
        except Exception as e:
            logger.error(f"AI analysis report generation failed: {str(e)}")
            return None
    
    def _assess_rejection_reasons(self, application, credit_risk_result):
        """Assess reasons for potential rejection"""
        reasons = []
        
        # Check credit risk
        if not credit_risk_result.get('success'):
            reasons.append({
                'factor': 'Credit Assessment',
                'severity': 'High',
                'description': 'Unable to complete credit risk assessment',
                'impact': 'Cannot evaluate creditworthiness'
            })
        elif credit_risk_result.get('risk_level') == 'HIGH':
            reasons.append({
                'factor': 'Credit Risk',
                'severity': 'High',
                'description': f'High credit risk detected (Score: {credit_risk_result.get("risk_score")})',
                'impact': 'Increased default probability'
            })
        
        # Check loan affordability
        if application.loan_amount > application.monthly_salary * 60:  # 5 years salary
            reasons.append({
                'factor': 'Loan Affordability',
                'severity': 'Medium',
                'description': 'Loan amount exceeds affordable limit',
                'impact': 'High debt-to-income ratio'
            })
        
        return reasons
    
    def _generate_recommendations(self, application, credit_risk_result):
        """Generate improvement recommendations"""
        recommendations = []
        
        if not credit_risk_result.get('success'):
            recommendations.append({
                'action': 'Manual Credit Review',
                'priority': 'High',
                'description': 'System credit assessment failed - requires manual review',
                'timeline': 'Immediate'
            })
        
        if application.cibil_score and application.cibil_score < 750:
            recommendations.append({
                'action': 'Improve Credit Score',
                'priority': 'Medium',
                'description': 'Increase credit score above 750 for better rates',
                'timeline': '3-6 months'
            })
        
        return recommendations
    
    def _generate_alternative_offers(self, application):
        """Generate alternative loan offers"""
        offers = []
        
        # Suggest smaller loan amount
        if application.loan_amount > application.monthly_salary * 48:
            suggested_amount = application.monthly_salary * 36  # 3 years salary
            offers.append({
                'type': 'Reduced Loan Amount',
                'amount': suggested_amount,
                'tenure': '60 months',
                'reason': 'Better aligned with income',
                'improvement': 'Lower EMI burden'
            })
        
        return offers
    
    def _generate_explanation(self, application, credit_risk_result, rejection_reasons):
        """Generate natural language explanation"""
        if not rejection_reasons:
            return "Application meets all criteria. Recommended for approval."
        
        explanation = "Application analysis completed. Key findings:\n\n"
        
        if credit_risk_result.get('success'):
            explanation += f"Credit Risk: {credit_risk_result.get('risk_category')} "
            explanation += f"(Score: {credit_risk_result.get('risk_score')}/100)\n"
        else:
            explanation += "Credit Risk: Assessment Failed - Manual Review Required\n"
        
        if rejection_reasons:
            explanation += "\nAreas needing improvement:\n"
            for reason in rejection_reasons:
                explanation += f"- {reason['description']}\n"
        
        return explanation
    
    def _make_decision(self, application, credit_risk_result, ai_report, ai_analysis_result):
        """Enhanced: Make final decision using both traditional and AI insights"""
        # If credit assessment failed completely
        if not credit_risk_result.get('success'):
            application.status = 'MANUAL_REVIEW'
            return 'MANUAL_REVIEW'
        
        # NEW: Consider AI analysis in decision making
        ai_risk_score = ai_analysis_result.get('financial_health_score')
        ai_risk_level = ai_analysis_result.get('risk_level')
        
        # Combine traditional and AI risk assessments
        traditional_score = credit_risk_result.get('risk_score', 0)
        traditional_level = credit_risk_result.get('risk_level')
        
        # Use AI insights if available, otherwise fall back to traditional
        if ai_risk_score is not None:
            # Weighted decision: 60% AI + 40% traditional
            combined_score = (ai_risk_score * 0.6) + (traditional_score * 0.4)
            risk_level = ai_risk_level if ai_risk_level else traditional_level
        else:
            combined_score = traditional_score
            risk_level = traditional_level
        
        # Make decision based on combined assessment
        if risk_level == 'LOW' and combined_score >= 70:
            application.status = 'APPROVED'
            return 'APPROVED'
        elif risk_level == 'MEDIUM' and combined_score >= 50:
            application.status = 'MANUAL_REVIEW'
            return 'MANUAL_REVIEW'
        else:
            application.status = 'REJECTED'
            return 'REJECTED'

    # NEW: Sync wrapper for existing code that calls this method
    def process_application_sync(self, application_id):
        """
        Synchronous wrapper for async process_application method
        Use this if you need to call from synchronous code
        """
        try:
            return asyncio.run(self.process_application(application_id))
        except Exception as e:
            logger.error(f"Sync wrapper failed: {str(e)}")
            return {'success': False, 'error': str(e)}