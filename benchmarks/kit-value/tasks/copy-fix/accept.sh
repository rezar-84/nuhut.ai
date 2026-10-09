#!/bin/sh
# usage: accept.sh <workspace>
set -eu
cd "$1"
grep -q '^## Installation$' README.md
! grep -q 'Instalation' README.md
