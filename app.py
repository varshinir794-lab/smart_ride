import sqlite3, hashlib, os
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, session, redirect, render_template, url_for
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'campusride-secret-2024')
DB_PATH = os.path.join(os.path.dirname(__file__), 'campus_ride.db')
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
def init_db():
    """Create tables and seed demo data if needed."""
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            from_location TEXT NOT NULL,
            to_location TEXT NOT NULL,
            departure_time TEXT NOT NULL,
            seats_total INTEGER NOT NULL,
            seats_available INTEGER NOT NULL,
            fare REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            eta_arrived_mins INTEGER DEFAULT 120,
            eta_complete_mins INTEGER DEFAULT 240,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(driver_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ride_id INTEGER NOT NULL,
            passenger_id INTEGER NOT NULL,
            status TEXT DEFAULT 'confirmed',
            booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(ride_id) REFERENCES rides(id),
            FOREIGN KEY(passenger_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER NOT NULL,
            to_user INTEGER NOT NULL,
            ride_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            review TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(from_user) REFERENCES users(id),
            FOREIGN KEY(to_user) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ride_id INTEGER,
            title TEXT DEFAULT 'Notification',
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        try:
            conn.execute("ALTER TABLE notifications ADD COLUMN title TEXT DEFAULT 'Notification'")
        except Exception:
            pass
        for col, default in [('eta_arrived_mins', 120), ('eta_complete_mins', 240)]:
            try:
                conn.execute(f"ALTER TABLE rides ADD COLUMN {col} INTEGER DEFAULT {default}")
            except Exception:
                pass
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            def sha(p): return hashlib.sha256(p.encode()).hexdigest()
            conn.executemany("INSERT INTO users(name,email,password,role,phone) VALUES(?,?,?,?,?)", [
                ('Arjun Mehta',     'arjun@campus.edu',  sha('pass123'), 'student', '9876543210'),
                ('Priya Sharma',    'priya@campus.edu',  sha('pass123'), 'student', '9876543211'),
                ('Dr. Ramesh Kumar','ramesh@campus.edu', sha('pass123'), 'staff',   '9876543212'),
            ])
            conn.executemany(
                "INSERT INTO rides(driver_id,from_location,to_location,departure_time,seats_total,seats_available,fare,status) VALUES(?,?,?,?,?,?,?,?)",
                [
                    (1,'Main Gate','City Centre Mall','2025-01-15 08:30',4,2,20,'active'),
                    (2,'Hostel Block A','Railway Station','2025-01-15 09:00',3,1,30,'active'),
                    (3,'Admin Block','Airport','2025-01-15 10:00',4,3,80,'active'),
                ]
            )

def sha256(pw): return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'success': False, 'message': 'Not authenticated'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return wrapper

def push_notification(conn, user_id, ride_id, title, message, ntype='info'):
    """Insert a notification row (handles both old and new schema)."""
    conn.execute(
        "INSERT INTO notifications(user_id,ride_id,title,message,type) VALUES(?,?,?,?,?)",
        (user_id, ride_id, title, message, ntype)
    )
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html',
        user_name=session['user_name'],
        user_role=session['user_role'],
        user_id=session['user_id']
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/login', methods=['POST'])
def do_login():
    d = request.json
    with get_db() as conn:
        u = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (d['email'], sha256(d['password']))
        ).fetchone()
    if not u:
        return jsonify({'success': False, 'message': 'Invalid email or password'})
    session['user_id']   = u['id']
    session['user_name'] = u['name']
    session['user_role'] = u['role']
    return jsonify({'success': True, 'name': u['name']})

@app.route('/register', methods=['POST'])
def do_register():
    d = request.json
    if not d.get('name') or not d.get('email') or not d.get('password'):
        return jsonify({'success': False, 'message': 'All fields are required'})
    if len(d['password']) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'})
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users(name,email,password,role,phone) VALUES(?,?,?,?,?)",
                (d['name'], d['email'], sha256(d['password']), d.get('role','student'), d.get('phone',''))
            )
        # Do NOT create a session — user must log in explicitly after registration.
        return jsonify({'success': True, 'redirect': '/login'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Email already registered'})
@app.route('/api/stats')
@login_required
def api_stats():
    with get_db() as conn:
        total_rides    = conn.execute("SELECT COUNT(*) FROM rides WHERE status!='completed'").fetchone()[0]
        total_users    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_bookings = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        my_rides       = conn.execute(
            "SELECT COUNT(*) FROM rides WHERE driver_id=?", (session['user_id'],)
        ).fetchone()[0]
    return jsonify({'total_rides': total_rides, 'total_users': total_users,
                    'total_bookings': total_bookings, 'my_rides': my_rides})
def row_to_ride(r):
    return {
        'id':              r['id'],
        'driver_id':       r['driver_id'],
        'driver_name':     r['driver_name'],
        'driver_role':     r['driver_role'],
        'from_location':   r['from_location'],
        'to_location':     r['to_location'],
        'departure_time':  r['departure_time'],
        'seats_total':     r['seats_total'],
        'seats_available': r['seats_available'],
        'fare':            r['fare'],
        'status':          r['status'] or 'active',
        'avg_rating':      r['avg_rating'],
        'match_score':     0,
        'eta_arrived_mins':  r['eta_arrived_mins']  if r['eta_arrived_mins']  is not None else 120,
        'eta_complete_mins': r['eta_complete_mins'] if r['eta_complete_mins'] is not None else 240,
    }

RIDE_QUERY = """
    SELECT r.*,
           u.name  AS driver_name,
           u.role  AS driver_role,
           ROUND(AVG(rt.rating),1) AS avg_rating
    FROM rides r
    JOIN users u ON u.id = r.driver_id
    LEFT JOIN ratings rt ON rt.to_user = r.driver_id
    {where}
    GROUP BY r.id
    ORDER BY r.created_at DESC
"""

@app.route('/api/rides')
@login_required
def api_rides():
    with get_db() as conn:
        rows = conn.execute(RIDE_QUERY.format(where="""
            WHERE r.status != 'completed'
              AND datetime(replace(r.departure_time,'T',' ')) >= datetime('now', 'localtime')
        """)).fetchall()
    return jsonify([row_to_ride(r) for r in rows])

@app.route('/api/rides/search', methods=['POST'])
@login_required
def api_search():
    d   = request.json
    frm = (d.get('from') or '').strip().lower()
    to  = (d.get('to') or '').strip().lower()
    dt  = d.get('date') or ''

    with get_db() as conn:
        rows = conn.execute(RIDE_QUERY.format(where="""
            WHERE r.status != 'completed'
              AND datetime(replace(r.departure_time,'T',' ')) >= datetime('now', 'localtime')
        """)).fetchall()
    def jaccard(a, b):
        if not a or not b: return 0
        sa, sb = set(a.split()), set(b.split())
        return len(sa & sb) / len(sa | sb) if sa | sb else 0

    results = []
    for r in rows:
        score = 0
        if frm: score += jaccard(frm, r['from_location'].lower()) * 50
        if to:  score += jaccard(to,  r['to_location'].lower())   * 50
        if dt and dt in r['departure_time']: score += 20
        ride = row_to_ride(r)
        ride['match_score'] = min(round(score), 100)
        results.append(ride)

    results.sort(key=lambda x: x['match_score'], reverse=True)
    return jsonify(results)

@app.route('/api/rides/create', methods=['POST'])
@login_required
def api_create_ride():
    d = request.json
    seats = int(d.get('seats', 1))
    fare  = float(d.get('fare', 0))
    eta_arrived  = int(d.get('eta_arrived_mins', 120))
    eta_complete = int(d.get('eta_complete_mins', 240))
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO rides(driver_id,from_location,to_location,departure_time,seats_total,seats_available,fare,status,eta_arrived_mins,eta_complete_mins) VALUES(?,?,?,?,?,?,?,'active',?,?)",
                (session['user_id'], d['from_location'], d['to_location'], d['departure_time'], seats, seats, fare, eta_arrived, eta_complete)
            )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/rides/book', methods=['POST'])
@login_required
def api_book():
    ride_id = request.json.get('ride_id')
    uid     = session['user_id']
    with get_db() as conn:
        ride = conn.execute("SELECT * FROM rides WHERE id=?", (ride_id,)).fetchone()
        if not ride:
            return jsonify({'success': False, 'message': 'Ride not found'})
        if ride['driver_id'] == uid:
            return jsonify({'success': False, 'message': 'Cannot book your own ride'})
        if ride['seats_available'] < 1:
            return jsonify({'success': False, 'message': 'No seats available'})
        if ride['status'] != 'active':
            return jsonify({'success': False, 'message': 'This ride is no longer accepting bookings'})
        # Check if departure time has already passed
        try:
            dep_str = ride['departure_time'].replace('T', ' ')
            dep_dt  = datetime.strptime(dep_str[:16], '%Y-%m-%d %H:%M')
            if dep_dt < datetime.now():
                return jsonify({'success': False, 'message': 'This ride has already departed and cannot be booked'})
        existing = conn.execute(
            "SELECT id FROM bookings WHERE ride_id=? AND passenger_id=?", (ride_id, uid)
        ).fetchone()
        if existing:
            return jsonify({'success': False, 'message': 'You have already booked this ride'})

        conn.execute("INSERT INTO bookings(ride_id,passenger_id) VALUES(?,?)", (ride_id, uid))
        conn.execute(
            "UPDATE rides SET seats_available = seats_available - 1 WHERE id=?", (ride_id,)
        )
        push_notification(conn, uid, ride_id,
            'Ride Booked! 🎫',
            f'Your seat on {ride["from_location"]} → {ride["to_location"]} is confirmed. '
            f'Departure: {ride["departure_time"]}.',
            'booking'
        )
        pax = conn.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
        push_notification(conn, ride['driver_id'], ride_id,
            'New Passenger 👤',
            f'{pax["name"]} booked a seat on your ride to {ride["to_location"]}.',
            'booking'
        )
    return jsonify({'success': True})
@app.route('/api/rides/driver-arrived', methods=['POST'])
@login_required
def api_driver_arrived():
    ride_id = request.json.get('ride_id')
    uid     = session['user_id']
    with get_db() as conn:
        ride = conn.execute("SELECT * FROM rides WHERE id=?", (ride_id,)).fetchone()
        if not ride:
            return jsonify({'success': False, 'message': 'Ride not found'})
        if ride['driver_id'] != uid:
            return jsonify({'success': False, 'message': 'Unauthorized'})
        if ride['status'] not in ('active', 'waiting'):
            return jsonify({'success': False, 'message': 'Ride is not in an active state'})

        conn.execute("UPDATE rides SET status='driver_arrived' WHERE id=?", (ride_id,))
        passengers = conn.execute(
            "SELECT b.passenger_id FROM bookings b WHERE b.ride_id=? AND b.status='confirmed'",
            (ride_id,)
        ).fetchall()
        for p in passengers:
            push_notification(conn, p['passenger_id'], ride_id,
                'Driver Has Arrived! 🚗',
                f'Your driver has arrived at {ride["from_location"]}. Please head to the pickup point now!',
                'driver_arrived'
            )

    return jsonify({'success': True, 'notified': len(passengers)})

@app.route('/api/rides/complete', methods=['POST'])
@login_required
def api_complete_ride():
    ride_id = request.json.get('ride_id')
    uid     = session['user_id']
    with get_db() as conn:
        ride = conn.execute("SELECT * FROM rides WHERE id=?", (ride_id,)).fetchone()
        if not ride:
            return jsonify({'success': False, 'message': 'Ride not found'})
        if ride['driver_id'] != uid:
            return jsonify({'success': False, 'message': 'Unauthorized: only the driver can complete this ride'})
        if ride['status'] == 'completed':
            return jsonify({'success': False, 'message': 'Ride is already completed'})

        conn.execute("UPDATE rides SET status='completed' WHERE id=?", (ride_id,))
        conn.execute(
            "UPDATE bookings SET status='completed' WHERE ride_id=? AND status='confirmed'",
            (ride_id,)
        )

        passengers = conn.execute(
            "SELECT b.passenger_id FROM bookings b WHERE b.ride_id=?", (ride_id,)
        ).fetchall()
        for p in passengers:
            push_notification(conn, p['passenger_id'], ride_id,
                'Ride Completed! ✅',
                f'Your ride from {ride["from_location"]} to {ride["to_location"]} has been completed. '
                f'Thank you for riding with CampusRide!',
                'completed'
            )
        push_notification(conn, uid, ride_id,
            'Ride Completed! 🏁',
            f'Your ride {ride["from_location"]} → {ride["to_location"]} has been marked as complete. Great drive!',
            'completed'
        )

    return jsonify({'success': True, 'notified': len(passengers)})
@app.route('/api/my-rides')
@login_required
def api_my_rides():
    uid = session['user_id']
    with get_db() as conn:
        offered = conn.execute("""
            SELECT r.*,
                   (SELECT COUNT(*) FROM bookings b WHERE b.ride_id=r.id AND b.status IN ('confirmed','completed')) AS bookings_count
            FROM rides r WHERE r.driver_id=? ORDER BY r.created_at DESC
        """, (uid,)).fetchall()

        booked_raw = conn.execute("""
            SELECT r.*, u.name AS driver_name
            FROM bookings bk
            JOIN rides r ON r.id = bk.ride_id
            JOIN users u ON u.id = r.driver_id
            WHERE bk.passenger_id=?
            ORDER BY bk.booked_at DESC
        """, (uid,)).fetchall()

    return jsonify({
        'offered': [{
            'id':              r['id'],
            'from_location':   r['from_location'],
            'to_location':     r['to_location'],
            'departure_time':  r['departure_time'],
            'seats_total':     r['seats_total'],
            'seats_available': r['seats_available'],
            'fare':            r['fare'],
            'status':          r['status'] or 'active',
            'bookings_count':  r['bookings_count'],
        } for r in offered],
        'booked': [{
            'id':            r['id'],
            'from_location': r['from_location'],
            'to_location':   r['to_location'],
            'departure_time':r['departure_time'],
            'fare':          r['fare'],
            'status':        r['status'] or 'active',
            'driver_name':   r['driver_name'],
        } for r in booked_raw],
    })
@app.route('/api/notifications')
@login_required
def api_notifications():
    uid = session['user_id']
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
            (uid,)
        ).fetchall()

    result = []
    for r in rows:
        try:
            title = r['title'] or _default_title(r['type'])
        except (IndexError, KeyError):
            title = _default_title(r['type'])
        result.append({
            'id':         r['id'],
            'ride_id':    r['ride_id'],
            'title':      title,
            'message':    r['message'],
            'type':       r['type'],
            'is_read':    bool(r['is_read']),
            'created_at': r['created_at'],
        })
    return jsonify(result)

