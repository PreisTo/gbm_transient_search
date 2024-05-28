import os
import numpy as np
import astropy.io.fits as fits
from gbmbkgpy.data.continuous_data import Data
from gbmbkgpy.utils.saa_calc import SAA_calc


class SolarFlare(object):
    def __init__(self, date):
        self._date = date
        self._load_data()
        self._calculate_mask()
        self._get_intervals()

    def _load_data(self):
        self._data = Data(
            dates=[self._date],
            data_type="ctime",
            detectors=["n5"],
            echans=["0", "1"],
        )
        self._saa = SAA_calc(self._data, time_after_SAA=5000, time_before_SAA=50)
        self._data.rebinn_data(30, self._saa.saa_mask)

    def _calculate_mask(self):
        self._mask = get_cutouts(
            self._data.counts[:, 0, 0] / self._data.time_bin_width,
            th=870,  # default threshold cps value
            t=self._data.time_bins[:, 0],
            cutout=60,
            mask=self._data.rebinned_saa_mask,
        )

    def _get_intervals(self):
        # including the saa
        jumps = self._mask.astype(int)[1:] - self._mask.astype(int)[:-1]
        starts = np.argwhere(jumps < 0)[:, 0]
        stops = np.argwhere(jumps > 0)[:, 0]
        if len(starts) != len(stops):
            if np.abs(len(starts)-len(stops))<2:
                if starts[0]>stops[0]:
                    stops = stops[1:]
                elif starts[-1]>stops[-1]:
                    starts  = starts[:-1]
            else:
                raise ValueError("Starts and Stops differ too much")
        intervals = []
        for a, o in zip(starts, stops):
            if a<o:
                intervals.append({"start":float(self._data.time_bins[a,0]),"stop":float(self._data.time_bins[o,1])})
            else:
                intervals.append({"start":float(self._data.time_bins[o,0]),"stop":float(self._data.time_bins[a,1])})

        self._sun_intervals = intervals

    @property
    def sun_intervals(self):
        return self._sun_intervals


def get_cutouts(c, th, t, cutout=120, mask=None):
    if mask is None:
        mask = np.ones_like(c)
    mask[c > th] = 0
    i = 0
    temp = np.zeros_like(t)
    while i < len(mask):
        try:
            if i != 0 and mask[i] == 0:
                i = np.argwhere(mask[i:] == 1)[0, 0]
            idx = np.argwhere(mask[i:] == 0)[0, 0]
            idx += i
            idx_stop = np.argwhere(mask[idx:] == 1)[0, 0]
            idx_stop += idx
            temp[t > t[idx] - cutout] = 1
            temp[t > t[idx_stop] + cutout] = 0
            mask[temp.astype(bool)] = 0
            i = np.argwhere(temp == 1)[-1, -1] + 1
            temp = np.zeros_like(t)
        except IndexError:
            i = len(mask)

    return mask.astype(bool)
