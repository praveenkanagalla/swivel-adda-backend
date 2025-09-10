import os
import psycopg
from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
import datetime
import razorpay

app = Flask(__name__)
CORS(app)

# ✅ JWT Secret (always set in Render environment variables)
SECRET_KEY = os.getenv("JWT_SECRET", "fallback_secret_key")

# ✅ Database connection helper
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

# ✅ Ensure users table exists
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

# ✅ Register endpoint
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
        cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
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

# ✅ Login endpoint
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
        "user_id": user[0],
        "email": user[2],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=12)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    return jsonify({
        "message": f"Welcome back, {user[1]}!",
        "token": token,
        "name": user[1],
        "email": user[2]
    }), 200

# ✅ Health check
@app.route('/')
def home():
    return jsonify({"message": "Flask API running with psycopg3 & Python 3.13.5!"})

# Razorpay Test Keys (set in .env or Render environment variables)
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_abc123")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "xyz987secret")

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ✅ Create Razorpay Order
@app.route('/create-order', methods=['POST'])
def create_order():
    try:
        data = request.get_json()
        amount = data.get("amount", 50000)  # default ₹500 (in paise)

        # Create an order in Razorpay
        order = razorpay_client.order.create({
            "amount": amount,        # Amount in paise (₹500 = 50000)
            "currency": "INR",
            "payment_capture": 1     # Auto capture
        })

        return jsonify({
            "id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "status": order["status"],
            "key": RAZORPAY_KEY_ID   # Send Key ID to frontend
        }), 200

    except Exception as e:
        print("❌ Razorpay order creation failed:", str(e))
        return jsonify({"message": "Failed to create order", "error": str(e)}), 500

# ✅ Run with waitress (production-ready)
if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
