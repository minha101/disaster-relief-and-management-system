
from getpass import getpass
from app import create_app
from app.extensions import db
from app.models import User, Role
from app.services.hooks import password_error

app = create_app()

with app.app_context():
    email = input("Super Admin email: ").strip().lower()

    user = User.query.filter_by(email=email).first()

    if not user:
        print("User not found! Check the email.")
    elif not user.has_role("super_admin"):
        print("This account is not a Super Admin.")
    else:
        password = getpass("Enter new password: ")
        confirm = getpass("Confirm new password: ")

        error = password_error(password)

        if error:
            print(error)
        elif password != confirm:
            print("Passwords do not match.")
        else:
            user.set_password(password)
            user.failed_logins = 0
            user.locked_until = None
            db.session.commit()
            print("Super Admin password reset successfully!")
