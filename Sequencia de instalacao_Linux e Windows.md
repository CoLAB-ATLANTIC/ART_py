
===================================   LINUX Ubuntu   ====================================================================================

		Criar e ativar ambiente art numa pasta .venvs/art com python do Ubuntu (como no anaconda)
		-------------------------------------------------------------------------------------------------------------------------------------------

				> sudo apt install python3.12-venv

				> mkdir -p ~/.venvs/art

				> python3 -m venv ~/.venvs/art
				
				> source .venvs/art/bin/activate
				
				> /home/manela/.venvs/art/bin/pip install Pyinstaller
				
				> /home/manela/.venvs/art/bin/pip install -r /home/manela/TransAtlantic/MINERVA/ART_py/python/requirements.txt

        
		Compilar o ART.py	
		--------------------------------------		
		
				> cd /home/maria.fraga/TransAtlantic/MINERVA/ART_py/buildScripts	
				
				> ./build_ubunto.sh
				
				
				O executavel será criado na pasta /buildScripts/dist/art.exe
		
				
		
   
===================================   LINUX   HPC ====================================================================================



		Criar e ativar ambiente com python 3.12 do proprio HPC. 
		-------------------------------------------------------------------------------------------------------------------------------------------

				> spack load python@3.12.7
				
				> pip3 install Pyinstaller
				
        > pip3 install -r /data/mohid/TransAtlantic/MINERVA/ART_py/python/requirements.txt

  
		Compilar o ART.py	
		--------------------------------------		
		
		> cd /data/mohid/TransAtlantic/MINERVA/ART_py/buildScripts	
		
		> ./build_HPC.sh
		
		
		O executavel será criado na pasta /buildScripts/dist/art.exe
		

		
   

===================================   WINDOWS   ====================================================================================



1 - Instalar no miniconda o env python 3.12 e ativa-lo (pode ser outra versão desde que seja 3.)
	 toda a instalação do ART é feita a partir deste env.
	

2 - D:\miniconda3\envs\py312\Scripts> pip install -r F:/MINERVA/ART_py/python/requirements_windows.txt

3 - Na pasta: ART_py\buildScripts executar:

		D:\OneDrive\TransAtlantic\MINERVA\ART_py\buildScripts\build_windows.bat
	
		Se der problema com o Pyinstaller ir para uma janela dos, activar o ambiente e executar os comandos:
	
		pip uninstall pyinstaller
		pip install https://github.com/pyinstaller/pyinstaller/tarball/develop
	
	
	
		
	