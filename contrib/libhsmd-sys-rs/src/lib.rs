extern crate libc;
use libc::{c_void, size_t};
use std::ffi::CString;
use std::slice;

extern "C" {
    fn c_init(secret: *const u8, network: *const i8) -> *const u8;
    fn tal_bytelen(ptr: *const c_void) -> size_t;
    fn tal_free(ptr: *const c_void);
    fn c_handle(
        cap: u64,
        dbid: u64,
        peer_id: *const u8,
        peer_id_len: size_t,
        msg: *const u8,
        msglen: size_t,
    ) -> *const u8;
}

#[derive(Debug)]
pub enum Error {
    Generic,
    StringConversion,
    Internal,
}

pub fn init(secret: Vec<u8>, network: &str) -> Result<Vec<u8>, Error> {
    let network = match CString::new(network) {
        Ok(s) => s,
        Err(_) => return Err(Error::StringConversion),
    };

    let res: *const u8 = unsafe { c_init(secret.as_ptr(), network.as_ptr()) };

    if res.is_null() {
        return Err(Error::Internal);
    }

    unsafe {
        let reslen = dbg!(tal_bytelen(res as *const c_void));
        let s = slice::from_raw_parts(res, reslen);
        let response: Vec<u8> = s.clone().to_vec();
        dbg!(tal_free(res as *const c_void));
        drop(res);
        Ok(response)
    }
}

pub fn handle(
    capabilities: u64,
    dbid: Option<u64>,
    peer_id: Option<Vec<u8>>,
    msg: Vec<u8>,
) -> Result<Vec<u8>, Error> {
    let peer_id = peer_id.unwrap_or_default();

    let res: *const u8 = unsafe {
        c_handle(
            capabilities,
            dbid.unwrap_or_default(),
            peer_id.as_ptr(),
            peer_id.len(),
            msg.as_ptr(),
            msg.len(),
        )
    };
    unsafe {
        let reslen = dbg!(tal_bytelen(res as *const c_void));
        let s = slice::from_raw_parts(res, reslen);
        let response: Vec<u8> = s.clone().to_vec();
        dbg!(tal_free(res as *const c_void));
        drop(res);
        Ok(response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_init() {
        let secret = [0 as u8; 32];
        let network = "bitcoin";

        let response = dbg!(init(secret.to_vec(), network)).unwrap();
        assert_eq!(response.len(), 177);
    }

    #[test]
    fn test_handle() {
        let secret =
            hex::decode("9f5a9ba98d7e816eebf496db2ff760dc17a4a2f0ae5a87c37cab4bbf6ee05530")
                .unwrap();
        let network = "testnet";
        let msg = hex::decode("00130200000001f25c0c5f21c46ed3f1063a9a41a489ed4e6bb2c18ef1998eb6618198b17137f90000000000666a6c8001e985010000000000160014f4d3100ee3828a602cbc47b1d70ac204e3342081f06a98200000012d70736274ff0100520200000001f25c0c5f21c46ed3f1063a9a41a489ed4e6bb2c18ef1998eb6618198b17137f90000000000666a6c8001e985010000000000160014f4d3100ee3828a602cbc47b1d70ac204e3342081f06a98200001012ba086010000000000220020cc2ef6e3d8102826a2167b463a77bfaf5b57c1ec24c52115d3c471320ad475720105475221026ecfe4d4dd089bbadcf19c860580dae91b2752261269c1f770f32f80e80680492102df1c73d6d45af5edac96953e0eaae5677411b46791092b4bef2c59648b83c20c52ae220602df1c73d6d45af5edac96953e0eaae5677411b46791092b4bef2c59648b83c20c0841c77c75000000002206026ecfe4d4dd089bbadcf19c860580dae91b2752261269c1f770f32f80e806804908109206e600000000000002df1c73d6d45af5edac96953e0eaae5677411b46791092b4bef2c59648b83c20c039c7fa80e43780ad63af6df575924b4c9ae3f1ad22f74067c28227fb45817b2e301").unwrap();
        let expected = hex::decode("0070141f930e76a8303ac0fe0eaa21cd6afd385453784c79799ed54f10f7a0d8980501e4e30f4208e93d526e7f3cb5592b723db5e56cf764e2540113101518fc7fe501").unwrap();

        let _ = dbg!(init(secret, network));
        let capabilities = 24;
        let dbid = Some(1);
        let node_id = Some(
            hex::decode("02312627fdf07fbdd7e5ddb136611bdde9b00d26821d14d94891395452f67af248")
                .unwrap(),
        );
        let res = dbg!(handle(capabilities, dbid, node_id, msg));
        assert_eq!(res.unwrap(), expected);
    }

    #[test]
    fn test_sign_message() {
        let secret = [0 as u8; 32];
        let network = "bitcoin";
        dbg!(init(secret.to_vec(), network)).unwrap();

        let cap = 1024;
        let request = hex::decode("0017000B48656c6c6f20776f726c64").unwrap();
        let expected = hex::decode("007b7fab40f2920dedc9ea573fc1a3eefd0492e85b8e4ee6874d57b12526c3a012694c940072eb12c0d263881b909d3c4bb8ea4ec5cc7bff21922689fb0e2e39018501").unwrap();

        let response = dbg!(handle(cap, None, None, request)).unwrap();
        assert_eq!(expected, response);
    }
}
