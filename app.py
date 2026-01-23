from flask import Flask, render_template, request, redirect, session, flash, url_for
import mysql.connector
from datetime import date

app = Flask(__name__)
app.secret_key = 'hotel_secret_key'

# ========== Database Connection ==========
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        port="3308",
        user="root",
        password="cocsit",
        database="hotel"
    )

# ========== 1. Registration & Home ==========
@app.route('/')
def index():
    return render_template('index.html')

# Replace your 'handle_register' and the old 'register' route with this:
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # This part runs when you click the "Create Account" button
        name = request.form.get('name')
        contact = request.form.get('contact')
        email = request.form.get('email')
        password = request.form.get('password') 
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO customers (name, contact, email, password) VALUES (%s, %s, %s, %s)", 
                           (name, contact, email, password))
            conn.commit()
            new_id = cursor.lastrowid
            cursor.close()
            conn.close()
            flash(f"Registration Successful! Your Login ID is: {new_id}")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error: {str(e)}")
            # If it fails, stay on the register page to show the error
            return redirect(url_for('register'))
    
    # This part runs when you just click the "Sign Up" link from the Login page
    return render_template('register.html')

# ========== 2. Login ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input_id = request.form.get('customer_id')
        user_password = request.form.get('password')
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM customers WHERE id = %s AND password = %s", (user_input_id, user_password))
            customer = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if customer:
                session['user_id'] = customer['id']
                session['user_name'] = customer['name']
                session['user_email'] = customer['email']
                session['role'] = 'customer'
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid ID or Password! Please try again.")
        except Exception as e:
            flash(f"Database Error: {str(e)}")
    return render_template('login.html')

# ========== 3. Dashboard ==========
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. COUNT ACTIVE BOOKINGS
        cursor.execute("SELECT COUNT(*) as active_count FROM bookings WHERE customer_id = %s AND status = 'booked'", (session['user_id'],))
        active_data = cursor.fetchone()
        active_count = active_data['active_count'] if active_data else 0

        # 2. AUTO-CLEANUP
        today = date.today()
        cleanup_query = """
            UPDATE rooms r
            JOIN bookings b ON r.room_id = b.room_id
            SET r.is_available = 1, b.status = 'completed'
            WHERE b.checkout_date < %s AND b.status = 'booked'
        """
        cursor.execute(cleanup_query, (today,))
        conn.commit()
        
        # 3. FETCH ROOMS
        cursor.execute("SELECT * FROM rooms WHERE is_available = 1 AND room_type = 'VIP'")
        vip_rooms = cursor.fetchall()

        cursor.execute("SELECT * FROM rooms WHERE is_available = 1 AND room_type = 'General'")
        general_rooms = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('dashboard.html', 
                               name=session['user_name'], 
                               vip_rooms=vip_rooms, 
                               general_rooms=general_rooms, 
                               active_bookings=active_count)
    except Exception as e:
        return f"Error: {str(e)}"

