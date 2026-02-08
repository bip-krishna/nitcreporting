import os
import random
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session, send_from_directory, abort, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.utils import secure_filename

app = Flask(__name__)

# CONFIG
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = "secret"

db = SQLAlchemy(app)
UPLOAD_DIR = os.path.join(app.instance_path, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------- MODELS ---------------- #

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))


class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(50), unique=True)
    capacity = db.Column(db.Integer)

class TokenBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_email = db.Column(db.String(100))
    fee_status = db.Column(db.String(20))
    payment_mode = db.Column(db.String(50))
    slot_time = db.Column(db.String(50))
    token_id = db.Column(db.String(20), unique=True)
    class10_doc = db.Column(db.String(255))
    class12_doc = db.Column(db.String(255))
    category_doc = db.Column(db.String(255))
    paid_receipt_doc = db.Column(db.String(255))
    sent_to_chanakya = db.Column(db.Boolean, default=False)
    admin1_notes = db.Column(db.Text)
    final_registration_completed = db.Column(db.Boolean, default=False)
    final_registration_completed_at = db.Column(db.String(50))


def parse_identity_from_email(email):
    local = (email or "").split("@")[0]
    if "_" not in local:
        return {"name": email or "Unknown", "roll_no": "--"}
    name_part, roll_part = local.split("_", 1)
    name = name_part.replace(".", " ").replace("-", " ").title()
    return {"name": name, "roll_no": roll_part.upper()}


def payment_label(raw_payment):
    if raw_payment == "already-paid":
        return "Already Paid"
    if raw_payment == "on-spot":
        return "On Spot Payment"
    if raw_payment == "education-loan":
        return "Education Loan"
    return (raw_payment or "NA").replace("-", " ").title()


def capacity_units_for_fee(fee_status):
    return 1 if (fee_status or "").lower() == "yes" else 2


def booking_to_view(booking):
    identity = parse_identity_from_email(booking.student_email)
    return {
        "id": booking.id,
        "token_id": booking.token_id,
        "student_email": booking.student_email,
        "student_name": identity["name"],
        "roll_no": identity["roll_no"],
        "fee_status": booking.fee_status,
        "slot_time": booking.slot_time,
        "payment_mode": booking.payment_mode,
        "payment_label": payment_label(booking.payment_mode),
        "queue_type": "X (Quick Review)" if (booking.fee_status or "").lower() == "yes" else "Y (Detailed Consultation)",
        "sent_to_chanakya": bool(booking.sent_to_chanakya),
        "class10_doc_url": f"/uploads/{booking.class10_doc}" if booking.class10_doc else None,
        "class12_doc_url": f"/uploads/{booking.class12_doc}" if booking.class12_doc else None,
        "category_doc_url": f"/uploads/{booking.category_doc}" if booking.category_doc else None,
        "paid_receipt_doc_url": f"/uploads/{booking.paid_receipt_doc}" if booking.paid_receipt_doc else None,
        "admin1_notes": booking.admin1_notes or "",
        "final_registration_completed": bool(booking.final_registration_completed),
        "final_registration_completed_at": booking.final_registration_completed_at or "",
    }


def save_uploaded_file(file_obj, email, label):
    if not file_obj or not file_obj.filename:
        return None
    safe_name = secure_filename(file_obj.filename)
    _, ext = os.path.splitext(safe_name)
    base_email = (email or "student").replace("@", "_at_").replace(".", "_")
    unique_name = f"{base_email}_{label}_{uuid.uuid4().hex[:10]}{ext}"
    file_obj.save(os.path.join(UPLOAD_DIR, unique_name))
    return unique_name


def generate_token_id():
    while True:
        token = f"TKN-{random.randint(100, 999)}"
        if not TokenBooking.query.filter_by(token_id=token).first():
            return token


def ensure_tokenbooking_columns():
    rows = db.session.execute(text("PRAGMA table_info(token_booking)")).fetchall()
    existing = {row[1] for row in rows}
    required_columns = {
        "token_id": "TEXT",
        "class10_doc": "TEXT",
        "class12_doc": "TEXT",
        "category_doc": "TEXT",
        "paid_receipt_doc": "TEXT",
        "sent_to_chanakya": "INTEGER DEFAULT 0",
        "admin1_notes": "TEXT",
        "final_registration_completed": "INTEGER DEFAULT 0",
        "final_registration_completed_at": "TEXT",
    }
    for column, ddl_type in required_columns.items():
        if column not in existing:
            db.session.execute(text(f"ALTER TABLE token_booking ADD COLUMN {column} {ddl_type}"))
    db.session.commit()



