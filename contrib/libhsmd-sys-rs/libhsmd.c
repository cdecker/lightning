#include "libhsmd.h"
#include "ccan/tal/tal.h"
#include "common/node_id.h"
#include "common/utils.h"
#include <ccan/str/hex/hex.h>
#include <common/setup.h>
#include <stdio.h>

u8 *c_init(u8 *hsm_secret, char *network_name) {
	struct secret sec;
	u8 *response;
	common_setup(NULL);
	if (sodium_init() == -1) {
		fprintf(
		    stderr,
		    "Could not initialize libsodium. Maybe not enough entropy"
		    " available ?");
		return NULL;
	}

	wally_init(0);
	secp256k1_ctx = wally_get_secp_context();

	sodium_mlock(&sec, sizeof(sec));
	memcpy(&sec.data, hsm_secret, sizeof(sec.data));

	/* Look up chainparams by their name */
	chainparams = chainparams_for_network(network_name);
	if (chainparams == NULL) {
		fprintf(stderr, "Could not find chainparams for network %s\n",
			network_name);
		return NULL;
	}

	response = hsmd_init(sec, chainparams->bip32_key_version);
	sodium_munlock(&sec, sizeof(sec));
	taken(response); // Clear the `take()` flag
	clean_tmpctx();
	return response;
}

u8 *c_handle(long long cap, long long dbid, const u8 *peer_id, size_t peer_id_len, u8 *request, size_t request_len) {
	struct hsmd_client *client;
	struct node_id peer;
	size_t max = peer_id_len;
	const u8 **cursor = &peer_id;
	const u8 *msg = tal_dup_arr(tmpctx, u8, request, request_len, 0);

	if (peer_id != NULL) {
		fromwire_node_id(cursor, &max, &peer);
		client = hsmd_client_new_peer(tmpctx, cap, dbid, &peer, NULL);
	} else {
		client = hsmd_client_new_main(tmpctx, cap, NULL);
	}
	u8 *res = hsmd_handle_client_message(tmpctx, client, msg);
	tal_steal(NULL, res);
	clean_tmpctx();
	taken(res); // Clear the `take()` flag

	return res;
}
