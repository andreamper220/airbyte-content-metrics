SELECT left(failure_reason, 500) FROM attempts WHERE job_id=42 ORDER BY created_at DESC LIMIT 1;
