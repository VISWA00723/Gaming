import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

# Database path
db_path = os.path.join('instance', 'newtruf.db')

# Admin user details
admin_name = "Admin User"
admin_email = "admin@newturf.com"
admin_phone = "1234567890"
admin_password = "admin123"
password_hash = generate_password_hash(admin_password)
created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if admin user already exists
cursor.execute('SELECT id FROM users WHERE email = ?', (admin_email,))
existing_user = cursor.fetchone()

if existing_user:
    # Update existing user to admin
    cursor.execute(
        'UPDATE users SET is_admin = 1 WHERE email = ?',
        (admin_email,)
    )
    print(f"Existing user {admin_email} has been updated to admin status.")
else:
    # Create new admin user
    cursor.execute(
        'INSERT INTO users (name, email, phone, password, created_at, is_admin) VALUES (?, ?, ?, ?, ?, 1)',
        (admin_name, admin_email, admin_phone, password_hash, created_at)
    )
    print(f"New admin user {admin_email} has been created.")

# Commit changes and close connection
conn.commit()
conn.close()

print(f"\nAdmin User Details:")
print(f"Email: {admin_email}")
print(f"Password: {admin_password}")
print(f"Login with these credentials to access admin features.")
