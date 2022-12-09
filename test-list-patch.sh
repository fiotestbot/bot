#!/bin/bash
set -e

abort() {
	echo "Error grabbing patch series"
	exit 1
}

if [ "$#" -lt 2 ]; then
	echo "Usage ${0} branch-name patch-reference [--cleanup]"
	exit 1
fi

BRANCH="$1"
REF="$2"
CLEANUP="$3"
DIR=fio-${REF}
CANONICAL=https://github.com/axboe/fio.git
DEST=(git@github.com:fiotestbot/fio.git)

git clone ${CANONICAL} ${DIR}
cd ${DIR}
b4 am -o - ${REF} | git am -s --whitespace=fix
git checkout -b ${BRANCH}

for d in ${DEST[@]}; do
	git push ${d} ${BRANCH}
done

cd ..
if [ "${CLEANUP}" = "--cleanup" ]; then
	rm -rf ${DIR}
fi
