Current trigger logic is as follows:

- Subtask-based trigger: each subtask can have its own trigger logic, which is defined in the subtask's configuration.


Questions

- What's the point of having check_all? all means the entire folders to watch? when would I like to do something different to all?

- What's 'days_run' key for? that logic is quite confusing at the time to make the child model matches the parent's temporal resolution.

- Time units for triggers included in the keywords?

- do we really need the enable? enabling trigger can merely check with the existence of the trigger key, and if it exists, then it's enabled. If not, then it's disabled. 



Further improvements: 

- Path library used everywhere (pathlib.Path) instead of os.path.join, os.path.isdir, etc.

- delete old mohid references in common places.