# maintenance/tests.py
from django.test import SimpleTestCase
from .utils.priority_calculator import PriorityCalculator
from .utils.sla_calculator import SLACalculator
from datetime import datetime, timedelta
from .models import RequestPriority

class PriorityCalculatorTests(SimpleTestCase):
    def test_emergency_keyword_detection(self):
        priority = PriorityCalculator.calculate_from_description("Water leak in the bathroom")
        self.assertEqual(priority, RequestPriority.EMERGENCY)

    def test_medium_default(self):
        priority = PriorityCalculator.calculate_from_description("Paint peeling on wall")
        self.assertEqual(priority, RequestPriority.MEDIUM)

class SLACalculatorTests(SimpleTestCase):
    def test_emergency_sla(self):
        now = datetime.now()
        due = SLACalculator.calculate_due_at(now, priority=RequestPriority.EMERGENCY)
        self.assertAlmostEqual((due - now).total_seconds() / 3600, 2, places=2)

    def test_breach_detection(self):
        # ✅ FIX: Make the deadline definitively 1 hour in the past
        past_due = datetime.now() - timedelta(hours=1)
        status = SLACalculator.check_status(past_due)
        self.assertTrue(status["breached"])
        self.assertGreater(status["hours_overdue"], 0)