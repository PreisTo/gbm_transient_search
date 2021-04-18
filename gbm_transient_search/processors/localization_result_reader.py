from datetime import datetime
import pytz
import urllib

import astropy.io.fits as fits
import numpy as np
import yaml
from chainconsumer import ChainConsumer
from astropy.coordinates import Angle
from astropy.coordinates import SkyCoord

from gbm_transient_search.exceptions.custom_exceptions import *
from gbm_transient_search.utils.env import get_env_value

from gbmgeometry.gbm_frame import GBMFrame
from astropy.coordinates import SkyCoord
import astropy.units as unit


class LocalizationResultReader(object):
    def __init__(
        self,
        trigger_name,
        data_type,
        post_equal_weights_file,
        trigger_file,
        result_file,
    ):
        self.trigger_name = trigger_name
        self.data_type = data_type

        self._K = None
        self._K_err = None
        self._index = None
        self._index_err = None
        self._xc = None
        self._xc_err = None
        self._alpha = None
        self._alpha_err = None
        self._xp = None
        self._xp_err = None
        self._beta = None
        self._beta_err = None
        self._kT = None
        self._kT_err = None

        self._phi_sat = None
        self._theta_sat = None

        # read trigger_file
        self._read_trigger(trigger_file)

        # read parameter values
        self._read_fit_result(result_file, model=self._trigger_data["spectral_model"])

        # read parameter values
        self._read_post_equal_weights_file(post_equal_weights_file)

        # Create a report containing all the results of the pipeline
        self._build_report()

    def _read_fit_result(self, result_file, model="cpl"):

        with fits.open(result_file) as f:
            values = f["ANALYSIS_RESULTS"].data["VALUE"]
            pos_error = f["ANALYSIS_RESULTS"].data["POSITIVE_ERROR"]
            neg_error = f["ANALYSIS_RESULTS"].data["NEGATIVE_ERROR"]

        self._ra = values[0]
        self._ra_pos_err = pos_error[0]
        self._ra_neg_err = neg_error[0]

        if np.absolute(self._ra_pos_err) > np.absolute(self._ra_neg_err):
            self._ra_err = np.absolute(self._ra_pos_err)
        else:
            self._ra_err = np.absolute(self._ra_neg_err)

        self._dec = values[1]
        self._dec_pos_err = pos_error[1]
        self._dec_neg_err = neg_error[1]

        if np.absolute(self._dec_pos_err) > np.absolute(self._dec_neg_err):
            self._dec_err = np.absolute(self._dec_pos_err)
        else:
            self._dec_err = np.absolute(self._dec_neg_err)

        self._K = values[2]
        self._K_pos_err = pos_error[2]
        self._K_neg_err = neg_error[2]

        if np.absolute(self._K_pos_err) > np.absolute(self._K_neg_err):
            self._K_err = np.absolute(self._K_pos_err)
        else:
            self._K_err = np.absolute(self._K_neg_err)

        if model == "cpl":
            self._index = values[3]
            self._index_pos_err = pos_error[3]
            self._index_neg_err = neg_error[3]

            if np.absolute(self._index_pos_err) > np.absolute(self._index_neg_err):
                self._index_err = np.absolute(self._index_pos_err)
            else:
                self._index_err = np.absolute(self._index_neg_err)

            self._xc = values[4]
            self._xc_pos_err = pos_error[4]
            self._xc_neg_err = neg_error[4]
            if np.absolute(self._xc_pos_err) > np.absolute(self._xc_neg_err):
                self._xc_err = np.absolute(self._xc_pos_err)
            else:
                self._xc_err = np.absolute(self._xc_neg_err)

        elif model == "pl":
            self._index = values[3]
            self._index_pos_err = pos_error[3]
            self._index_neg_err = neg_error[3]

            if np.absolute(self._index_pos_err) > np.absolute(self._index_neg_err):
                self._index_err = np.absolute(self._index_pos_err)
            else:
                self._index_err = np.absolute(self._index_neg_err)

        elif model == "blackbody":
            self._kT = values[3]
            self._kT_pos_err = pos_error[3]
            self._kT_neg_err = neg_error[3]

            if np.absolute(self._kT_pos_err) > np.absolute(self._kT_neg_err):
                self._kT_err = np.absolute(self._kT_pos_err)
            else:
                self._kT_err = np.absolute(self._kT_neg_err)
        else:
            raise Exception("Unknown spectral model")

        self._model = model

    def _read_trigger(self, trigger_file):
        with open(trigger_file, "r") as f:
            self._trigger_data = yaml.safe_load(f)

            # TODO: use trigger information

    def _read_post_equal_weights_file(self, post_equal_weights_file):

        # Sometimes chainconsumer does not give an error - In this case we will need the errors from the
        # 3ml fits files
        (
            self._ra,
            ra_err,
            self._dec,
            dec_err,
            self._balrog_one_sig_err_circle,
            self._balrog_two_sig_err_circle,
        ) = get_best_fit_with_errors(post_equal_weights_file, self._model)

        if ra_err is not None:
            self._ra_err = ra_err

        if dec_err is not None:
            self._dec_err = dec_err

    def _build_report(self):
        self._report = {
            "trigger": self._trigger_data,
            "fit_result": {
                "model": self._model,
                "ra": convert_to_float(self._ra),
                "ra_err": convert_to_float(self._ra_err),
                "dec": convert_to_float(self._dec),
                "dec_err": convert_to_float(self._dec_err),
                "spec_K": convert_to_float(self._K),
                "spec_K_err": convert_to_float(self._K_err),
                "spec_index": convert_to_float(self._index),
                "spec_index_err": convert_to_float(self._index_err),
                "spec_xc": convert_to_float(self._xc),
                "spec_xc_err": convert_to_float(self._xc_err),
                "spec_alpha": convert_to_float(self._alpha),
                "spec_alpha_err": convert_to_float(self._alpha_err),
                "spec_xp": convert_to_float(self._xp),
                "spec_xp_err": convert_to_float(self._xp_err),
                "spec_beta": convert_to_float(self._beta),
                "spec_beta_err": convert_to_float(self._beta_err),
                "spec_kT": convert_to_float(self._kT),
                "spec_kT_err": convert_to_float(self._kT_err),
                "sat_phi": convert_to_float(self._phi_sat),
                "sat_theta": convert_to_float(self._theta_sat),
                "balrog_one_sig_err_circle": convert_to_float(
                    self._balrog_one_sig_err_circle
                ),
                "balrog_two_sig_err_circle": convert_to_float(
                    self._balrog_two_sig_err_circle
                ),
            },
        }

    def save_result_yml(self, file_path):
        with open(file_path, "w") as f:
            yaml.dump(self._report, f, default_flow_style=False)

    def __repr__(self):
        """
        Examine the balrog results.
        """

        print(f"Result Reader for {self.trigger_name}")
        return str(self._report)

    @property
    def ra(self):

        return self._ra, self._ra_err

    @property
    def dec(self):

        return self._dec, self._dec_err

    @property
    def K(self):

        return self._K, self._K_err

    @property
    def alpha(self):

        return self._alpha, self._alpha_err

    @property
    def xp(self):

        return self._xp, self._xp_err

    @property
    def beta(self):

        return self._beta, self._beta_err

    @property
    def index(self):

        return self._index, self._index_err

    @property
    def xc(self):

        return self._xc, self._xc_err

    @property
    def kT(self):

        return self._kT, self._kT_err

    @property
    def model(self):

        return self._model


