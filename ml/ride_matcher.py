import numpy as np
from datetime import datetime
class RideMatcher:
    def __init__(self):
        self.location_coords = {
            "main gate": (0, 0), "hostel block a": (0.5, 0.3),
            "hostel block b": (0.6, 0.4), "admin block": (1.0, 0.5),
            "library": (1.2, 0.8), "canteen": (0.8, 0.6),
            "tech park": (3.0, 2.0), "city centre mall": (4.0, 3.0),
            "railway station": (5.0, 4.0), "airport": (10.0, 8.0),
            "bus stand": (4.5, 3.5), "medical college": (2.0, 1.5),
            "engineering block": (1.5, 1.0), "science block": (1.8, 1.2),
            "sports complex": (2.5, 0.5),
        }
    def _tokenize(self, text: str) -> set:
        return set(text.lower().replace(",", " ").split())

    def _similarity(self, query: str, target: str) -> float:
        if not query or not target:
            return 0.5
        q = self._tokenize(query)
        t = self._tokenize(target)
        if not q or not t:
            return 0.5
        jaccard = len(q & t) / len(q | t) if (q | t) else 0
        bonus = 0.3 if query.lower() in target.lower() or target.lower() in query.lower() else 0
        return min(1.0, jaccard + bonus)

    def _time_score(self, departure_time: str, query_date: str) -> float:
        if not query_date:
            return 0.5
        try:
            diff = abs((datetime.strptime(departure_time[:10], "%Y-%m-%d") -
                        datetime.strptime(query_date[:10], "%Y-%m-%d")).days)
            return max(0.0, 1.0 - diff * 0.2)
        except Exception:
            return 0.5

    def _availability_score(self, available: int, total: int) -> float:
        if total == 0:
            return 0
        return available / total * 0.8 + 0.2

    def rank_rides(self, rides: list, from_loc: str, to_loc: str, date: str = "") -> list:
        for ride in rides:
            from_s  = self._similarity(from_loc, ride.get("from_location", ""))
            to_s    = self._similarity(to_loc,   ride.get("to_location",   ""))
            time_s  = self._time_score(ride.get("departure_time", ""), date)
            avail_s = self._availability_score(ride.get("seats_available", 0), ride.get("seats_total", 1))
            rating  = (ride.get("avg_rating") or 3.5) / 5.0
            ride["match_score"] = round((0.35*from_s + 0.35*to_s + 0.15*time_s + 0.10*avail_s + 0.05*rating) * 100, 1)
        rides.sort(key=lambda x: x["match_score"], reverse=True)
        return rides

    def predict_demand(self) -> dict:
        np.random.seed(42)
        hours  = list(range(6, 23))
        base   = np.array([2,5,8,10,7,4,3,3,4,6,9,12,10,7,4,3,2])
        demand = (base + np.random.randint(-1, 2, len(hours))).clip(0).tolist()
        popular_routes = [
            {"route": "Hostel → Main Gate",           "count": 45, "peak": "8:00 AM"},
            {"route": "Campus → Railway Station",     "count": 38, "peak": "6:00 PM"},
            {"route": "Main Gate → Tech Park",        "count": 32, "peak": "9:00 AM"},
            {"route": "Library → Bus Stand",          "count": 28, "peak": "5:00 PM"},
            {"route": "Admin Block → Airport",        "count": 15, "peak": "10:00 AM"},
        ]
        return {
            "hours": [f"{h}:00" for h in hours],
            "demand": demand,
            "popular_routes": popular_routes,
            "peak_hour": "8:00 AM",
            "recommendation": "High demand expected tomorrow morning (8–10 AM). Consider offering rides!",
        }