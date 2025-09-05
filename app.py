import os
import psycopg
from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
import datetime
from dotenv import load_dotenv

# Load environment variables (local .env file support)
load_dotenv()

app = Flask(__name__)
CORS(app)

# ✅ Secret key for JWT token
SECRET_KEY = os.getenv("JWT_SECRET", "PRA24@123ab")

# ✅ Database connection
def get_db_connection():
    try:
        conn = psycopg.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", 5432)),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "password"),
            dbname=os.getenv("DB_NAME", "userdata"),
            connect_timeout=10
        )
        return conn
    except Exception as err:
        print("❌ Database connection failed:", err)
        return None

# ✅ Ensure table exists
def create_user_table():
    conn = get_db_connection()
    if conn is None:
        print("⚠️ Skipping table creation - No DB connection")
        return
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                email VARCHAR(255) UNIQUE,
                password VARCHAR(255)
            )
        """)
        conn.commit()
    conn.close()

create_user_table()

# ✅ Register route
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

    with conn.cursor() as cursor:
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

# ✅ Login route
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

    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name, email, password FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
    conn.close()

    if not user or user[3] != password:  # index 3 = password
        return jsonify({"message": "Invalid credentials"}), 401

    payload = {
        'user_id': user[0],
        'email': user[2],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=12)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

    return jsonify({
        "message": f"Welcome back, {user[1]}!",
        "token": token,
        "name": user[1],
        "email": user[2]
    }), 200

# ✅ Health check route
@app.route('/')
def home():
    return jsonify({"message": "Flask API running with psycopg3 & Python 3.13.5!"})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
