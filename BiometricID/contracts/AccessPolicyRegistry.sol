// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AccessPolicyRegistry
/// @notice Stores on-chain hashes and URIs of MFA access policies, bound to
///         resources and assurance levels.  The full policy definition lives
///         off-chain; only its hash is recorded here so auditors can verify
///         integrity.
contract AccessPolicyRegistry {
    struct PolicyRecord {
        uint8 level;
        bytes32 policyHash;
        string policyURI;
        uint256 updatedAt;
    }

    /// resourceHash → PolicyRecord
    mapping(bytes32 => PolicyRecord) public policies;

    address public owner;

    event PolicySet(
        bytes32 indexed resourceHash,
        uint8 level,
        bytes32 policyHash,
        string policyURI,
        uint256 timestamp
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Not authorised");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// @notice Create or update a policy record for a resource.
    function setPolicy(
        bytes32 resourceHash,
        uint8 level,
        bytes32 policyHash,
        string calldata policyURI
    ) external onlyOwner {
        policies[resourceHash] = PolicyRecord({
            level: level,
            policyHash: policyHash,
            policyURI: policyURI,
            updatedAt: block.timestamp
        });

        emit PolicySet(resourceHash, level, policyHash, policyURI, block.timestamp);
    }

    /// @notice Verify that a given policy hash matches the on-chain record.
    function verifyPolicy(bytes32 resourceHash, bytes32 candidate) external view returns (bool) {
        return policies[resourceHash].policyHash == candidate;
    }
}
