Current trigger logic is as follows:

- Subtask-based trigger: each subtask can have its own trigger logic, which is defined in the subtask's configuration.

- Trigger class (`python/common/trigger.py`): the old `check_triggers` / `write_trigger` functions of `pre_processing.py` were moved into a `Trigger` class, built once per block (`Trigger(yaml, logger, block, section='PRE_PROCESSING')`). It reads the block's `TRIGGER` subtree only when `ENABLE` is set; otherwise every method returns without doing anything. `post_processing.py` still uses the old functions.

- Execution order per block in `pre_processing.execute`:
  1. `trigger.check(days_run, current_initial_date)`: waits for the trigger files of the dependencies.
  2. `trigger.check_condition(current_initial_date, current_final_date)`: runs the condition script (see below).
  3. `trigger.write(..., status="Running")` before running the block's executable.
  4. `trigger.write(..., status="Finished")` after it, when the log check (if any) passes.

- `check`: only runs when `CHECK_ALL` is true and on the first run (`days_run == 0`). For each folder in `FOLDERS_TO_WATCH` it waits for `<folder><START>_<END>.dat` to exist and then for its `STATUS` line to be `FINISHED`. If the maximum waiting time is reached, it logs it and resumes execution anyway (it never stops the run).

- Time units are now part of the keyword names:
  - `TRIGGER_MAX_WAIT` -> `TRIGGER_MAX_WAIT_H` (hours, default `DEFAULT_MAX_WAIT_H = 6`).
  - `TRIGGER_POLLING_RATE` -> `TRIGGER_POLLING_RATE_S` (seconds, default `DEFAULT_POLLING_RATE_S = 120`).
  - The constants in `mohid/util/constants.py` were renamed accordingly.

- `write`: the trigger files are now written to `<ART.LOG.FOLDER_PATH>/triggers/<block>/<START>_<END>.dat` (before: `<MOHID_WATER.MAIN_PATH>/Logs/Triggers/<block>/`), so it no longer depends on a MOHID Water section. Only written when `WRITE_TRIGGER` is true. The argument was renamed from `stage` to `status`.

- Conditional trigger (`check_condition`), new: a block can be stopped depending on the result of an external Python script. Keywords inside the block's `TRIGGER`:
  - `CONDITION_SCRIPT`: path to the `.py` file to execute.
  - `CONDITION_DAT`: path to the `.dat` file with all the configuration the script needs to compute the condition.
  - `CONDITION_DAT_DATE_CHANGE` (optional, default true): updates `START` / `END` in the `.dat` file to the current run period before executing the script.

  Both `CONDITION_SCRIPT` and `CONDITION_DAT` must be given (one without the other is an error). The script is executed as `python <CONDITION_SCRIPT> <CONDITION_DAT>` with ART's own interpreter, from the script's folder, and all its output is copied to ART's log.

  Contract for the script: the last line it prints must be `True` (condition met) or `False` (not met). Anything printed before is just logged.
  - `True`: execution continues.
  - `False`: raises `TriggerConditionNotMet` (a `ValueError`), so ART's error routine logs it, sends the error email (if configured) and stops the whole run.
  - Script crash (exit code != 0) or a last line other than `True` / `False`: raises a `ValueError` pointing to the script.

  Example (OvertOpXB1p0, `src/regime_watcher.py` prints `True` if any profile has `Regime > REGIME_THRESHOLD` in any day of the period):

  ```yaml
  PRE_PROCESSING:
    Regime_Watcher:
      RUN: 1
      TRIGGER:
        ENABLE: 1
        CONDITION_SCRIPT: /home/franklinayala/applications/OvertOpXB1p0/src/regime_watcher.py
        CONDITION_DAT: /home/franklinayala/applications/OvertOpXB1p0/config/regime_watcher.dat
  ```


Questions

- What's the point of having check_all? all means the entire folders to watch? when would I like to do something different to all?

- What's 'days_run' key for? that logic is quite confusing at the time to make the child model matches the parent's temporal resolution.

- Time units for triggers included in the keywords?

- do we really need the enable? enabling trigger can merely check with the existence of the trigger key, and if it exists, then it's enabled. If not, then it's disabled. 



Further improvements: 

- Path library used everywhere (pathlib.Path) instead of os.path.join, os.path.isdir, etc.

- delete old mohid references in common places.