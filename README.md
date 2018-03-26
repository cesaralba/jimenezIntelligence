
## Preparar el entorno

* **Ejecución**
~~~
cd ALGUNOTROSITIO
python3 -mvenv SACBenv
source ALGUNOTROSITIO/SACBenv/bin/activate
pip install -r requirements.txt
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
source /etc/sysconfig/SuperManager
~~~

* **Desarrollo** (desarrollo incluye ejecución)
~~~
source ALGUNSITIO/SACBenv/bin/activate
source /etc/sysconfig/SuperManager
~~~


## Invocaciones

Archivos en */home/calba/devel/SuperManager/**

* Procesa mercado (mayormente que funciona el módulo)
~~~
python ReadMercadoFiles.py /home/calba/devel/SuperManager/SuperManager-201711030825.html
~~~
Para actualizar los datos:
* Actualiza datos Temporada
~~~
python DescargaTemporada.py -e 62 -i /home/calba/devel/SuperManager/temporada/ACB2017.latest.p -o /tmp/kk1.p
~~~
* Actualiza datos Supermanager (mercado incluido)
~~~
python GetSuperManagerMerged.py -i /home/calba/devel/SuperManager/full/SM2017.latest.p -o /tmp/kk1.p -t /home/calba/devel/SuperManager/temporada/ACB2017.latest.p
~~~
* Genera la información par Supermanager
~~~
python InformeSuperManager.py -i /home/calba/devel/SuperManager/full/SM2017.latest.p -t /home/calba/devel/SuperManager/temporada/ACB2017.latest.p
~~~

## Últimos ficheros:
* Temporada (estadisticas y calendario): */home/calba/devel/SuperManager/temporada/ACB2017.latest.p*
* SuperManager: */home/calba/devel/SuperManager/full/SM2017.latest.p*

## Competiciones y temporadas

* Liga: LACB cod_edicion 28 (1983-1984)
* Copa: CREY cod_edicion  48 (1983-1984) http://www.acb.com/partcopa.php?cod_edicion1=48&x=8&y=6&cod_competicion=CREY
* Supercopa: SCOPA cod_edicion 1 (1985) http://www.acb.com/fichas/SCOPA1001.php (Ojo: el num de competicion no se rellena con ceros)

# TODO

* Informe evolucion de jugadores (SM)
* Validacion de resultados de WWW
* Captura de fechas de partidos futuros
* Informe previo a la jornada
* Detección Playoff
* Clasificacion
* Partidos pendientes
* TeamGuesser
* Estadisticas historicas (descargarlo todo, vamos)
* Cuenta atras
