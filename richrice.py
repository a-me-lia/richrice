import requests
import time
import random
from threading import Thread
from queue import Queue
import threading

def freerice_login(username, password):
    # Create a session to preserve cookies and other session data across requests
    session = requests.Session()

    # The POST endpoint from your Network tab:
    login_url = "https://accounts.freerice.com/auth/login?_format=json"
    
    # JSON body (adjust field names if needed).
    # In many Drupal setups, the expected fields are "name" and "pass",
    # but verify these from the actual request payload you see in DevTools.
    payload = {
        "username": username,
        "password": password
    }

    # Headers. Include what you see in DevTools (User-Agent, Origin, Accept, etc.)
    headers = {
        "content-type": "application/json",
        "accept": "application/json;version=2",
        "origin": "https://play.freerice.com",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        # Add any other headers from the Network tab if necessary:
        # "sec-ch-ua": "\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
        # ...
    }

    response = session.post(login_url, json=payload, headers=headers)
    

    base_delay = 1  # Start with 1 second delay
    retry_count = 0
    while True:
        if response.status_code == 200:
            response_data = response.json()
            print("Login request succeeded.")
            print("Response JSON:", response_data)
            
            token = response_data.get("token")
            user_uuid = response_data.get("uuid")   # <- The UUID from response
            
            # Optionally extract userData or other fields as well
            user_data = response_data.get("userData", {})
            print(f"Logged in as: {user_data.get('username')}")
            
            # Now return all three
            return session, user_uuid, token
        else:
            retry_count += 1
            delay = base_delay * (2 ** (retry_count - 1))  # Exponential backoff
            print(f"Login request failed. Attempt {retry_count}")
            print("Status code:", response.status_code)
            print("Response text:", response.text)
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)
            
            # Retry the request
            response = session.post(login_url, json=payload, headers=headers)
    

    return None, None, None
            

def simulate_answer(session, token, submit_response=None):
    game_url = "https://engine.freerice.com/games/232b86f5-d908-4327-9a33-dec59f9f661f"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Cache-Control": "max-age=0",
        "Cookie": "_ga=GA1.1.110237357.1733952427; _ga_SL4745ZT9E=GS1.1.1736737001.19.1.1736739361.1.0.0",
        "Priority": "u=0, i",
        "sec-ch-ua": "\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    if not submit_response:
        # Fetch the current game data from the specified URL

        response = session.get(game_url, headers=headers)
        if response.status_code != 200:
            print("Failed to fetch game data.")
            return None
        game_data = response.json()
    else:
        game_data = submit_response.json()

    # Extract the question text
    question_text = game_data['data']['attributes']['question']['text']

    # Use regex to extract numbers for multiplication
    match = re.match(r'(\d+)\s*x\s*(\d+)', question_text)
    if not match:
        print("Failed to parse question.")
        return None
    num1, num2 = int(match.group(1)), int(match.group(2))
    answer = num1 * num2

    # Find the option ID corresponding to the correct answer
    options = game_data['data']['attributes']['question']['options']
    correct_option = next((opt for opt in options if int(opt['text']) == answer), None)
    if not correct_option:
        print("Correct option not found.")
        return None
    answer_id = correct_option['id']

    # Submit the answer using PATCH method
    submit_url = f"https://engine.freerice.com/games/{game_data['data']['id']}/answer"
    payload = {"answer": answer_id}

    submit_response = session.patch(submit_url, json=payload, headers=headers)
    if submit_response.status_code != 200:
        print(f"Failed to submit answer. Status code: {submit_response.status_code}")
        return None

    return submit_response


def answer_multiple(n, freerice_session, token):
    previous_response = None
    start_time = time.time()
    request_count = 0
    successful_requests = 0

    for i in range(1, n + 1):
        retry_delay = 1
        while True:
            try:
                previous_response = simulate_answer(freerice_session, token, previous_response)
                request_count += 1
                
                if previous_response is not None and previous_response.status_code == 200:
                    successful_requests += 1
                    break
                    
                print(f"\nRequest failed at question {i}")
                if previous_response is not None:
                    print(f"Status code: {previous_response.status_code}")
                
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
                previous_response = None
            except Exception as e:
                print(f"Error occurred: {str(e)}")
                time.sleep(retry_delay)
                retry_delay *= 2
                previous_response = None

        if i % 100 == 0:
            total_elapsed = time.time() - start_time
            if total_elapsed > 0:
                requests_per_second = request_count / total_elapsed
                requests_per_minute = requests_per_second * 60
                requests_per_hour = requests_per_second * 3600
                print(
                    f"\rRequest {i}/{n} | "
                    f"Successful: {successful_requests} | "
                    f"Requests/sec: {requests_per_second:.2f} | "
                    f"Requests/min: {requests_per_minute:.2f} | "
                    f"Requests/hr: {requests_per_hour:.2f}"
                )

    # Final statistics print after the loop completes
    total_time = time.time() - start_time
    if total_time > 0:
        requests_per_second = request_count / total_time
        requests_per_minute = requests_per_second * 60
        requests_per_hour = requests_per_second * 3600
        print(
            f"\nFinal Stats - Requests/sec: {requests_per_second:.2f} | "
            f"Requests/min: {requests_per_minute:.2f} | "
            f"Requests/hr: {requests_per_hour:.2f}"
        )
    else:
        print("\nTotal time is zero, cannot calculate rates.")

    return successful_requests

# Add this new class to track thread statistics
class ThreadStats:
    def __init__(self):
        self.lock = threading.Lock()
        self.total_successful = 0
        self.start_time = time.time()
        
    def increment_success(self, count=1):
        with self.lock:
            self.total_successful += count
            
    def get_stats(self):
        total_time = time.time() - self.start_time
        if total_time > 0:
            requests_per_second = self.total_successful / total_time
            requests_per_minute = requests_per_second * 60
            requests_per_hour = requests_per_second * 3600
            return {
                'successful': self.total_successful,
                'rps': requests_per_second,
                'rpm': requests_per_minute,
                'rph': requests_per_hour
            }
        return None

if __name__ == "__main__":

    import re
    import argparse

    parser = argparse.ArgumentParser(description='Run FreeRice automation')
    parser.add_argument('-u', '--username', default='mikoyae', help='FreeRice username')
    parser.add_argument('-p', '--password', default='lovemarchseventh', help='FreeRice password')
    parser.add_argument('-n', '--num-requests', type=int, default=1000, help='Number of requests to make')
    # Add thread count argument
    parser.add_argument('-t', '--threads', type=int, default=1, help='Number of threads to use')
    args = parser.parse_args()


    
    # Split requests across threads
    from threading import Thread
    threads = []
    requests_per_thread = args.num_requests // args.threads
    
    # Create shared statistics object
    stats = ThreadStats()
    
    def thread_worker(thread_id):
        print(f"Thread {thread_id} starting...")
        session, uuid, token = freerice_login(args.username, args.password)
        if session and token:
            successful = answer_multiple(requests_per_thread, session, token)
            stats.increment_success(successful)
            print(f"Thread {thread_id} completed with {successful} successful requests")
        else:
            print(f"Thread {thread_id} failed to login")
    
    # Create and start threads
    for i in range(args.threads):
        thread = Thread(target=thread_worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Print final statistics
    final_stats = stats.get_stats()
    if final_stats:
        print("\nFinal Combined Statistics:")
        print(f"Total Successful Requests: {final_stats['successful']}")
        print(f"Requests/sec: {final_stats['rps']:.2f}")
        print(f"Requests/min: {final_stats['rpm']:.2f}")
        print(f"Requests/hr: {final_stats['rph']:.2f}")
