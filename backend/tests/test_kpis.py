"""KPI threshold checks, no live database required."""
from django.test import SimpleTestCase
from analytics.queries import percent, movement

class ManuscriptKpiTest(SimpleTestCase):
    def test_growth_percent(self):
        self.assertEqual(percent(105,100),5.0)
        self.assertEqual(percent(94,100),-6.0)
        self.assertIsNone(percent(100,0))
    def test_thresholds(self):
        self.assertEqual(movement(5),'Stable')
        self.assertEqual(movement(-5),'Stable')
        self.assertEqual(movement(5.1),'Rising')
        self.assertEqual(movement(-5.1),'Falling')
