# test_ai_complete.py
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    print("🤖 Testing Complete AI Integration...")
    
    # Check API keys
    openai_key = os.getenv('OPENAI_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    google_key = os.getenv('GOOGLE_API_KEY')
    
    print(f"🔑 OpenAI Key: {'✅ Present' if openai_key else '❌ Missing'}")
    print(f"🔑 Anthropic Key: {'✅ Present' if anthropic_key else '❌ Missing'}")
    print(f"🔑 Google Key: {'✅ Present' if google_key else '❌ Missing'}")
    
    if not openai_key:
        print("💡 Please add OPENAI_API_KEY to your .env file")
        return
    
    # Try to import and test
    try:
        from services.ai_analysis_engine import ai_analyzer
        
        # Test data
        sample_data = {
            'first_name': 'Rajesh',
            'last_name': 'Kumar',
            'monthly_salary': 85000,
            'loan_amount': 2800000,
            'property_valuation': 3500000,
            'cibil_score': 790,
            'existing_emi': 12000,
            'company_name': 'Tech Solutions Ltd',
            'is_non_agricultural': True,
            'is_rented': False
        }
        
        print("\n🧪 Running AI analysis...")
        result = await ai_analyzer.analyze_application(sample_data)
        
        print("\n" + "="*50)
        print("🎉 AI ANALYSIS RESULTS")
        print("="*50)
        
        print(f"📊 Analysis Type: {result.get('analysis_type', 'N/A')}")
        print(f"💰 Financial Health Score: {result.get('financial_health_score', 'N/A')}/100")
        print(f"⚡ Risk Level: {result.get('risk_level', 'N/A')}")
        print(f"📝 Status: {result.get('status', 'N/A')}")
        
        # Show AI insights if available
        if result.get('has_ai_insights'):
            print(f"\n🤖 AI Enhanced Explanation:")
            print(f"   {result.get('ai_enhanced_explanation', 'N/A')}")
        else:
            print(f"\n📋 Generated Explanation:")
            print(f"   {result.get('generated_explanation', 'N/A')}")
        
        # Show rejection reasons if any
        if result.get('rejection_reasons'):
            print(f"\n⚠️  Rejection Reasons ({len(result['rejection_reasons'])}):")
            for reason in result['rejection_reasons']:
                print(f"   • {reason['factor']}: {reason['description']} (Severity: {reason['severity']})")
        else:
            print(f"\n✅ No rejection reasons - Application looks good!")
        
        # Show recommendations
        if result.get('recommendations'):
            print(f"\n💡 Recommendations ({len(result['recommendations'])}):")
            for rec in result['recommendations']:
                print(f"   • {rec['action']}: {rec['description']} (Priority: {rec['priority']})")
        
        # Show alternative offers
        if result.get('alternative_offers'):
            print(f"\n🎯 Alternative Offers ({len(result['alternative_offers'])}):")
            for offer in result['alternative_offers']:
                print(f"   • {offer['type']}: ₹{offer['amount']:,.0f} - {offer.get('reason', '')}")
        
        # Show LLM insights if available
        if result.get('llm_enhanced_insights'):
            llm_info = result['llm_enhanced_insights']
            print(f"\n🧠 LLM Analysis Details:")
            print(f"   Model Used: {llm_info.get('model_used', 'N/A')}")
            print(f"   Processed: {llm_info.get('llm_processed', False)}")
            if llm_info.get('error'):
                print(f"   Error: {llm_info.get('error')}")
                
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())