#!/bin/bash

set -eu

function soLong {
  MSG=${1:-No msg}
  echo ${MSG}
  exit 1
}

CONFIGFILE=${DEVSMCONFIGFILE:-/etc/sysconfig/SuperManager}
[ -f ${CONFIGFILE} ] && source ${CONFIGFILE}

if [ ${SM_DEBUGSCRIPTS:-0} = 1 ]
then
  set -vx
fi

ME="$(readlink -e $0)"
HEREDIR=$(cd "$(dirname ${ME})" && pwd )
BASEDIR=$(cd "${HEREDIR}/../" && pwd )
TODAY=$(date '+%Y%m%d%H%M')

CLAVEYEAR=${FILEKEY:-2024}
COMPO=${SM_COMPETICION:-LACB}

if [ -n "${SM_DATADIR}" ] ; then
  ROOTDATA=${SM_DATADIR}
else
  ROOTDATA=${BASEDIR}
fi

[ "x${SM_REPO}" = "x" ] && soLong "ORROR: No se ha suministrado valor para SM_REPO. Adios."

WRKDIR="${ROOTDATA}/wrk"
[ -d ${WRKDIR} ] || soLong "ORROR: No se encuentra código descargado. Pruebe a ejecutar ${HEREDIR}/buildVENV.sh . Adios."

VENV=${VENVHOME:-"${BASEDIR}/venv"}
ACTIVATIONSCR="${VENV}/bin/activate"

if [ -f "${ACTIVATIONSCR}" ] ; then
  source "${ACTIVATIONSCR}"
else
  soLong "ORROR: Incapaz de encontrar activador de virtualenv. Pruebe a ejecutar ${HEREDIR}/buildVENV.sh . Adios."
fi

ORIGSMFILE="${ROOTDATA}/temporada/${COMPO}${CLAVEYEAR}.latest.p"
DESTSMFILE="${ROOTDATA}/temporada/${COMPO}${CLAVEYEAR}.newest.p"
DESTSMFILEDATED="${ROOTDATA}/temporada/${COMPO}${CLAVEYEAR}.${TODAY}.p"

if [ -f ${ORIGSMFILE} ]
then
  ORIGPARAM="-i ${ORIGSMFILE}"
else
  ORIGPARAM="-f"
fi

python ${WRKDIR}/bin/DescargaTemporada.py ${ORIGPARAM} -o ${DESTSMFILE} -b

if [ $? = 0 ]
then
  if [ -f ${DESTSMFILE} ]
  then
    cp ${DESTSMFILE} ${DESTSMFILEDATED}
    gzip -f -9 ${DESTSMFILEDATED}
    cp ${DESTSMFILEDATED}.gz ${DESTSMFILE}.gz
    mv ${DESTSMFILE} ${ORIGSMFILE}
  fi
fi
