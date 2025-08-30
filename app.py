from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import jwt
import datetime
import os

app = Flask(__name__)
CORS(app)

# ✅ Secret key for JWT token (read from environment, fallback for local testing)
SECRET_KEY = os.getenv("JWT_SECRET", "PRA24@123ab")

# ✅ Database connection function (works for both local + Render)
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),  # Render will override this
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "PRA24@123ab"),
            database=os.getenv("DB_NAME", "userdata"),
            connect_timeout=10
        )
        return conn
    except mysql.connector.Error as err:
        print("❌ Database connection failed:", err)
        return None

# ✅ Ensure table exists (only if DB available)
def create_user_table():
    conn = get_db_connection()
    if conn is None:
        print("⚠️ Skipping table creation - No DB connection")
        return
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255),
            email VARCHAR(255) UNIQUE,
            password VARCHAR(255)
        )
    """)
    conn.commit()
    conn.close()

create_user_table()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not all([name, email, password]):
        return jsonify({"message": "All fields are required"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database not connected"}), 500

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"message": "User already exists"}), 400

    cursor.execute(
        "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
        (name, email, password)
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Registration successful"}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"message": "Email and password required"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database not connected"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user or user['password'] != password:
        return jsonify({"message": "Invalid credentials"}), 401

    payload = {
        'user_id': user['id'],
        'email': user['email'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

    return jsonify({
        "message": f"Welcome back, {user['name']}!",
        "token": token,
        "name": user['name'],
        "email": user['email']
    }), 200

if __name__ == '__main__':
    # ✅ In production Render uses gunicorn, locally you can run Flask
    app.run(host="0.0.0.0", port=5000, debug=True)
