import os
import numpy as np
import luigi
import yaml
from datetime import datetime

from gbm_bkg_pipe.balrog_handler import ProcessLocalizationResult
from gbm_bkg_pipe.plots import (
    Create3DLocationPlot,
    CreateCornerPlot,
    CreateLightcurve,
    CreateLocationPlot,
    CreateMollLocationPlot,
    CreateSatellitePlot,
    CreateSpectrumPlot,
    CreateBkgModelPlot,
)
from gbm_bkg_pipe.configuration import gbm_bkg_pipe_config
from gbm_bkg_pipe.utils.file_utils import if_dir_containing_file_not_existing_then_make
from gbm_bkg_pipe.trigger_search import TriggerSearch
from gbm_bkg_pipe.utils.env import get_env_value
from gbm_bkg_pipe.utils.upload_utils import (
    upload_transient_report,
    upload_plot,
    upload_date_plot,
)

base_dir = os.path.join(os.environ.get("GBMDATA"), "bkg_pipe")

_valid_gbm_detectors = np.array(gbm_bkg_pipe_config["data"]["detectors"]).flatten()
_valid_echans = np.array(gbm_bkg_pipe_config["data"]["echans"]).flatten()


class UploadTriggers(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter(default="ctime")
    remote_host = luigi.Parameter()

    resources = {"cpu": 1}

    def requires(self):
        return TriggerSearch(
            date=self.date, data_type=self.data_type, remote_host=self.remote_host
        )

    def output(self):
        filename = f"upload_triggers_done.txt"

        return luigi.LocalTarget(
            os.path.join(base_dir, f"{self.date:%y%m%d}", self.data_type, filename)
        )

    def run(self):
        with self.input().open("r") as f:
            trigger_information = yaml.safe_load(f)

        upload_tasks = []

        for t_info in trigger_information["triggers"].values():

            upload_tasks.extend(
                [
                    UploadReport(
                        date=datetime.strptime(t_info["date"], "%y%m%d"),
                        data_type=trigger_information["data_type"],
                        trigger_name=t_info["trigger_name"],
                        remote_host=self.remote_host,
                    ),
                    UploadAllPlots(
                        date=datetime.strptime(t_info["date"], "%y%m%d"),
                        data_type=trigger_information["data_type"],
                        trigger_name=t_info["trigger_name"],
                        remote_host=self.remote_host,
                    ),
                ]
            )
        yield upload_tasks

        os.system(f"touch {self.output().path}")


class UploadReport(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    trigger_name = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        return ProcessLocalizationResult(
            date=self.date,
            data_type=self.data_type,
            trigger_name=self.trigger_name,
            remote_host=self.remote_host,
        )

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "trigger",
                self.trigger_name,
                f"{self.trigger_name}_report.yml",
            )
        )

    def run(self):
        with self.input()["result_file"].open() as f:
            result = yaml.safe_load(f)

        report = upload_transient_report(
            trigger_name=self.trigger_name,
            result=result,
            wait_time=float(gbm_bkg_pipe_config["upload"]["report"]["interval"]),
            max_time=float(gbm_bkg_pipe_config["upload"]["report"]["max_time"]),
        )

        with open(self.output().path, "w") as f:
            yaml.dump(report, f, default_flow_style=False)


class UploadAllPlots(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    trigger_name = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        return {
            "lightcurves": UploadAllLightcurves(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
            ),
            "location": UploadLocationPlot(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
            ),
            "corner": UploadCornerPlot(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
            ),
            "molllocation": UploadMollLocationPlot(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
            ),
            "satellite": UploadSatellitePlot(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
            ),
            "spectrum": UploadSpectrumPlot(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
            ),
            "3d_location": Upload3DLocationPlot(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
            ),
            # "balrogswift": UploadBalrogSwiftPlot(
            #     date=self.date,
            #     data_type=self.data_type,
            #     trigger_name=self.trigger_name,
            #     remote_host=self.remote_host,
            # ),
        }

    def output(self):

        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "trigger",
                self.trigger_name,
                "upload",
                f"{self.trigger_name}_upload_plot_all.done",
            )
        )

    def run(self):
        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")


class UploadAllLightcurves(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    trigger_name = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        upload_lightcurves = {}

        for det in _valid_gbm_detectors:
            upload_lightcurves[det] = UploadLightcurve(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
                detector=det,
            )
        return upload_lightcurves

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "trigger",
                self.trigger_name,
                "upload",
                f"{self.trigger_name}_upload_plot_all_lightcurves.done",
            )
        )

    def run(self):
        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")


