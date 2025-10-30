# create_admin.py

import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Admin

def create_admin():
    with app.app_context():
        # Check if admin already exists
        existing_admin = Admin.query.filter_by(username='admin').first()
        if existing_admin:
            print("Admin user already exists!")
            return
        
        # Create new admin
        ADMIN_USERNAME = 'admin'
        ADMIN_PASSWORD = 'admin123'  # Change this in production!
        
        new_admin = Admin(username=ADMIN_USERNAME)
        new_admin.set_password(ADMIN_PASSWORD)
        
        db.session.add(new_admin)
        db.session.commit()
        
        print(f"Admin user created successfully!")
        print(f"Username: {ADMIN_USERNAME}")
        print(f"Password: {ADMIN_PASSWORD}")

if __name__ == '__main__':
    create_admin()