# ---------------- PAGE ROUTES ---------------- #

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    if request.method == "GET":
        return render_template("login.html")
    return jsonify({"success": True})

@app.route("/student.html")
def student_page():
    email = session.get("student_email")
    existing_booking = None
    if email:
        current = TokenBooking.query.filter_by(student_email=email).order_by(TokenBooking.id.desc()).first()
        if current:
            existing_booking = booking_to_view(current)
    final_admission_slip_url = None
    if existing_booking and existing_booking["final_registration_completed"]:
        final_admission_slip_url = url_for("final_registration_print_page", booking_id=existing_booking["id"])
    return render_template(
        "student.html",
        email=email,
        has_booking=existing_booking is not None,
        existing_booking=existing_booking,
        final_admission_slip_url=final_admission_slip_url,
    )

@app.route("/admin.html")
def admin_page():
    bookings = TokenBooking.query.order_by(TokenBooking.id.desc()).all()
    quick_bookings = [booking_to_view(b) for b in bookings if (b.fee_status or "").lower() == "yes"]
    detailed_bookings = [booking_to_view(b) for b in bookings if (b.fee_status or "").lower() == "no"]
    return render_template(
        "admin.html",
        quick_bookings=quick_bookings,
        detailed_bookings=detailed_bookings
    )

@app.route("/book-token.html")
def book_token_page():
    email = session.get("student_email")
    slots = Slot.query.order_by(Slot.id.asc()).all()
    slot_data = [{"time": s.time, "capacity": s.capacity} for s in slots]
    existing_booking = None
    if email:
        current = TokenBooking.query.filter_by(student_email=email).order_by(TokenBooking.id.desc()).first()
        if current:
            existing_booking = booking_to_view(current)
    return render_template("book-token.html", email=email, slots=slot_data, existing_booking=existing_booking)
@app.route("/lateadmin.html")
def lateadmin_page():
    return render_template("lateadmin.html")

@app.route("/admin2.html")
def admin2_page():
    chanakya_queue = TokenBooking.query.filter_by(sent_to_chanakya=True).order_by(TokenBooking.id.asc()).all()
    chanakya_bookings = [booking_to_view(b) for b in chanakya_queue]
    selected_booking_id = request.args.get("booking", type=int)
    active_booking = None
    if chanakya_bookings:
        active_booking = chanakya_bookings[0]
        if selected_booking_id is not None:
            for booking in chanakya_bookings:
                if booking["id"] == selected_booking_id:
                    active_booking = booking
                    break
    return render_template("admin2.html", chanakya_bookings=chanakya_bookings, active_booking=active_booking)


@app.route("/final-registration-print/<int:booking_id>")
def final_registration_print_page(booking_id):
    booking = TokenBooking.query.get(booking_id)
    if not booking:
        return abort(404)

    admin_email = session.get("admin_email")
    student_email = session.get("student_email")
    if not admin_email:
        if not student_email or student_email != booking.student_email:
            return abort(403)
        if not booking.final_registration_completed:
            return abort(403)

    return render_template(
        "final-registration-print.html",
        booking=booking_to_view(booking),
        generated_at=booking.final_registration_completed_at or datetime.now().strftime("%d %b %Y, %I:%M %p"),
        generated_by=admin_email or "Admissions Office",
    )


@app.route("/complete-final-registration", methods=["POST"])
def complete_final_registration():
    if not session.get("admin_email"):
        return jsonify({"success": False, "message": "Admin login required."}), 401

    data = request.get_json(silent=True) or {}
    booking_id = data.get("booking_id")
    if not booking_id:
        return jsonify({"success": False, "message": "booking_id is required."}), 400

    booking = TokenBooking.query.get(booking_id)
    if not booking:
        return jsonify({"success": False, "message": "Booking not found."}), 404

    booking.final_registration_completed = True
    if not booking.final_registration_completed_at:
        booking.final_registration_completed_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Final registration completed.",
        "print_url": url_for("final_registration_print_page", booking_id=booking.id),
    })


