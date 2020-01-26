from astropy.time import Time
from astroplan import EclipsingSystem, FixedTarget
from astroplan.plots import plot_finder_image, dark_style_sheet, plot_altitude
from telegram import InlineKeyboardButton, ReplyKeyboardMarkup
import matplotlib.pyplot as plt
import numpy as np
import astropy.units as u
import datetime

def Eclipse(tt0, P, dur=None):
    t0   = Time(tt0, format='jd')

    today  = Time(datetime.datetime.utcnow())
    eclsys = EclipsingSystem(primary_eclipse_time=t0,
                             orbital_period=P*u.day, duration=dur*u.hour)
    necl   = eclsys.next_primary_eclipse_time(today, n_eclipses=10)

    return necl

def FindingChart(target):
    obj = FixedTarget.from_name(target)
    fig, ax = plt.subplots()
    _,_ = plot_finder_image(obj, ax=ax)
    fig.savefig('findingchart.png')
    del(fig,ax)
    return

def Altitude(target, obs, time):
    tw    = obs.twilight_evening_civil(Time(time), which='next').datetime
    times = Time(tw) + np.linspace(-2, 16, 200)*u.hour

    moon = obs.moon_altaz(times).alt
    #sun  = obs.sun_altaz(times).alt

    plot_altitude(target, obs, times, brightness_shading=True, airmass_yaxis=True, style_sheet=dark_style_sheet)
    plt.plot_date(times.plot_date, moon.degree, '-', lw=1, c='gray')
    #plt.plot_date(times.plot_date, sun.degree, '-', lw=1, c='gold')
    plt.title(target.name)
    plt.savefig('altitude.png', bbox_inches='tight')
    plt.clf()
    return
