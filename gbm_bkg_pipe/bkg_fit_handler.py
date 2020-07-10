import os
import time
import json
import numpy as np
import luigi
import yaml
from chainconsumer import ChainConsumer

from luigi.contrib.external_program import ExternalProgramTask

from gbm_bkg_pipe.configuration import gbm_bkg_pipe_config

from gbmbkgpy.io.export import PHAWriter
from gbmbkgpy.io.plotting.plot_result import ResultPlotGenerator

base_dir = os.path.join(os.environ.get("GBMDATA"), "bkg_pipe")
bkg_n_cores_multinest = gbm_bkg_pipe_config["phys_bkg"]["multinest"]["n_cores"]
bkg_path_to_python = gbm_bkg_pipe_config["phys_bkg"]["multinest"]["path_to_python"]

run_detectors = gbm_bkg_pipe_config["data"]["detectors"]
run_echans = gbm_bkg_pipe_config["data"]["echans"]


class GBMBackgroundModelFit(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter(default="ctime")

    resources = {"cpu": 1}

    def requires(self):

        bkg_fit_tasks = {}

        for dets in run_detectors:

            for echans in run_echans:

                bkg_fit_tasks[
                    f"bkg_d{'_'.join(dets)}_e{'_'.join(echans)}"
                ] = RunPhysBkgModel(date=self.date, echans=echans, detectors=dets)

                bkg_fit_tasks[
                    f"result_plot_d{'_'.join(dets)}_e{'_'.join(echans)}"
                ] = BkgModelResultPlot(date=self.date, echans=echans, detectors=dets)

                bkg_fit_tasks[
                    f"corner_plot_d{'_'.join(dets)}_e{'_'.join(echans)}"
                ] = BkgModelCornerPlot(date=self.date, echans=echans, detectors=dets)

        return bkg_fit_tasks

    def output(self):

        return luigi.LocalTarget(
            os.path.join(
                base_dir,
                f"{self.date:%y%m%d}",
                self.data_type,
                "phys_bkg",
                "phys_bkg_combined.hdf5",
            )
        )

    def run(self):

        bkg_fit_results = []

        for det in run_detectors:

            for echan in run_echans:

                bkg_fit_results.append(
                    self.input()[f"bkg_{det}_e{echan}"]["result_file"].path
                )

        # PHACombiner and save combined file
        pha_writer = PHAWriter.from_result_files(bkg_fit_results)

        pha_writer.save_combined_hdf5(self.output().path)


class RunPhysBkgModel(ExternalProgramTask):
    date = luigi.DateParameter()
    data_type = luigi.Parameter(default="ctime")
    echans = luigi.ListParameter()
    detectors = luigi.ListParameter()
    always_log_stderr = True

    resources = {"cpu": bkg_n_cores_multinest}

    worker_timeout = 60 * 60  # 1 hour

    def requires(self):
        return None

    def output(self):
        job_dir = os.path.join(
            base_dir,
            f"{self.date:%y%m%d}",
            self.data_type,
            "phys_bkg",
            f"det_{'_'.join(self.detectors)}",
            f"e{'_'.join(self.echans)}",
        )
        return {
            "result_file": luigi.LocalTarget(os.path.join(job_dir, "fit_result.hdf5")),
            "posteriour": luigi.LocalTarget(
                os.path.join(job_dir, "post_equal_weights.dat")
            ),
            "params_json": luigi.LocalTarget(os.path.join(job_dir, "params.json")),
            "finished": luigi.LocalTarget(os.path.join(job_dir, "finished.txt")),
        }

    def program_args(self):

        fit_script_path = f"{os.path.dirname(os.path.abspath(__file__))}/phys_bkg_model/fit_phys_bkg.py"

        command = []

        # Run with mpi in parallel
        if bkg_n_cores_multinest > 1:

            command.extend(["mpiexec", f"-n", f"{bkg_n_cores_multinest}"])

        command.extend(
            [
                f"{bkg_path_to_python}",
                f"{fit_script_path}",
                f"-dates",
                f"{self.date:%y%m%d}",
                f"-dtype",
                f"{self.data_type}",
            ]
        )

        command.append("-dets")
        command.extend(self.detectors)

        command.append("-e")
        command.extend(self.echans)

        command.extend(
            [f"-out", f"{os.path.dirname(self.output()['result_file'].path)}",]
        )
        return command


class BkgModelResultPlot(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter(default="ctime")
    echans = luigi.Parameter()
    detectors = luigi.Parameter()

    resources = {"cpu": 1}

    def requires(self):
        return RunPhysBkgModel(
            date=self.date, echans=self.echans, detectors=self.detectors
        )

    def output(self):
        job_dir = os.path.join(
            base_dir,
            f"{self.date:%y%m%d}",
            self.data_type,
            "phys_bkg",
            f"det_{'_'.join(self.detectors)}",
            f"e{'_'.join(self.echans)}",
        )

        plot_files = []

        for detector in self.detectors:
            for echan in self.echans:

                filename = f"plot_date_{self.date:%y%m%d}_det_{detector}_echan_{echan}__{''}.pdf"

                plot_files.append(luigi.LocalTarget(os.path.join(job_dir, filename)))
        return plot_files

    def run(self):

        config_plot_path = f"{os.path.dirname(os.path.abspath(__file__))}/phys_bkg_model/config_result_plot.yml"

        plot_generator = ResultPlotGenerator.from_result_file(
            config_file=config_plot_path,
            result_data_file=self.input()["result_file"].path,
        )

        plot_generator.create_plots(
            output_dir=os.path.dirname(self.output().path), time_stamp=""
        )


class BkgModelCornerPlot(luigi.Task):
    date = luigi.DateParameter()
    data_type = luigi.Parameter(default="ctime")
    echans = luigi.Parameter()
    detectors = luigi.Parameter()

    resources = {"cpu": 1}

    def requires(self):
        return RunPhysBkgModel(
            date=self.date, echans=self.echans, detectors=self.detectors
        )

    def output(self):
        job_dir = os.path.join(
            base_dir,
            f"{self.date:%y%m%d}",
            self.data_type,
            "phys_bkg",
            f"det_{'_'.join(self.detectors)}",
            f"e{'_'.join(self.echans)}",
        )

        return luigi.LocalTarget(os.path.join(job_dir, "corner_plot.pdf",))

    def run(self):

        with self.input()["params_json"].open() as f:

            param_names = json.load(f)

        safe_param_names = [name.replace("_", " ") for name in param_names]

        if len(safe_param_names) > 1:

            chain = np.loadtxt(self.input()["posteriour"].path, ndmin=2)

            c2 = ChainConsumer()

            c2.add_chain(chain[:, :-1], parameters=safe_param_names).configure(
                plot_hists=False,
                contour_labels="sigma",
                colors="#cd5c5c",
                flip=False,
                max_ticks=3,
            )

            c2.plotter.plot(filename=self.output().path)

        else:
            print(
                "Your model only has one paramter, we cannot make a cornerplot for this."
            )

        # with self.output().temporary_path() as self.temp_output_path:
        #     run_some_external_command(output_path=self.temp_output_path)
