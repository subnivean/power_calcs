import csv
from pathlib import Path
import arrow

# Pick 10 random weekdays between May 1 and Sep 30;
# actual days to be determined by GMP.
CRITICAL_PEAK_DAYS = (
    '2018-06-01',
    '2018-06-15',
    '2018-07-06',
    '2018-07-18',
    '2018-07-24',
    '2018-08-03',
    '2018-08-20',
    '2018-08-30',
    '2018-09-04',
    '2018-09-19',
)

# DATASOURCE = 'gmpdata'
DATASOURCE = 'mike_johnson_gmpdata'

def get_data():
    allflines = []
    for ndx, f in enumerate(sorted(Path(DATASOURCE).glob('UsageData_2*'))):
        flines = f.read_text().splitlines()
        if ndx > 0:
            flines.pop(0)
        allflines.extend(flines)

    return allflines


def calc_cost(data, rate):
    # totbyhr = [0.0 for n in range(24)]

    critpkkwh = 0
    totkwh = 0

    if rate == 1:
        dailyrate = 0.480
        pkrate = 0.16446
        offpkrate = 0.16446
    elif rate == 11:
        dailyrate = 0.635
        pkrate = 0.26114
        offpkrate = 0.11131
    elif rate == 14:
        dailyrate = 0.635
        critpkrate = 0.67216
        pkrate = 0.25428
        offpkrate = 0.10839

    yrlyrate = 365 * dailyrate
    totcost = yrlyrate

    usagebyclass = {c: 0.0 for c in ('critpeak', 'peak', 'offpeak')}
    countbyclass = {c: 0 for c in ('critpeak', 'peak', 'offpeak')}

    drdr = csv.DictReader(data)
    for rec in drdr:

        if 'NGEN' in rec['ServiceAgreement']:
            # Skip these records as they are 'Net Generation' values
            continue

        dstr = rec['IntervalStart']
        dstr = dstr[-1::-1].replace('-', 'T', 1)[-1::-1]
        dobj = arrow.get(dstr)
        hr = int(dobj.format("HH"))
        wday = dobj.weekday()
        ymd = dobj.format('YYYY-MM-DD')

        if wday in (5, 6):
            kwhrate = offpkrate
            rateclass = 'offpeak'
        elif rate == 14 and ymd in CRITICAL_PEAK_DAYS and 12 <= hr < 20:
            kwhrate = critpkrate
            rateclass = 'critpeak'
        elif 13 <= hr < 21:
            kwhrate = pkrate
            rateclass = 'peak'
        else:
            kwhrate = offpkrate
            rateclass = 'offpeak'

        kwh = float(rec['Quantity'])

        intcost = kwhrate * kwh
        totcost += intcost
        totkwh += kwh

        usagebyclass[rateclass] += kwh
        countbyclass[rateclass] += 1

    return totcost, totkwh, usagebyclass, countbyclass


data = get_data()

for rate in (1, 11, 14):
    totcost, totkwh, usagebyclass, countbyclass = calc_cost(data, rate)
    # print(usagebyclass)
    print(f"Rate: {rate:02d}  Cost of power from grid: ${totcost:.2f}  "
          f"Total kWh: {totkwh:.1f}  "
          f"Peak kWh: {usagebyclass['peak']:.1f}  "
          f"OffPeak kWh: {usagebyclass['offpeak']:.1f}  "
          f"CritPeak kWh: {usagebyclass['critpeak']:.1f} "
          f"Peak count: {countbyclass['peak']:d}  "
          f"OffPeak count: {countbyclass['offpeak']:d}  "
          f"CritPeak count: {countbyclass['critpeak']:d}")
