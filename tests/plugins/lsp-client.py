#!/usr/bin/env python3

# A simple LSP client, that knows when it has to accept a
# lower-than-signalled amount. This is because the LSP took a
# percentage of the invoice amount.

from pyln.client import Plugin
from pprint import pprint


plugin = Plugin()

@plugin.hook("htlc_accepted")
def on_htlc_accepted(onion, htlc, plugin, **kwargs):
    pprint({"htlc": htlc, "onion": onion})

    exppayload = (
        '2d'  # Length prefix
        '02' '03' '0f4240'  # TLV 02: forward_amt
        '04' '01' '72'  # TLV 04: cltv
        '08' '23' '01d0fabd251fcbbe2b93b4b927b26ad2a1a99077152e45ded1e678afa45dbec50f4240'  # TLV 08: payment data
    )


    assert htlc['amount_msat'] == 900000 ,"Forward amount is not 900k msat"
    assert onion['forward_msat'] == 10**6,"Onion does not mention 1m msat"
    assert onion['payload'] == exppayload,"Onion payload changed"

    # Adjust the payload so we have amt_to_forward == 900'000 and
    # total_msat == 900'00. total_msat is in bytes 32- of the
    # payment_data because ... premature optimization is a thing in
    # the spec too
    payload = (  # No length prefix!
        # Modified forward_amt, MUST match the HTLC value
        '02' '03' '0DBBA0'
        '04' '01' '72'
        # Modified total_msat, MUST match the invoice value
        '08' '23' '01d0fabd251fcbbe2b93b4b927b26ad2a1a99077152e45ded1e678afa45dbec50DBBA0'
    )


    return {
        'result': 'continue',
        'payload': payload,
    }


plugin.run()
