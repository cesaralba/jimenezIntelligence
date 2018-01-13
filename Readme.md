
## Preparar el entorno

* **Ejecución**
~~~
cd ALGUNOTROSITIO
python3 -mvenv SACBenv
source ALGUNOTROSITIO/SACBenv/bin/activate
pip install -r requirements-dev.txt
~~~

* **Desarrollo** (desarrollo incluye ejecución)
~~~
cd ALGUNSITIO
python3 -mvenv SACBenv
source ALGUNSITIO/SACBenv/bin/activate
pip install -r requirements-dev.txt
~~~

## Cargar el entorno

* **Ejecución**
~~~
source ALGUNOTROSITIO/SACBenv/bin/activate
~~~

* **Desarrollo** (desarrollo incluye ejecución)
~~~
source ALGUNSITIO/SACBenv/bin/activate
~~~


## LoadFiles

. /home/calba/Dropbox/devel/SuperManagerPython/SACBenv/bin/activate
. /etc/sysconfig/SuperManager

Archivos en /home/calba/devel/SuperManager/*

python ReadMercadoFiles.py /home/calba/devel/SuperManager/SuperManager-201711030825.html

Para actualizar los datos
python GetSuperManagerMerged.py -i /home/calba/devel/SuperManager/full/SM2017.latest.p -o /tmp/kk1.p -t /home/calba/devel/SuperManager/temporada/ACB2017.latest.p

python InformeSuperManager.py -i /home/calba/devel/SuperManager/full/SM2017.latest.p -t /home/calba/devel/SuperManager/temporada/ACB2017.latest.p

Últimos ficheros:
* Temporada (estadisticas y calendario): /home/calba/devel/SuperManager/temporada/ACB2017.latest.p
* SuperManager: /home/calba/devel/SuperManager/full/SM2017.latest.p

## Competiciones y temporadas

* Liga: LACB cod_edicion 28 (1983-1984)
* Copa: CREY cod_edicion  48 (1983-1984) http://www.acb.com/partcopa.php?cod_edicion1=48&x=8&y=6&cod_competicion=CREY
* Supercopa: SCOPA cod_edicion 1 (1985) http://www.acb.com/fichas/SCOPA1001.php (Ojo: el num de competicion no se rellena con ceros)

# TODO

* Codigo de equipo en mercado
    * Murcia, qué hermosa eres
* Informe evolucion de jugadores (SM)
* Captura de fechas de partidos futuros
* Informe previo a la jornada
* Detección Playoff
* Clasificacion
* Partidos pendientes
* TeamGuesser
* Estadisticas historicas (descargarlo todo, vamos)
* Cuenta atras
