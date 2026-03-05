# -*- coding: utf-8 -*-

import grpc
from . import key_agent_pb2 as key_agent_dot_key__agent__pb2

_SERVICE_NAME = 'keyagent.v1.KeyAgentService'


class KeyAgentServiceStub(object):
    def __init__(self, channel):
        self.CreateEnvelopeKey = channel.unary_unary(
            '/keyagent.v1.KeyAgentService/CreateEnvelopeKey',
            request_serializer=key_agent_dot_key__agent__pb2.CreateEnvelopeKeyRequest.SerializeToString,
            response_deserializer=key_agent_dot_key__agent__pb2.CreateEnvelopeKeyResponse.FromString,
        )
        self.RotateEnvelopeKey = channel.unary_unary(
            '/keyagent.v1.KeyAgentService/RotateEnvelopeKey',
            request_serializer=key_agent_dot_key__agent__pb2.RotateEnvelopeKeyRequest.SerializeToString,
            response_deserializer=key_agent_dot_key__agent__pb2.RotateEnvelopeKeyResponse.FromString,
        )
        self.GetPublicKey = channel.unary_unary(
            '/keyagent.v1.KeyAgentService/GetPublicKey',
            request_serializer=key_agent_dot_key__agent__pb2.GetPublicKeyRequest.SerializeToString,
            response_deserializer=key_agent_dot_key__agent__pb2.GetPublicKeyResponse.FromString,
        )
        self.CheckEnvelopeKey = channel.unary_unary(
            '/keyagent.v1.KeyAgentService/CheckEnvelopeKey',
            request_serializer=key_agent_dot_key__agent__pb2.CheckEnvelopeKeyRequest.SerializeToString,
            response_deserializer=key_agent_dot_key__agent__pb2.CheckEnvelopeKeyResponse.FromString,
        )
        self.EnsureSecret = channel.unary_unary(
            '/keyagent.v1.KeyAgentService/EnsureSecret',
            request_serializer=key_agent_dot_key__agent__pb2.EnsureSecretRequest.SerializeToString,
            response_deserializer=key_agent_dot_key__agent__pb2.EnsureSecretResponse.FromString,
        )


KeyAgentStub = KeyAgentServiceStub


class KeyAgentServiceServicer(object):
    def CreateEnvelopeKey(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def RotateEnvelopeKey(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetPublicKey(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def CheckEnvelopeKey(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def EnsureSecret(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_KeyAgentServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
        'CreateEnvelopeKey': grpc.unary_unary_rpc_method_handler(
            servicer.CreateEnvelopeKey,
            request_deserializer=key_agent_dot_key__agent__pb2.CreateEnvelopeKeyRequest.FromString,
            response_serializer=key_agent_dot_key__agent__pb2.CreateEnvelopeKeyResponse.SerializeToString,
        ),
        'RotateEnvelopeKey': grpc.unary_unary_rpc_method_handler(
            servicer.RotateEnvelopeKey,
            request_deserializer=key_agent_dot_key__agent__pb2.RotateEnvelopeKeyRequest.FromString,
            response_serializer=key_agent_dot_key__agent__pb2.RotateEnvelopeKeyResponse.SerializeToString,
        ),
        'GetPublicKey': grpc.unary_unary_rpc_method_handler(
            servicer.GetPublicKey,
            request_deserializer=key_agent_dot_key__agent__pb2.GetPublicKeyRequest.FromString,
            response_serializer=key_agent_dot_key__agent__pb2.GetPublicKeyResponse.SerializeToString,
        ),
        'CheckEnvelopeKey': grpc.unary_unary_rpc_method_handler(
            servicer.CheckEnvelopeKey,
            request_deserializer=key_agent_dot_key__agent__pb2.CheckEnvelopeKeyRequest.FromString,
            response_serializer=key_agent_dot_key__agent__pb2.CheckEnvelopeKeyResponse.SerializeToString,
        ),
        'EnsureSecret': grpc.unary_unary_rpc_method_handler(
            servicer.EnsureSecret,
            request_deserializer=key_agent_dot_key__agent__pb2.EnsureSecretRequest.FromString,
            response_serializer=key_agent_dot_key__agent__pb2.EnsureSecretResponse.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        _SERVICE_NAME, rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


class KeyAgent(object):
    @staticmethod
    def CreateEnvelopeKey(request, target, options=(), channel_credentials=None, call_credentials=None, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(
            request, target,
            '/keyagent.v1.KeyAgentService/CreateEnvelopeKey',
            key_agent_dot_key__agent__pb2.CreateEnvelopeKeyRequest.SerializeToString,
            key_agent_dot_key__agent__pb2.CreateEnvelopeKeyResponse.FromString,
            options, channel_credentials, call_credentials, wait_for_ready, timeout, metadata, compression,
        )

    @staticmethod
    def RotateEnvelopeKey(request, target, options=(), channel_credentials=None, call_credentials=None, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(
            request, target,
            '/keyagent.v1.KeyAgentService/RotateEnvelopeKey',
            key_agent_dot_key__agent__pb2.RotateEnvelopeKeyRequest.SerializeToString,
            key_agent_dot_key__agent__pb2.RotateEnvelopeKeyResponse.FromString,
            options, channel_credentials, call_credentials, wait_for_ready, timeout, metadata, compression,
        )

    @staticmethod
    def GetPublicKey(request, target, options=(), channel_credentials=None, call_credentials=None, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(
            request, target,
            '/keyagent.v1.KeyAgentService/GetPublicKey',
            key_agent_dot_key__agent__pb2.GetPublicKeyRequest.SerializeToString,
            key_agent_dot_key__agent__pb2.GetPublicKeyResponse.FromString,
            options, channel_credentials, call_credentials, wait_for_ready, timeout, metadata, compression,
        )

    @staticmethod
    def CheckEnvelopeKey(request, target, options=(), channel_credentials=None, call_credentials=None, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(
            request, target,
            '/keyagent.v1.KeyAgentService/CheckEnvelopeKey',
            key_agent_dot_key__agent__pb2.CheckEnvelopeKeyRequest.SerializeToString,
            key_agent_dot_key__agent__pb2.CheckEnvelopeKeyResponse.FromString,
            options, channel_credentials, call_credentials, wait_for_ready, timeout, metadata, compression,
        )

    @staticmethod
    def EnsureSecret(request, target, options=(), channel_credentials=None, call_credentials=None, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(
            request, target,
            '/keyagent.v1.KeyAgentService/EnsureSecret',
            key_agent_dot_key__agent__pb2.EnsureSecretRequest.SerializeToString,
            key_agent_dot_key__agent__pb2.EnsureSecretResponse.FromString,
            options, channel_credentials, call_credentials, wait_for_ready, timeout, metadata, compression,
        )
