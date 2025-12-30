import os



def get_app_name():
    name = os.environ.get('APP_USER')
    if name:
        return name
    else:
        return 'zstack'