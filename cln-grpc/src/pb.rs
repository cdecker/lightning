tonic::include_proto!("cln");

use cln_rpc::primitives::Amount as JAmount;

impl From<JAmount> for Amount {
    fn from(a: JAmount) -> Self {
        match a {
            JAmount::Millisatoshi(v) => Amount {
                unit: Some(amount::Unit::Millisatoshi(v)),
            },
            JAmount::Satoshi(v) => Amount {
                unit: Some(amount::Unit::Satoshi(v)),
            },
            JAmount::Millibitcoin(v) => Amount {
                unit: Some(amount::Unit::Satoshi(v * 100_000)),
            },
            JAmount::Bitcoin(v) => Amount {
                unit: Some(amount::Unit::Bitcoin(v)),
            },
        }
    }
}
