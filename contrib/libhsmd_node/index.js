const hsmd = require('bindings')('hsmd')
module.exports = {
    Init: hsmd.Init,
    Handle: hsmd.Handle
}
