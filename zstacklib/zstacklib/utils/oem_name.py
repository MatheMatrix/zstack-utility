import os



def get_oem_name():
    name = os.environ.get('OEM_NAME')
    if name:
        return name
    else:
        return 'zstack'