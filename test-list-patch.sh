#!/bin/bash

abort() {
	echo "Error grabbing patch series"
	exit 1
}

if [ "$#" -ne 2 ]; then
	echo "Usage ${0} branch-name patch-reference"
	exit 1
fi

BRANCH="$1"
REF="$2"
DIR=fio-${BRANCH}
TEMP_FILE=$(mktemp)

rm -rf ${DIR}
git clone ssh://vincentkfu@git.kernel.dk/data/git/fio.git ${DIR}
b4 am ${REF} &> ${TEMP_FILE} || abort
MBX=$(tail ${TEMP_FILE} -n 1 | tr -s " " | cut -d " " -f 4)
cd ${DIR}
git am -s --whitespace=fix .${MBX}
git checkout -b ${BRANCH}
git push git@github.com:vincentkfu/fio.git ${BRANCH}
