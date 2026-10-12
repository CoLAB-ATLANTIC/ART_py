#!/bin/bash


#===============================================================
# To define the Python3 folder path remove comment (::) from 
# the following line and put the path to the folder.
#===============================================================

root=/data/mohid

art_path=$root/TransAtlantic/MINERVA/ART_py

output_path=$art_path/bin/

#============================
# DO NOT CHANGE BELOW THIS
#============================

spack load python@3.12.7

#spack load miniconda3@24.3.0
#source activate ART

cd $art_path/buildScripts

rm -r build
rm -r dist
rm art.spec


pyinstaller --onefile $art_path/python/art.py --paths=$art_path/python/common/ --paths=$art_path/python/


cd dist
mv art art.exe

cp art.exe $output_path
 
cd ..




