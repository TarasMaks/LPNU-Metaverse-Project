// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title BiometricCommitmentRegistry
/// @notice Stores SHA-256 commitments of biometric templates.  Raw biometric
///         data is NEVER stored on-chain — only the commitment hash, a version
///         string, and a URI pointing to off-chain encrypted storage.
contract BiometricCommitmentRegistry {
    struct Commitment {
        bytes32 commitment;
        string version;
        string storageURI;
        bool active;
        uint256 updatedAt;
    }

    /// userId (bytes32) → Commitment
    mapping(bytes32 => Commitment) public commitments;

    /// Authorised relayer / service address (set at deployment).
    address public owner;

    event CommitmentStored(
        bytes32 indexed userId,
        bytes32 commitment,
        string version,
        string storageURI,
        uint256 timestamp
    );
    event CommitmentRevoked(bytes32 indexed userId, uint256 timestamp);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not authorised");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// @notice Store or update a biometric commitment.
    function storeCommitment(
        bytes32 userId,
        bytes32 commitment,
        string calldata version,
        string calldata storageURI
    ) external onlyOwner {
        commitments[userId] = Commitment({
            commitment: commitment,
            version: version,
            storageURI: storageURI,
            active: true,
            updatedAt: block.timestamp
        });

        emit CommitmentStored(userId, commitment, version, storageURI, block.timestamp);
    }

    /// @notice Revoke a commitment (e.g. after template compromise → re-enroll).
    function revokeCommitment(bytes32 userId) external onlyOwner {
        require(commitments[userId].active, "Not active");
        commitments[userId].active = false;
        emit CommitmentRevoked(userId, block.timestamp);
    }

    /// @notice Verify that a supplied commitment matches the on-chain record.
    function verifyCommitment(bytes32 userId, bytes32 candidate) external view returns (bool) {
        Commitment storage c = commitments[userId];
        return c.active && c.commitment == candidate;
    }
}