class UploadLightcurve(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    detector = luigi.Parameter()
    trigger_name = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        return {
            "create_report": UploadReport(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
            ),
            "plot_file": CreateLightcurve(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
                detector=self.detector,
            ),
        }

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "trigger",
                self.trigger_name,
                "upload",
                f"{self.trigger_name}_{self.detector}_upload_plot_lightcurve.done",
            )
        )

    def run(self):

        upload_plot(
            trigger_name=self.trigger_name,
            data_type=self.data_type,
            plot_file=self.input()["plot_file"].path,
            plot_type="lightcurve",
            wait_time=float(gbm_bkg_pipe_config["upload"]["plot"]["interval"]),
            max_time=float(gbm_bkg_pipe_config["upload"]["plot"]["max_time"]),
            det_name=self.detector,
        )

        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")


class UploadLocationPlot(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    trigger_name = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        return {
            "create_report": UploadReport(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
            ),
            "plot_file": CreateLocationPlot(
                date=self.date,
                data_type=self.data_type,
                trigger_name=self.trigger_name,
                remote_host=self.remote_host,
            ),
        }

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "trigger",
                self.trigger_name,
                "upload",
                f"{self.trigger_name}_upload_plot_location.done",
            )
        )

    def run(self):

        upload_plot(
            trigger_name=self.trigger_name,
            data_type=self.data_type,
            plot_file=self.input()["plot_file"].path,
            plot_type="location",
            wait_time=float(gbm_bkg_pipe_config["upload"]["plot"]["interval"]),
            max_time=float(gbm_bkg_pipe_config["upload"]["plot"]["max_time"]),
        )

        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")


class UploadCornerPlot(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    trigger_name = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        return {
            "create_report": UploadReport(
                date=self.date,
                remote_host=self.remote_host,
                trigger_name=self.trigger_name,
                data_type=self.data_type,
            ),
            "plot_file": CreateCornerPlot(
                date=self.date,
                remote_host=self.remote_host,
                trigger_name=self.trigger_name,
                data_type=self.data_type,
            ),
        }

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "trigger",
                self.trigger_name,
                "upload",
                f"{self.trigger_name}_upload_plot_corner.done",
            )
        )

    def run(self):

        upload_plot(
            trigger_name=self.trigger_name,
            data_type=self.data_type,
            plot_file=self.input()["plot_file"].path,
            plot_type="allcorner",
            wait_time=float(gbm_bkg_pipe_config["upload"]["plot"]["interval"]),
            max_time=float(gbm_bkg_pipe_config["upload"]["plot"]["max_time"]),
        )

        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")


class UploadMollLocationPlot(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    trigger_name = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        return {
            "create_report": UploadReport(
                date=self.date,
                remote_host=self.remote_host,
                trigger_name=self.trigger_name,
                data_type=self.data_type,
            ),
            "plot_file": CreateMollLocationPlot(
                date=self.date,
                remote_host=self.remote_host,
                trigger_name=self.trigger_name,
                data_type=self.data_type,
            ),
        }

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "trigger",
                self.trigger_name,
                "upload",
                f"{self.trigger_name}_upload_plot_molllocation.done",
            )
        )

    def run(self):
        upload_plot(
            trigger_name=self.trigger_name,
            data_type=self.data_type,
            plot_file=self.input()["plot_file"].path,
            plot_type="molllocation",
            wait_time=float(gbm_bkg_pipe_config["upload"]["plot"]["interval"]),
            max_time=float(gbm_bkg_pipe_config["upload"]["plot"]["max_time"]),
        )

        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")


class UploadSatellitePlot(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    trigger_name = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        return {
            "create_report": UploadReport(
                date=self.date,
                remote_host=self.remote_host,
                trigger_name=self.trigger_name,
                data_type=self.data_type,
            ),
            "plot_file": CreateSatellitePlot(
                date=self.date,
                remote_host=self.remote_host,
                trigger_name=self.trigger_name,
                data_type=self.data_type,
            ),
        }

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "trigger",
                self.trigger_name,
                "upload",
                f"{self.trigger_name}_upload_plot_satellite.done",
            )
        )

    def run(self):

        upload_plot(
            trigger_name=self.trigger_name,
            data_type=self.data_type,
            plot_file=self.input()["plot_file"].path,
            plot_type="satellite",
            wait_time=float(gbm_bkg_pipe_config["upload"]["plot"]["interval"]),
            max_time=float(gbm_bkg_pipe_config["upload"]["plot"]["max_time"]),
        )

        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")


