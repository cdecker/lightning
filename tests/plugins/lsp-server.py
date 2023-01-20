#!/usr/bin/env python3

# A simple JIT LSP (sort-of). It discounts incoming HTLCs, with the
# approval of the client, to pay for its services.

from pyln.client import Plugin
from pprint import pprint

plugin = Plugin()

@plugin.hook("htlc_accepted")
def on_htlc_accepted(onion, plugin, **kwargs):
    pprint(onion)
    assert onion['forward_msat'] == 1000000 ,"pay may have split the total payment into smaller parts"

    assert onion['payload'].startswith('1202030f4240'),"Payload does not match, may need to adjust lsp-server.py plugin"

    # We know what the payload looks like, so let's replace that right
    # away without parsing. Length prefix stripped.
    payload = (
        '02' +  # amt_to_forward
        '030DBBA0' +  # 900'000 in hex, reduced amount!
        onion['payload'][12:]  # Rest of the payload (scid may change)
    )

    print('='*80)
    pprint(kwargs)
    print('='*80)
    return {
        "result": "continue",
        "payload": payload
    }


plugin.run()
