
import datetime
import os 
import re
import subprocess
import logging
import stat
import time
import pandas as pd 
import shutil

#########################################################################

def modify_end_dat_date(file, new_value):
    changed = False
    with open(file, "r") as f:
        text = f.read()
    f.close
    lines = text.split("\n")
    for i in range(0, len(lines)):
        if re.search("^END", lines[i]):
            changed = True
            lines[i] = '{0:30}{1}'.format("END", ": " + new_value)
    if changed:
        #print("Modifying " + file.__str__() + " END value to " + new_value)
        print()
    else:
        lines.append('{0:30}{1}'.format("END", ": " + new_value))
    text = "\n".join(lines)
    with open(file,"w") as f:
        f.write(text)
    f.close
    return changed


def modify_start_dat_date(file, new_value):
    changed = False
    with open(file, "r") as f:
        text = f.read()
    f.close
    lines = text.split("\n")
    for i in range(0, len(lines)):
        if re.search("^START", lines[i]):
            changed = True
            lines[i] = '{0:30}{1}'.format("START", ": " + new_value)
    if changed:
        #print("Modifying " + file.__str__() + " START value to " + new_value)
        print()
    else:
         lines.append('{0:30}{1}'.format("START", ": " + new_value))
    text = "\n".join(lines)
    with open(file,"w") as f:
        f.write(text)
    f.close
    return changed


def date_to_julday(date):

    ts = pd.Timestamp(year = date.year,  month = date.month, day = date.day, 
           hour = date.hour, minute=date.minute, second=date.second)
    juld = ts.to_julian_date()
    return juld

def julday_to_date(juld):
    date = pd.to_datetime(juld, unit='D', origin='julian')
    return date

def create_file_name_with_date(filename, initial_date, final_date):
    if '%Yi' in filename:
        filename = filename.replace("%Yi", str(initial_date.year))
    if '%Mi' in filename:
        if initial_date.month < 10:
            filename = filename.replace("%Mi", "0" + str(initial_date.month))
        else:
            filename = filename.replace("%Mi", str(initial_date.month))
    if '%Di' in filename:
        if initial_date.day < 10:
            filename = filename.replace("%Di", "0" + str(initial_date.day))
        else:
            filename = filename.replace("%Di", str(initial_date.day))
    if '%Yf' in filename:
        filename = filename.replace("%Yf", str(final_date.year))
    if '%Mf' in filename:
        if final_date.month < 10:
            filename = filename.replace("%Mf", "0" + str(final_date.month))
        else:
            filename = filename.replace("%Mf", str(final_date.month))
    if '%Df' in filename:
        if final_date.day < 10:
            filename = filename.replace("%Df", "0" + str(final_date.day))
        else:
            filename = filename.replace("%Df", str(final_date.day))
    return filename

#########################################################################

path_work = os.getcwd() 

logfolder = "Logs"
isExist = os.path.exists(logfolder)
if not isExist:
    os.makedirs(logfolder)

#--------------------------------------------------
#  Reading the imput file
#--------------------------------------------------

