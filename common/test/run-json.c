#include "../json.c"
#include "../json_escaped.c"
#include <stdio.h>

/* AUTOGENERATED MOCKS START */
/* AUTOGENERATED MOCKS END */


// issue #577

static void do_json_tok_bitcoin_amount(const char* val, uint64_t expected)
{
	uint64_t amount;
	jsmntok_t tok;

	tok.start = 0;
	tok.end = strlen(val);

	fprintf(stderr, "do_json_tok_bitcoin_amount(\"%s\", %"PRIu64"): ", val, expected);

	assert(json_tok_bitcoin_amount(val, &tok, &amount) == true);
	assert(amount == expected);

	fprintf(stderr, "ok\n");
}


static int test_json_tok_bitcoin_amount(void)
{
	do_json_tok_bitcoin_amount("0.00000001", 1);
	do_json_tok_bitcoin_amount("0.00000007", 7);
	do_json_tok_bitcoin_amount("0.00000008", 8);
	do_json_tok_bitcoin_amount("0.00000010", 10);
	do_json_tok_bitcoin_amount("0.12345678", 12345678);
	do_json_tok_bitcoin_amount("0.01234567", 1234567);
	do_json_tok_bitcoin_amount("123.45678900", 12345678900);

	return 0;
}

static int test_json_filter(void)
{
	struct json_result *result = new_json_result(NULL);
	jsmntok_t *toks;
	const jsmntok_t *x;
	bool valid;
	int i;
	char *badstr = tal_arr(result, char, 256);
	const char *str;

	/* Fill with junk, and nul-terminate (256 -> 0) */
	for (i = 1; i < 257; i++)
		badstr[i-1] = i;

	json_object_start(result, NULL);
	json_add_string(result, "x", badstr);
	json_object_end(result);

	/* Parse back in, make sure nothing crazy. */
	str = json_result_string(result);

	toks = json_parse_input(str, strlen(str), &valid);
	assert(valid);
	assert(toks);

	assert(toks[0].type == JSMN_OBJECT);
	x = json_get_member(str, toks, "x");
	assert(x);
	assert(x->type == JSMN_STRING);

	/* There are 7 one-letter escapes, and (32-5) \uXXXX escapes. */
	assert((x->end - x->start) == 255 + 7*1 + (32-5)*5);
	/* No control characters. */
	for (i = x->start; i < x->end; i++) {
		assert((unsigned)str[i] >= ' ');
		assert((unsigned)str[i] != 127);
	}
	tal_free(result);
	return 0;
}

static void test_json_escape(void)
{
	int i;

	for (i = 1; i < 256; i++) {
		char badstr[2];
		struct json_result *result = new_json_result(NULL);
		struct json_escaped *esc;

		badstr[0] = i;
		badstr[1] = 0;

		json_object_start(result, NULL);
		esc = json_escape(NULL, badstr);
		json_add_escaped_string(result, "x", take(esc));
		json_object_end(result);

		const char *str = json_result_string(result);
		if (i == '\\' || i == '"'
		    || i == '\n' || i == '\r' || i == '\b'
		    || i == '\t' || i == '\f')
			assert(strstarts(str, "\n{\n  \"x\": \"\\"));
		else if (i < 32 || i == 127) {
			assert(strstarts(str, "\n{\n  \"x\": \"\\u00"));
		} else {
			char expect[] = "\n{\n  \"x\": \"?\"\n}";
			expect[11] = i;
			assert(streq(str, expect));
		}
		tal_free(result);
	}
}

static void test_json_partial(void)
{
	const tal_t *ctx = tal(NULL, char);

	assert(streq(json_partial_escape(ctx, "\\")->s, "\\\\"));
	assert(streq(json_partial_escape(ctx, "\\\\")->s, "\\\\"));
	assert(streq(json_partial_escape(ctx, "\\\\\\")->s, "\\\\\\\\"));
	assert(streq(json_partial_escape(ctx, "\\\\\\\\")->s, "\\\\\\\\"));
	assert(streq(json_partial_escape(ctx, "\\n")->s, "\\n"));
	assert(streq(json_partial_escape(ctx, "\n")->s, "\\n"));
	assert(streq(json_partial_escape(ctx, "\\\"")->s, "\\\""));
	assert(streq(json_partial_escape(ctx, "\"")->s, "\\\""));
	assert(streq(json_partial_escape(ctx, "\\t")->s, "\\t"));
	assert(streq(json_partial_escape(ctx, "\t")->s, "\\t"));
	assert(streq(json_partial_escape(ctx, "\\b")->s, "\\b"));
	assert(streq(json_partial_escape(ctx, "\b")->s, "\\b"));
	assert(streq(json_partial_escape(ctx, "\\r")->s, "\\r"));
	assert(streq(json_partial_escape(ctx, "\r")->s, "\\r"));
	assert(streq(json_partial_escape(ctx, "\\f")->s, "\\f"));
	assert(streq(json_partial_escape(ctx, "\f")->s, "\\f"));
	/* You're allowed to escape / according to json.org. */
	assert(streq(json_partial_escape(ctx, "\\/")->s, "\\/"));
	assert(streq(json_partial_escape(ctx, "/")->s, "/"));

	assert(streq(json_partial_escape(ctx, "\\u0FFF")->s, "\\u0FFF"));
	assert(streq(json_partial_escape(ctx, "\\u0FFFx")->s, "\\u0FFFx"));

	/* Unknown escapes should be escaped. */
	assert(streq(json_partial_escape(ctx, "\\x")->s, "\\\\x"));
	tal_free(ctx);
}

int main(void)
{
	test_json_tok_bitcoin_amount();
	test_json_filter();
	test_json_escape();
	test_json_partial();
	assert(!taken_any());
	take_cleanup();
}
