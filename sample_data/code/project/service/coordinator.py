import math
from service.worker import execute_calculation

def dispatch_batch(task_id: int, scale_factor: int):
    # Unguarded division
    normalized = 1000 / scale_factor
    return execute_calculation(task_id, normalized)
