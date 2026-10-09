from report import fmt_money


def csv_line(row):
    return "%s,%s" % (row["region"], fmt_money(row["amount"]))
