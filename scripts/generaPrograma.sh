#!/bin/bash

set -eu

CONFIGFILE=${DEVSMCONFIGFILE:-/etc/sysconfig/SuperManager}
[ -f ${CONFIGFILE} ] && source ${CONFIGFILE}

if [ ${SM_DEBUGSCRIPTS:-0} = 1 ]
then
  set -vx
fi

TARGETCLUB=${1:-RMB}
CLAVEYEAR=${FILEKEY:-2023}
COMPO=${SM_COMPETICION:-ACB}

BASEDIR=$(cd "$(dirname $(readlink -e $0))/../" && pwd )
TODAY=$(date '+%Y%m%d%H%M')

if [ -n "${SM_DATADIR}" ] ; then
  ROOTDATA=${SM_DATADIR}
else
  ROOTDATA=${BASEDIR}
fi

if [ "x${SM_REPO}" = "x" ]
then
  echo "ORROR: No se ha suministrado valor para SM_REPO. Adios."
  exit 1
fi

BRANCHNAME=${USEBRANCH:-master}
WRKDIR="${ROOTDATA}/wrk"
if [ ! -d ${WRKDIR} ]
then
  mkdir -p ${WRKDIR}
  git clone -q --branch ${BRANCHNAME} ${SM_REPO} ${WRKDIR}

  if [ $? != 0 ]
  then
    echo "$0: Problems with GIT. Bye"
    exit 1
  fi
fi

VENV=${VENVHOME:-"${BASEDIR}/venv"}

if [ -f "${VENV}/bin/activate" ] ; then
  source "${VENV}/bin/activate"
else
  echo "ORROR: Incapaz de encontrar activador de virtualenv"
fi

ORIGSMFILE="${ROOTDATA}/temporada/${COMPO}${CLAVEYEAR}.latest.p"
REPORTDIR="${ROOTDATA}/programa/${COMPO}-${CLAVEYEAR}"

DESTFILENAME="sigPartido${COMPO}-${TARGETCLUB}-ACB${CLAVEYEAR}-${TODAY}.pdf"
DESTFILE="${REPORTDIR}/${DESTFILENAME}"

[ -d ${REPORTDIR} ] || mkdir -pv ${REPORTDIR}
if [ $? != 0 ]
then
  echo "$0: Problems creating ${REPORTDIR}"
  exit 1
fi

export PYTHONPATH=${PYTHONPATH:-""}:${WRKDIR}

python ${WRKDIR}/bin/generaPrograma.py -t ${ORIGSMFILE} -e ${TARGETCLUB} -o ${DESTFILE}

if [ $? = 0 ]
then
  echo "$0: Generado ${DESTFILE}"
fi


