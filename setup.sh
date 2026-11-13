#!/bin/sh
# Install postmarketOS Duranium on a Samsung Galaxy Tab Active3 (SM-T570;
# the LTE SM-T575 with --bring-up) from this Linux PC. Guide:
# docs/INSTALL.md; ./setup.sh --help
# scripts/config (config.toml) needs Python 3.11 (tomllib), before anything
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null || {
	echo "setup.sh: needs python3 3.11 or newer (config.toml is read with tomllib)" >&2
	exit 1
}
exec bash "$(dirname "$0")/scripts/installer/setup" "$@"
