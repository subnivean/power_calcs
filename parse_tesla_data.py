import sys
from pathlib import Path

import arrow
import numpy as np

DATADIR = "./tesla_gateway_data"
NODES = ('home', 'solar', 'pwall', 'grid')

PEAKRATE = 0.26119
OFFPEAKRATE = 0.11133
NETRATE = 0.15417
KONACHARGERATE = 7.3  # By examination of instant energy use
POWERWALLEFFICIENCY = 0.85  # Round-trip efficiency
SOLARCITINGINCENTIVE = 0.01
RENEWABLEENERGEYCERT = 0.03
BASEPEAKRATIO = (8 * 5) / (7 * 24)

KONAMILES = dict(
             Aug=4517,
             Sep=6341,
             Oct=8256,
             Nov=10307,
            )


def parse_rec(rec):
    dstr = rec[0]
    dobj = arrow.get(dstr)
    hour = int(dobj.format("HH"))
    wday = dobj.weekday()
    ymd = dobj.format('YYYY-MM-DD')
    home, solar, pwall, grid = [float(r) / 12 for r in rec[1:]]

    if battery is False:
        grid += (pwall / POWERWALLEFFICIENCY if pwall < 0 else pwall)
        pwall = 0

    if wday > 4:
        ratetype = "offpeak"
    else:
        ratetype = 'peak' if hour >= 13 and hour < 21 else 'offpeak'

    return ratetype, home, solar, pwall, grid

kwh = dict()

for node in NODES:
    kwh[node] = {'peak': {'in': 0.0, 'out': 0.0},
                 'offpeak': {'in': 0.0, 'out': 0.0}}

startdate, enddate, battery = sys.argv[1:]
startdate = arrow.get(startdate, "YYYYMMDD")
enddate = arrow.get(enddate, "YYYYMMDD")
battery = bool(eval(battery.title()))

homedays = []
for d in arrow.Arrow.range('day', startdate, enddate):
    datestr = d.strftime("%Y%m%d")

    fpath = (Path(DATADIR) / (f"{datestr}.csv"))
    # print(f"fpath:'{fpath}'")

    if not fpath.is_file():
        continue

    lines = fpath.read_text().splitlines()
    recs = [l.split(',') for l in lines]

    ldate = f"{datestr[0:4]}-{datestr[4:6]}-{datestr[6:]}"
    frecs = [r for r in recs if len(r) == 5 and ldate in r[0]]

    for rec in frecs:
        ratetype, home, solar, pwall, grid = parse_rec(rec)

        homeinout = 'out' if home < 0.0 else 'in'
        solarinout = 'out' if solar < 0.0 else 'in'
        pwallinout = 'out' if pwall < 0.0 else 'in'
        gridinout = 'out' if grid < 0.0 else 'in'

        kwh['home'][ratetype][homeinout] += home
        kwh['solar'][ratetype][solarinout] += solar
        kwh['pwall'][ratetype][pwallinout] += pwall
        kwh['grid'][ratetype][gridinout] += grid

        homedays.append(home)

homedays = np.array(homedays)

konacharging = homedays[homedays > KONACHARGERATE / 12 * 0.95]
konakwh = len(konacharging) / 12 * KONACHARGERATE
# Assumes (!) all charging is done during offpeak hours
konacost = konakwh * OFFPEAKRATE

print()
print(f"Kona kWh: {int(konakwh):.2f}  Kona cost: ${konacost:.2f}")
print()

# Now that we have usage/generation, calculate cost:
netpeakuse = kwh['grid']['peak']['in'] + kwh['grid']['peak']['out']
netoffpeakuse = kwh['grid']['offpeak']['in'] + kwh['grid']['offpeak']['out']

if netpeakuse < 0:
    netoffpeakuse += netpeakuse
    netpeakuse = 0

totalhome = kwh['home']['peak']['in'] + kwh['home']['offpeak']['in']

cost = netpeakuse * PEAKRATE + netoffpeakuse * OFFPEAKRATE

excess = totalhome - (netpeakuse + netoffpeakuse)
if excess < 0:
    cost += excess * NETRATE

print(f"{'Power usage exluding Kona':^44s}")
print(f"{'Offpeak':>23s}{'Peak':>16s}")
print(f"{'Source':9s}{'In':>6s}{'Out':>10s}{'In':>8s}{'Out':>10s}")
print("=" * 45)
for source in ('home', 'grid', 'solar', 'pwall'):
    konaadj = konakwh if source in ('home', 'grid') else 0.00
    print(f"{source:8s}"
          f"{kwh[source]['offpeak']['in'] - konaadj:9.2f}"
          f"{kwh[source]['offpeak']['out']:9.2f}"
          f"{kwh[source]['peak']['in']:9.2f}"
          f"{kwh[source]['peak']['out']:9.2f}")

print()
print(f"{'Grid cost (exluding EV):':35s} ${cost - konacost:8.2f}")
rawcost = ((kwh['home']['offpeak']['in'] - konakwh) * OFFPEAKRATE
           + kwh['home']['peak']['in'] * PEAKRATE)
print(f"{'No-solar grid cost (exluding EV):':35s} ${rawcost:8.2f}")

print()
solarsavings = rawcost - (cost - konacost)
print(f"{'Solar savings (without incentives):':35s} ${solarsavings:8.2f}")
totalsolar = kwh['solar']['peak']['in'] + kwh['solar']['offpeak']['in']
incentives = totalsolar * (SOLARCITINGINCENTIVE + RENEWABLEENERGEYCERT)
print(f"{'Solar savings (with incentives):':35s} ${solarsavings + incentives:8.2f}")

homepeak = kwh['home']['peak']['in']
homeoffpeak = kwh['home']['offpeak']['in']
adjhomeoffpeak = homeoffpeak - konakwh
adjhometotal = homepeak + adjhomeoffpeak
peakratio = homepeak / (homepeak + adjhomeoffpeak)
basecost = BASEPEAKRATIO * adjhometotal * PEAKRATE + (1 - BASEPEAKRATIO) * adjhometotal * OFFPEAKRATE
