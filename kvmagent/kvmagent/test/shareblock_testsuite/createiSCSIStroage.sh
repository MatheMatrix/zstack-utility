LVM_VERSION=${LVM_VERSION:-2.03.12}

if ! command -v targetctl >/dev/null 2>&1; then
    yum install targetcli -y
fi

if ! rpm -q lvm2 >/dev/null 2>&1 || \
   ! rpm -q lvm2-lockd >/dev/null 2>&1 || \
   ! rpm -q sanlock >/dev/null 2>&1; then
    yum install "lvm2-${LVM_VERSION}*" "lvm2-lockd-${LVM_VERSION}*" sanlock -y

    installed_lvm_version=$(rpm -q --qf '%{VERSION}' lvm2)
    installed_lvm_lockd_version=$(rpm -q --qf '%{VERSION}' lvm2-lockd)
    case "$installed_lvm_version" in
        "$LVM_VERSION"*) ;;
        *)
            echo "lvm2 version must be ${LVM_VERSION}, actual ${installed_lvm_version}" >&2
            exit 1
            ;;
    esac
    case "$installed_lvm_lockd_version" in
        "$LVM_VERSION"*) ;;
        *)
            echo "lvm2-lockd version must be ${LVM_VERSION}, actual ${installed_lvm_lockd_version}" >&2
            exit 1
            ;;
    esac
fi

deviceName=`lsblk -o NAME -d|grep -Ev 'sda|vda'|grep -v NAME|awk 'NR==1'`

sed -i "s/sdb/$deviceName/g" ./saveconfig.json

targetctl restore ./saveconfig.json
mkdir -p /etc/sanlock/
touch /etc/sanlock/sanlock.conf
