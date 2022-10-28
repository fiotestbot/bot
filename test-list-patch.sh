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

rm -rf ${DIR}
git clone ssh://vincentkfu@git.kernel.dk/data/git/fio.git ${DIR}
cd ${DIR}
b4 am -o - ${REF} | git am -s --whitespace=fix
git checkout -b ${BRANCH}
git push git@github.com:vincentkfu/fio.git ${BRANCH}
