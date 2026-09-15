import requests
import threading
import time

class DataReceiverRetrievalAgent:
    def __init__(self):
        # Define the insurance company API endpoints (now pointing to our combined app on port 5000)
        self.endpoints = [
            ("Tawuniya", "http://localhost:5000/api/taawuniya/get_offers"),
            ("Takaful Al-Rajhi", "http://localhost:5000/api/takaful_alrajhi/get_offers"),
            ("Medgulf", "http://localhost:5000/api/medgulf/get_offers"),
            ("ACIG", "http://localhost:5000/api/acig/get_offers")
        ]

    def fetch_from_endpoint(self, company, url, payload, results_list, index):
        """Fetch offers from a single endpoint and store in results_list at index."""
        try:
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                offers = response.json()  # Expecting a list of offers
                # Ensure each offer has company field (our mocks already do)
                results_list[index] = offers
            else:
                print(f"Error from {company}: HTTP {response.status_code}")
                results_list[index] = []
        except Exception as e:
            print(f"Exception fetching from {company}: {e}")
            results_list[index] = []

    def get_unified_quote_set(self, customer_data):
        """
        Step 1: Receive authenticated customer's data.
        Step 2: Validate and structure inputs (we assume data is already validated).
        Step 3: Build API request payload for each insurer.
        Step 4: Send requests to insurer APIs in parallel.
        Step 5: Receive live JSON responses.
        Step 6: Normalize and merge responses into one unified quote set.
        Step 7: Pass unified quote set to Agent 2.
        """
        # In a real system, we would validate customer_data here.
        # For simplicity, we assume it contains: vehicle_value, driver_age, etc.
        payload = customer_data  # Our mock APIs expect JSON with vehicle_value, driver_age, etc.

        # Prepare to collect results from each endpoint
        results = [None] * len(self.endpoints)
        threads = []

        # Start a thread for each endpoint
        for i, (company, url) in enumerate(self.endpoints):
            thread = threading.Thread(target=self.fetch_from_endpoint, args=(company, url, payload, results, i))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Flatten the list of lists into a single list of offers
        unified_quotes = []
        for company_offers in results:
            if company_offers:
                unified_quotes.extend(company_offers)

        # Optionally, we could do additional normalization here (e.g., ensure all offers have same fields)
        # But our mocks already return consistent fields.

        return unified_quotes

# Example usage (for testing)
if __name__ == "__main__":
    # Example customer data
    customer_data = {
        "vehicle_value": 70000,
        "driver_age": 35,
        # Add other fields as needed by the mock APIs
    }

    agent1 = DataReceiverRetrievalAgent()
    quotes = agent1.get_unified_quote_set(customer_data)
    print("Unified Quote Set:")
    for q in quotes:
        print(q)