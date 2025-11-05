#!/bin/bash
set -ex

# prepare_env_simple.sh: Simplified version of prepare_env.sh
# Only installs Python libraries, assumes all RPMs are already installed.
# Usage: bash prepare_env_simple.sh
#
# Prerequisites:
#   - Caller should activate virtualenv before running this script
#   - All required RPMs are installed (python3.11, libvirt-devel, gcc, etc.)

SCRIPTS_HOME="/root/.zguest/zstack-utility/kvmagent/kvmagent/test/unittest_tools"
PYPI_SOURCE="/root/.zguest/zstack-utility/zstackbuild/pypi_source/pypi/simple"
UNITTEST_PYPI_SOURCE="${SCRIPTS_HOME}/unittest_pypi_source/pypi/simple"

# configure pip source
configure_pip() {
    pip3.11 config set global.index-url file://${PYPI_SOURCE}
    pip3.11 config set global.extra-index-url file://${UNITTEST_PYPI_SOURCE}
    echo "==>> configure_pip done"
}

# build zstacklib and kvmagent tar.gz
build_packages() {
    cd /root/.zguest/zstack-utility/zstacklib/
    bash install.sh

    cd /root/.zguest/zstack-utility/kvmagent/
    bash install.sh

    echo "==>> build_packages done"
}

# install zstacklib and kvmagent
install_packages() {
    cd /root/.zguest/zstack-utility/zstacklib/
    pip3.11 install dist/zstacklib-*.tar.gz

    cd /root/.zguest/zstack-utility/kvmagent/
    pip3.11 install dist/kvmagent-*.tar.gz

    echo "==>> install_packages done"
}

# install test dependencies
install_test_deps() {
    cd ${SCRIPTS_HOME}/unittest_pypi_source/
    pip3.11 install -r requirements/requirements3.txt
    echo "==>> install_test_deps done"
}

# main
configure_pip
build_packages
install_packages
install_test_deps

echo "==>> prepare_env_simple.sh completed successfully"
