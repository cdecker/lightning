lightning-fetchinvoice -- Command for fetch an invoice for an offer
===================================================================

SYNOPSIS
--------

**(WARNING: experimental-offers only)**

**fetchinvoice** *offer* \[*msatoshi*\] \[*quantity*\] \[*recurrence_counter*\] \[*recurrence_start*\] \[*recurrence_label*\] \[*timeout*\]

DESCRIPTION
-----------

The **fetchinvoice** RPC command contacts the issuer of an *offer* to get
an actual invoice that can be paid.  It highlights any changes between the
offer and the returned invoice.

The offer must not contain *send_invoice*; see lightning-sendinvoice(7).

*msatoshi* is required if the *offer* does not specify
an amount at all, otherwise it is not allowed.

*quantity* is is required if the *offer* specifies
*quantity_min* or *quantity_max*, otherwise it is not allowed.

*recurrence_counter* is required if the *offer*
specifies *recurrence*, otherwise it is not allowed.
*recurrence_counter* should first be set to 0, and incremented for
each successive invoice in a given series.

*recurrence_start* is required if the *offer*
specifies *recurrence_base* with *start_any_period* set, otherwise it
is not allowed.  It indicates what period number to start at.

*recurrence_label* is required if *recurrence_counter* is set, and
otherwise is not allowed.  It must be the same as prior fetchinvoice
calls for the same recurrence, as it is used to link them together.

*timeout* is an optional timeout; if we don't get a reply before this
we fail (default, 60 seconds).

RETURN VALUE
------------

[comment]: # (GENERATE-FROM-SCHEMA-START)
On success, an object is returned, containing:
- **invoice** (string): The BOLT12 invoice we fetched
- **changes** (object): Summary of changes from offer:
  - **description_appended** (string, optional): extra characters appended to the *description* field.
  - **description** (string, optional): a completely replaced *description* field
  - **vendor_removed** (string, optional): The *vendor* from the offer, which is missing in the invoice
  - **vendor** (string, optional): a completely replaced *vendor* field
  - **msat** (msat, optional): the amount, if different from the offer amount multiplied by any *quantity* (or the offer had no amount, or was not in BTC).
- **next_period** (object, optional): Only for recurring invoices if the next period is under the *recurrence_limit*:
  - **counter** (u64): the index of the next period to fetchinvoice
  - **starttime** (u64): UNIX timestamp that the next period starts
  - **endtime** (u64): UNIX timestamp that the next period ends
  - **paywindow_start** (u64): UNIX timestamp of the earliest time that the next invoice can be fetched
  - **paywindow_end** (u64): UNIX timestamp of the latest time that the next invoice can be fetched
[comment]: # (GENERATE-FROM-SCHEMA-END)

The following error codes may occur:
- -1: Catchall nonspecific error.
- 1002: Offer has expired.
- 1003: Cannot find a route to the node making the offer.
- 1004: The node making the offer returned an error message.
- 1005: We timed out trying to fetch an invoice.

AUTHOR
------

Rusty Russell <<rusty@rustcorp.com.au>> is mainly responsible.

SEE ALSO
--------

lightning-sendinvoice(7), lightning-pay(7).

RESOURCES
---------

Main web site: <https://github.com/ElementsProject/lightning>

[comment]: # ( SHA256STAMP:e2b81ad7a61dd6a6d55e21c5367c3286aaf00cee734b2719a8e38bc87f7ac8aa)
