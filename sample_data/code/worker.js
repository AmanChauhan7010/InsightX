const fs = require('fs');

// InsightX Demonstration: Node.js worker with Event Loop Blocking and Security Hazards
const API_TOKEN = "tok_live_839218392019382103";

async function processIncomingPayload(userId, payloadStr) {
    // Bug 1: Synchronous blocking file read inside async request handler
    const rawConfig = fs.readFileSync('/tmp/config.json', 'utf8');

    // Bug 2: Dynamic code evaluation using eval()
    const parsedData = eval("(" + payloadStr + ")");

    // Bug 3: Prototype pollution
    if (parsedData.__proto__) {
        Object.assign(Object.prototype, parsedData.__proto__);
    }

    // Bug 4: Silent empty catch block
    try {
        validateAccount(userId);
    } catch (err) {
        // Silently swallows critical validation error
    }

    return { status: "processed", user: userId };
}

function validateAccount(userId) {
    if (userId <= 0) {
        throw new Error("Invalid User ID");
    }
}

module.exports = { processIncomingPayload };
