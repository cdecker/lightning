/* Converted to C by Rusty Russell, based on bitcoin source: */
// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2012 The Bitcoin Developers
// Distributed under the MIT/X11 software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.
#include "address.h"
#include "base58.h"
#include "privkey.h"
#include "pubkey.h"
#include "shadouble.h"
#include <assert.h>
#include <ccan/build_assert/build_assert.h>
#include <ccan/tal/str/str.h>
#include <common/utils.h>
#include <string.h>
#include <wally_core.h>

static char *to_base58(const tal_t *ctx, u8 version,
		       const struct ripemd160 *rmd)
{
	u8 raw[sizeof(*rmd) + 1];
	char *out, *res;
	raw[0] = version;
	memcpy(raw + 1, rmd, sizeof(*rmd));
	wally_base58_from_bytes(raw, sizeof(raw), BASE58_FLAG_CHECKSUM, &out);

	if (out == NULL)
		return NULL;

	res = tal_strdup(ctx, out);
	wally_free_string(out);
	return res;
}

char *bitcoin_to_base58(const tal_t *ctx, bool test_net,
			const struct bitcoin_address *addr)
{
	return to_base58(ctx, test_net ? 111 : 0, &addr->addr);
}

char *p2sh_to_base58(const tal_t *ctx, bool test_net,
		     const struct ripemd160 *p2sh)
{
	return to_base58(ctx, test_net ? 196 : 5, p2sh);
}

static bool from_base58(u8 *version, struct ripemd160 *rmd, const char *base58,
			size_t base58_len)
{
	size_t written;
	u8 buf[1 + sizeof(*rmd) + BASE58_CHECKSUM_LEN];
	char b58[base58_len + 1];
	/* Avoid memcheck complaining if decoding resulted in a short value */
	memset(buf, 0, sizeof(buf));
	/* libwally uses strlen internally, so this must be 0-terminated */
	memcpy(b58, base58, base58_len);
	b58[base58_len] = 0;

	if (wally_base58_to_bytes(b58, BASE58_FLAG_CHECKSUM, buf, sizeof(buf),
				  &written) != WALLY_OK)
		return false;
	assert(written == sizeof(buf) - BASE58_CHECKSUM_LEN);

	*version = buf[0];
	memcpy(rmd, buf + 1, sizeof(*rmd));
	return true;
}

bool bitcoin_from_base58(bool *test_net,
			 struct bitcoin_address *addr,
			 const char *base58, size_t len)
{
	u8 version;

	if (!from_base58(&version, &addr->addr, base58, len))
		return false;

	if (version == 111)
		*test_net = true;
	else if (version == 0)
		*test_net = false;
	else
		return false;
	return true;
}

bool p2sh_from_base58(bool *test_net,
		      struct ripemd160 *p2sh,
		      const char *base58, size_t len)
{
	u8 version;

	if (!from_base58(&version, p2sh, base58, len))
		return false;

	if (version == 196)
		*test_net = true;
	else if (version == 5)
		*test_net = false;
	else
		return false;
	return true;
}

bool key_from_base58(const char *base58, size_t base58_len,
		     bool *test_net, struct privkey *priv, struct pubkey *key)
{
	// 1 byte version, 32 byte private key, 1 byte compressed, 4 byte checksum
	u8 keybuf[1 + 32 + 1 + 4];
	char b58[base58_len + 1];
	size_t written;
	memcpy(b58, base58, base58_len);
	b58[base58_len] = 0;

	if (wally_base58_to_bytes(b58, BASE58_FLAG_CHECKSUM, keybuf, sizeof(keybuf),
				  &written) == WALLY_EINVAL)
		return false;

	/* Byte after key should be 1 to represent a compressed key. */
	if (keybuf[1 + 32] != 1)
		return false;

	if (keybuf[0] == 128)
		*test_net = false;
	else if (keybuf[0] == 239)
		*test_net = true;
	else
		return false;

	/* Copy out secret. */
	memcpy(priv->secret.data, keybuf + 1, sizeof(priv->secret.data));

	if (!secp256k1_ec_seckey_verify(secp256k1_ctx, priv->secret.data))
		return false;

	/* Get public key, too. */
	if (!pubkey_from_privkey(priv, key))
		return false;

	return true;
}
