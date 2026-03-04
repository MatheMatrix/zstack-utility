# -*- coding: utf-8 -*-
# 与 Go key-manager key-agent proto 一致：KeyAgentService, CreateEnvelopeKey, RotateEnvelopeKey, GetPublicKey(bytes), EnsureSecret

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection


# ----- 空 request/response（与 Go 一致） -----

class CreateEnvelopeKeyRequest(object):
    def SerializeToString(self):
        return b''

    @classmethod
    def FromString(cls, _):
        return cls()


class CreateEnvelopeKeyResponse(object):
    def __init__(self, created=False):
        self.created = created

    def SerializeToString(self):
        # proto3: field 1, type 0 (varint), value 1 or 0
        return b'\x08\x01' if self.created else b'\x08\x00'

    @classmethod
    def FromString(cls, buf):
        # field 1 varint: created
        created = False
        i = 0
        while i < len(buf):
            if buf[i] != 0x08:  # tag 1, varint
                i += 1
                continue
            i += 1
            if i < len(buf) and buf[i] in (0, 1):
                created = bool(buf[i])
                i += 1
            break
        return cls(created=created)


class RotateEnvelopeKeyRequest(object):
    def SerializeToString(self):
        return b''

    @classmethod
    def FromString(cls, _):
        return cls()


class RotateEnvelopeKeyResponse(object):
    def SerializeToString(self):
        return b''

    @classmethod
    def FromString(cls, _):
        return cls()


class GetPublicKeyRequest(object):
    def SerializeToString(self):
        return b''

    @classmethod
    def FromString(cls, _):
        return cls()


def _decode_varint(buf, offset):
    n = 0
    shift = 0
    while offset < len(buf):
        b = buf[offset]
        offset += 1
        n |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return n, offset


def _encode_varint(n):
    if n == 0:
        return b'\x00'
    buf = []
    while n:
        buf.append(n & 0x7F)
        n >>= 7
    for i in range(len(buf) - 1):
        buf[i] |= 0x80
    return bytes(reversed(buf))


def _encode_length_delimited(field_number, data):
    """data: bytes. Returns tag + varint(len) + data."""
    tag = (field_number << 3) | 2
    return bytes([tag]) + _encode_varint(len(data)) + data


class GetPublicKeyResponse(object):
    def __init__(self, public_key=b''):
        self.public_key = public_key  # bytes

    def SerializeToString(self):
        if not self.public_key:
            return b''
        # field 1, type 2 (length-delimited)
        head = bytes([0x0A])  # tag
        L = len(self.public_key)
        varint = []
        while L:
            varint.append(L & 0x7F)
            L >>= 7
        for i in range(len(varint) - 1):
            varint[i] |= 0x80
        return head + bytes(reversed(varint)) + self.public_key

    @classmethod
    def FromString(cls, buf):
        public_key = b''
        i = 0
        while i < len(buf):
            tag = buf[i]
            i += 1
            if tag == 0x0A:  # field 1, length-delimited
                n, i = _decode_varint(buf, i)
                if i + n <= len(buf):
                    public_key = buf[i:i + n]
                    i += n
                break
            # skip unknown
            wire = tag & 7
            if wire == 0:
                _, i = _decode_varint(buf, i)
            elif wire == 2:
                n, i = _decode_varint(buf, i)
                i += n
            else:
                break
        return cls(public_key=public_key)


class EnsureSecretRequest(object):
    def __init__(self, encrypted_dek=b'', description='', vm_uuid='', purpose='', provider_name=''):
        self.encrypted_dek = encrypted_dek if isinstance(encrypted_dek, bytes) else b''
        self.description = description or ''
        self.vm_uuid = vm_uuid or ''
        self.purpose = purpose or ''
        self.provider_name = provider_name or ''

    def SerializeToString(self):
        parts = []
        if self.encrypted_dek:
            parts.append(_encode_length_delimited(1, self.encrypted_dek))
        if self.description:
            parts.append(_encode_length_delimited(2, self.description.encode('utf-8')))
        if self.vm_uuid:
            parts.append(_encode_length_delimited(3, self.vm_uuid.encode('utf-8')))
        if self.purpose:
            parts.append(_encode_length_delimited(4, self.purpose.encode('utf-8')))
        if self.provider_name:
            parts.append(_encode_length_delimited(5, self.provider_name.encode('utf-8')))
        return b''.join(parts)

    @classmethod
    def FromString(cls, buf):
        # kvm-agent 仅作客户端，可不实现反序列化
        return cls()


class EnsureSecretResponse(object):
    def __init__(self, secret_uuid=''):
        self.secret_uuid = secret_uuid

    def SerializeToString(self):
        if self.secret_uuid:
            return _encode_length_delimited(1, self.secret_uuid.encode('utf-8'))
        return b''

    @classmethod
    def FromString(cls, buf):
        secret_uuid = ''
        i = 0
        while i < len(buf):
            tag = buf[i]
            i += 1
            if tag == 0x0A:  # field 1, length-delimited
                n, i = _decode_varint(buf, i)
                if i + n <= len(buf):
                    secret_uuid = buf[i:i + n].decode('utf-8', errors='replace')
                    i += n
                break
            wire = tag & 7
            if wire == 0:
                _, i = _decode_varint(buf, i)
            elif wire == 2:
                n, i = _decode_varint(buf, i)
                i += n
            else:
                break
        return cls(secret_uuid=secret_uuid)
