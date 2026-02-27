import mysql.connector
from datetime import datetime

# Connect to the database
conn = mysql.connector.connect(
    host="localhost",
    port="3308",
    user="root",
    password="cocsit",
    database="hotel"
)
cursor = conn.cursor()

# ========== Helper Function for Validation ==========
def get_non_empty_input(prompt):
    """Ensures the user does not leave a field empty."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("⚠️ This field cannot be empty. Please enter a value.")

# ========== Auto Release Rooms ==========
def auto_release_rooms():
    today = datetime.today().date()
    cursor.execute("""
        SELECT booking_id, room_id FROM bookings
        WHERE checkout_date < %s AND status = 'booked'
    """, (today,))
    results = cursor.fetchall()

    for booking_id, room_id in results:
        cursor.execute("UPDATE bookings SET status = 'completed' WHERE booking_id = %s", (booking_id,))
        cursor.execute("UPDATE rooms SET is_available = 1 WHERE room_id = %s", (room_id,))

    if results:
        conn.commit()
        print(f"🔄 {len(results)} room(s) auto-released based on check-out date.")

# ========== Admin Authentication ==========
def admin_auth():
    pin = input("Enter admin PIN: ")
    return pin == "1234"

# ========== Customer Registration (Fixed) ==========
def register_customer():
    print("\n--- Customer Registration ---")
    name = get_non_empty_input("Enter customer name: ")
    contact = get_non_empty_input("Enter contact number: ")
    email = get_non_empty_input("Enter email: ")

    cursor.execute("""
        INSERT INTO customers (name, contact, email)
        VALUES (%s, %s, %s)
    """, (name, contact, email))

    conn.commit()
    customer_id = cursor.lastrowid
    print(f"✅ Customer registered successfully! Your Customer ID is: {customer_id}")
    return customer_id

# ========== View Available Rooms ==========
def view_available_rooms():
    cursor.execute("SELECT * FROM rooms WHERE is_available = 1")
    rooms = cursor.fetchall()
    if not rooms:
        print("❌ No available rooms right now.")
        return
    print("\nAvailable Rooms:")
    for room in rooms:
        print(f"Room ID: {room[0]}, Type: {room[1]}, Price: ₹{room[3]}")

# ========== Book Room with Registration Check ==========
def book_room_flow():
    choice = input("Are you already registered? (yes/no): ").strip().lower()
    if choice == 'no':
        customer_id = register_customer()
    else:
        customer_id = get_non_empty_input("Enter your customer ID: ")
        cursor.execute("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
        result = cursor.fetchone()
        if not result:
            print("❌ Customer not found. Please register first.")
            return

    book_room(customer_id)

def book_room(customer_id):
    view_available_rooms()
    room_id = get_non_empty_input("Enter Room ID to book: ")
    cursor.execute("SELECT * FROM rooms WHERE room_id = %s AND is_available = 1", (room_id,))
    result = cursor.fetchone()
    if not result:
        print("❌ Room not available.")
        return

    checkin_date = get_non_empty_input("Enter check-in date (YYYY-MM-DD): ")
    checkout_date = get_non_empty_input("Enter check-out date (YYYY-MM-DD): ")

    cursor.execute("""
        INSERT INTO bookings (customer_id, room_id, checkin_date, checkout_date, status)
        VALUES (%s, %s, %s, %s, 'booked')
    """, (customer_id, room_id, checkin_date, checkout_date))

    cursor.execute("UPDATE rooms SET is_available = 0 WHERE room_id = %s", (room_id,))
    conn.commit()
    print("✅ Room booked successfully!")

# ========== Cancel Booking ==========
def cancel_booking():
    booking_id = get_non_empty_input("Enter your booking ID to cancel: ")
    cursor.execute("SELECT * FROM bookings WHERE booking_id = %s AND status = 'booked'", (booking_id,))
    result = cursor.fetchone()
    if not result:
        print("❌ Booking not found or already canceled.")
        return

    room_id = result[2]
    cursor.execute("UPDATE bookings SET status = 'canceled' WHERE booking_id = %s", (booking_id,))
    cursor.execute("UPDATE rooms SET is_available = 1 WHERE room_id = %s", (room_id,))
    conn.commit()
    print("✅ Booking canceled successfully.")

# ========== Show Booking Receipt ==========
def show_booking_receipt():
    booking_id = get_non_empty_input("Enter your booking ID: ")
    cursor.execute("SELECT * FROM bookings WHERE booking_id = %s", (booking_id,))
    result = cursor.fetchone()
    if not result:
        print("❌ Booking not found.")
        return

    customer_id = result[1]
    room_id = result[2]
    checkin_date = result[3]
    checkout_date = result[4]
    status = result[5]

    cursor.execute("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
    customer = cursor.fetchone()

    cursor.execute("SELECT * FROM rooms WHERE room_id = %s", (room_id,))
    room = cursor.fetchone()

    print("\n📄 Booking Receipt:")
    print(f"Booking ID  : {booking_id}")
    print(f"Customer    : {customer[1]} (ID: {customer_id})")
    print(f"Contact     : {customer[2]}")
    print(f"Email       : {customer[3]}")
    print(f"Room ID     : {room_id}")
    print(f"Room Type   : {room[1]}")
    print(f"Price/Night : ₹{room[3]}")
    print(f"Check-in    : {checkin_date}")
    print(f"Check-out   : {checkout_date}")
    print(f"Status      : {status}")

# ========== Admin Revenue Report ==========
def revenue_report():
    cursor.execute("""
        SELECT r.room_id, r.room_type, r.price_per_night, b.checkin_date, b.checkout_date
        FROM bookings b
        JOIN rooms r ON b.room_id = r.room_id
        WHERE b.status = 'booked'
    """)
    bookings = cursor.fetchall()

    total_revenue = 0
    print("\n💰 Revenue Report:")
    for row in bookings:
        room_id, room_type, price, checkin_date, checkout_date = row
        check_in_date = datetime.strptime(str(checkin_date), "%Y-%m-%d")
        check_out_date = datetime.strptime(str(checkout_date), "%Y-%m-%d")
        nights = (check_out_date - check_in_date).days
        amount = nights * price
        total_revenue += amount
        print(f"Room {room_id} ({room_type}): ₹{amount} ({nights} nights)")

    print(f"\n🔢 Total Revenue: ₹{total_revenue}")

# ========== Extend Booking ==========
def extend_booking():
    booking_id = get_non_empty_input("Enter your booking ID to extend: ")
    cursor.execute("SELECT * FROM bookings WHERE booking_id = %s AND status = 'booked'", (booking_id,))
    booking = cursor.fetchone()

    if not booking:
        print("❌ Active booking not found.")
        return

    room_id = booking[2]
    current_checkout = booking[4]
    print(f"Current check-out date: {current_checkout}")

    new_checkout = get_non_empty_input("Enter new check-out date (YYYY-MM-DD): ")

    cursor.execute("""
        SELECT * FROM bookings
        WHERE room_id = %s AND status = 'booked'
        AND checkin_date < %s AND checkout_date > %s AND booking_id != %s
    """, (room_id, new_checkout, current_checkout, booking_id))

    conflict = cursor.fetchone()

    if conflict:
        print("❌ Cannot extend booking. Another booking exists during that time.")
    else:
        cursor.execute("UPDATE bookings SET checkout_date = %s WHERE booking_id = %s", (new_checkout, booking_id))
        conn.commit()
        print("✅ Booking extended successfully.")


# ========== View Registered Customers (Admin Only) ==========
def view_registered_customers():
    cursor.execute("SELECT customer_id, name, contact, email FROM customers")
    customers = cursor.fetchall()
    if not customers:
        print("❌ No customers registered yet.")
        return

    print("\n📋 Registered Customers:")
    for c in customers:
        print(f"ID: {c[0]}, Name: {c[1]}, Contact: {c[2]}, Email: {c[3]}")


# ========== Main Menu ==========
def main():
    auto_release_rooms()

    while True:
        print("\n🏨 Welcome to Hotel Management System")
        print("1. Register Customer")
        print("2. View Available Rooms")
        print("3. Book a Room")
        print("4. Cancel Booking")
        print("5. Show Booking Receipt")
        print("6. Admin: Revenue Report")
        print("7. Extend Booking")
        print("8. Exit")
        print("9. Admin: View Registered Customers")

        choice = input("Enter your choice: ")

        if choice == '1':
            register_customer()
        elif choice == '2':
            view_available_rooms()
        elif choice == '3':
            book_room_flow()
        elif choice == '4':
            cancel_booking()
        elif choice == '5':
            show_booking_receipt()
        elif choice == '6':
            if admin_auth():
                revenue_report()
            else:
                print("❌ Invalid admin PIN!")
        elif choice == '7':
            extend_booking()
        elif choice == '9':
            if admin_auth():
                view_registered_customers()
            else:
                print("❌ Invalid admin PIN!")
        elif choice == '8':
            print("👋 Thank you for using the system.")
            break
        else:
            print("❌ Invalid choice. Please try again.")

    cursor.close()
    conn.close()


