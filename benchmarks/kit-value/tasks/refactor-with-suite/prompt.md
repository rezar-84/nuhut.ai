Refactor report.py: extract the totals computation in summarize() into a function
compute_totals(rows) that returns {"total": ..., "count": ..., "by_region": {...}}, and
rename fmt_money to format_money everywhere. Behaviour must not change. Commit your change
when you're done.