class UploadSpectrumPlot(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    trigger_name = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        return {
            "create_report": UploadReport(
                date=self.date,
                remote_host=self.remote_host,
                trigger_name=self.trigger_name,
                data_type=self.data_type,
            ),
            "plot_file": CreateSpectrumPlot(
                date=self.date,
                remote_host=self.remote_host,
                trigger_name=self.trigger_name,
                data_type=self.data_type,
            ),
        }

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "trigger",
                self.trigger_name,
                "upload",
                f"{self.trigger_name}_upload_plot_spectrum.done",
            )
        )

    def run(self):

        upload_plot(
            trigger_name=self.trigger_name,
            data_type=self.data_type,
            plot_file=self.input()["plot_file"].path,
            plot_type="spectrum",
            wait_time=float(gbm_bkg_pipe_config["upload"]["plot"]["interval"]),
            max_time=float(gbm_bkg_pipe_config["upload"]["plot"]["max_time"]),
        )

        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")


class Upload3DLocationPlot(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    trigger_name = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        return {
            "create_report": UploadReport(
                date=self.date,
                remote_host=self.remote_host,
                trigger_name=self.trigger_name,
                data_type=self.data_type,
            ),
            "plot_file": Create3DLocationPlot(
                date=self.date,
                remote_host=self.remote_host,
                trigger_name=self.trigger_name,
                data_type=self.data_type,
            ),
        }

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "trigger",
                self.trigger_name,
                "upload",
                f"{self.trigger_name}_upload_plot_3dlocation.done",
            )
        )

    def run(self):

        upload_plot(
            trigger_name=self.trigger_name,
            data_type=self.data_type,
            plot_file=self.input()["plot_file"].path,
            plot_type="3dlocation",
            wait_time=float(gbm_bkg_pipe_config["upload"]["plot"]["interval"]),
            max_time=float(gbm_bkg_pipe_config["upload"]["plot"]["max_time"]),
        )

        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")


# class UploadBalrogSwiftPlot(luigi.Task):
#     date = luigi.DateParameter()
#     data_type = luigi.Parameter()
#     trigger_name = luigi.Parameter()
#     remote_host = luigi.Parameter()

#     def requires(self):
#         return {
#             "create_report": UploadReport(
#                 date=self.date,
#                 remote_host=self.remote_host,
#                 trigger_name=self.trigger_name,
#                 data_type=self.data_type,
#             ),
#             "plot_file": CreateBalrogSwiftPlot(
#                 date=self.date,
#                 remote_host=self.remote_host,
#                 trigger_name=self.trigger_name,
#                 data_type=self.data_type,
#             ),
#         }

#     def output(self):
#         return luigi.LocalTarget(
#             os.path.join(
#                 base_dir,
#                 f"{self.date:%y%m%d}",
#                 self.data_type,
#                 "trigger",
#                 self.trigger_name,
#                 "upload",
#                 f"{self.trigger_name}_upload_plot_balrogswift.done",
#             )
#         )

#     def run(self):

#         upload_plot(
#             trigger_name=self.trigger_name,
#             data_type=self.data_type,
#             plot_file=self.input()["plot_file"].path,
#             plot_type="balrogswift",
#             wait_time=float(gbm_bkg_pipe_config["upload"]["plot"]["interval"]),
#             max_time=float(gbm_bkg_pipe_config["upload"]["plot"]["max_time"]),
#         )

#         if_dir_containing_file_not_existing_then_make(self.output().path)

#         os.system(f"touch {self.output().path}")


class UploadBkgResultPlots(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        upload_bkg_plots = {}

        for det in _valid_gbm_detectors:
            for e in _valid_echans:
                upload_bkg_plots[f"{det}_{e}"] = UploadBkgResultPlot(
                    date=self.date,
                    data_type=self.data_type,
                    remote_host=self.remote_host,
                    detector=det,
                    echan=e,
                )
        return upload_bkg_plots

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "upload",
                "upload_plot_all_bkg_results.done",
            )
        )

    def run(self):
        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")


class UploadBkgResultPlot(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter()
    detector = luigi.Parameter()
    echan = luigi.Parameter()
    remote_host = luigi.Parameter()

    def requires(self):
        return {
            "plot_file": CreateBkgModelPlot(
                date=self.date,
                data_type=self.data_type,
                remote_host=self.remote_host,
                detector=self.detector,
                echan=self.echan,
            ),
        }

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "upload",
                f"{self.detector}_{self.echan}_upload_plot_lightcurve.done",
            )
        )

    def run(self):

        upload_date_plot(
            date=self.date,
            data_type=self.data_type,
            plot_file=self.input()["plot_file"].path,
            plot_type="bkg_result",
            wait_time=float(gbm_bkg_pipe_config["upload"]["plot"]["interval"]),
            max_time=float(gbm_bkg_pipe_config["upload"]["plot"]["max_time"]),
            det_name=self.detector,
            echan=self.echan,
        )

        if_dir_containing_file_not_existing_then_make(self.output().path)

        os.system(f"touch {self.output().path}")
