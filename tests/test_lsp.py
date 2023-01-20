# Tests related to implementing a JIT LSP.
#
# A JIT LSP is a service provider that will open and close channels on
# demand, and expect to be paid for that service. The payment is
# performed directly inline with the first payment being forwarded, by
# reducing the forwarded amount. The user-node also has to opt-in to
# this, by sidestepping some verifications that are performed on the
# recipient, such as the reduced HTLC amount being forwarded and a
# reduced overall payment value (sum of all HTLCs). The latter is
# usually done by staging an invoice with the reduced amount instead
# of the actual amount the user entered. Tricking the HTLC
# verification and HTLC set verification is a bit trickier.

from fixtures import *  # noqa: F401,F403
from pathlib import Path
from pprint import pprint

def test_lsp_amount_manipulation(node_factory):
    """The LSP reduces the amount on the fly and client accepts.

    Both sides of this negotiation opt-in to the LSP keeping more than
    the pure fee. We use `l1` as a sender, `l2` as the LSP, and `l3`
    as the recipient.

    """
    base = Path(__file__).parent / "plugins"
    pserver = base / "lsp-server.py"
    pclient = base / "lsp-client.py"
    l1, l2, l3 = node_factory.line_graph(3, opts=[
        {},  # Sender is unmodified
        {"important-plugin": pserver},
        {"important-plugin": pclient},
    ], wait_for_announce=True)

    # l3 creates an invoice for the total amount. This is usually done
    # on the client side, without actually talking to the node, but
    # here we just use the existing functionality.
    invLarge = l3.rpc.invoice(
        amount_msat=10 * 10**5,
        label='inv1',
        description='desc1',
        preimage='00'*32,
    )['bolt11']
    pprint(l1.rpc.decodepay(invLarge))

    print(invLarge)

    # Now delete it, so we don't have a conflict on the `payment_hash`
    l3.rpc.delinvoice(label='inv1', status='unpaid')

    # And now fill it back in again
    invSmall = l3.rpc.invoice(
        amount_msat=9 * 10**5,
        label='inv1',
        description='desc1',
        preimage='00'*32,
    )['bolt11']
    pprint(l1.rpc.decodepay(invSmall))

    # The sender pays the large invoice
    l1.rpc.pay(invLarge)
