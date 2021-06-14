const hsmd = require('bindings')('hsmd')


function testInit() {
    var got = hsmd.Init("0000000000000000000000000000000000000000000000000000000000000000", "bitcoin");
    var expected = '006f02058e8b6c2ad363ec59aa136429256d745164c2bdc87f98f0a68690ec2c5c9b0b0488b21e02af562dfb0000000077e8a0b57210b61746f6ccfe7ae983f2ae86c1786846b0caa8f38e7fef3c9dd403a2551256f0b0b1545ef15c40af45a592654fb4c31b7508426e6424f67330c1bdf7c33aec8fe6b15bd9424313cc1660418c56c36d32e45ec1ad67fcc4c0adf3df';
    if (got == expected)
	console.log("OK")
    else
	console.log("Fail")
}

function testHandle() {
    hsmd.Init("0000000000000000000000000000000000000000000000000000000000000000", "bitcoin");
    var msg = '0017000B48656c6c6f20776f726c64';
    var got = hsmd.Handle(1024, 0, null, msg);
    var expected = '007b7fab40f2920dedc9ea573fc1a3eefd0492e85b8e4ee6874d57b12526c3a012694c940072eb12c0d263881b909d3c4bb8ea4ec5cc7bff21922689fb0e2e39018501';
    if (got == expected)
	console.log("OK")
    else
	console.log("Fail")
}

testInit()

testHandle()
