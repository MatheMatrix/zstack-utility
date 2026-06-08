import time


def normalize_report_speed(speed):
    if speed is None:
        return None

    try:
        speed = int(speed)
    except (TypeError, ValueError):
        return None

    return max(0, speed)


def calculate_detail_speed(remain, last_progress_remain, last_progress_time, last_speed, fallback_speed=None, now=None):
    current_time = time.time() if now is None else now
    speed = last_speed if last_speed and last_speed > 0 else 0

    if speed <= 0 and fallback_speed is not None and fallback_speed > 0:
        speed = fallback_speed

    if last_progress_remain is None:
        return current_time, remain, speed

    if remain < last_progress_remain:
        time_delta = current_time - last_progress_time if last_progress_time is not None else 0
        data_delta = last_progress_remain - remain
        speed = max(0, data_delta / time_delta) if time_delta > 0 else 0
        return current_time, remain, speed

    if remain > last_progress_remain:
        return current_time, remain, 0

    return last_progress_time, last_progress_remain, speed


def summarize_block_job(block_jobs):
    for status in ('running', 'ready'):
        job = next((item for item in (block_jobs or []) if item.get('status') == status), None)
        if not job:
            continue

        total = job.get('len', 0)
        offset = job.get('offset', 0)
        remain = max(0, total - offset)
        speed = normalize_report_speed(job.get('speed'))
        percent = int(offset * 100.0 / total) if total > 0 else 0
        if remain > 0:
            percent = min(percent, 99)

        return {
            'status': status,
            'device': job.get('device'),
            'offset': offset,
            'total': total,
            'remain': remain,
            'speed': speed,
            'percent': percent,
        }

    return {
        'status': 'completed',
        'device': None,
        'offset': 0,
        'total': 0,
        'remain': 0,
        'speed': None,
        'percent': 100,
    }
