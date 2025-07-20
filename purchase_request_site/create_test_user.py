"""
Script to create test users programmatically
Usage: python create_test_user.py
"""

from database import get_db, init_database
from user_service import create_user_from_cli
from dotenv import load_dotenv
import os


def create_test_user(
    name: str, email: str, personal_email: str, address: str, team: str
):
    """Create a test user with a generated signature"""

    # Load environment and initialize database
    load_dotenv()
    init_database()

    # Create a signature file for this user
    signature_path = "purchase_request_site/static/img/default_signature.png"

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
            signature_path=signature_path,
        )

        print("✅ User created successfully!")
        print(f"   ID: {user.id}")
        print(f"   Name: {user.name}")
        print(f"   Email: {user.email}")
        print(f"   Personal Email: {user.personal_email}")
        print(f"   Team: {user.team}")
        print(f"   Address: {user.address}")
        print(f"   Signature: {user.signature_filename}")
        print(
            f"   Signature Size: {len(user.signature_data) if user.signature_data else 0} bytes"
        )

        # Clean up the temporary signature file
        if os.path.exists(signature_path):
            os.remove(signature_path)
            print(f"   Cleaned up: {signature_path}")

        return user

    except Exception as e:
        print(f"❌ Error creating user: {e}")
        # Clean up on error
        if os.path.exists(signature_path):
            os.remove(signature_path)
        return None
    finally:
        db.close()


if __name__ == "__main__":
    # Create some test users
    test_users = [
        {
            "name": "Alice Johnson",
            "email": "alice.johnson@mcmaster.ca",
            "personal_email": "alice.johnson@gmail.com",
            "address": "456 University Ave, Hamilton, ON, Canada",
            "team": "Aerodynamics",
        },
        {
            "name": "Bob Smith",
            "email": "bob.smith@mcmaster.ca",
            "personal_email": "bob.smith@yahoo.com",
            "address": "789 Main St W, Hamilton, ON, Canada",
            "team": "Electrical",
        },
        {
            "name": "Carol Davis",
            "email": "carol.davis@mcmaster.ca",
            "personal_email": "carol.davis@outlook.com",
            "address": "321 King St E, Hamilton, ON, Canada",
            "team": "Mechanical",
        },
    ]

    print("Creating test users...\n")

    for i, user_data in enumerate(test_users, 1):
        print(f"Creating user {i}/{len(test_users)}: {user_data['name']}")
        user = create_test_user(**user_data)
        if user:
            print("Success!\n")
        else:
            print("Failed!\n")

    print("✅ Test user creation complete!")
