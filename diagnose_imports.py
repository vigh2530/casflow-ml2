# diagnose_imports.py
import sys
import os

print("🔍 Diagnosing Import Issues...")
print(f"Python path: {sys.executable}")
print(f"Working directory: {os.getcwd()}")

# Check basic imports
try:
    import flask
    print("✅ Flask imported successfully")
except ImportError as e:
    print(f"❌ Flask import failed: {e}")

try:
    import flask_sqlalchemy
    print("✅ Flask-SQLAlchemy imported successfully")
except ImportError as e:
    print(f"❌ Flask-SQLAlchemy import failed: {e}")

try:
    from openai import AsyncOpenAI
    print("✅ OpenAI imported successfully")
except ImportError as e:
    print(f"❌ OpenAI import failed: {e}")

try:
    from anthropic import AsyncAnthropic
    print("✅ Anthropic imported successfully")
except ImportError as e:
    print(f"❌ Anthropic import failed: {e}")

try:
    import google.generativeai
    print("✅ Google Generative AI imported successfully")
except ImportError as e:
    print(f"❌ Google Generative AI import failed: {e}")

# Check if we can import the analyzer
try:
    from services.ai_analysis_engine import ai_analyzer
    print("✅ AI Analyzer imported successfully")
except Exception as e:
    print(f"❌ AI Analyzer import failed: {e}")
    import traceback
    traceback.print_exc()