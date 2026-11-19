"""
Tests for Code Root Cause & Diagnostic Intelligence Engine
"""

import unittest
from insightx.code_analyzer import CodeDiagnosticEngine

class TestCodeDiagnosticEngine(unittest.TestCase):
    def setUp(self):
        self.engine = CodeDiagnosticEngine()

    def test_clean_code_snippet(self):
        code = """
def multiply(a: int, b: int) -> int:
    return a * b
"""
        res = self.engine.analyze_code(code, "python")
        self.assertEqual(res["status"], "HEALTHY")
        self.assertEqual(res["health_score"], 100)
        self.assertEqual(res["issues_count"], 0)
        self.assertEqual(res["top_root_cause"]["cause"], "Clean Execution — No Defects Detected")
        self.assertIn("No syntax errors", res["explanation"]["summary"])

    def test_memory_leak_detection(self):
        code = """
cache = []
def worker(item):
    cache.append(item)
"""
        res = self.engine.analyze_code(code, "python")
        self.assertEqual(res["status"], "ANOMALOUS")
        self.assertLess(res["health_score"], 100)
        self.assertGreaterEqual(res["issues_count"], 1)
        self.assertIn("Memory", res["top_root_cause"]["cause"])
        self.assertIn("deque", res["recommendations"][0]["action"])

    def test_resource_leak_detection(self):
        code = """
def fetch_data():
    conn = db.connect()
    data = conn.execute("SELECT 1")
    return data
"""
        res = self.engine.analyze_code(code, "python")
        self.assertEqual(res["status"], "ANOMALOUS")
        types = [iss["type"] for iss in res["issues"]]
        self.assertIn("UnclosedResourceLeak", types)
        self.assertIn("Context Manager", res["recommendations"][0]["action"])

    def test_zero_division_detection(self):
        code = """
def compute(x):
    return x / 0
"""
        res = self.engine.analyze_code(code, "python")
        self.assertEqual(res["status"], "ANOMALOUS")
        types = [iss["type"] for iss in res["issues"]]
        self.assertIn("ZeroDivisionError", types)

    def test_traceback_correlation(self):
        code = """
def compute(x):
    return x + "invalid"
"""
        trace = """
Traceback (most recent call last):
  File "test.py", line 2, in compute
    return x + "invalid"
TypeError: unsupported operand type(s) for +: 'int' and 'str'
"""
        res = self.engine.analyze_code(code, "python", trace)
        self.assertEqual(res["status"], "ANOMALOUS")
        self.assertIn("TypeError", res["issues"][0]["type"])

    def test_payment_regression_with_traceback(self):
        code = '''import sqlite3, threading
request_history = []
payment_lock = threading.Lock()
def process_payment(user_id, amount, audit_log=[]):
    payment_lock.acquire()
    request_history.append({'user': user_id, 'amount': amount})
    audit_log.append(user_id)
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute(f'SELECT balance FROM accounts WHERE user_id = "{user_id}"')
    row = cursor.fetchone()
    fee_ratio = 100 / amount
    payment_lock.release()
    return {'status': 'success', 'fee_ratio': fee_ratio}
process_payment('U1001', 0)'''

        trace = '''Traceback (most recent call last):
  File "payment.py", line 21, in <module>
    process_payment('U1001', 0)
  File "payment.py", line 17, in process_payment
    fee_ratio = 100 / amount
ZeroDivisionError: division by zero'''

        res = self.engine.analyze_code(code, "python", trace)
        self.assertEqual(res["status"], "ANOMALOUS")
        self.assertLessEqual(res["health_score"], 40)
        self.assertGreaterEqual(res["issues_count"], 5)

        # Confirm Rank #1 is ZeroDivisionError with confirmed runtime evidence
        top_cause = res["top_root_cause"]
        self.assertIn("ZeroDivisionError", top_cause["cause"])
        self.assertEqual(top_cause["score_type"], "Confirmed Runtime Evidence")
        self.assertEqual(top_cause["status"], "Confirmed Runtime Failure")

        # Confirm secondary static defects were also diagnosed
        issue_types = {iss["type"] for iss in res["issues"]}
        self.assertIn("MutableDefaultArgument", issue_types)
        self.assertIn("PotentialDeadlock", issue_types)
        self.assertIn("UnclosedResourceLeak", issue_types)
        self.assertIn("SQLInjectionVulnerability", issue_types)
        self.assertIn("UnboundedCollectionGrowth", issue_types)

        # Confirm verified refactored code
        self.assertTrue(res["is_verified"])
        self.assertIn("def process_payment(user_id, amount, audit_log=None):", res["refactored_code"])
        self.assertIn("with payment_lock:", res["refactored_code"])
        self.assertIn("with sqlite3.connect('payments.db') as conn:", res["refactored_code"])
        self.assertIn("amount == 0", res["refactored_code"])

    def test_payment_regression_without_traceback(self):
        code = '''import sqlite3, threading
request_history = []
payment_lock = threading.Lock()
def process_payment(user_id, amount, audit_log=[]):
    payment_lock.acquire()
    request_history.append({'user': user_id, 'amount': amount})
    audit_log.append(user_id)
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute(f'SELECT balance FROM accounts WHERE user_id = "{user_id}"')
    row = cursor.fetchone()
    fee_ratio = 100 / amount
    payment_lock.release()
    return {'status': 'success', 'fee_ratio': fee_ratio}
process_payment('U1001', 0)'''

        res = self.engine.analyze_code(code, "python", None)
        self.assertEqual(res["status"], "ANOMALOUS")
        # Must be labeled as heuristic / static analysis result, NOT confirmed runtime
        top_cause = res["top_root_cause"]
        self.assertEqual(top_cause["score_type"], "Heuristic Risk Weight")
        self.assertEqual(top_cause["status"], "Static Analysis Defect")

    def test_refactored_code_safe_execution(self):
        import sqlite3, os
        # Initialize test table in payments.db
        with sqlite3.connect("payments.db") as c:
            c.execute("CREATE TABLE IF NOT EXISTS accounts (user_id TEXT PRIMARY KEY, balance REAL)")
            c.execute("INSERT OR REPLACE INTO accounts VALUES ('U1001', 500.0)")

        code = '''import sqlite3, threading
request_history = []
payment_lock = threading.Lock()
def process_payment(user_id, amount, audit_log=[]):
    payment_lock.acquire()
    request_history.append({'user': user_id, 'amount': amount})
    audit_log.append(user_id)
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute(f'SELECT balance FROM accounts WHERE user_id = "{user_id}"')
    row = cursor.fetchone()
    fee_ratio = 100 / amount
    payment_lock.release()
    return {'status': 'success', 'fee_ratio': fee_ratio}
process_payment('U1001', 0)'''

        res = self.engine.analyze_code(code, "python")
        self.assertTrue(res["is_verified"])
        
        # Test executing the refactored code in an isolated scope
        scope = {}
        exec(res["refactored_code"], scope)
        fn = scope["process_payment"]
        out = fn("U1001", 0)
        self.assertEqual(out["status"], "error")
        self.assertEqual(out["fee_ratio"], 0.0)

        # Cleanup test db
        if os.path.exists("payments.db"):
            os.remove("payments.db")

    def test_language_detection(self):
        self.assertEqual(self.engine.detect_language("app.py"), "python")
        self.assertEqual(self.engine.detect_language("server.js"), "javascript")
        self.assertEqual(self.engine.detect_language("schema.sql"), "sql")
        self.assertEqual(self.engine.detect_language("Main.java"), "java")
        self.assertEqual(self.engine.detect_language("algo.cpp"), "cpp")

    def test_javascript_static_analysis(self):
        js_code = """
        const query = "SELECT * FROM users WHERE id = " + userId;
        db.query(query);
        eval("2 + 2");
        if (a == b) { console.log('match'); }
        """
        res = self.engine.analyze_code(js_code, "javascript")
        self.assertEqual(res["status"], "ANOMALOUS")
        types = {iss["type"] for iss in res["issues"]}
        self.assertIn("EvalInjectionHazard", types)
        self.assertIn("SQLInjectionVulnerability", types)
        self.assertIn("LooseEqualityCoercion", types)

    def test_sql_static_analysis(self):
        sql_code = """
        UPDATE users SET is_active = 0;
        SELECT * FROM large_orders_table;
        """
        res = self.engine.analyze_code(sql_code, "sql")
        self.assertEqual(res["status"], "ANOMALOUS")
        types = {iss["type"] for iss in res["issues"]}
        self.assertIn("UnboundedUpdateClause", types)
        self.assertIn("SelectStarSaturation", types)

    def test_java_static_analysis(self):
        java_code = """
        public class Service {
            public void run() {
                Connection conn = DriverManager.getConnection("url");
            }
        }
        """
        res = self.engine.analyze_code(java_code, "java")
        self.assertEqual(res["status"], "ANOMALOUS")
        types = {iss["type"] for iss in res["issues"]}
        self.assertIn("UnclosedAutoCloseableLeak", types)

    def test_cpp_static_analysis(self):
        cpp_code = """
        void process(char* input) {
            char buffer[64];
            strcpy(buffer, input);
            int x = 100 / 0;
        }
        """
        res = self.engine.analyze_code(cpp_code, "cpp")
        self.assertEqual(res["status"], "ANOMALOUS")
        types = {iss["type"] for iss in res["issues"]}
        self.assertIn("BufferOverflowHazard", types)
        self.assertIn("ZeroDivisionCrash", types)

    def test_analyze_project_zip(self):
        demo_zip = self.engine.get_demo_project_zip()
        self.assertGreater(len(demo_zip), 100)

        # Traceback indicating runtime failure in payment_service.py
        trace = """Traceback (most recent call last):
  File "main.py", line 8, in <module>
    res = dispatch_transaction("U1001", 0)
  File "services/payment_service.py", line 17, in process_payment
    fee_ratio = 100 / amount
ZeroDivisionError: division by zero"""

        res = self.engine.analyze_project_zip(demo_zip, trace, "Test Microservice Repo")
        self.assertEqual(res["status"], "ANOMALOUS")
        self.assertGreaterEqual(res["total_files_scanned"], 4)
        self.assertGreaterEqual(res["clean_files_count"], 1)  # user_model.py is clean
        self.assertGreaterEqual(res["defective_files_count"], 2)

        # Confirm Rank #1 root cause across the whole project is the ZeroDivisionError in payment_service.py
        top_cause = res["global_ranked_root_causes"][0]
        self.assertIn("ZeroDivisionError", top_cause["cause"])
        self.assertIn("payment_service.py", top_cause["file"])
        self.assertEqual(top_cause["score_type"], "Confirmed Runtime Evidence")

        # Confirm remediated zip was created
        self.assertGreater(len(res["remediated_zip_bytes"]), 100)


if __name__ == "__main__":
    unittest.main()

