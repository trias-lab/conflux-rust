import eth_utils
import rlp
# import sender as sender
from rlp.sedes import big_endian_int, binary

from .exceptions import InvalidTransaction
from . import utils
from .utils import TT256, mk_contract_address, zpad, int_to_32bytearray, \
    big_endian_to_int, ecsign, ecrecover_to_pub, normalize_key, str_to_bytes, \
    encode_hex, address


class Transaction(rlp.Serializable):
    """
    A transaction is stored as:
    [nonce, gasprice, startgas, to, value, data, v, r, s]

    nonce is the number of transactions already sent by that account, encoded
    in binary form (eg.  0 -> '', 7 -> '\x07', 1000 -> '\x03\xd8').

    (v,r,s) is the raw Electrum-style signature of the transaction without the
    signature made with the private key corresponding to the sending account,
    with 0 <= v <= 3. From an Electrum-style signature (65 bytes) it is
    possible to extract the public key, and thereby the address, directly.

    A valid transaction is one where:
    (i) the signature is well-formed (ie. 0 <= v <= 3, 0 <= r < P, 0 <= s < N,
        0 <= r < P - N if v >= 2), and
    (ii) the sending account has enough funds to pay the fee and the value.
    """

    fields = [
        ('nonce', big_endian_int),
        ('gas_price', big_endian_int),
        ('gas', big_endian_int),
        ('action', address),
        ('value', big_endian_int),
        ('data', binary),
        ('v', big_endian_int),
        ('r', big_endian_int),
        ('s', big_endian_int),
    ]

    _sender = None

    def __init__(self, nonce, gas_price, gas, action, value, data, v=0, r=0,
                 s=0):

        super(Transaction, self).__init__(
            nonce, gas_price, gas, action, value, data, v, r, s
        )
        if self.gas_price >= TT256 or \
                self.value >= TT256 or self.nonce >= TT256:
            raise InvalidTransaction("Values way too high!")

    @property
    def sender(self):
        return self._sender

    @sender.setter
    def sender(self, value):
        self._sender = value

    def sign(self, key):
        rawhash = utils.sha3(
            rlp.encode(unsigned_tx_from_tx(self), UnsignedTransaction))

        key = normalize_key(key)

        v, r, s = ecsign(rawhash, key)
        v = v - 27

        ret = self.copy(
            v=v, r=r, s=s
        )
        ret._sender = utils.privtoaddr(key)
        return ret

    @property
    def hash(self):
        return utils.sha3(rlp.encode(self))

    def hash_hex(self):
        return eth_utils.encode_hex(self.hash)

    def to_dict(self):
        d = {}
        for name, _ in self.__class__._meta.fields:
            d[name] = getattr(self, name)
        d['sender'] = '0x' + encode_hex(self.sender)
        d['hash'] = '0x' + encode_hex(self.hash)
        return d

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.hash == other.hash

    def __lt__(self, other):
        return isinstance(other, self.__class__) and self.hash < other.hash

    def __hash__(self):
        return utils.big_endian_to_int(self.hash)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '<Transaction(%s)>' % encode_hex(self.hash)[:4]


class UnsignedTransaction(rlp.Serializable):
    fields = [
        (field, sedes) for field, sedes in Transaction._meta.fields if
        field not in "vrs"
    ]


def unsigned_tx_from_tx(tx):
    return UnsignedTransaction(
        nonce=tx.nonce,
        gas_price=tx.gas_price,
        gas=tx.gas,
        value=tx.value,
        action=tx.action,
        data=tx.data
    )
