
pipEnvInstall: requirements.txt requirements-dev.txt
	python -m pip install -r requirements.txt -r requirements-dev.txt


pipEnvUpdateCheck: requirements.txt requirements-dev.txt
	python -m pip install -U --dry-run -r requirements.txt -r requirements-dev.txt

pipEnvUpdate: requirements.txt requirements-dev.txt
	python -m pip install -U -r requirements.txt -r requirements-dev.txt

pipEnvCheck: requirements.txt requirements-dev.txt
	python -m pip check