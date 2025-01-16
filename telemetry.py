import requests
import time
import threading
import argparse
import re

class TelemetryClient:
    def __init__(self, username, password, interval=10):
        """
        Initializes the Telemetry Client.

        :param username: FreeRice username
        :param password: FreeRice password
        :param interval: Time interval in seconds between telemetry reports
        """
        self.username = username
        self.password = password
        self.interval = interval
        self.session = None
        self.token = None
        self.user_uuid = None
        self.initial_rice_total = 0
        self.prev_rice_total = 0
        self.total_rice_gained = 0
        self.start_time = None  # To track when rice tracking started
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

    def freerice_login(self):
        """
        Logs into FreeRice and retrieves session information along with initial rice total.
        """
        session = requests.Session()
        login_url = "https://accounts.freerice.com/auth/login?_format=json"
        
        payload = {
            "username": self.username,
            "password": self.password
        }

        headers = {
            "content-type": "application/json",
            "accept": "application/json;version=2",
            "origin": "https://play.freerice.com",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }

        try:
            response = session.post(login_url, json=payload, headers=headers)
            if response.status_code == 200:
                response_data = response.json()
                print("Telemetry Login succeeded.")
                
                self.token = response_data.get("token")
                self.user_uuid = response_data.get("uuid")
                user_data = response_data.get("userData", {})
                username_logged = user_data.get('username')

 

                
                print(f"Logged in as: {username_logged}")

                
                self.session = session
                self.start_time = time.time()  # Start tracking time after login

                           # Retrieve 'user_rice_total' from userData
                self.initial_rice_total = self.fetch_current_rice_total()

                if self.initial_rice_total is None:
                    print("Error: 'user_rice_total' is missing or None in login response.")
                    return False

                if not isinstance(self.initial_rice_total, int):
                    print(f"Error: 'user_rice_total' is of type {type(self.initial_rice_total)}, expected int.")
                    return False
                print(f"Initial Rice Total: {self.initial_rice_total}")
                self.prev_rice_total = self.initial_rice_total
                return True
            else:
                print("Telemetry Login failed.")
                print("Status code:", response.status_code)
                print("Response text:", response.text)
                return False
        except Exception as e:
            print(f"Exception during telemetry login: {str(e)}")
            return False

    def fetch_current_rice_total(self):
        """
        Fetches the current user rice total from the game endpoint.
        """
        game_url = "https://engine.freerice.com/games/232b86f5-d908-4327-9a33-dec59f9f661f"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }

        try:
            response = self.session.get(game_url, headers=headers)
            if response.status_code == 200:
                game_data = response.json()
                # Safely extract 'user_rice_total'
                data = game_data.get('data', {})
                attributes = data.get('attributes', {})
                user_rice_total = attributes.get('user_rice_total')

                if user_rice_total is None:
                    print("Error: 'user_rice_total' is missing or None in game data.")
                    return 0  # Default to 0 to prevent NoneType errors

                if not isinstance(user_rice_total, int):
                    print(f"Error: 'user_rice_total' is of type {type(user_rice_total)}, expected int.")
                    return 0

                return user_rice_total
            else:
                print("Telemetry failed to fetch game data.")
                print("Status code:", response.status_code)
                return 0
        except Exception as e:
            print(f"Exception during fetching game data: {str(e)}")
            return 0

    def calculate_effective_rates(self, delta_rice, elapsed_time):
        """
        Calculates effective RPS, RPM, RPH based on rice gained.

        :param delta_rice: Rice gained since last check
        :param elapsed_time: Elapsed time in seconds since tracking started
        :return: Tuple (effective_rps, effective_rpm, effective_rph)
        """
        effective_requests = delta_rice / 10  # Each request corresponds to 10 rice
        if elapsed_time > 0:
            effective_rps = effective_requests / elapsed_time
            effective_rpm = effective_rps * 60
            effective_rph = effective_rps * 3600
            return effective_rps, effective_rpm, effective_rph
        else:
            return 0, 0, 0

    def telemetry_loop(self):
        """
        The main loop that fetches rice total and prints telemetry data.
        """
        while not self.stop_event.is_set():
            current_time = time.time()
            if self.start_time is None:
                # If start_time hasn't been set yet, set it now
                self.start_time = current_time

            elapsed_time = current_time - self.start_time

            fetch_rice = self.fetch_current_rice_total()
            if fetch_rice == 0:
                delta = 0
            else:
                delta = fetch_rice - self.prev_rice_total

            if fetch_rice is not None:

                with self.lock:
                    self.total_rice_gained += delta

                if delta > 0:
                    self.prev_rice_total = fetch_rice

                # Calculate overall effective rates
                with self.lock:
                    overall_effective_rps = (self.total_rice_gained / 10) / elapsed_time if elapsed_time > 0 else 0
                    overall_effective_rpm = overall_effective_rps * 60
                    overall_effective_rph = overall_effective_rps * 3600

                print(
                    f"Telemetry Report - "
                    f"Run Time: {int(elapsed_time)}s | "
                    f"Delta Rice: {delta} | "
                    f"Total Rice Gained: {self.total_rice_gained} | "
                    f"Effective RPS: {overall_effective_rps:.2f} | "
                    f"Effective RPM: {overall_effective_rpm:.2f} | "
                    f"Effective RPH: {overall_effective_rph:.2f}"
                )
            else:
                print("Telemetry could not retrieve current rice total.")

            # Wait for the specified interval
            self.stop_event.wait(self.interval)

    def start(self):
        """
        Starts the telemetry client.
        """
        if not self.freerice_login():
            print("Telemetry client failed to log in. Exiting.")
            return

        telemetry_thread = threading.Thread(target=self.telemetry_loop, daemon=True)
        telemetry_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nTelemetry client stopping...")
            self.stop_event.set()
            telemetry_thread.join()
            print("Telemetry client stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='FreeRice Telemetry Client')
    parser.add_argument('-u', '--username', default='mikoyae', help='FreeRice username')
    parser.add_argument('-p', '--password', default='lovemarchseventh', help='FreeRice password')
    parser.add_argument('-i', '--interval', type=int, default=10, help='Telemetry report interval in seconds')
    args = parser.parse_args()

    telemetry_client = TelemetryClient(username=args.username, password=args.password, interval=args.interval)
    telemetry_client.start()