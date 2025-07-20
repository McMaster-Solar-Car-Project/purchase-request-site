#!/usr/bin/env python3
"""
Simple script to create users programmatically
Run from the project root directory: python create_users.py
"""

import sys
import os
from database import get_db, init_database
from user_service import create_user_from_cli
from dotenv import load_dotenv

# Add the purchase_request_site directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'purchase_request_site'))

# Ensure we're working from the correct directory for database access
os.chdir('purchase_request_site')


def create_user_programmatically(name: str, email: str, personal_email: str, address: str, team: str, password: str):
    """Create a user with auto-generated signature"""
    
    # Load environment and initialize database
    load_dotenv()
    init_database()
    
    # Use the default signature file (relative to purchase_request_site directory)
    signature_path = 'static/img/default_signature.png'
    
    # Get database session
    db = next(get_db())
    
    try:
        # Create the user
        user = create_user_from_cli(
            db=db,
            name=name,
            email=email,
            personal_email=personal_email,
            address=address,
            team=team,
            password=password,
            signature_path=signature_path
        )
        
        print(f"✅ User '{name}' created successfully!")
        print(f"   Email: {user.email}")
        print(f"   Personal Email: {user.personal_email}")
        print(f"   Team: {user.team}")
        print(f"   Signature: {len(user.signature_data)} bytes stored")
        
        # Clean up the temporary signature file
        if os.path.exists(signature_path):
            os.remove(signature_path)
            
        return user
        
    except Exception as e:
        print(f"❌ Error creating user '{name}': {e}")
        # Clean up on error
        if os.path.exists(signature_path):
            os.remove(signature_path)
        return None
    finally:
        db.close()


def list_all_users():
    """List all users in the database"""
    load_dotenv()
    init_database()
    
    from database import User
    db = next(get_db())
    
    try:
        users = db.query(User).all()
        print(f"\n📊 Total users in database: {len(users)}")
        for user in users:
            sig_size = len(user.signature_data) if user.signature_data else 0
            print(f"   • {user.name} ({user.email}) - {user.team} - Signature: {sig_size} bytes")
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Creating test users...\n")
    
    # Example users to create
    test_users = [
        {
            "name": "Alice Johnson",
            "email": "alice.johnson@mcmaster.ca",
            "personal_email": "alice.johnson@gmail.com",
            "address": "456 University Ave, Hamilton, ON, Canada",
            "team": "Aerodynamics",
            "password": "alice123"
        },
        {
            "name": "Bob Smith",
            "email": "bob.smith@mcmaster.ca", 
            "personal_email": "bob.smith@yahoo.com",
            "address": "789 Main St W, Hamilton, ON, Canada",
            "team": "Electrical",
            "password": "bob456"
        }
    ]
    
    # Create each user
    for user_data in test_users:
        create_user_programmatically(**user_data)
        print()
    
    # List all users
    list_all_users()
    
    print("\n💡 To create more users, call create_user_programmatically() with your parameters!")
    print("💡 Example:")
    print('   create_user_programmatically(')
    print('       name="Your Name",')
    print('       email="your.email@mcmaster.ca",')
    print('       personal_email="your.personal@gmail.com",')
    print('       address="Your Address",')
    print('       team="Your Team",')
    print('       password="your_password"')
    print('   )') 