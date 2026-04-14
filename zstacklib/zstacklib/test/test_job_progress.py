import unittest

from zstacklib.utils.job_progress import calculate_detail_speed, normalize_report_speed, summarize_block_job


class TestJobProgress(unittest.TestCase):
    def test_summarize_running_block_job(self):
        summary = summarize_block_job([{
            'device': 'drive-virtio-disk0',
            'len': 200,
            'offset': 50,
            'speed': '10',
            'status': 'running',
        }])
        self.assertEqual('running', summary['status'])
        self.assertEqual('drive-virtio-disk0', summary['device'])
        self.assertEqual(50, summary['offset'])
        self.assertEqual(200, summary['total'])
        self.assertEqual(150, summary['remain'])
        self.assertEqual(10, summary['speed'])
        self.assertEqual(25, summary['percent'])

    def test_summarize_ready_block_job(self):
        summary = summarize_block_job([{
            'device': 'job-ready',
            'len': 100,
            'offset': 100,
            'speed': None,
            'status': 'ready',
        }])
        self.assertEqual('ready', summary['status'])
        self.assertEqual(100, summary['percent'])

    def test_summarize_completed_when_no_job(self):
        summary = summarize_block_job([])
        self.assertEqual('completed', summary['status'])
        self.assertEqual(100, summary['percent'])
        self.assertIsNone(summary['device'])

    def test_query_block_jobs_speed_can_be_used_as_fallback(self):
        remain = 160 * 1024 * 1024
        state = calculate_detail_speed(remain, None, None, 0, fallback_speed=1024 * 1024, now=0)
        self.assertEqual(1024 * 1024, state[2])

    def test_no_fallback_when_no_qos(self):
        remain = 160 * 1024 * 1024
        state = calculate_detail_speed(remain, None, None, 0, fallback_speed=None, now=0)
        self.assertEqual(0, state[2])

    def test_normalize_report_speed(self):
        self.assertEqual(1024, normalize_report_speed('1024'))
        self.assertEqual(0, normalize_report_speed(-1))
        self.assertIsNone(normalize_report_speed('bad'))

    def test_first_sample_uses_fallback_speed(self):
        last_time, last_remain, speed = calculate_detail_speed(
            160 * 1024 * 1024, None, None, 0, fallback_speed=1024 * 1024, now=0)
        self.assertEqual(0, last_time)
        self.assertEqual(160 * 1024 * 1024, last_remain)
        self.assertEqual(1024 * 1024, speed)

    def test_keep_last_speed_when_progress_not_flushed(self):
        state = calculate_detail_speed(160 * 1024 * 1024, None, None, 0, fallback_speed=1024 * 1024, now=0)
        state = calculate_detail_speed(160 * 1024 * 1024, state[1], state[0], state[2], fallback_speed=1024 * 1024, now=15)
        self.assertEqual(1024 * 1024, state[2])
        self.assertEqual(0, state[0])
        self.assertEqual(160 * 1024 * 1024, state[1])

    def test_measure_average_speed_from_batched_progress(self):
        state = calculate_detail_speed(160 * 1024 * 1024, None, None, 0, now=0)
        state = calculate_detail_speed(160 * 1024 * 1024, state[1], state[0], state[2], now=15)
        self.assertEqual(0, state[2])

        state = calculate_detail_speed(144 * 1024 * 1024, state[1], state[0], state[2], now=16)
        self.assertEqual(1024 * 1024, state[2])
        self.assertEqual(16, state[0])
        self.assertEqual(144 * 1024 * 1024, state[1])

    def test_actual_qmp_trace_uses_delta_over_time(self):
        samples = [
            (0, 395313152),
            (2, 502267904),
            (4, 615514112),
            (6, 695205888),
            (8, 743440384),
        ]

        state = (None, None, 0)
        observed_speeds = []
        for now, processed in samples:
            remain = 4195352576 - processed
            state = calculate_detail_speed(remain, state[1], state[0], state[2], now=now)
            observed_speeds.append(state[2])

        self.assertEqual(0, observed_speeds[0])
        self.assertEqual((502267904 - 395313152) / 2.0, observed_speeds[1])
        self.assertEqual((615514112 - 502267904) / 2.0, observed_speeds[2])
        self.assertEqual((695205888 - 615514112) / 2.0, observed_speeds[3])
        self.assertEqual((743440384 - 695205888) / 2.0, observed_speeds[4])

    def test_reset_speed_when_remain_grows(self):
        state = calculate_detail_speed(80, None, None, 4, now=1)
        state = calculate_detail_speed(100, state[1], state[0], state[2], now=2)
        self.assertEqual(0, state[2])
        self.assertEqual(2, state[0])
        self.assertEqual(100, state[1])


if __name__ == '__main__':
    unittest.main()
