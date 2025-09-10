import os
import psycopg
from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
import razorpay
from dotenv import load_dotenv
import razorpay

# ✅ Load environment variables (from .env locally, or Render env in production)
load_dotenv()

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


# 🔑 Replace with your Razorpay Test Keys
RAZORPAY_KEY_ID = "rzp_test_RFtj1A3i6aEjew"
RAZORPAY_KEY_SECRET = "v5VGOV3nhe82BOD0dpUAsZYB"

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

@app.route('/create-order', methods=['POST'])
def create_order():
    data = request.get_json()
    amount = data.get('amount')
    if not amount:
        return jsonify({"error": "Amount is required"}), 400

    try:
        # Razorpay expects amount in paise
        order = client.order.create({
            "amount": int(amount) * 100,
            "currency": "INR",
            "payment_capture": 1
        })
        return jsonify(order)
    except razorpay.errors.RazorpayError as e:
        return jsonify({"error": str(e)}), 500

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    data = request.get_json()
    try:
        client.utility.verify_payment_signature(data)
        return jsonify({"status": "Payment Verified"})
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"status": "Payment Verification Failed"}), 400

# ✅ Run with waitress (production-ready)
if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
