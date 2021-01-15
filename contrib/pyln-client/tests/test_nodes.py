from pyln.testing.fixtures import *
from pyln.client.nodes import RpcNode, ShortChannelId


def test_listpeers(node_factory):
    l1, l2 = node_factory.line_graph(2)

    node = RpcNode(l1.rpc)
    peers = node.peers
    assert len(peers) == 1
    assert node.peer(peers[0].id) == peers[0]

    channels = node.channels
    assert len(channels) == 1
    assert node.channel(channels[0].short_channel_id) == channels[0]

    # Going up a level from the channel should still give us the peer
    assert peers[0] == channels[0].peer

    # Access a detail that is stored in the backing dict of peers and channels
    assert peers[0].connected  # .connected is stored in peer.data and not peer.__dict__
    assert (
        channels[0].msatoshi_to_us_max is not None
    )  # deprecated but accessible through channel.data


def test_short_channel_id():
    scid = ShortChannelId("608576x1879x0")
    scid2 = ShortChannelId(669136388508549120)

    assert scid.numval == 669136388508549120
    assert scid.to_triple() == (608576, 1879, 0)
    assert str(scid) == "608576x1879x0"

    assert scid == scid2
