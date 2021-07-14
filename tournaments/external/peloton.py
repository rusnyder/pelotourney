from datetime import datetime
from typing import List

import requests
import structlog
from requests.cookies import RequestsCookieJar

logger = structlog.get_logger(__name__)


class BadCredentials(Exception):
    """Raised to indicate the provided Peloton username/password was invalid"""

    pass


class NotAuthenticated(Exception):
    """Raised to indicate the PelotonProfile does not have an active, valid session id."""

    def __init__(self, username: str):
        self.username = username
        self.message = "Peloton user does not have an active session"
        super().__init__(self.message)

    def __str__(self):
        return f"{self.username} -> {self.message}"


class PelotonClient(requests.Session):
    SESSION_COOKIE = "peloton_session_id"
    COOKIE_DOMAIN = ".onepeloton.com"

    def __init__(
        self, base_url: str = "https://api.onepeloton.com/", username: str = None
    ):
        self.base_url = base_url
        self.username = username
        super().__init__()

    def login(self, *, username: str = None, password: str):
        username = username or self.username
        if not username:
            raise Exception("Cannot login without a username")
        logger.info("Logging into Peloton API", username=username)
        resp = self.post(
            "/auth/login",
            json={"username_or_email": username, "password": password},
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            raise BadCredentials()
        return resp.json()

    def load_session(self, session_id: str):
        cookie_jar = RequestsCookieJar()
        cookie_jar.set(self.SESSION_COOKIE, session_id, domain=self.COOKIE_DOMAIN)
        resp = self.get("/auth/check_session", cookies=cookie_jar)
        if resp.status_code < 400 and resp.json().get("is_valid", False):
            self.cookies.set(self.SESSION_COOKIE, session_id, domain=self.COOKIE_DOMAIN)
            if self.username is None:
                self.username = resp.json().get("user", {}).get("username")
        else:
            raise NotAuthenticated(username=self.username)

    def request(self, method, url, *args, **kwargs) -> requests.Response:
        url = self.base_url.rstrip("/") + "/" + url.lstrip("/")
        return super().request(method, url, *args, **kwargs)

    def get_json(self, url, **kwargs):
        resp = self.get(url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_workouts(
        self,
        user_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
        ride_ids: List[str] = None,
    ) -> List[dict]:
        limit = 20
        page = 0
        workouts = []
        while True:
            logger.info(
                "Fetching page of workouts", user_id=user_id, page=page, limit=limit
            )
            data = self.get_json(
                f"/api/user/{user_id}/workouts",
                params={"limit": limit, "page": page, "joins": "ride"},
            )
            for workout in data["data"]:
                keep = True
                # Filter workouts outside the requested range
                if start_date or end_date:
                    workout_ts = float(workout["created_at"])
                    if start_date and (workout_ts < start_date.timestamp()):
                        keep = False
                    if end_date and (workout_ts > end_date.timestamp()):
                        keep = False
                # Filter workouts not matching the requested ride ids
                if ride_ids and workout["ride"]["id"] not in ride_ids:
                    keep = False
                # Only record workouts meeting all search criteria
                if keep:
                    workouts.append(workout)

            # If end date is provided and the earliest workout doesn't yet exceed it,
            # grab another page (reverse chronological) and repeat
            if start_date and data["data"]:
                earliest_workout_ts = data["data"][-1]["created_at"]
                logger.info(
                    "Comparing timestamps",
                    start_date=start_date,
                    earliest_workout=datetime.utcfromtimestamp(earliest_workout_ts),
                )
                if earliest_workout_ts > start_date.timestamp():
                    logger.info("Grabbing next page")
                    page += 1
                else:
                    logger.info("All good")
                    break
            else:
                break
        return workouts

    def get_rides(self, ride_ids: List[str]):
        return [self.get_json(f"/api/ride/{ride_id}") for ride_id in ride_ids]

    def search_users(self, user_query: str, limit: int = 40) -> List[dict]:
        data = self.get_json(
            "/api/user/search",
            params={"user_query": user_query, "limit": limit},
        )
        return data["data"]
