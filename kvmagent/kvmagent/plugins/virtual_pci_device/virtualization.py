from abc import ABCMeta, abstractmethod


class VirtualizationHandler(object):
    __metaclass__ = ABCMeta
    @abstractmethod
    def get_all_devices(self):
        pass

    @abstractmethod
    def get_all_devices(self):
        pass

    @abstractmethod
    def slice_device(self, request):
        pass

    @abstractmethod
    def reset_device(self, request):
        pass