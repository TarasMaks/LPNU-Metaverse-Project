// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AuditLog
/// @notice Immutable on-chain log of access and authentication events.
///         All entries are hashed — no PII is stored on-chain.
contract AuditLog {
    struct AuditEntry {
        string eventType;
        bytes32 actorHash;
        bytes32 resourceHash;
        string outcome;
        uint256 timestamp;
    }

    AuditEntry[] public entries;

    address public owner;

    event EventRecorded(
        uint256 indexed entryId,
        string eventType,
        bytes32 indexed actorHash,
        bytes32 indexed resourceHash,
        string outcome,
        uint256 timestamp
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Not authorised");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// @notice Append a new audit event.
    function recordEvent(
        string calldata eventType,
        bytes32 actorHash,
        bytes32 resourceHash,
        string calldata outcome
    ) external onlyOwner {
        uint256 id = entries.length;
        entries.push(AuditEntry({
            eventType: eventType,
            actorHash: actorHash,
            resourceHash: resourceHash,
            outcome: outcome,
            timestamp: block.timestamp
        }));

        emit EventRecorded(id, eventType, actorHash, resourceHash, outcome, block.timestamp);
    }

    /// @notice Return the total number of audit entries.
    function entryCount() external view returns (uint256) {
        return entries.length;
    }
}
