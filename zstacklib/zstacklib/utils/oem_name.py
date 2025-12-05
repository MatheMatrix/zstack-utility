'''

@author: haoyu.ding
'''

'''
This value is defined to facilitate replacing the name 'zstack' in paths and files.
It defaults to 'zstack'. When building the binary package, if the parameter
OEM_NAME=*** is provided, the oem-build.xml script will replace this value with ***.
The actual runtime and deployment name in the target environment will then be that value.
'''
oemname = 'zstack'

def get_oem_name():
    return oemname
