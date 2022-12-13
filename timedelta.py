# https://docs.python.org/3/library/datetime.html#datetime.timedelta
from datetime import timedelta
# 0 <= microseconds < 1000000
# 0 <= seconds < 3600*24 (the number of seconds in one day)
# -999999999 <= days <= 999999999

d=str(timedelta(seconds=(3600*24+1)))
print(d)