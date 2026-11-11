#!/bin/bash
# The installer's test suite: ./setup.sh against a fake tablet (mock adb,
# heimdall, lsusb and USB console), a local release server and a throwaway
# signing key. Needs no tablet and no network.
#
#   tests/installer/run.sh            every case
#   tests/installer/run.sh PATTERN    the cases whose name contains PATTERN
#   KEEP=1 ...                        keep the work directory
# Work directory: build/test-installer (GTA3_TEST_DIR).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
RUN=${GTA3_TEST_DIR:-$REPO/build/test-installer}
rm -rf "$RUN"
mkdir -p "$RUN"

# shellcheck source=tests/installer/lib.sh
. "$HERE/lib.sh"
# shellcheck source=tests/installer/cases.sh
. "$HERE/cases.sh"

HTTP_PID=
cleanup() {
	[ -n "$HTTP_PID" ] && kill "$HTTP_PID" 2>/dev/null
	[ "${KEEP:-0}" = 1 ] || rm -rf "$RUN"
	return 0
}
trap cleanup EXIT

echo "building fixtures in $RUN ..."
if ! build_fixtures > "$RUN/fixtures.log" 2>&1; then
	cat "$RUN/fixtures.log"
	# a PC without the tools (a container): GTA3_TEST_ALLOW_SKIP=1 reports
	# the suite as skipped instead of failed; the laptop gate never sets it
	if [ "${GTA3_TEST_ALLOW_SKIP:-}" = 1 ] && grep -q "missing on this PC" "$RUN/fixtures.log"; then
		echo "SKIPPED: the installer tests did not run"
		exit 0
	fi
	exit 2
fi

pass=0 failed=()
for t in $(declare -F | awk '{ print $3 }' | grep '^t_'); do
	case $t in *"${1:-}"*) ;; *) continue ;; esac
	CASE=$RUN/cases/$t
	mkdir -p "$CASE"
	printf '%-44s ' "${t#t_}"
	if (
		set -euo pipefail
		CONSOLE_PID=
		trap '[ -n "$CONSOLE_PID" ] && kill "$CONSOLE_PID" 2>/dev/null; true' EXIT
		"$t"
	) > "$CASE/case.log" 2>&1; then
		echo PASS
		pass=$((pass + 1))
	else
		echo FAIL
		sed 's/^/  /' "$CASE/case.log"
		failed+=("${t#t_}")
	fi
done

echo
echo "$pass passed, ${#failed[@]} failed${failed:+: ${failed[*]}}"
[ ${#failed[@]} -eq 0 ]
