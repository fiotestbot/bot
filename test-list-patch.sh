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
CANONICAL=https://github.com/axboe/fio.git
DEST=(git@github.com:vincentkfu/fio.git)

rm -rf ${DIR}
git clone ${CANONICAL} ${DIR}
cd ${DIR}
b4 am -o - ${REF} | git am -s --whitespace=fix
git checkout -b ${BRANCH}

for d in ${DEST[@]}; do
	git push ${d} ${BRANCH}
done
