::===============================================================
:: To define the Python3 folder path remove comment (::) from 
:: the following line and put the path to the folder.
::===============================================================


rmdir /S /q build
rmdir /S /q dist

del art.spec
del Pipfile*


rem NOTA:: esta instalação deverá ser feita com o ambiente activado, numa janela DOS
rem F:/>cd F:/MINERVA/ART_py/ART_env/Scripts
rem F:/MINERVA/ART_py/ART_env/Scripts>activate
rem e estamos no ambiente activado


set art_path=C:/Projects/ART_py

rem :============================
rem :: DO NOT CHANGE BELOW THIS
rem ::============================

pyinstaller --onefile %art_path%/python/art.py --paths=%art_path%/python/common/ --paths=%art_path%/python/

copy dist/art.exe C:/Projects/ART_py/bin


pause
