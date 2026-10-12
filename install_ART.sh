#!/bin/bash

#art_path=$HOME/Mohid/ART_tools/ART_py
art_path=$HOME/TransAtlantic/MINERVA/ART_py

output_path=$art_path/bin



#============================
# DO NOT CHANGE BELOW THIS
#============================

cd $HOME

mkdir -p $output_path

#---- Installing python and librarys --------

spack load python@3.12.1

pip3 install Pyinstaller

pip3 install -r $art_path/python/requirements.txt


#---- Compiling --------

cd $art_path/buildScripts


rm -r build
rm -r dist
rm art.spec

pyinstaller --onefile $art_path/python/art.py --paths=$art_path/python/common/ --paths=$art_path/python/

cd dist
mv art art.exe

cp art.exe $output_path/
 
cd ..


