-- Retention is applied by rjp.load.supabase.apply_retention() at the end of each
-- run (WINDOW_DAYS, default 7). This file documents the equivalent manual SQL,
-- useful for an ad-hoc cleanup or a scheduled Supabase cron job.
DELETE FROM jobs WHERE posted_at < now() - INTERVAL '7 days';