with open("control_art.dat", "r") as file:

    file_lines = file.readlines()
    number_of_lines = len(file_lines)
    
    for n in range(0,number_of_lines):
        line = file_lines[n]        
       
        if re.search("^START.+:", line):
            StartDate = line.split()    
        elif re.search("^END.+:", line):
            EndDate = line.split()
            
        elif re.search("^USE_LINUX.+:", line):    
            use_linux  = int(line.split()[2])  

        elif re.search("^CONFIGURATION_FILE.+:", line):
            configfile = line.split()[2]     

        elif re.search("^TRIGGER_POLLING_RATE.+:", line):
            srate = line.split()[2]
            rate = float(srate)*60.

        elif re.search("^TRIGGER_MAX_WAIT.+:", line):
            stimer = line.split()[2]
            maxwait = float(stimer)*60.

        elif re.search("^NUMBER_OF_RUNS.+:", line):
            #sdays = line.split()
            days_operational = int(line.split()[2])

        #--------------------------------------------------------

        elif re.search("^GETDATA .+:", line):
            
            GETDATA = int(line.split()[2])
        elif re.search("^DATA_FILENAME.+:", line):
            DATA_FILENAME = line.split()[2]
        
        elif re.search("^GETDATA_FOLDER.+:", line):
            GETDATA_FOLDER = line.split()[2]
        
        elif re.search("^DOWNLOAD_DATA_FOLDER.+:", line):
            download_data_folder = line.split()[2]

        elif re.search("^EXTRACT .+:", line):
            EXTRACT = int(line.split()[2])

        elif re.search("^EXTRACT_FILENAME.+:", line):
            EXTRACT_FILENAME = line.split()[2]

        elif re.search("^EXPORT2HDF5_FOLDER.+:", line):
            EXPORT2HDF5_FOLDER = line.split()[2]

        elif re.search("^EXTRACT_DATA_FOLDER.+:", line):
            extract_data_folder = line.split()[2]

        elif re.search("^INTERPOLATE .+:", line):
            INTERPOLATE = int(line.split()[2])

        elif re.search("^INTERPOLATE_FILENAME.+:", line):
            INTERPOLATE_FILENAME = line.split()[2]
        
        elif re.search("^INTERPOLATE_FOLDER.+:", line):
            INTERPOLATE_FOLDER = line.split()[2]

        elif re.search("^INTERPOLATE_DATA_FOLDER.+:", line):
            interpolate_data_folder = line.split()[2]

        elif re.search("^SPLIT .+:", line):
      
            SPLIT = int(line.split()[2])

        elif re.search("^SPLIT_FILENAME.+:", line):
            
            SPLIT_FILENAME = line.split()[2]
        
        elif re.search("^SPLIT_FOLDER.+:", line):
            SPLIT_FOLDER = line.split()[2]
        
        elif re.search("^SPLIT_DATA_FOLDER.+:", line):
            split_data_folder = line.split()[2]

        elif re.search("^GLUE_RESULTS.+:", line):
            GLUE_RESULTS= int(line.split()[2])

        elif re.search("^GLUE_NUM_FILES.+:", line):
            
            GLUE_NUM_FILES = int(line.split()[2])

            GLUE_FILENAME = [""] * GLUE_NUM_FILES
            path_glue     = [""] * GLUE_NUM_FILES

            # vamos trabalhar com linhas "limpas" (sem \n) mas mantendo ordem
            clean_lines = [l.strip() for l in file_lines]

            for i in range(GLUE_NUM_FILES):
                begin_tag = f"<begin_glue_{i+1}>"
                end_tag   = f"<end_glue_{i+1}>"

                # encontra onde começa o bloco
                try:
                    ibeg = clean_lines.index(begin_tag)
                except ValueError:
                    raise ValueError(f"Não encontrei {begin_tag} no control_art.dat")

                # valida que o bloco tem pelo menos 2 linhas a seguir
                if ibeg + 2 >= len(clean_lines):
                    raise ValueError(f"Bloco {begin_tag} incompleto (faltam linhas de filename/path).")

                # lê exatamente as 2 linhas após o begin_tag
                GLUE_FILENAME[i] = clean_lines[ibeg + 1].strip()
                path_glue[i]     = clean_lines[ibeg + 2].strip()

                # (opcional) valida que existe o end_tag algures depois
                try:
                    iend = clean_lines.index(end_tag, ibeg + 1)
                except ValueError:
                    raise ValueError(f"Não encontrei {end_tag} para fechar o bloco iniciado em {begin_tag}")

                # (opcional) valida que o end_tag vem depois das 2 linhas esperadas
                if iend < ibeg + 3:
                    raise ValueError(f"Bloco {begin_tag} fechado cedo demais; esperado 2 linhas entre begin/end.")

        elif re.search("^GLUE_DATA_FOLDER.+:", line):
            glue_data_folder = line.split()[2]
            
            

