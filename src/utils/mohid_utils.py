'''
Checks MOHID log to verify that the run was successful
'''


def verify_run(filename, messages):
    with open(filename, 'r') as f:
        lines = f.read().splitlines()
        for i in range(-1, -200, -1):
            for message in messages:
                try:
                    if message in lines[i]:
                        return True
                except:
                    return False
    return False

'''
Allows to create dynamic names for the files in static folders for OBC gathering.
Example: if given the datetime object that represents "2019-07-23" for initial_date and "2019-08-12" for final_date
it changes "Hydrodynamic_%Yi-%Mi-%di_%Yf-%Mf-%df" to "Hydrodynamic_2019-07-23_%2019-08-12"
'''


def create_file_name_with_date(filename, initial_date, final_date):
    if '%Yi' in filename:
        filename = filename.replace("%Yi", str(initial_date.year))
    if '%mi' in filename:
        if initial_date.month < 10:
            filename = filename.replace("%mi", "0" + str(initial_date.month))
        else:
            filename = filename.replace("%mi", str(initial_date.month))
    if '%di' in filename:
        if initial_date.day < 10:
            filename = filename.replace("%di", "0" + str(initial_date.day))
        else:
            filename = filename.replace("%di", str(initial_date.day))
    if '%Yf' in filename:
        filename = filename.replace("%Yf", str(final_date.year))
    if '%mf' in filename:
        if final_date.month < 10:
            filename = filename.replace("%mf", "0" + str(final_date.month))
        else:
            filename = filename.replace("%mf", str(final_date.month))
    if '%df' in filename:
        if final_date.day < 10:
            filename = filename.replace("%df", "0" + str(final_date.day))
        else:
            filename = filename.replace("%df", str(final_date.day))
    return filename