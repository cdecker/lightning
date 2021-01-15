from typing import List, Dict, Tuple, Optional, Union, Type, TypeVar, Any
from pyln.client.lightning import LightningRpc
import binascii


T = TypeVar("T")


class QueryList(List[T]):
    def first(self) -> Optional[T]:
        if len(self) == 0:
            return None
        return self[0]


P = TypeVar("P", bound="Pubkey")


class RpcResultWrapper(object):
    """Base class for objects wrapping an RPC result.

    The JSON-RPC returns a bunch of nested JSON objects that are
    rather cumbersome to work with, requiring string indexing and not
    allowing utility accessors to fields. This base class provides
    common functionality making API usage more pythonic.

    """

    def __getattr__(self, name):
        """Mux data fields into the lookup."""
        data = self.__getattribute__("data")
        if name in data:
            return data[name]
        else:
            return self.__getattribute__(name)

    def __eq__(self, other):
        """If the backing data is the same, then we are the same."""
        if not isinstance(other, RpcResultWrapper):
            return False
        else:
            return self.data == other.data


class Pubkey:
    def __init__(self, raw: bytes) -> None:
        self.raw: bytes = raw

    @classmethod
    def from_hex(cls: Type[P], h: Union[str, bytes]) -> P:
        if isinstance(h, str):
            h = h.encode("ASCII")

        return cls(
            raw=binascii.unhexlify(h),
        )

    def __str__(self) -> str:
        return binascii.hexlify(self.raw).decode("ASCII")

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Pubkey):
            return False
        else:
            return self.raw == other.raw


class NodeId(Pubkey):
    pass


class ShortChannelId(object):
    def __init__(self, value: Union[str, int]) -> None:
        self.numval: int
        if isinstance(value, str):
            s = value.split("x")
            assert len(s) == 3
            self.numval = int(s[0]) << 40 | int(s[1]) << 16 | int(s[2])
        else:
            self.numval = value

    @property
    def txindex(self) -> int:
        return self.numval >> 16 & 0xFFFFFF

    @property
    def block(self) -> int:
        return self.numval >> 40

    @property
    def outindex(self) -> int:
        return self.numval & 0xFFFF

    def to_triple(self) -> Tuple[int, int, int]:
        return (self.block, self.txindex, self.outindex)

    def __str__(self) -> str:
        return "{}x{}x{}".format(self.block, self.txindex, self.outindex)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ShortChannelId):
            return False
        else:
            return self.numval == other.numval

    def __cmp__(self, other: "ShortChannelId") -> bool:
        return self.numval < other.numval


class FeatureBits(object):
    def __init__(self, bits: bytes) -> None:
        self.bits = bits

    @classmethod
    def from_hex(cls: Type["FeatureBits"], h: Union[str, bytes]) -> "FeatureBits":
        if isinstance(h, str):
            h = h.encode("ASCII")

        return cls(
            bits=binascii.unhexlify(h),
        )


class Peer(RpcResultWrapper):
    def __init__(self) -> None:
        self.id: NodeId
        self.channels: List[Channel] = []
        self.features: FeatureBits
        self.connected: bool
        self.rpc: LightningRpc
        self.data: Dict[str, Any]

    @classmethod
    def from_dict(cls: Type["Peer"], d: Dict[str, Any], rpc: LightningRpc) -> "Peer":
        self = Peer()
        self.rpc = rpc
        self.id = NodeId.from_hex(d["id"])
        self.connected = d["connected"]
        self.features = FeatureBits.from_hex(d["features"])
        self.data = d

        for c in d["channels"]:
            c = Channel.from_dict(c, peer=self, rpc=self.rpc)
            self.channels.append(c)

        return self

    def __str__(self) -> str:
        return "Peer[id={self.id}]".format(self=self)

    def __repr__(self) -> str:
        return self.__str__()


class Channel(RpcResultWrapper):
    def __init__(self) -> None:
        self.data: Dict[str, Any]
        self.short_channel_id: ShortChannelId
        self.rpc: LightningRpc

    @classmethod
    def from_dict(
        cls: Type["Channel"], d: Dict[str, Any], peer: Peer, rpc: LightningRpc
    ) -> "Channel":
        self = Channel()
        self.rpc = rpc
        self.short_channel_id = ShortChannelId(d["short_channel_id"])
        self.data = d
        self.peer = peer
        return self


class RpcNode(object):
    """A node to which we have RPC access."""

    def __init__(self, rpc: LightningRpc) -> None:
        self.rpc = rpc

    def peer(self, id: NodeId) -> Optional[Peer]:
        peers = self.rpc.listpeers(str(id))["peers"]
        if len(peers) != 1:
            return None
        else:
            return Peer.from_dict(peers[0], rpc=self.rpc)

    @property
    def peers(self) -> List[Peer]:
        peers = self.rpc.listpeers()["peers"]

        res: QueryList[Peer] = QueryList()
        for d in peers:
            res.append(Peer.from_dict(d, self.rpc))

        return res

    @property
    def channels(self) -> List[Channel]:
        chans = []
        for p in self.peers:
            chans.extend(p.channels)
        return chans

    def channel(self, q: Union[ShortChannelId, Pubkey]) -> Channel:
        chans = self.channels

        if isinstance(q, ShortChannelId):
            for c in chans:
                if c.short_channel_id == q:
                    return c

            return None

    def id(self) -> NodeId:
        info = self.rpc.getinfo()
        return info["id"]
