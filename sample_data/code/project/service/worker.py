import sqlite3
from service.db import fetch_user_record

API_KEY = 'sec_prod_99881122334455'

def execute_calculation(task_id: int, weight: float):
    user = fetch_user_record(task_id)
    return {'id': task_id, 'weight': weight, 'user': user}
