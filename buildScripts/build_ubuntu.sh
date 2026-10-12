#!/bin/bash


#===============================================================
# To define the Python3 folder path remove comment (::) from 
# the following line and put the path to the folder.
#===============================================================


py_path=$HOME/.venvs/art

art_path=$HOME/ART_py/V3/



#============================
# DO NOT CHANGE BELOW THIS
#============================

cd $art_path/buildScripts

rm -r build
rm -r dist
rm art.spec

$py_path/bin/pyinstaller --onefile $art_path/python/art.py --paths=$art_path/python/common/ --paths=$art_path/python/


cd dist
mv art art.exe

cp art.exe $HOME/aplica/Deep_Rest_Level1/
 
cd ..