#------------------------------------------------------------------------------

        elif re.search("^CONVERT_2_NETCDF.+:", line):
            
            CONVERT_2_NETCDF = int(line.split()[2])

            CONVERT2NC_FILENAME = [""] * GLUE_NUM_FILES
            path_NC             = [""] * GLUE_NUM_FILES

            # vamos trabalhar com linhas "limpas" (sem \n) mas mantendo ordem
            clean_lines = [l.strip() for l in file_lines]

            for i in range(GLUE_NUM_FILES):
                begin_tag = f"<begin_convert_{i+1}>"
                end_tag   = f"<end_convert_{i+1}>"

                # encontra onde começa o bloco
                try:
                    ibeg = clean_lines.index(begin_tag)
                except ValueError:
                    raise ValueError(f"Não encontrei {begin_tag} no control_art.dat")

                # valida que o bloco tem pelo menos 2 linhas a seguir
                if ibeg + 2 >= len(clean_lines):
                    raise ValueError(f"Bloco {begin_tag} incompleto (faltam linhas de filename/path).")

                # lê exatamente as 2 linhas após o begin_tag
                CONVERT2NC_FILENAME[i] = clean_lines[ibeg + 1].strip()
                path_NC[i]     = clean_lines[ibeg + 2].strip()

                # (opcional) valida que existe o end_tag algures depois
                try:
                    iend = clean_lines.index(end_tag, ibeg + 1)
                except ValueError:
                    raise ValueError(f"Não encontrei {end_tag} para fechar o bloco iniciado em {begin_tag}")

                # (opcional) valida que o end_tag vem depois das 2 linhas esperadas
                if iend < ibeg + 3:
                    raise ValueError(f"Bloco {begin_tag} fechado cedo demais; esperado 2 linhas entre begin/end.")

#------------------------------------------------------------------------------
            
        elif re.search("^NC_DATA_FOLDER.+:", line):
            nc_data_folder = line.split()[2]

        elif re.search("^MERGE_NC_FILES.+:", line):
            MERGE_NC_FILES = int(line.split()[2])

        elif re.search("^CONVERT2NC_FINAL_FILENAME.+:", line):
            CONVERT2NC_FINAL_FILENAME = line.split()[2]

        
        elif re.search("^SEND_NC_FILE.+:", line):
            SEND_NC_FILE = int(line.split()[2])

        elif re.search("^SEND_FOLDER.+:", line):
            SEND_FOLDER = line.split()[2]
            
            

        elif re.search("^BACKUP_FORCASTING.+:", line):
            BACKUP_FORCASTING = int(line.split()[2])
        elif re.search("^BACKUP_SOFTWARE_FOLDER.+:", line):
            BACKUP_SOFTWARE_FOLDER = line.split()[2]
        elif re.search("^BACKUP_DIR.+:", line):
            BACKUP_DIR = line.split()[2]
file.close


#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

if use_linux == 1:
    slash = "/"
    extensao = ".sh"
else:
    slash = "\\"
    extensao = ".bat"


   #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++    

start = datetime.datetime(int(StartDate[2]),int(StartDate[3]),int(StartDate[4]),int(StartDate[5]),0,0)
end =   datetime.datetime(int(EndDate[2]),int(EndDate[3]),int(EndDate[4]),int(EndDate[5]),0,0)

#--------------------------------------------------
#  Logging information to screen and file
#--------------------------------------------------

logfile = logfolder + "/" + create_file_name_with_date("Control_art_%Yi-%Mi-%Di.log", start, end)

logger = logging.getLogger(__name__)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(logfile, mode="w", encoding="utf-8")

logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.handlers

logger.setLevel("INFO")

formatter = logging.Formatter(
                            "{asctime} - {levelname} - {message}",
                            style="{",
                            datefmt="%Y-%m-%d %H:%M:%S",
                            )