# ========== 4. My Bookings ==========
@app.route('/my_bookings')
def my_bookings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT b.*, r.room_type, r.price_per_night
            FROM bookings b
            JOIN rooms r ON b.room_id = r.room_id
            WHERE b.customer_id = %s
            ORDER BY b.booking_id DESC
        """
        cursor.execute(query, (session['user_id'],))
        user_bookings = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('my_bookings.html', bookings=user_bookings)
    except Exception as e:
        return f"Error: {str(e)}"

# ========== 5. Booking Flow ==========
@app.route('/book/<int:room_id>')
def book_room_page(room_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('booking.html', room_id=room_id)

@app.route('/confirm_booking', methods=['POST'])
def confirm_booking():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    room_id = request.form.get('room_id')
    checkin = request.form.get('checkin')
    checkout = request.form.get('checkout')
    customer_id = session['user_id']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT price_per_night FROM rooms WHERE room_id = %s", (room_id,))
        room = cursor.fetchone()
        d1 = date.fromisoformat(checkin)
        d2 = date.fromisoformat(checkout)
        nights = max((d2-d1).days, 1)
        total_amt = nights * room['price_per_night']

        cursor.execute("""
            INSERT INTO bookings (customer_id, room_id, checkin_date, checkout_date, status, total_amount)
            VALUES (%s, %s, %s, %s, 'booked', %s)
        """, (customer_id, room_id, checkin, checkout, total_amt))
        
        new_booking_id = cursor.lastrowid 
        cursor.execute("UPDATE rooms SET is_available = 0 WHERE room_id = %s", (room_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('show_receipt', booking_id=new_booking_id))
    except Exception as e:
        flash(f"Booking Failed: {str(e)}")    
        return redirect(url_for('dashboard'))

# ========== 6. Receipts & Profile ==========
@app.route('/receipt/<int:booking_id>')
@app.route('/receipt')
def show_receipt(booking_id=None):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if booking_id:
            query = "SELECT b.*, r.room_type, r.price_per_night FROM bookings b JOIN rooms r ON b.room_id = r.room_id WHERE b.booking_id = %s AND b.customer_id = %s"
            cursor.execute(query, (booking_id, session['user_id']))
        else:
            query = "SELECT b.*, r.room_type, r.price_per_night FROM bookings b JOIN rooms r ON b.room_id = r.room_id WHERE b.customer_id = %s ORDER BY b.booking_id DESC LIMIT 1"
            cursor.execute(query, (session['user_id'],))
        booking = cursor.fetchone()
        cursor.close()
        conn.close()
        if booking:
            delta = booking['checkout_date'] - booking['checkin_date']
            nights = max(delta.days, 1) 
            return render_template('receipt.html', b=booking, nights=nights, total=booking['total_amount'])
        return redirect(url_for('my_bookings'))
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/cancel_booking/<int:booking_id>')
def cancel_booking(booking_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT room_id FROM bookings WHERE booking_id = %s", (booking_id,))
        booking = cursor.fetchone()
        if booking:
            cursor.execute("UPDATE bookings SET status = 'canceled' WHERE booking_id = %s", (booking_id,))
            cursor.execute("UPDATE rooms SET is_available = 1 WHERE room_id = %s", (booking['room_id'],))
            conn.commit()
            flash("Booking canceled successfully.")
        cursor.close()
        conn.close()
        return redirect(url_for('my_bookings'))
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect(url_for('my_bookings'))

# ========== 7. Logout & Admin Section ==========
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            # FIX: Check the database instead of hardcoded 'hotel123'
            cursor.execute("SELECT * FROM admins WHERE username = %s AND password = %s", (username, password))
            admin = cursor.fetchone()
            cursor.close()
            conn.close()

            if admin:
                session['admin_logged_in'] = True
                session['role'] = 'admin'
                return redirect(url_for('admin_dashboard'))
            else:
                flash("Invalid Admin Credentials")
        except Exception as e:
            flash(f"Database Error: {str(e)}. Make sure the 'admins' table exists!")
            
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    search_query = request.args.get('search', '').strip()
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as total FROM bookings")
        total_overall = cursor.fetchone()['total']
        
        cursor.execute("SELECT SUM(total_amount) as revenue FROM bookings WHERE status IN ('booked', 'completed')")
        rev_data = cursor.fetchone()
        total_revenue = rev_data['revenue'] if rev_data and rev_data['revenue'] else 0

        base_query = """
            SELECT b.booking_id, c.name as customer_name, r.room_type, b.status, b.total_amount, b.checkin_date
            FROM bookings b
            JOIN customers c ON b.customer_id = c.id
            JOIN rooms r ON b.room_id = r.room_id
        """
        if search_query:
            sql = base_query + " WHERE LOWER(c.name) LIKE LOWER(%s) OR b.booking_id = %s ORDER BY b.booking_id DESC"
            cursor.execute(sql, (f"%{search_query}%", search_query if search_query.isdigit() else -1))
        else:
            cursor.execute(base_query + " ORDER BY b.booking_id DESC")
        
        all_bookings = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin_dashboard.html', bookings=all_bookings, revenue=total_revenue, total_all=total_overall, search_val=search_query)
    except Exception as e:
        return f"Admin Error: {str(e)}"

# Route to view the separate Settings Page
@app.route('/admin/settings')
def admin_settings():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    return render_template('admin_settings.html')

# Route to process the change (stays the same but redirects to login on success)
@app.route('/admin/update_account', methods=['POST'])
def admin_update_account():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    new_username = request.form.get('new_username')
    new_password = request.form.get('new_password')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE admins SET username = %s, password = %s WHERE id = 1", 
                       (new_username, new_password))
        conn.commit()
        cursor.close()
        conn.close()
        
        session.clear() # Security best practice: force re-login
        flash("Credentials updated! Please login with your new details.")
        return redirect(url_for('admin_login'))
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect(url_for('admin_settings'))
# ========== UPDATED: Admin Price Update with Confirmation Feedback ==========
@app.route('/admin/update_price', methods=['POST'])
def update_price():
    # Only allow if admin session is active
    if not session.get('admin_logged_in'):
        flash("Unauthorized access. Please login as Admin.")
        return redirect(url_for('admin_login'))

    new_price = request.form.get('new_price')
    room_type = request.form.get('room_type')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # SQL to update the price for all rooms of that type
        cursor.execute("UPDATE rooms SET price_per_night = %s WHERE room_type = %s", 
                       (new_price, room_type))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Success feedback
        flash(f"SUCCESS: {room_type} room prices updated to ₹{new_price} successfully!")
        return redirect(url_for('admin_dashboard'))
        
    except Exception as e:
        flash(f"ERROR: {str(e)}")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ========== User Profile Logic ==========
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Fetch user details
        cursor.execute("SELECT name, email, contact FROM customers WHERE id = %s", (session['user_id'],))
        user_info = cursor.fetchone()
        
        # Count total successful stays
        cursor.execute("SELECT COUNT(*) as total FROM bookings WHERE customer_id = %s AND status != 'canceled'", (session['user_id'],))
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        return render_template('profile.html', user=user_info, total_stays=stats['total'])
    except Exception as e:
        return f"Profile Error: {str(e)}"

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_email = request.form.get('email')
        new_contact = request.form.get('contact')
        try:
            query = "UPDATE customers SET name = %s, email = %s, contact = %s WHERE id = %s"
            cursor.execute(query, (new_name, new_email, new_contact, session['user_id']))
            conn.commit()
            session['user_name'] = new_name # Update session name too
            flash("Profile updated successfully!")
            return redirect(url_for('profile'))
        except Exception as e:
            flash(f"Update failed: {str(e)}")
        finally:
            cursor.close()
            conn.close()

    # GET method: show current info
    cursor.execute("SELECT name, email, contact FROM customers WHERE id = %s", (session['user_id'],))
    user_info = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit_profile.html', user=user_info)
if __name__ == "__main__":
    app.run(debug=True)