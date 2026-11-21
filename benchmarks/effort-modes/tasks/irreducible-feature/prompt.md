Implement `RateLimiter(capacity, refill_per_sec)` in `token_bucket.py` with `allow(key, cost=1.0, now=0.0) -> bool`:
- Validate positive `capacity` and `refill_per_sec` (`ValueError` otherwise).
- Each distinct `key` starts full at `capacity` tokens on first sight.
- Refill linearly by `max(0.0, now - last_now) * refill_per_sec`, capped at `capacity`.
- When sufficient tokens exist for `cost`, deduct `cost` and return `True`; otherwise leave remaining refilled tokens intact and return `False`.