@app.route("/livestatus.html")
def livestatus_page():
    email = session.get("student_email")
    queue = TokenBooking.query.filter_by(sent_to_chanakya=False).order_by(TokenBooking.id.asc()).all()

    now_serving = queue[0] if queue else None
    upcoming_tokens = [b.token_id for b in queue[1:6] if b.token_id]
    current_booking = None
    for booking in queue:
        if booking.student_email == email:
            current_booking = booking
            break

    x_count = 0
    y_count = 0
    student_token = current_booking.token_id if current_booking else "--"

    if current_booking:
        ahead = [b for b in queue if b.id < current_booking.id]
        x_count = sum(1 for b in ahead if (b.fee_status or "").lower() == "yes")
        y_count = sum(1 for b in ahead if (b.fee_status or "").lower() != "yes")

    students_ahead = x_count + y_count
    expected_time_minutes = (3 * x_count) + (6 * y_count)

    return render_template(
        "livestatus.html",
        email=email,
        now_serving_token=now_serving.token_id if now_serving and now_serving.token_id else "--",
        student_token=student_token,
        upcoming_tokens=upcoming_tokens,
        x_count=x_count,
        y_count=y_count,
        students_ahead=students_ahead,
        expected_time_minutes=expected_time_minutes,
        updated_label="Live",
    )


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    if not session.get("admin_email"):
        abort(403)
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)

# @app.route("/success-token.html")
# def success_token():
#     email = session.get("student_email")
#     return render_template("success-token.html", email=email)


@app.route("/set-40")
def set_40():

    slots = Slot.query.all()

    for s in slots:
        s.capacity = 40

    db.session.commit()

    return "All slots set to 40"
 
@app.route("/success-token.html")
def success_token():

    email = session.get("student_email")
    booking = session.get("booking")

    return render_template(
        "success-token.html",
        email=email,
        booking=booking
    )


@app.route("/proceed-to-chanakya", methods=["POST"])
def proceed_to_chanakya():
    if not session.get("admin_email"):
        return jsonify({"success": False, "message": "Admin login required."}), 401

    data = request.get_json(silent=True) or {}
    booking_id = data.get("booking_id")
    admin1_notes = (data.get("admin1_notes") or "").strip()
    if not booking_id:
        return jsonify({"success": False, "message": "booking_id is required."}), 400

    booking = TokenBooking.query.get(booking_id)
    if not booking:
        return jsonify({"success": False, "message": "Booking not found."}), 404

    booking.sent_to_chanakya = True
    booking.admin1_notes = admin1_notes
    db.session.commit()
    return jsonify({"success": True, "message": "Student moved to Chanakya queue."})


@app.route("/reject-booking", methods=["POST"])
def reject_booking():
    if not session.get("admin_email"):
        return jsonify({"success": False, "message": "Admin login required."}), 401

    data = request.get_json(silent=True) or {}
    booking_id = data.get("booking_id")
    if not booking_id:
        return jsonify({"success": False, "message": "booking_id is required."}), 400

    booking = TokenBooking.query.get(booking_id)
    if not booking:
        return jsonify({"success": False, "message": "Booking not found."}), 404

    slot_obj = Slot.query.filter_by(time=booking.slot_time).first()
    if slot_obj:
        slot_obj.capacity += capacity_units_for_fee(booking.fee_status)

    for doc_name in [booking.class10_doc, booking.class12_doc, booking.category_doc, booking.paid_receipt_doc]:
        if not doc_name:
            continue
        path = os.path.join(UPLOAD_DIR, doc_name)
        if os.path.exists(path):
            os.remove(path)

    db.session.delete(booking)
    db.session.commit()
    return jsonify({"success": True, "message": "Profile rejected and booking removed."})



# ---------------- LOGIN API ---------------- #

@app.route("/login", methods=["POST"])
def login():

    data = request.get_json()

    role = data.get("role")
    email = data.get("email").strip()
    password = data.get("password").strip()

    # -------- STUDENT LOGIN -------- #
    if role == "student":
        user = Student.query.filter_by(
            email=email,
            password=password
        ).first()

        if user:
            session["student_email"] = email   # ⭐ STORE EMAIL
            return jsonify({"success":True,"redirect":"student.html"})

        return jsonify({"success":False,"message":"Invalid student login"})

    # -------- ADMIN LOGIN -------- #
    if role == "admin":
        hall_role = (data.get("hallRole") or data.get("hall_role") or "").strip().lower()
        user = Admin.query.filter_by(
            email=email,
            password=password
        ).first()

        if user:
            session["admin_email"] = email
            session["admin_hall_role"] = hall_role
            redirect_page = "admin2.html" if hall_role == "chanakya" else "admin.html"
            return jsonify({"success":True,"redirect":redirect_page})

        return jsonify({"success":False,"message":"Invalid admin login"})

    return jsonify({"success":False,"message":"Invalid role"})

