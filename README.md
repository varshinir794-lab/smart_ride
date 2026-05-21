# 🚗 CampusRide – Smart Campus Ride Sharing

## Features
- **Auth**: Login/Register with hashed passwords (SHA-256), session management
- **Ride Management**: Offer rides, search rides, book seats in real-time
- **AI/ML Matching**: Jaccard similarity-based ride matching with multi-factor scoring
- **Demand Forecasting**: ML model predicts hourly ride demand patterns
- **Database**: SQLite with Users, Rides, Bookings, Ratings tables
- **Role-based**: Student & Staff accounts with badges

## Quick Start

```bash
# 1. Install dependencies
pip install flask scikit-learn numpy werkzeug

# 2. Run the app
python3 app.py

# 3. Open browser
http://localhost:5000
```

## Demo Accounts
| Role    | Email                  | Password |
|---------|------------------------|----------|
| Student | arjun@campus.edu       | pass123  |
| Staff   | ramesh@campus.edu      | pass123  |
| Student | priya@campus.edu       | pass123  |

## Tech Stack
- **Frontend**: HTML5, CSS3 (dark futuristic theme), Vanilla JS
- **Backend**: Python Flask (REST API)
- **Database**: SQLite3 (auto-created on first run)
- **ML**: Jaccard similarity matching + demand forecasting (NumPy)

## Project Structure
```
campus_ride/
├── app.py               # Flask backend + routes
├── ml/
│   └── ride_matcher.py  # ML matching & demand prediction
├── templates/
│   ├── login.html       # Auth page
│   └── dashboard.html   # Main app dashboard
├── campus_ride.db       # Auto-created SQLite DB
└── requirements.txt

