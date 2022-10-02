from datetime import timedelta
from math import floor

import numpy as np
import pandas as pd

tage = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

df = pd.read_json("timew_export.json")

df["start"] = (
    pd.to_datetime(df["start"], format="%Y%m%dT%H%M%SZ")
    .dt.tz_localize("utc")
    .dt.tz_convert("Europe/Berlin")
)
df["end"] = (
    pd.to_datetime(df["end"], format="%Y%m%dT%H%M%SZ")
    .dt.tz_localize("utc")
    .dt.tz_convert("Europe/Berlin")
)
df["workmin"] = (df.end - df.start).astype("timedelta64[m]")
df["tag"] = df.start.dt.date
df["wd"] = df.start.dt.weekday  # Mo=1,So=7

sdate = df.iloc[0].tag
edate = df.iloc[-1].tag
days = []
delta = edate - sdate  # as timedelta
for i in range(delta.days + 1):
    day = sdate + timedelta(days=i)
    days.append(day)


columns = [
    "Datum",
    "Wochentag",
    "Start",
    "Ende",
    "Pausen",
    "ArbeitszeitSoll",
    "ArbeitszeitIst",
    "Differenz",
]
df_target = pd.DataFrame(columns=columns)

for day in days:
    newline = {}
    newline["Datum"] = day.strftime("%d.%m.%Y")
    newline["Wochentag"] = tage[day.weekday()]
    if day.weekday() in [5, 6]:
        newline["ArbeitszeitSoll"] = 0
    else:
        newline["ArbeitszeitSoll"] = 480
    if not day in df.tag.values:
        newline["Start"] = ""
        newline["Ende"] = ""
        newline["ArbeitszeitIst"] = 0
        newline["Pausen"] = "00:00"
    else:
        today = df[df.tag == day]
        start = today.iloc[0].start
        end = today.iloc[-1].end
        total_minutes = np.ceil((end - start).total_seconds() / 60)
        newline["Start"] = start.strftime("%H:%M")
        newline["Ende"] = end.strftime("%H:%M")
        newline["ArbeitszeitIst"] = int(today["workmin"].sum())

        pausen_minuten = total_minutes - newline["ArbeitszeitIst"]
        pausen_stunden = floor(pausen_minuten / 60)
        pausen_minuten -= pausen_stunden * 60
        newline["Pausen"] = (
            "{:02.0f}".format(pausen_stunden) + ":" + "{:02.0f}".format(pausen_minuten)
        )
    newline["Differenz"] = newline["ArbeitszeitIst"] - newline["ArbeitszeitSoll"]
    newdf = pd.DataFrame(data=[newline], columns=columns)
    df_target = pd.concat([df_target, newdf])

df_target.to_excel("arbeitszeit.xlsx")
