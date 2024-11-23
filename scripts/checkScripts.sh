#!/bin/bash

set -eu

BASEDIR=$(cd "$(dirname $(readlink -e $0))" && pwd )

CONFIGFILE="${DEVSMCONFIGFILE:-/etc/sysconfig/SuperManager}"
[ -f "${CONFIGFILE}" ] && source ${CONFIGFILE}

if [ -n "${SM_DATADIR}" ] ; then
  ROOTDATA=${SM_DATADIR}
else
  ROOTDATA=${BASEDIR}
fi

WRKDIR="${ROOTDATA}/wrk"
[ -d ${WRKDIR} ] || soLong "ORROR: No se encuentra código descargado. Pruebe a ejecutar ${HEREDIR}/buildVENV.sh . Adios."

LOC="${WRKDIR}/scripts/*"
ECHOLOC=$(echo ${LOC})


if [ ${#LOC} = ${#ECHOLOC} ]
then
  echo "Scripts not found in ${WRKDIR}"
  exit 1
fi

for MYFILE in ${WRKDIR}/scripts/*
do
  FILEHERE=${BASEDIR}/$(basename ${MYFILE} )
  if [ -f ${FILEHERE} ]
  then
    MD5HERE=$(md5sum ${FILEHERE} | awk '{print $1}')
    MD5WRK=$(md5sum ${MYFILE} | awk '{print $1}')

    if [ ${MD5HERE} != ${MD5WRK} ]
    then
      echo "$(readlink -e ${FILEHERE}) and $(readlink -e ${MYFILE}) differ"
      diff ${FILEHERE}  ${MYFILE} || true
    fi
  else
    echo "$(readlink -e ${MYFILE}) does not exist in ${BASEDIR}"
  fi
done