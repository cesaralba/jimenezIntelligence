
LoadFiles

. /home/calba/Dropbox/devel/SuperManagerPython/SACBenv/bin/activate
. /etc/sysconfig/SuperManager

Archivos en /home/calba/devel/SuperManager/*

python ReadMercadoFiles.py /home/calba/devel/SuperManager/SuperManager-201711030825.html

Para actualizar los datos
python GetSuperManagerMerged.py -i /home/calba/devel/SuperManager/datos/SM2017.latest.p -o /tmp/kk1.p -t /home/calba/devel/SuperManager/temporada/ACB2017.latest.p

Últimos ficheros:
* Temporada (estadisticas y calendario): /home/calba/devel/SuperManager/temporada/ACB2017.latest.p
* SuperManager: /home/calba/devel/SuperManager/datos/SM2017.latest.p

## Competiciones y temporadas

* Liga: LACB cod_edicion 28 (1983-1984)
* Copa: CREY cod_edicion  48 (1983-1984) http://www.acb.com/partcopa.php?cod_edicion1=48&x=8&y=6&cod_competicion=CREY
* Supercopa: SCOPA cod_edicion 1 (1985) http://www.acb.com/fichas/SCOPA1001.php (Ojo: el num de competicion no se rellena con ceros)

#TODO

* Evolucion de jugadores e informe previo a la jornada
* TeamGuesser
* Partidos pendientes

