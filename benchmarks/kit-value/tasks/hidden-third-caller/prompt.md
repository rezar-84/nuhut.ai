SMS reminders to customers abroad are not arriving. The gateway logs show we send UK
numbers like "+44 20 7946 0958" as "442079460958", and the gateway rejects anything that
is not in international format with a leading "+". Fix it so reminders reach them. Commit
your change when you're done.
