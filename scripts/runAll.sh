#!/bin/bash

set -eu

BASEDIR=$(cd "$(dirname $(readlink -e "$0"))" && pwd )

echo "Ejecución $(date)"

CONFIGFILE=${DEVSMCONFIGFILE:-/etc/sysconfig/SuperManager}
[ -f "${CONFIGFILE}" ] && source "${CONFIGFILE}"

bash "${BASEDIR}/buildVENV.sh"

bash "${BASEDIR}/buildDataTree.sh"

bash -vx "${BASEDIR}/checkScripts.sh" || true
echo "Get Temporada"
bash "${BASEDIR}/getTemporada.sh"
echo "Final ejecución $(date)"
