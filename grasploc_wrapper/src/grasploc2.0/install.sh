# Capture and exit on errors
set -e
trap 'previous_command=$this_command; this_command=$BASH_COMMAND' DEBUG
trap 'err "exit $? due to $previous_command"' EXIT

# Globals
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source default bash
. "${SCRIPT_DIR}/default_bash_script/default-bash.sh"

default_cmd_line_parse "$@"

info "Installing linters"
"${SCRIPT_DIR}/linters/install" -v "${VERBOSITY}"

# Install Boost for PCL
info "Installing boost"
sudo apt install -y libboost-all-dev &> /dev/null

# Install Eigen for PCL
# TODO(Kevin): Check if already installed
info "Installing Eigen 3.3.3"
tmp_eigen="$(mktemp)"
tmp_eigen_dir="$(mktemp -d)"
debug "wget and extract"
wget -q -O ${tmp_eigen} http://bitbucket.org/eigen/eigen/get/3.3.3.tar.gz
tar -xf "${tmp_eigen}" -C "${tmp_eigen_dir}"

debug "install"
cd "${tmp_eigen_dir}/eigen-eigen-67e894c6cd8f"
mkdir build
cd build
cmake "${tmp_eigen_dir}/eigen-eigen-67e894c6cd8f" &> /dev/null
sudo make --quiet install &> /dev/null

# Install FLANN for PCL
info "Installing FLANN 1.8"
sudo add-apt-repository -y ppa:v-launchpad-jochen-sprickerhof-de/pcl &> /dev/null
debug "apt update"
sudo apt update -qq
debug "install"
sudo apt install -y libflann-dev &> /dev/null

# Install VTK for PCL
info "Installing VTK"
# Note: VTK 6 has some problems
sudo apt install -y libvtk5-dev &> /dev/null

# Install PCL
info "Installing PCL 1.7.2 from source with c++11"
# TODO: Check if already installed
debug "TODO: Check if already installed"
tmp_pcl="$(mktemp)"
tmp_pcl_dir="$(mktemp -d)"
debug "wget and extract"
wget -q -O ${tmp_pcl} https://github.com/PointCloudLibrary/pcl/archive/pcl-1.7.2.tar.gz
tar -xf "${tmp_pcl}" -C "${tmp_pcl_dir}"

debug "install"
cd "${tmp_pcl_dir}/pcl-pcl-1.7.2"
mkdir build
cd build
cmake -DCMAKE_CXX_FLAGS="-std=c++11" -DCMAKE_BUILD_TYPE=Release "${tmp_pcl_dir}/pcl-pcl-1.7.2" &> /dev/null
sudo make --quiet -j8 install &> /dev/null

info "Installation complete"
