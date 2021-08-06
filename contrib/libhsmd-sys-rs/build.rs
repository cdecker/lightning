use std::process::Command;

fn main() {
    let output = Command::new("clang")
        .arg("-dumpmachine")
        .output()
        .expect("retrieving platform via clang")
        .stdout;
    let machine = std::str::from_utf8(&output).expect("clang output is not utf8");

    println!("cargo:rustc-link-search=native=cl/external/{}/", machine);
    println!("cargo:rustc-link-lib=static=sodium");
    println!("cargo:rustc-link-lib=wallycore");
    println!("cargo:rustc-link-lib=backtrace");

    let src = [
        "bitcoin/block.c",
        "bitcoin/chainparams.c",
        "bitcoin/preimage.c",
        "bitcoin/privkey.c",
        "bitcoin/psbt.c",
        "bitcoin/pubkey.c",
        "bitcoin/script.c",
        "bitcoin/shadouble.c",
        "bitcoin/short_channel_id.c",
        "bitcoin/signature.c",
        "bitcoin/tx.c",
        "bitcoin/varint.c",
        "ccan/ccan/autodata/autodata.c",
        "ccan/ccan/asort/asort.c",
        "ccan/ccan/breakpoint/breakpoint.c",
        "ccan/ccan/crypto/hkdf_sha256/hkdf_sha256.c",
        "ccan/ccan/crypto/hmac_sha256/hmac_sha256.c",
        "ccan/ccan/crypto/ripemd160/ripemd160.c",
        "ccan/ccan/crypto/shachain/shachain.c",
        "ccan/ccan/crypto/siphash24/siphash24.c",
        "ccan/ccan/err/err.c",
        "ccan/ccan/fdpass/fdpass.c",
        "ccan/ccan/htable/htable.c",
        "ccan/ccan/intmap/intmap.c",
        "ccan/ccan/io/fdpass/fdpass.c",
        "ccan/ccan/io/io.c",
        "ccan/ccan/io/poll.c",
        "ccan/ccan/isaac/isaac64.c",
        "ccan/ccan/list/list.c",
        "ccan/ccan/noerr/noerr.c",
        "ccan/ccan/ptr_valid/ptr_valid.c",
        "ccan/ccan/read_write_all/read_write_all.c",
        "ccan/ccan/str/hex/hex.c",
        "ccan/ccan/take/take.c",
        "ccan/ccan/tal/str/str.c",
        "ccan/ccan/tal/tal.c",
        "ccan/ccan/time/time.c",
        "ccan/ccan/timer/timer.c",
        "ccan/ccan/utf8/utf8.c",
        "common/amount.c",
        "common/bigsize.c",
        "common/bip32.c",
        "common/bolt12_merkle.c",
        "common/channel_id.c",
        "common/daemon.c",
        "common/daemon_conn.c",
        "common/derive_basepoints.c",
        "common/hash_u5.c",
        "common/hsm_encryption.c",
        "common/key_derive.c",
        "common/memleak.c",
        "common/msg_queue.c",
        "common/node_id.c",
        "common/pseudorand.c",
        "common/setup.c",
        "common/status.c",
        "common/status_levels.c",
        "common/status_wire.c",
        "common/status_wiregen.c",
        "common/subdaemon.c",
        "common/type_to_string.c",
        "common/utils.c",
        "common/utxo.c",
        "common/version.c",
        "external/libwally-core/src/ccan/ccan/base64/base64.c",
        "hsmd/hsmd_wiregen.c",
        "hsmd/libhsmd.c",
        "wire/fromwire.c",
        "wire/peer_wire.c",
        "wire/peer_wiregen.c",
        "wire/tlvstream.c",
        "wire/towire.c",
        "wire/wire_io.c",
        "wire/wire_sync.c",
        "external/libwally-core/src/base58.c",
        "external/libwally-core/src/base64.c",
        "external/libwally-core/src/bip32.c",
        "external/libwally-core/src/hex.c",
        "external/libwally-core/src/hmac.c",
        "external/libwally-core/src/internal.c",
        "external/libwally-core/src/psbt.c",
        "external/libwally-core/src/pullpush.c",
        "external/libwally-core/src/script.c",
        "external/libwally-core/src/secp256k1/src/secp256k1.c",
        "external/libwally-core/src/sign.c",
        "external/libwally-core/src/transaction.c",
        "hsmd/libhsmd_status.c",
        "external/libwally-core/src/ccan/ccan/crypto/sha256/sha256.c",
        "external/libwally-core/src/ccan/ccan/crypto/sha512/sha512.c",
    ];

    cc::Build::new()
        .files(src.iter().map(|f| format!("cl/{}", f)))
        .file("shims.c")
        .file("libhsmd.c")
        .include("cl/")
        .include("cl/ccan/")
        .include("cl/external/x86_64-pc-linux-gnu/libbacktrace-build/")
        .include("cl/external/libbacktrace/")
        .include("cl/external/libsodium/src/libsodium/include/")
        .include("cl/external/libsodium/src/libsodium/include/sodium/")
        .include("cl/external/x86_64-pc-linux-gnu/libsodium-build/src/libsodium/include/")
        .include("cl/external/libwally-core/")
        .include("cl/external/libwally-core/include/")
        .include("cl/external/libwally-core/src/")
        .include("cl/external/libwally-core/src/ccan/")
        .include("cl/external/libwally-core/src/secp256k1/")
        .include("cl/external/libwally-core/src/secp256k1/include/")
        .include("cl/external/libwally-core/src/secp256k1/src")
        .define("BUILD_ELEMENTS", Some("1"))
        .define("SHACHAIN_BITS", Some("48"))
        .define("USE_NUM_NONE", Some("1"))
        .define("ECMULT_WINDOW_SIZE", Some("15"))
        .define("ECMULT_GEN_PREC_BITS", Some("4"))
        .define("USE_SCALAR_INV_BUILTIN", Some("1"))
        .define("USE_FIELD_INV_BUILTIN", Some("1"))
        .define("ENABLE_MODULE_EXTRAKEYS", Some("1"))
        .define("ENABLE_MODULE_RECOVERY", Some("1"))
        .define("ENABLE_MODULE_SCHNORRSIG", Some("1"))
        .define("ENABLE_MODULE_ECDH", Some("1"))
        .define("ENABLE_MODULE_ECDSA_S2C", Some("0"))
        .define("EXPERIMENTAL_FEATURES", Some("0"))
        .flag("-Wno-nonnull-compare")
        .flag("-Wno-unused-parameter")
        .flag("-Wno-implicit-function-declaration")
        .flag("-Wno-unused-function")
	.flag("-Wno-unknown-warning-option")
	.flag("-Wno-old-style-declaration")
	.flag("-Wno-implicit-fallthrough")
	.flag("-Wno-sign-compare")
	.flag("-Wno-pointer-sign")
	.flag("-Wno-unused-variable")
	.flag("-Wno-missing-field-initializers")
	.flag("-Wno-empty-body")
	.flag("-Wno-type-limits")
        .compile("libhsmd");

}
