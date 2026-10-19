Add an optional discount code to orders, end to end: read it from the orders CSV (a
`discount_code` column), keep it on Order, validate it (uppercase letters and digits, at
most 12 characters; an invalid code is a ValueError), and include it in the JSON export.
Commit your change when you're done.