console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

#--------------------------------------------------
#  Data inicial do run
#--------------------------------------------------

string_data = "START   : %Yi %Mi %Di 0 0 0"
start_string = create_file_name_with_date(string_data, start, start)

string_only = "%Yi %Mi %Di 0 0 0"
start_only = create_file_name_with_date(string_only, start, start)

# ---- CONTROL.DAT FILE
with open(("control.dat"),"w") as file:
    file.write(start_string + "\n" )
    file.write("NUMBER_OF_RUNS : " + str(days_operational) + "\n" )    
file.close

# ---- CONTROL_WRF.DAT FILE
string_wrf=create_file_name_with_date("%Yi %Mi %Di", start, start)
with open(("control_wrf.dat"),"w") as file:
    file.write(string_wrf + "\n" )
file.close

diajini=date_to_julday(start)
diajfim=date_to_julday(end)

current_date = start
diaj = diajini

#--------------------------------------------------
#  Loop principal
#--------------------------------------------------

frase="ART RUN FINISHED"
conteudo="treta"
check_data = 1

nn=0
while diaj <=  diajfim:
    
    logger.info('')
    logger.info('-------------------------------------------------')
    logger.info("Running control_art for day: " + string_wrf)
    logger.info('-------------------------------------------------')

    run_model = 0

    # ---- GET_WRF DATA -----------
    if GETDATA == 1:

        logger.info("Downloading data  file")

        # Get wrf nc file
        os.chdir(GETDATA_FOLDER)
        subprocess.call(['sh', "Get_wrf2.sh"])
        os.chdir(path_work)
 
    if check_data == 1:  

        
        
        # Check file exists
        file_path = download_data_folder + create_file_name_with_date(DATA_FILENAME, current_date, current_date)
        if os.path.exists(file_path):
            logger.info( "INFO - SUCCESSFUL" + " checkink data " )
        else:
          logger.info("ERROR: Data file " + file_path + " not exist!!!" )
          break 
          
                    
    
    if INTERPOLATE == 1:
    
        logger.info("Interpolating nc file for the mohid grid" )
        
        # -------  Interpolate to Azores grid -------------------
        os.chdir(INTERPOLATE_FOLDER)
        subprocess.call(['sh', "Interpolate_run.sh"]) 

        # Check file exists
        file_path = interpolate_data_folder + create_file_name_with_date(INTERPOLATE_FILENAME, current_date, current_date)
        if os.path.exists(file_path):
            logger.info( "INFO - SUCCESSFUL" + " interpolated file " + file_path )
 
        else:
            logger.info("ERROR: interpolated file " + file_path + " not exist!!!" )
            break

        os.chdir(path_work)
    
    
    if EXTRACT == 1:
        
       
        logger.info("Converting wrf nc file to HDF5" )

        # -------  Export to hdf5 -------------------
        os.chdir(EXPORT2HDF5_FOLDER)
        subprocess.call(['sh', "Export2hdf5_run.sh"]) 

        # Check file exists
        file_path = extract_data_folder + create_file_name_with_date(EXTRACT_FILENAME, current_date, current_date)
        
        
        if os.path.exists(file_path):
            logger.info( "INFO - SUCCESSFUL" + " Converting the interpolated file " + file_path )
        else:
            logger.info("ERROR: extract file " + file_path + " not exist!!!" )
            break
                
        os.chdir(path_work)

    if SPLIT == 1:
        
        logger.info("Spliting wrf file" )

        # -------  Split interpolate files -------------------

        os.chdir(SPLIT_FOLDER)
        subprocess.call(['sh', "HDF5Extractor_run.sh"]) 

        # Check file exists
        diajtreta= diaj-1
        nfile=0
        for i in range(0, days_operational):

            diajtreta = diajtreta + 1

            date_aux = julday_to_date(diajtreta)
            file_path = split_data_folder + create_file_name_with_date(SPLIT_FILENAME, date_aux, date_aux)
                                    
            if os.path.exists(file_path):
                nfile=nfile+1
        
        if nfile == days_operational:
            logger.info( "INFO - SUCCESSFUL" + " Spliting the results" )
            run_model=1
        else:
            logger.info("ERROR: Split files with problems!!!" )
            break
            
        os.chdir(path_work)    
        
    run_model = 1  
    
    # --- Run the model -------------------

    if run_model == 1:

        logger.info("Runing the model")

        os.chdir(path_work)

        timer=maxwait
        nn=nn + 1    
        file_run="run_mohid" + str(nn) + extensao
        file_log="out"+ str(nn) + ".log"
        
        if use_linux == 1: 

            with open((file_run),"w") as file:
                
                file.write("#!/bin/bash" + "\n" )
                file.write("\n" )
    #            file.write("#SBATCH --job-name=Azores6km" + "\n" )
    #            file.write("#SBATCH --time=6-23:00:00" + "\n" )
    #
    #            file.write("#SBATCH --nodes=1" + "\n" )
    #            file.write("#SBATCH --ntasks=16" + "\n" )
    #            file.write("#SBATCH --ntasks-per-node=16" + "\n" )
    #            file.write("#SBATCH --cpus-per-task=1" + "\n" )
    #            file.write("#SBATCH --hint=multithread" + "\n" )  
    #            file.write("#SBATCH --threads-per-core=2" + "\n" )
    #            file.write("#SBATCH --mem=50GB" + "\n" )   
    #            file.write("#SBATCH --output=" + file_log + "\n" )
    #            file.write("#SBATCH --nodelist=vasco-da-gama" + "\n" ) 
    #            file.write("\n" )
                file.write("source /data/mohid/Mohid/mohid_run_mpi_intel.env" + "\n" )
                file.write("./art.exe " + configfile + "\n" )        
            file.close

            os.chmod(file_run, stat.S_IRWXU)
            
            subprocess.call(['sh', file_run])      ## runing mohid  #aqui

        else:

            with open((file_run),"w") as file:
                file.write("\n" )
                file.write("art.exe " + configfile + "\n" )        
            file.close

            subprocess.call(['sbatch', file_run])  ## runing mohid #aqui
      
        #-------------------    para tirar depois quando o sbatch estiver a correr ----------------
      
        diaj_control1 =  diaj + days_operational - 1
        diaj_control2 =  diaj_control1 + 1
        
        diaj_date1 = julday_to_date(diaj_control1)
        diaj_date2 = julday_to_date(diaj_control2)        
        
        ###file_logaux = "/home/maria.fraga/aplica/Azores6km/Azores_Level2/Logs/Triggers/%Yi-%Mi-%Di_%Yf-%Mf-%Df.dat"
        file_logaux = logfolder + "/Triggers/%Yi-%Mi-%Di_%Yf-%Mf-%Df.dat" 
        
        file_log = create_file_name_with_date(file_logaux, diaj_date1, diaj_date2)
        frase= "STATUS                        : FINISHED"
        
 
        #-------------------    ate aqui ----------------
        
        finished = False
        sucess=0
        
        finished = True  # aqui
        while not finished:
            
            try:
                with open(file_log, "r") as file:
                    conteudo = file.read()
                file.close
            except: 
                continue
    
            index = conteudo.find(frase)

            if index > -1:
                sucess = 1
                finished=True
            else:
                time.sleep(rate)  
                timer = timer - rate
                if timer < 0:
                    break
       
        sucess = 1 #aqui
        if sucess == 1:

            logger.info("SUCCESSFUL - running the model")

            run_next_day = 0

            #--------------------------------------------------
            #  GLUE dos ficheiros hdf5
            #--------------------------------------------------

            if GLUE_RESULTS == 1:


                isExist = os.path.exists(glue_data_folder)
                if not isExist:
                    os.makedirs(glue_data_folder)                  

                n_glue=0

                for i in range(GLUE_NUM_FILES):

                 
                    file_run =  path_glue[i] + "run_GLUE.sh"
                    file_glue = path_glue[i] + "GetInputData.dat"

                    diaj_aux = diaj + days_operational - 1
                    date_aux = julday_to_date(diaj_aux)
                    date_aux_string = create_file_name_with_date("%Yf %Mf %Df 0 0 0", current_date, date_aux)

                    #aqui
                    changed_start=modify_start_dat_date(file_glue, start_only)
                    changed_end  =modify_end_dat_date(file_glue, date_aux_string)
                    
                    
                    logger.info("Gluing the results for file: " + str(i+1))

                    #aqui
                    os.chdir(path_glue[i])
                    subprocess.call(['sh', file_run])  ## runing glue aqui
                    
                    # # Check file exists
                    file_path = glue_data_folder + create_file_name_with_date(GLUE_FILENAME[i], current_date, current_date)
                    
                    if os.path.exists(file_path):
                        n_glue = n_glue + 1
                   
                if n_glue == GLUE_NUM_FILES:
                    run_next_day = 1
                else:
                    logger.info("ERROR: not Gluing the results to HDF5 file" )
                    break
                  
                os.chdir(path_work)
                
            #--------------------------------------------------
            #  Convert_2_NETCDF
            #--------------------------------------------------
            
            if CONVERT_2_NETCDF == 1:
               
                isExist = os.path.exists(nc_data_folder)
                if not isExist:
                    os.makedirs(nc_data_folder)                  
 
 
                n_convert=0

                for i in range(GLUE_NUM_FILES):
                 
                    logger.info("Converting the results to NC file:: " + str(i+1) )

                    file_run = path_NC[i] + "Export2netcdf_run.sh"
                    file_NC =  path_NC[i] + "Export2netcdf.dat"
                    
                    #aqui               
                    changed_start=modify_start_dat_date(file_NC, start_only)
                    changed_end  =modify_end_dat_date(file_NC, start_only)
                    
                    os.chdir(path_NC[i])
                    subprocess.call(['sh', file_run])  ## runing convert_2_ nc #aqui
                    
                    # Check file exists
                    file_path = nc_data_folder + create_file_name_with_date(CONVERT2NC_FILENAME[i], current_date, current_date)
                    if os.path.exists(file_path):
                        n_convert = n_convert + 1

                if n_convert == GLUE_NUM_FILES:
                   run_next_day = 1
                else:
                  logger.info("ERROR: not Convert to nc file" )
                  break
                  
                os.chdir(path_work)
                
                if MERGE_NC_FILES  == 1:

                    bat_nco = "merge_nco" + extensao
                    file_out = nc_data_folder + create_file_name_with_date(CONVERT2NC_FINAL_FILENAME,current_date,current_date)

                    hydro_nc = nc_data_folder + create_file_name_with_date(CONVERT2NC_FILENAME[0], current_date, current_date)
                    water_nc = nc_data_folder + create_file_name_with_date(CONVERT2NC_FILENAME[1], current_date, current_date)
                    out1_nc = "lixo1.nc"
                    out2_nc = "lixo2.nc"

                    if use_linux == 1: 

                        with open((bat_nco),"w") as file1:
                            shutil.copyfile(water_nc, out1_nc)
                            file1.write("ncks -O -C -v temperature,time,lat,lon,mask " + water_nc + " " + out1_nc +  "\n" )
                            file1.write("ncks -A -C -v u,v,time,lat,lon,mask " + hydro_nc + " " + out1_nc +  "\n" )
                            file1.write("ncwa -a depth " + out1_nc + " " + out2_nc  +  "\n" )
                            file1.write("cp " + out2_nc + " " + file_out +  "\n" )
                            file1.write("rm -f " + water_nc + "\n" )
                            file1.write("rm -f " + hydro_nc + "\n" )
                            file1.write("rm -f " + out1_nc + "\n" )
                            file1.write("rm -f " + out2_nc + "\n" )
                        file1.close

                        os.chmod(bat_nco, stat.S_IRWXU)

                        try:
                            subprocess.call(['sh', './'+bat_nco])
                            logger.info("SUCCESSFUL - merging nc files")
                        except:
                            logger.error("NOT SUCCESSFUL -  merging to file: " + file_out)

                    else:

                        with open((bat_nco),"w") as file1:

                            shutil.copyfile(water_nc, "nco/" + out1_nc)
                            file_out=file_out.replace("/", slash)
                            water_nc=water_nc.replace("/", slash)
                            hydro_nc=hydro_nc.replace("/", slash)
 
                            file1.write("cd nco" + "\n" )
                            file1.write("ncks -O -C -v temperature,time,lat,lon,mask " + water_nc + " " + out1_nc +  "\n" )
                            file1.write("ncks -A -C -v u,v,time,lat,lon,mask " + hydro_nc + " " + out1_nc +  "\n" )
                            file1.write("ncwa -a depth " + out1_nc + " " + out2_nc  +  "\n" )
                            
                            file1.write("copy " + out2_nc + " " + file_out +  "\n")
                            file1.write("del  " + out1_nc + "\n" )
                            file1.write("del  " + out2_nc + "\n" )
                            
                            file1.write("cd .." + "\n" )
                            file1.write("del " + water_nc + "\n" )
                            file1.write("del " + hydro_nc + "\n" )
                        
                        file1.close

                        try:
                            subprocess.run(bat_nco)
                            logger.info("SUCCESSFUL - merging the nc files" )
                        except:
                            logger.error("NOT SUCCESSFUL - merging to file: " + file_out)


            if SEND_NC_FILE == 1:
            
                path_NC_folder = SEND_FOLDER

                logger.info("Sending mohid file to wrf site")

                os.chdir(path_NC_folder)
                
                file_run="send_mohid2wrf.sh"
                
                subprocess.call(['sh', file_run])  #PUT the file mohid2wrf in the site 

                file_sending_log="sending.log"

                if os.stat(file_sending_log).st_size==0:
                    run_next_day = 1
                else:
                    logger.info("ERROR: not sending mohid file to wrf sitw" )
                    break

                os.chdir(path_work)
                

            if BACKUP_FORCASTING == 1:
                    
                    logger.info("Bakuping the forecasting results" )

                    file_run = BACKUP_SOFTWARE_FOLDER + "Copy_several_files_run.sh"
                    file_NC =  BACKUP_SOFTWARE_FOLDER + "GetInputData.dat"
                    
                    #aqui               
                    changed_start=modify_start_dat_date(file_NC, start_only)
                    changed_end  =modify_end_dat_date(file_NC, start_only)
                    
                    os.chdir(BACKUP_SOFTWARE_FOLDER)
                    subprocess.call(['sh', file_run])  ## runing convert_2_ nc #aqui
                    
                    os.chdir(path_work)                    

            run_next_day = 1  #aqui
            if run_next_day == 1:

                #--------------------------------------------------
                #  next day
                #--------------------------------------------------
                os.chdir(path_work)
                
                diaj = diaj + 1

                current_date =  julday_to_date(diaj)
                
                start = current_date

                start_string = create_file_name_with_date(string_data, current_date, current_date)
                start_only  = create_file_name_with_date(string_only, current_date, current_date)

                with open(("control.dat"),"w") as file:
                    file.write(start_string + "\n" )
                    file.write("NUMBER_OF_RUNS : " + str(days_operational) + "\n" )
                file.close

                string_wrf=create_file_name_with_date("%Yi %Mi %Di", current_date, current_date)
                with open(("control_wrf.dat"),"w") as file:
                    file.write(string_wrf + "\n" )
                file.close

            else:
                logger.error("NOT SUCCESSFUL -  running control_art for day: " + start_string)
                break
        







            