def _default_title(ntype):
    return {
        'driver_arrived': 'Driver Has Arrived! 🚗',
        'completed':      'Ride Completed ✅',
        'booking':        'Booking Confirmed 🎫',
    }.get(ntype, 'Notification')

@app.route('/api/notifications/unread-count')
@login_required
def api_unread_count():
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",
            (session['user_id'],)
        ).fetchone()[0]
    return jsonify({'count': count})

@app.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def api_mark_read():
    d   = request.json or {}
    uid = session['user_id']
    with get_db() as conn:
        if d.get('id'):
            conn.execute(
                "UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?",
                (d['id'], uid)
            )
        else:
            conn.execute(
                "UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,)
            )
    return jsonify({'success': True})

@app.route('/api/notifications/clear', methods=['POST'])
@login_required
def api_clear_notifs():
    with get_db() as conn:
        conn.execute("DELETE FROM notifications WHERE user_id=?", (session['user_id'],))
    return jsonify({'success': True})
@app.route('/api/ml/predict-demand')
@login_required
def api_predict_demand():
    with get_db() as conn:

        # 1. Hourly booking distribution — normalise datetime format first
        # departure_time can be '2026-04-26T19:33' or '2025-01-15 09:00'
        # Replace 'T' with ' ' so strftime parses both correctly
        # Filter to campus hours 6-22 only
        hourly = conn.execute("""
            SELECT CAST(strftime('%H', replace(r.departure_time,'T',' ')) AS INTEGER) AS hour,
                   COUNT(b.id) AS cnt
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            GROUP BY hour
            HAVING hour BETWEEN 6 AND 22
        """).fetchall()
        hour_map = {row['hour']: row['cnt'] for row in hourly}
        hours    = list(range(6, 23))
        demand   = [hour_map.get(h, 0) for h in hours]

        # 2. Peak hour
        peak_val = max(demand) if any(demand) else 0
        peak_h   = hours[demand.index(peak_val)] if peak_val > 0 else 8

        # 3. Popular routes — LOWER() fixes case sensitivity so
        #    'Admin Block → Airport' and 'admin block → Airport' merge into one
        popular_routes = conn.execute("""
            SELECT LOWER(r.from_location) || ' → ' || LOWER(r.to_location) AS route,
                   COUNT(b.id) AS count,
                   strftime('%H:%M', replace(r.departure_time,'T',' ')) AS peak
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            GROUP BY LOWER(r.from_location), LOWER(r.to_location)
            ORDER BY count DESC
            LIMIT 6
        """).fetchall()

        # 4. Busiest day of week
        busiest_day = conn.execute("""
            SELECT CASE strftime('%w', replace(r.departure_time,'T',' '))
                   WHEN '0' THEN 'Sunday'    WHEN '1' THEN 'Monday'
                   WHEN '2' THEN 'Tuesday'   WHEN '3' THEN 'Wednesday'
                   WHEN '4' THEN 'Thursday'  WHEN '5' THEN 'Friday'
                   ELSE 'Saturday' END AS day,
                   COUNT(*) AS cnt
            FROM rides r
            GROUP BY day ORDER BY cnt DESC LIMIT 1
        """).fetchone()

        # 5. Average fare
        avg_fare = conn.execute(
            "SELECT ROUND(AVG(fare), 2) AS avg FROM rides WHERE fare > 0"
        ).fetchone()['avg'] or 0

        # 6. Seat utilisation %
        util = conn.execute("""
            SELECT ROUND(
                100.0 * SUM(seats_total - seats_available) / NULLIF(SUM(seats_total), 0)
            , 1) AS pct FROM rides
        """).fetchone()['pct'] or 0

        # 7. Completed rides
        completed = conn.execute(
            "SELECT COUNT(*) FROM rides WHERE status='completed'"
        ).fetchone()[0]

        # 8. Active rides now
        active_now = conn.execute(
            "SELECT COUNT(*) FROM rides WHERE status='active'"
        ).fetchone()[0]

        # 9. New users this week
        new_users = conn.execute("""
            SELECT COUNT(*) FROM users
            WHERE created_at >= datetime('now', '-7 days')
        """).fetchone()[0]

        # 10. Recommendation
        if peak_val == 0:
            recommendation = "No bookings yet — be the first to offer a ride!"
        else:
            recommendation = (
                f"Peak demand is at {peak_h}:00 with {peak_val} bookings. "
                f"Post your ride 30 mins before for best visibility!"
            )

    return jsonify({
        'hours':            [f'{h}:00' for h in hours],
        'demand':           demand,
        'peak_hour':        f'{peak_h}:00',
        'recommendation':   recommendation,
        'popular_routes':   [dict(r) for r in popular_routes],
        'avg_fare':         avg_fare,
        'seat_utilisation': util,
        'completed_rides':  completed,
        'active_now':       active_now,
        'new_users_week':   new_users,
        'busiest_day':      busiest_day['day'] if busiest_day else 'N/A',
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000, host='0.0.0.0')
