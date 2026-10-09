"""Sales summary."""


def fmt_money(amount):
    return "${:,.2f}".format(amount)


def summarize(rows):
    total = 0
    count = 0
    by_region = {}
    for row in rows:
        total += row["amount"]
        count += 1
        by_region[row["region"]] = by_region.get(row["region"], 0) + row["amount"]
    lines = ["Total: " + fmt_money(total), "Orders: %d" % count]
    for region in sorted(by_region):
        lines.append("  %s: %s" % (region, fmt_money(by_region[region])))
    return "\n".join(lines)
