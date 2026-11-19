import asyncio
import time
import sqlite3
import os

# InsightX Demonstration: Payment Service with Async Blocking & Resource Leak
transaction_history = []  # Unbounded memory accumulation

def get_database_connection():
    # Bug: Resource instantiated without context manager or guaranteed finally close
    conn = sqlite3.connect("payments.db")
    return conn

async def process_payment(user_id: int, amount: float, audit_log=[]):
    # Bug 1: Mutable default argument container
    audit_log.append({"user": user_id, "amount": amount})
    transaction_history.append({"user": user_id, "amount": amount})

    # Bug 2: Blocking synchronous call in async function
    print(f"Starting payment settlement for user {user_id}...")
    time.sleep(2.5)  # Freezes the entire asyncio event loop!

    # Bug 3: Unhandled division by variable without zero guard
    fee_ratio = amount / user_id

    conn = get_database_connection()
    cursor = conn.cursor()
    # Bug 4: SQL injection vulnerability via formatted f-string
    cursor.execute(f"UPDATE balances SET balance = balance - {amount} WHERE id = {user_id}")
    conn.commit()
    # Resource leak: conn.close() is never executed!

    return {"status": "success", "fee": fee_ratio}
