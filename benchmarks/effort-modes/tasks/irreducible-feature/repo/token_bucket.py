"""Per-key token bucket rate limiter."""


class RateLimiter(object):
    def __init__(self, capacity, refill_per_sec):
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec

    def allow(self, key, cost=1.0, now=0.0):
        raise NotImplementedError
