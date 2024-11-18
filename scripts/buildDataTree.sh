#!/bin/bash

set -eu

CONFIGFILE=${DEVSMCONFIGFILE:-/etc/sysconfig/SuperManager}
[ -f ${CONFIGFILE} ] && source ${CONFIGFILE}

if [ ${SM_DEBUGSCRIPTS:-0} = 1 ]
then
  set -vx
fi

BASEDIR=$(cd "$(dirname $(readlink -e $0))/../" && pwd )

if [ -n "${SM_DATADIR}" ] ; then
  ROOTDATA=${SM_DATADIR}
else
  ROOTDATA=${BASEDIR}
fi

mkdir -pv ${ROOTDATA}/{temporada,programa}