#---------------------Booking API-----------------------#
@app.route("/submit-booking", methods=["POST"])
def submit_booking():
    data = request.get_json(silent=True) or {}
    slot = request.form.get("slot") or data.get("slot")
    fee = request.form.get("fee") or data.get("fee")
    payment = request.form.get("payment") or data.get("payment")
    class10_file = request.files.get("docClass10")
    class12_file = request.files.get("docClass12")
    category_file = request.files.get("docCategory")
    paid_receipt_file = request.files.get("paidReceipt")

    email = session.get("student_email")

    if not email:
        return jsonify({"success": False, "message": "Please login as student first."})

    if fee not in ["yes", "no"]:
        return jsonify({"success": False, "message": "Invalid fee status."})

    if not slot:
        return jsonify({"success": False, "message": "Slot is required."})

    if fee == "no" and not payment:
        return jsonify({"success": False, "message": "Payment mode is required for unpaid fee."})
    if fee == "yes" and not paid_receipt_file:
        return jsonify({"success": False, "message": "Fee receipt is required for paid candidates."})

    if not class10_file or not class12_file:
        return jsonify({"success": False, "message": "Class 10 and Class 12 documents are required."})

    existing_booking = TokenBooking.query.filter_by(student_email=email).first()
    if existing_booking:
        return jsonify({
            "success": False,
            "message": f"You already booked a slot ({existing_booking.slot_time}). Multiple bookings are not allowed."
        })

    slot_obj = Slot.query.filter_by(time=slot).first()
    if not slot_obj:
        return jsonify({"success": False, "message": "Invalid slot selected."})
    needed_capacity = capacity_units_for_fee(fee)
    if slot_obj.capacity < needed_capacity:
        return jsonify({"success": False, "message": "Selected slot is full. Please choose another slot."})

    token_id = generate_token_id()
    class10_name = save_uploaded_file(class10_file, email, "class10")
    class12_name = save_uploaded_file(class12_file, email, "class12")
    category_name = save_uploaded_file(category_file, email, "category")
    receipt_name = save_uploaded_file(paid_receipt_file, email, "receipt")

    booking = TokenBooking(
        student_email=email,
        fee_status=fee,
        payment_mode=payment if fee == "no" else "already-paid",
        slot_time=slot,
        token_id=token_id,
        class10_doc=class10_name,
        class12_doc=class12_name,
        category_doc=category_name,
        paid_receipt_doc=receipt_name,
        sent_to_chanakya=False
    )
    slot_obj.capacity -= needed_capacity
    db.session.add(booking)
    db.session.commit()

    # store lightweight data in session for success page
    session["booking"] = {
        "slot": slot,
        "token": token_id,
        "fee": fee,
        "payment": payment if fee == "no" else "already-paid"
    }

    return jsonify({
        "success": True,
        "redirect": "/success-token.html"
    })

# ---------------- INIT DB ---------------- #

with app.app_context():
    db.create_all()
    ensure_tokenbooking_columns()

    if not Student.query.first():
        db.session.add_all([
            Student(email="krishna_b250946ec@nitc.ac.in",password="kkj@1234"),
            Student(email="prabhu_b250123cs@nitc.ac.in",password="prabhu@nitc"),
            Student(email="nishad_b251069ec@nitc.ac.in",password="nishad@1234")
        ])

    if not Admin.query.first():
        db.session.add(
            Admin(email="jimmy@nitc.ac.in",password="jimmy@1234")
        )

    db.session.commit()
    slots = Slot.query.all()

    if not slots:
        slots = [
            Slot(time="9:00 AM - 10:00 AM", capacity=40),
            Slot(time="10:00 AM - 11:00 AM", capacity=40),
            Slot(time="11:00 AM - 12:00 PM", capacity=40),
            Slot(time="12:00 PM - 1:00 PM", capacity=40),
            Slot(time="1:00 PM - 2:00 PM", capacity=40),
            Slot(time="2:00 PM - 3:00 PM", capacity=40),
            Slot(time="3:00 PM - 4:00 PM", capacity=40),
            Slot(time="4:00 PM - 5:00 PM", capacity=40),
        ]
        db.session.add_all(slots)
        db.session.commit()



# ---------------- RUN ---------------- #

if __name__ == "__main__":
    app.run(debug=True)