model_param_lookup = {
    "pl": ["ra (deg)", "dec (deg)", "K", "index"],
    "cpl": ["ra (deg)", "dec (deg)", "K", "index", "xc"],
    "sbpl": ["ra (deg)", "dec (deg)", "K", "alpha", "break", "beta"],
    "band": ["ra (deg)", "dec (deg)", "K", "alpha", "xp", "beta"],
    "blackbody": ["ra (deg)", "dec (deg)", "K", "kT"],
    "solar_flare": [
        "ra (deg)",
        "dec (deg)",
        "K-bl",
        "xb-bl",
        "alpha-bl",
        "beta-bl",
        "K-brems",
        "Epiv-brems",
        "kT-brems",
    ],
}


def get_best_fit_with_errors(post_equal_weigts_file, model):
    """
    load fit results and get best fit and errors
    :return:
    """
    chain = loadtxt2d(post_equal_weigts_file)

    parameter = model_param_lookup[model]

    # RA-DEC plot
    c2 = ChainConsumer()

    c2.add_chain(chain[:, :-1], parameters=parameter).configure(
        plot_hists=False,
        contour_labels="sigma",
        colors="#cd5c5c",
        flip=False,
        max_ticks=3,
    )

    # Calculate err radius #
    chains, parameters, truth, extents, blind, log_scales = c2.plotter._sanitise(
        None, None, None, None, color_p=True, blind=None
    )

    summ = c2.analysis.get_summary(
        parameters=["ra (deg)", "dec (deg)"], chains=chains, squeeze=False
    )[0]
    ra = summ["ra (deg)"][1]
    try:
        ra_pos_err = summ["ra (deg)"][2] - summ["ra (deg)"][1]
        ra_neg_err = summ["ra (deg)"][1] - summ["ra (deg)"][0]

        if np.absolute(ra_pos_err) > np.absolute(ra_neg_err):
            ra_err = np.absolute(ra_pos_err)
        else:
            ra_err = np.absolute(ra_neg_err)

    except:
        ra_err = None

    dec = summ["dec (deg)"][1]

    try:
        dec_pos_err = summ["dec (deg)"][2] - summ["dec (deg)"][1]
        dec_neg_err = summ["dec (deg)"][1] - summ["dec (deg)"][0]

        if np.absolute(dec_pos_err) > np.absolute(dec_neg_err):
            dec_err = np.absolute(dec_pos_err)
        else:
            dec_err = np.absolute(dec_neg_err)

    except:
        dec_err = None

    hist, x_contour, y_contour = c2.plotter._get_smoothed_histogram2d(
        chains[0], "ra (deg)", "dec (deg)"
    )  # ra, dec in deg here

    hist[hist == 0] = 1e-16
    val_contour = c2.plotter._convert_to_stdev(hist.T)

    mask = val_contour < 0.68
    points = []
    for i in range(len(mask)):
        for j in range(len(mask[i])):
            if mask[i][j]:
                points.append([x_contour[j], y_contour[i]])
    points = np.array(points)
    best_fit_point = [ra, dec]
    best_fit_point_vec = [
        np.cos(best_fit_point[1] * np.pi / 180)
        * np.cos(best_fit_point[0] * np.pi / 180),
        np.cos(best_fit_point[1] * np.pi / 180)
        * np.sin(best_fit_point[0] * np.pi / 180),
        np.sin(best_fit_point[1] * np.pi / 180),
    ]
    alpha_largest = 0

    for point_2 in points:
        point_2_vec = [
            np.cos(point_2[1] * np.pi / 180) * np.cos(point_2[0] * np.pi / 180),
            np.cos(point_2[1] * np.pi / 180) * np.sin(point_2[0] * np.pi / 180),
            np.sin(point_2[1] * np.pi / 180),
        ]
        alpha = np.arccos(np.dot(point_2_vec, best_fit_point_vec)) * 180 / np.pi
        if alpha > alpha_largest:
            alpha_largest = alpha
    alpha_one_sigma = alpha

    mask = val_contour < 0.95
    points = []
    for i in range(len(mask)):
        for j in range(len(mask[i])):
            if mask[i][j]:
                points.append([x_contour[j], y_contour[i]])
    points = np.array(points)
    alpha_largest = 0

    for point_2 in points:
        point_2_vec = [
            np.cos(point_2[1] * np.pi / 180) * np.cos(point_2[0] * np.pi / 180),
            np.cos(point_2[1] * np.pi / 180) * np.sin(point_2[0] * np.pi / 180),
            np.sin(point_2[1] * np.pi / 180),
        ]
        alpha = np.arccos(np.dot(point_2_vec, best_fit_point_vec)) * 180 / np.pi
        if alpha > alpha_largest:
            alpha_largest = alpha
    alpha_two_sigma = alpha

    return ra, ra_err, dec, dec_err, alpha_one_sigma, alpha_two_sigma


def loadtxt2d(intext):
    try:
        return np.loadtxt(intext, ndmin=2)
    except:
        return np.loadtxt(intext)


def convert_to_float(value):
    if value is not None:
        return float(value)
    else:
        return None
