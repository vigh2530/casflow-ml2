# services/ai_analysis_engine.py
import os
import json
import asyncio
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

# Try to import AI libraries with fallbacks
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ OpenAI not available")

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("⚠️ Anthropic not available")

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("⚠️ Google Generative AI not available")

class CasaFlowAIAnalyzer:
    def __init__(self):
        self.risk_thresholds = {
            'cibil_min': 750,
            'salary_to_emi_ratio': 0.5,
            'loan_to_value_max': 0.8
        }
        
        # Initialize AI clients only if available
        self.openai_client = None
        self.anthropic = None
        self.gemini = None
        
        if OPENAI_AVAILABLE and os.getenv('OPENAI_API_KEY'):
            try:
                self.openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                print("✅ OpenAI client initialized")
            except Exception as e:
                print(f"❌ OpenAI client failed: {e}")
        
        if ANTHROPIC_AVAILABLE and os.getenv('ANTHROPIC_API_KEY'):
            try:
                self.anthropic = AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
                print("✅ Anthropic client initialized")
            except Exception as e:
                print(f"❌ Anthropic client failed: {e}")
        
        if GOOGLE_AVAILABLE and os.getenv('GOOGLE_API_KEY'):
            try:
                genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
                self.gemini = genai.GenerativeModel('gemini-pro')
                print("✅ Google AI client initialized")
            except Exception as e:
                print(f"❌ Google AI client failed: {e}")
        
        print(f"🤖 AI Analyzer initialized - OpenAI: {self.openai_client is not None}, "
              f"Anthropic: {self.anthropic is not None}, Google: {self.gemini is not None}")
    
    async def analyze_application(self, application_data):
        """Comprehensive AI analysis combining rule-based and LLM analysis"""
        try:
            print("🔄 Starting AI analysis...")
            
            # First, run traditional rule-based analysis (synchronous)
            rule_based_analysis = self._rule_based_analysis(application_data)
            print(f"✅ Rule-based analysis completed - Score: {rule_based_analysis.get('financial_health_score')}")
            
            # Then try to enhance with LLM analysis if available
            llm_analysis = {}
            if self.openai_client:
                try:
                    print("🔄 Attempting LLM analysis...")
                    llm_analysis = await self._llm_analysis(application_data, rule_based_analysis)
                    print("✅ LLM analysis completed")
                except Exception as e:
                    print(f"❌ LLM analysis failed: {e}")
                    llm_analysis = {'error': str(e), 'analysis_type': 'llm_failed'}
            else:
                print("⚠️ Skipping LLM analysis - OpenAI client not available")
                llm_analysis = {'analysis_type': 'llm_skipped'}
            
            # Combine both analyses
            combined_analysis = self._combine_analyses(rule_based_analysis, llm_analysis)
            print("🎉 AI analysis completed successfully!")
            
            return combined_analysis
            
        except Exception as e:
            print(f"💥 AI analysis failed completely: {e}")
            # Fallback to basic rule-based analysis
            basic_analysis = self._rule_based_analysis(application_data)
            basic_analysis['analysis_type'] = 'emergency_fallback'
            basic_analysis['error'] = str(e)
            return basic_analysis
    
    def _rule_based_analysis(self, application_data):
        """Your existing rule-based analysis logic"""
        analysis = {
            'rejection_reasons': [],
            'recommendations': [],
            'alternative_offers': [],
            'financial_health_score': 0,
            'generated_explanation': '',
            'status': 'APPROVED',
            'risk_level': 'LOW',
            'analysis_type': 'rule_based'
        }
        
        # Perform various checks
        self._check_credit_profile(application_data, analysis)
        self._check_loan_affordability(application_data, analysis)
        self._check_loan_to_value_ratio(application_data, analysis)
        self._check_employment_stability(application_data, analysis)
        
        # Generate explanations and alternatives
        self._generate_explanation(analysis)
        self._generate_alternative_offers(application_data, analysis)
        self._calculate_financial_health_score(application_data, analysis)
        self._determine_final_status(analysis)
        
        return analysis
    
    async def _llm_analysis(self, application_data, rule_based_analysis):
        """LLM-powered analysis"""
        if not self.openai_client:
            raise Exception("OpenAI client not available")
        
        try:
            prompt = self._build_llm_prompt(application_data, rule_based_analysis)
            
            print("🔄 Calling OpenAI API...")
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Using cheaper model for testing
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300
            )
            
            analysis_text = response.choices[0].message.content
            
            return {
                'executive_summary': analysis_text,
                'analysis_type': 'llm_enhanced',
                'llm_processed': True,
                'model_used': 'gpt-3.5-turbo'
            }
            
        except Exception as e:
            raise Exception(f"OpenAI API call failed: {str(e)}")
    
    def _build_llm_prompt(self, application_data, rule_based_analysis):
        """Build comprehensive prompt for LLM analysis"""
        return f"""
        As a loan risk analyst, provide a brief assessment of this loan application:

        APPLICANT: {application_data.get('first_name', '')} {application_data.get('last_name', '')}
        SALARY: ₹{application_data.get('monthly_salary', 0):,}/month
        LOAN AMOUNT: ₹{application_data.get('loan_amount', 0):,}
        PROPERTY VALUE: ₹{application_data.get('property_valuation', 0):,}
        CIBIL SCORE: {application_data.get('cibil_score', 0)}
        EXISTING EMI: ₹{application_data.get('existing_emi', 0):,}/month

        Provide a 2-3 sentence summary focusing on:
        1. Key risk factors
        2. Overall recommendation
        3. Any major concerns

        Be concise and professional.
        """
    
    def _combine_analyses(self, rule_based, llm_enhanced):
        """Combine rule-based and LLM analyses"""
        combined = {
            **rule_based,  # Keep all rule-based results
            'llm_enhanced_insights': llm_enhanced,
            'combined_risk_score': rule_based.get('financial_health_score', 50),  # For now, use rule-based score
            'analysis_timestamp': datetime.now().isoformat(),
        }
        
        # Enhance explanations with LLM insights if available
        if llm_enhanced.get('executive_summary'):
            combined['ai_enhanced_explanation'] = llm_enhanced['executive_summary']
            combined['has_ai_insights'] = True
        else:
            combined['has_ai_insights'] = False
        
        return combined

    # YOUR EXISTING RULE-BASED METHODS (keep them exactly as they were)
    def _check_credit_profile(self, application_data, analysis):
        cibil_score = application_data.get('cibil_score')
        if cibil_score is None or cibil_score < 10:
            analysis['rejection_reasons'].append({
                'factor': 'Credit History',
                'severity': 'High',
                'description': 'Unable to verify credit history or insufficient credit data',
                'impact': 'Cannot assess repayment behavior'
            })
            analysis['recommendations'].append({
                'action': 'Build Credit History',
                'priority': 'High',
                'description': 'Start with secured credit card and make timely payments',
                'timeline': '6-12 months'
            })
        elif cibil_score < self.risk_thresholds['cibil_min']:
            analysis['rejection_reasons'].append({
                'factor': 'Credit Score',
                'severity': 'Medium',
                'description': f'CIBIL score of {cibil_score} below minimum requirement of {self.risk_thresholds["cibil_min"]}',
                'impact': 'Higher risk of default'
            })
            analysis['recommendations'].append({
                'action': 'Improve Credit Score',
                'priority': 'High',
                'description': 'Pay existing debts on time and reduce credit utilization',
                'timeline': '3-6 months'
            })

    def _check_loan_affordability(self, application_data, analysis):
        monthly_salary = Decimal(str(application_data.get('monthly_salary', 0)))
        existing_emi = Decimal(str(application_data.get('existing_emi', 0)))
        loan_amount = Decimal(str(application_data.get('loan_amount', 0)))
        
        # Calculate affordable EMI (50% of monthly salary)
        affordable_emi = monthly_salary * Decimal('0.5')
        total_emi_obligation = affordable_emi - existing_emi
        
        if total_emi_obligation <= 0:
            analysis['rejection_reasons'].append({
                'factor': 'Debt Burden',
                'severity': 'High',
                'description': 'Existing EMI obligations exceed affordable limits',
                'impact': 'No capacity for additional loan'
            })
            return
        
        # Simple EMI calculation (8.5% annual interest, 60 months tenure)
        interest_rate = Decimal('0.085')
        tenure_months = 60
        monthly_interest = interest_rate / 12
        
        # EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)
        principal = loan_amount
        emi_numerator = principal * monthly_interest * (1 + monthly_interest) ** tenure_months
        emi_denominator = (1 + monthly_interest) ** tenure_months - 1
        calculated_emi = emi_numerator / emi_denominator
        
        if calculated_emi > total_emi_obligation:
            analysis['rejection_reasons'].append({
                'factor': 'Loan Affordability',
                'severity': 'Medium',
                'description': f'Requested loan EMI (₹{calculated_emi:.0f}) exceeds affordable limit (₹{total_emi_obligation:.0f})',
                'impact': 'High debt burden ratio'
            })
            
            # Calculate suggested loan amount based on affordable EMI
            suggested_principal = (total_emi_obligation * ((1 + monthly_interest) ** tenure_months - 1))
            suggested_principal = suggested_principal / (monthly_interest * (1 + monthly_interest) ** tenure_months)
            
            analysis['alternative_offers'].append({
                'type': 'Reduced Loan Amount',
                'amount': float(suggested_principal),
                'tenure': '60 months',
                'emi': float(total_emi_obligation),
                'interest_rate': '8.5%',
                'reason': 'Better aligned with your income and existing obligations'
            })

    def _check_loan_to_value_ratio(self, application_data, analysis):
        loan_amount = Decimal(str(application_data.get('loan_amount', 0)))
        property_valuation = Decimal(str(application_data.get('property_valuation', 0)))
        
        if property_valuation > 0:
            ltv_ratio = loan_amount / property_valuation
            
            if ltv_ratio > self.risk_thresholds['loan_to_value_max']:
                analysis['rejection_reasons'].append({
                    'factor': 'Loan-to-Value Ratio',
                    'severity': 'Medium',
                    'description': f'LTV ratio of {ltv_ratio:.1%} exceeds maximum allowed {self.risk_thresholds["loan_to_value_max"]:.1%}',
                    'impact': 'Higher collateral risk'
                })
                
                # Suggest maximum loan amount based on LTV
                max_loan = property_valuation * Decimal(str(self.risk_thresholds['loan_to_value_max']))
                analysis['alternative_offers'].append({
                    'type': 'LTV Adjusted Loan',
                    'amount': float(max_loan),
                    'max_ltv': f'{self.risk_thresholds["loan_to_value_max"]:.1%}',
                    'reason': 'Maintains healthy loan-to-value ratio'
                })

    def _check_employment_stability(self, application_data, analysis):
        monthly_salary = application_data.get('monthly_salary', 0)
        company_name = application_data.get('company_name', '')
        
        # Simple employment stability check
        if monthly_salary < 30000:
            analysis['rejection_reasons'].append({
                'factor': 'Income Level',
                'severity': 'Medium',
                'description': 'Monthly salary below minimum threshold for this loan type',
                'impact': 'Limited repayment capacity'
            })
            
            analysis['alternative_offers'].append({
                'type': 'Smaller Personal Loan',
                'amount': min(500000, monthly_salary * 10),  # 10x monthly salary
                'tenure': '36 months',
                'purpose': 'Income-based smaller loan',
                'features': ['Lower amount', 'Shorter tenure']
            })

    def _generate_explanation(self, analysis):
        """Generate natural language explanation"""
        if not analysis['rejection_reasons']:
            analysis['generated_explanation'] = (
                "✅ Your application meets all our criteria! "
                "Based on our analysis, your financial profile shows strong repayment capacity "
                "and excellent creditworthiness. Congratulations!"
            )
            return
        
        explanation = "After careful review of your application, here's our assessment:\n\n"
        
        for reason in analysis['rejection_reasons']:
            explanation += f"🔴 {reason['description']} (Severity: {reason['severity']})\n"
        
        if analysis['recommendations']:
            explanation += "\n💡 We recommend the following actions:\n"
            for rec in analysis['recommendations']:
                explanation += f"• {rec['description']} (Priority: {rec['priority']})\n"
        
        if analysis['alternative_offers']:
            explanation += "\n🎯 Alternative options available:\n"
            for offer in analysis['alternative_offers']:
                explanation += f"• {offer['type']}: ₹{offer['amount']:,.0f}\n"
        
        analysis['generated_explanation'] = explanation

    def _generate_alternative_offers(self, application_data, analysis):
        """Generate alternative loan products based on profile"""
        monthly_salary = application_data.get('monthly_salary', 0)
        cibil_score = application_data.get('cibil_score', 0)
        
        # Credit builder loan for lower scores
        if cibil_score < 700 and monthly_salary > 40000:
            analysis['alternative_offers'].append({
                'type': 'Credit Builder Loan',
                'amount': 50000,
                'tenure': '12 months',
                'interest_rate': '12%',
                'purpose': 'Build credit history',
                'features': ['Low amount', 'Short tenure', 'Credit reporting']
            })
        
        # Top-up loan for existing customers with good history
        if cibil_score > 750 and monthly_salary > 80000:
            analysis['alternative_offers'].append({
                'type': 'Preferred Customer Loan',
                'amount': min(2000000, monthly_salary * 24),
                'tenure': '84 months',
                'interest_rate': '7.5%',
                'features': ['Lower interest', 'Longer tenure', 'Flexible repayment']
            })

    def _calculate_financial_health_score(self, application_data, analysis):
        """Calculate overall financial health score (0-100)"""
        score = 50  # Base score
        
        # CIBIL Score contribution (0-30 points)
        cibil_score = application_data.get('cibil_score', 0)
        if cibil_score >= 800:
            score += 30
        elif cibil_score >= 750:
            score += 20
        elif cibil_score >= 700:
            score += 10
        elif cibil_score < 600:
            score -= 20
        
        # Income stability (0-20 points)
        monthly_salary = application_data.get('monthly_salary', 0)
        if monthly_salary >= 100000:
            score += 20
        elif monthly_salary >= 50000:
            score += 15
        elif monthly_salary >= 30000:
            score += 10
        else:
            score -= 10
        
        # Debt-to-Income ratio (0-15 points)
        existing_emi = application_data.get('existing_emi', 0)
        if monthly_salary > 0:
            dti_ratio = existing_emi / monthly_salary
            if dti_ratio < 0.2:
                score += 15
            elif dti_ratio < 0.4:
                score += 10
            elif dti_ratio > 0.6:
                score -= 15
        
        # Loan-to-Value ratio (0-15 points)
        loan_amount = application_data.get('loan_amount', 0)
        property_valuation = application_data.get('property_valuation', 0)
        if property_valuation > 0:
            ltv_ratio = loan_amount / property_valuation
            if ltv_ratio < 0.6:
                score += 15
            elif ltv_ratio < 0.8:
                score += 10
            elif ltv_ratio > 0.9:
                score -= 10
        
        # Property type bonus (0-10 points)
        if application_data.get('is_non_agricultural'):
            score += 10
        
        # Residence stability (0-10 points)
        if not application_data.get('is_rented'):
            score += 10
        
        analysis['financial_health_score'] = max(0, min(100, int(score)))

    def _determine_final_status(self, analysis):
        """Determine final application status based on analysis"""
        rejection_reasons = analysis['rejection_reasons']
        
        # Check for critical rejection reasons
        critical_reasons = [r for r in rejection_reasons if r['severity'] == 'Critical']
        high_reasons = [r for r in rejection_reasons if r['severity'] == 'High']
        
        if critical_reasons:
            analysis['status'] = 'REJECTED'
            analysis['risk_level'] = 'VERY_HIGH'
        elif high_reasons:
            analysis['status'] = 'REJECTED'
            analysis['risk_level'] = 'HIGH'
        elif rejection_reasons:
            analysis['status'] = 'UNDER_REVIEW'
            analysis['risk_level'] = 'MEDIUM'
        else:
            analysis['status'] = 'APPROVED'
            analysis['risk_level'] = 'LOW'

# Singleton instance for easy import
ai_analyzer = CasaFlowAIAnalyzer()