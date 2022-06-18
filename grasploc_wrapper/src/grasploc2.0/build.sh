# Globals
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source default bash
. "${SCRIPT_DIR}/default_bash_script/default-bash.sh"

# Build
mkdir -p "${SCRIPT_DIR}/build"
cd "${SCRIPT_DIR}/build"
cmake ../
make -j8