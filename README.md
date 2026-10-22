# ART

ART (Automatic Running Tool) automates the execution of numerical models (MOHID Water, SWAN, WW3...) in
hindcast or operational mode. A single YAML file describes the simulation period, the model to run and the
pre/post-processing tools to chain around it; ART then loops over every period and, for each one, runs
pre-processing → model → post-processing, with logging, email notifications and trigger files to synchronize
with other runs.

```bash
cd src
python art.py /path/to/art.yaml
```

or 

```bash
python path/to/art.py /path/to/art.yaml
```

## YAML sections

### `ART`
General behaviour of the run.
- `PROJECT_PATH`, `LOG.FOLDER_PATH`: where logs, trigger and condition files are written.
- `MODULE`: which models to run (`MOHID_WATER`, `SWAN`, `WW3`, ...). Any other enabled name runs as a
  non-standard module (only pre/post-processing).
- `PRE_PROCESSING`, `RUN_SIMULATION`, `POST_PROCESSING`: switch each stage of the cycle on/off.
- `RUN_TWICE`: repeat each period once more.
- `EMAIL_NOTIFICATION`: `ENABLE`, `USER`, `PASSWORD`, `RECEIVERS` to get the run log by email on success/error.

### `SIMULATION`
Simulation period and how it is split.
- `OPERATIONAL_MODE`: `1` runs `NUMBER_OF_RUNS` periods starting `REF_DAYS_TO_START` days from today;
  `0` (hindcast) runs from `START_DATE` to `END_DATE`.
- `DAYS_PER_RUN`: length of each period. `MONTH_MODE` makes periods follow calendar months.
- `AUTOMATIC_DATE`: take the dates from `control.dat` (next to the YAML) instead.

### `TRIGGER`
Synchronization between ART runs and blocks through `.dat` status files. It can be set at top level (model run)
or inside any pre/post-processing block.
- `ENABLE`, `WRITE_TRIGGER`: write `Running`/`Finished` status to `<LOG.FOLDER_PATH>/triggers/<name>/`.
- `CHECK_ALL`, `FOLDERS_TO_WATCH`, `TRIGGER_MAX_WAIT_H`, `TRIGGER_POLLING_RATE_S`: wait for other runs to finish.
- `CONDITION_SCRIPT`, `CONDITION_DAT`: run an external script that decides (`True`/`False`) whether the run goes on.

See [docs/trigger_logic.md](docs/trigger_logic.md) for details.

### `MOHID_WATER`
Runs MOHID Water: writes `Model_X.dat` and the `.dat` keywords per model, gathers restart files, runs the model
(serial, `OPENMP` or `MPI` + MohidDDC) and backs up the results.
- `MAIN_PATH`, `EXE_PATH`, `TREE_PATH`.
- `MODELS`: one entry per nested model (`NAME`, `PATH`, `DT`, `STORAGE_PATH`, `RESULTS_LIST`, `mohidwater.dat`...).
- `MPI`, `OPENMP`: parallel execution settings.

### `PRE_PROCESSING`
Named blocks of external tools run before the model, in order, for each period (e.g. downloading and
interpolating forcing). Per block:
- `RUN`, `EXE_PATH`, `FLAGS`.
- `DAT_DATE_CHANGE` + `CONFIG_FILEPATH`: set the tool's `START`/`END` to the current period.
- `OUTPUT_TO_FILE` + `OUTPUT_FILEPATH`: redirect the tool output.
- `LOGFILE_CHECK`: log file whose `NOT SUCCESSFULL` marks the block as failed.
- `TRIGGER`: block-level trigger (see above).

### `POST_PROCESSING`
Same block structure as `PRE_PROCESSING`, run after the model (e.g. gluing HDF5 results, converting to NetCDF,
sending/backing up files).
