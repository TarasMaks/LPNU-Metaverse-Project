// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title IdentityRegistry
/// @notice Maps DID hashes to wallet addresses with key-rotation support.
contract IdentityRegistry {
    struct Identity {
        address wallet;
        bool active;
        uint256 registeredAt;
    }

    mapping(bytes32 => Identity) public identities;

    event IdentityRegistered(bytes32 indexed didHash, address indexed wallet, uint256 timestamp);
    event KeyRotated(bytes32 indexed didHash, address indexed oldWallet, address indexed newWallet, uint256 timestamp);
    event IdentityRevoked(bytes32 indexed didHash, uint256 timestamp);

    modifier onlyOwner(bytes32 didHash) {
        require(identities[didHash].wallet == msg.sender, "Not identity owner");
        require(identities[didHash].active, "Identity revoked");
        _;
    }

    /// @notice Register a new DID → wallet mapping.
    function registerIdentity(bytes32 didHash, address wallet) external {
        require(identities[didHash].wallet == address(0), "Already registered");
        require(wallet != address(0), "Zero address");

        identities[didHash] = Identity({
            wallet: wallet,
            active: true,
            registeredAt: block.timestamp
        });

        emit IdentityRegistered(didHash, wallet, block.timestamp);
    }

    /// @notice Rotate the controlling wallet for an existing DID.
    function rotateKey(bytes32 didHash, address newWallet) external onlyOwner(didHash) {
        require(newWallet != address(0), "Zero address");
        address old = identities[didHash].wallet;
        identities[didHash].wallet = newWallet;

        emit KeyRotated(didHash, old, newWallet, block.timestamp);
    }

    /// @notice Permanently deactivate a DID.
    function revokeIdentity(bytes32 didHash) external onlyOwner(didHash) {
        identities[didHash].active = false;
        emit IdentityRevoked(didHash, block.timestamp);
    }

    /// @notice Check whether a DID is active.
    function isActive(bytes32 didHash) external view returns (bool) {
        return identities[didHash].active;
    }
}
