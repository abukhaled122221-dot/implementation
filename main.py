import time
import threading
from flask import Flask
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from taawuniya import app as taawuniya_app
from takaful_alrajhi import app as takaful_alrajhi_app
from medgulf import app as medgulf_app
from acig import app as acig_app
from agent1 import DataReceiverRetrievalAgent
from agent2 import RecommendationAgent
from agent3 import ExplainerAgent

def run_flask_app(app, port):
    """Run a Flask app on a given port (for use in a thread)."""
    app.run(port=port, debug=False, use_reloader=False)

def start_mock_apis():
    """Start all mock insurance API servers in background threads."""
    apis = [
        (taawuniya_app, 5001),
        (takaful_alrajhi_app, 5002),
        (medgulf_app, 5003),
        (acig_app, 5004)
    ]
    threads = []
    for app, port in apis:
        thread = threading.Thread(target=run_flask_app, args=(app, port), daemon=True)
        thread.start()
        threads.append(thread)
        print(f"Started mock API for {app.name} on port {port}")
    # Give servers a moment to start
    time.sleep(2)
    return threads

def get_user_input():
    """Prompt user for car and driver data."""
    print("=== إدخال بيانات السيارة والسائق ===")
    try:
        vehicle_value = float(input("قيمة السيارة (بالريال): "))
        driver_age = int(input("عمر السائق: "))
        # Optional: purpose of use, vehicle age, etc. We'll keep simple.
        purpose = input("غرض الاستخدام (شخصي/عمل/كلي) [افتراضي: شخصي]: ").strip()
        if not purpose:
            purpose = "شخصي"
        vehicle_age = input("عمر السيارة (بالسنوات) [افتراضي: 5]: ").strip()
        vehicle_age = int(vehicle_age) if vehicle_age else 5
    except ValueError:
        print("القيمة غير صحيحة، سيتم استخدام القيم الافتراضية.")
        vehicle_value = 70000
        driver_age = 35
        purpose = "شخصي"
        vehicle_age = 5
    return {
        "vehicle_value": vehicle_value,
        "driver_age": driver_age,
        "purpose_of_use": purpose,
        "vehicle_age": vehicle_age
    }

def main():
    print("بدء نظام توصية تأمين السيارات THIQA (прототип)")
    print("تشغيل محاكيات واجهات API لشركات التأمين...")
    api_threads = start_mock_apis()

    try:
        while True:
            print("\n" + "="*50)
            customer_data = get_user_input()
            print("\nجاري معالجة الطلب...")

            # Agent 1: Data Receiver and Retrieval Agent
            agent1 = DataReceiverRetrievalAgent()
            unified_quotes = agent1.get_unified_quote_set(customer_data)
            if not unified_quotes:
                print("لم يتم استلام أي عروض من شركات التأمين. يرجى المحاولة مرة أخرى.")
                continue
            print(f"تم استلام {len(unified_quotes)} عرض من شركات التأمين.")

            # Agent 2: Recommendation Agent
            agent2 = RecommendationAgent()
            recommended_quote, breakdown = agent2.recommend(unified_quotes, customer_data)
            if not recommended_quote:
                print("لم تتمكن من تقديم توصية.")
                continue

            # Prepare scored quotes for Agent 3 (need list of dicts with 'quote' and 'score')
            # We'll reuse agent2's compute_scores to get scored list
            scored_list = agent2.compute_scores(unified_quotes, customer_data)

            # Agent 3: Explainer Agent
            agent3 = ExplainerAgent()
            explanation = agent3.explain(recommended_quote, breakdown, scored_list)

            print("\n" + "="*50)
            print(explanation)
            print("="*50)

            # Ask if user wants another recommendation
            again = input("\nهل ترغب في تجربة توصية أخرى؟ (نعم/لا) [لا]: ").strip()
            if again.lower() not in ['نعم', 'yes', 'y']:
                break
    except KeyboardInterrupt:
        print("\nتم إيقاف البرنامج بواسطة المستخدم.")
    finally:
        print("\nإيقاف محاكيات واجهات API...")
        # Since we used daemon threads, they will be killed when main exits.
        # We'll just exit.
        print("شكرًا لاستخدام نظام THIQA.")

if __name__ == "__main__":
    main()